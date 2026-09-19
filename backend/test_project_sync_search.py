"""
Unit and integration tests for Phase Architectural Stabilization:
Automatic Active Revit Project Synchronization, Project Isolation,
Duplicate Prevention, Stale Context Invalidation, and Explicit Name Search.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app, SESSION_CONTEXT
from backend.semantic_search import (
    search_views,
    understand_query,
    extract_explicit_view_name,
)


class TestProjectSyncSearch(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        # Reset session context before each test
        SESSION_CONTEXT["project_id"] = None
        SESSION_CONTEXT["results"] = []
        SESSION_CONTEXT["current_level"] = None
        SESSION_CONTEXT["current_view_type"] = None
        SESSION_CONTEXT["current_category"] = None

    # ============================================================
    # 1. PROJECT SWITCH & SESSION CONTEXT INVALIDATION
    # ============================================================

    @patch("backend.main.get_active_project_id")
    @patch("backend.main.get_active_project_info")
    def test_session_invalidation_on_project_switch(self, mock_info, mock_id):
        # Step 1: Active project is Project A (id: 1)
        mock_id.return_value = 1
        mock_info.return_value = {
            "success": True,
            "synced": True,
            "project_id": 1,
            "project_name": "Snowdon Towers Sample Architectural",
        }

        with patch("backend.main.search") as mock_search:
            mock_search.return_value = {
                "target": "VIEW",
                "results": [
                    {
                        "result_type": "view",
                        "name": "Level 1 Floor Plan",
                        "project_id": 1,
                        "revit_view_id": 101,
                    }
                ],
            }

            resp1 = self.client.post("/chat", json={"message": "show me floor plans"})
            self.assertEqual(resp1.status_code, 200)
            data1 = resp1.json()
            self.assertEqual(data1["type"], "search_results")
            self.assertEqual(SESSION_CONTEXT["project_id"], 1)
            self.assertEqual(len(SESSION_CONTEXT["results"]), 1)

        # Step 2: User switches to Project B (id: 2)
        mock_id.return_value = 2
        mock_info.return_value = {
            "success": True,
            "synced": True,
            "project_id": 2,
            "project_name": "Snowdon Towers Sample Structural",
        }

        # User asks follow-up: "open the first one" (referring to Project A's results)
        resp2 = self.client.post("/chat", json={"message": "open the first one"})
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()

        # EXPECTED: Stale context from Project A MUST NOT be used while Project B is active!
        self.assertEqual(data2["type"], "clarification")
        self.assertIn("The active Revit project has changed", data2["message"])

    # ============================================================
    # 2. EXPLICIT VIEW NAME SEARCH
    # ============================================================

    def test_explicit_view_name_extraction(self):
        info1 = understand_query("show me the view named S100")
        self.assertEqual(info1["explicit_view_name"], "S100")

        info2 = understand_query("show me S100")
        self.assertEqual(info2["explicit_view_name"], "S100")

        info3 = understand_query("find view called foundation")
        self.assertEqual(info3["explicit_view_name"], "foundation")

        info4 = understand_query("show me floor plans")
        self.assertIsNone(info4["explicit_view_name"])

    @patch("backend.main.get_active_project_id")
    @patch("backend.main.get_active_project_info")
    @patch("backend.main.search")
    def test_explicit_view_name_no_match_returns_clarification(
        self, mock_search, mock_info, mock_id
    ):
        mock_id.return_value = 1
        mock_info.return_value = {
            "success": True,
            "synced": True,
            "project_id": 1,
            "project_name": "Project A",
        }

        mock_search.return_value = {
            "target": "VIEW",
            "query_info": {"explicit_view_name": "S100"},
            "results": [],
        }

        resp = self.client.post("/chat", json={"message": "show me the view named S100"})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertEqual(data["type"], "clarification")
        self.assertEqual(data["results"], [])
        self.assertIn("couldn't find an entity named 'S100'", data["message"])

    # ============================================================
    # 3. CONVERSATIONAL QUERIES DO NOT TRIGGER SEARCH
    # ============================================================

    def test_conversational_queries_no_search(self):
        conversational_inputs = [
            "hello",
            "hi",
            "how are you?",
            "how was your day?",
            "what's up?",
            "tell me about yourself",
            "thanks",
            "thank you",
        ]

        with patch("backend.main.search") as mock_search:
            for query in conversational_inputs:
                with self.subTest(query=query):
                    mock_search.reset_mock()
                    resp = self.client.post("/chat", json={"message": query})
                    self.assertEqual(resp.status_code, 200)
                    mock_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
