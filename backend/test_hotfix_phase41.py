import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient

from backend.main import app, SESSION_CONTEXT
from backend.semantic_search import (
    understand_query,
    calculate_view_type_score,
    calculate_specialized_penalty,
)
from backend.gemini_service import (
    fallback_intent_classifier,
    classify_intent_with_gemini,
)


class TestPhase41Hotfix(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        SESSION_CONTEXT["project_id"] = None
        SESSION_CONTEXT["results"] = []
        SESSION_CONTEXT["current_level"] = None
        SESSION_CONTEXT["current_view_type"] = None
        SESSION_CONTEXT["current_category"] = None

    # ============================================================
    # TEST GROUP 1: Active Project Queries (PROJECT_INFO)
    # ============================================================

    def test_group1_fallback_intent_project_info(self):
        queries = [
            "What project am I working on?",
            "Which project is open right now?",
            "Show current project info",
            "What project is open?",
            "Tell me the active project name",
        ]
        for q in queries:
            classification = fallback_intent_classifier(q)
            self.assertEqual(
                classification["intent"],
                "PROJECT_INFO",
                f"Query '{q}' failed fallback classification as PROJECT_INFO",
            )

    @patch("backend.main.get_active_project_info")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    def test_group1_chat_endpoint_project_info(self, mock_classify, mock_get_info):
        mock_classify.return_value = {
            "intent": "PROJECT_INFO",
            "confidence": 0.98,
            "entities": {},
            "conversationalResponse": "You are currently working on **Snowdon Towers Sample Structural**.",
        }
        mock_get_info.return_value = {
            "success": True,
            "project_id": 1,
            "project_name": "Snowdon Towers Sample Structural",
            "file_path": "C:\\Snowdon.rvt",
        }

        response = self.client.post(
            "/chat",
            json={"message": "What project am I working on?"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertEqual(data["intent"], "PROJECT_INFO")
        self.assertEqual(data["target"], "CONVERSATION")
        self.assertEqual(data["results"], [])
        self.assertIn("Snowdon Towers Sample Structural", data["message"])

    # ============================================================
    # TEST GROUP 2: Structural Plan Queries (No Schedule Contamination)
    # ============================================================

    def test_group2_query_understanding_structural_plans(self):
        info = understand_query("structural plans")
        self.assertEqual(info["view_type"], "StructuralPlan")
        self.assertTrue(info["is_plan_query"])

    def test_group2_scoring_penalizes_schedules_for_structural_plans(self):
        query_info = understand_query("structural plans")

        vt_score_plan = calculate_view_type_score(query_info, "StructuralPlan", "01 - Entry Level")
        vt_score_schedule = calculate_view_type_score(query_info, "Schedule", "Structural Wall Schedule")

        pen_plan = calculate_specialized_penalty(query_info, "01 - Entry Level")
        pen_schedule = calculate_specialized_penalty(query_info, "Structural Wall Schedule")

        self.assertGreater(vt_score_plan, vt_score_schedule)
        self.assertEqual(pen_plan, 0.0)
        self.assertEqual(pen_schedule, -50.0)
        self.assertLess(vt_score_schedule + pen_schedule, -80.0)

    # ============================================================
    # TEST GROUP 3: Structural Schedule Queries (Explicit Schedules)
    # ============================================================

    def test_group3_query_understanding_structural_schedules(self):
        info = understand_query("show me structural schedules")
        self.assertEqual(info["view_type"], "Schedule")

    def test_group3_scoring_boosts_schedules(self):
        query_info = understand_query("show me structural schedules")

        vt_score_schedule = calculate_view_type_score(query_info, "Schedule", "Structural Wall Schedule")
        vt_score_plan = calculate_view_type_score(query_info, "StructuralPlan", "01 - Entry Level")

        self.assertGreater(vt_score_schedule, vt_score_plan)

    # ============================================================
    # TEST GROUP 4: Conversational Intent Preservation
    # ============================================================

    @patch("backend.gemini_service.classify_intent_with_gemini")
    def test_group4_conversational_intents(self, mock_classify):
        mock_classify.return_value = {
            "intent": "GENERAL_CONVERSATION",
            "confidence": 0.95,
            "entities": {},
            "conversationalResponse": "Hello! 👋 I am your RevitAI Assistant.",
        }

        response = self.client.post("/chat", json={"message": "Hello"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "GENERAL_CONVERSATION")
        self.assertEqual(data["results"], [])

    # ============================================================
    # TEST GROUP 5: False Positive Guarding (Explicit View Names)
    # ============================================================

    def test_group5_explicit_view_name_extraction(self):
        info = understand_query("Show me the view named S100")
        self.assertEqual(info["explicit_view_name"], "S100")

    def test_group5_generic_view_not_extracted_as_explicit(self):
        info = understand_query("structural plans")
        self.assertIsNone(info["explicit_view_name"])

    # ============================================================
    # TEST GROUP 6: Project Switching Context Invalidation
    # ============================================================

    @patch("backend.main.get_active_project_id")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    @patch("backend.main.search")
    def test_group6_project_switch_clears_context(self, mock_search, mock_classify, mock_get_id):
        # 1. Project A (id = 1)
        mock_get_id.return_value = 1
        SESSION_CONTEXT["project_id"] = 1
        SESSION_CONTEXT["results"] = [{"name": "L1 Floor Plan", "project_id": 1}]

        # 2. User switches to Project B (id = 2)
        mock_get_id.return_value = 2
        mock_classify.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {"viewType": "FloorPlan"},
            "normalizedQuery": "floor plans",
        }
        mock_search.return_value = {
            "target": "VIEW",
            "results": [{"name": "Ground Floor", "project_id": 2, "result_type": "view"}],
        }

        response = self.client.post("/chat", json={"message": "show floor plans"})
        self.assertEqual(response.status_code, 200)

        self.assertEqual(SESSION_CONTEXT["project_id"], 2)
        self.assertEqual(len(SESSION_CONTEXT["results"]), 1)
        self.assertEqual(SESSION_CONTEXT["results"][0]["project_id"], 2)


if __name__ == "__main__":
    unittest.main()
