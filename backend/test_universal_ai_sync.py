"""
Focused regression test suite for RevitAI Universal AI Intelligence,
Project Synchronization, Query Normalization, and Conversational Search.
"""

import unittest
from unittest.mock import MagicMock, patch

from backend.semantic_search import (
    calculate_exact_match_score,
    calculate_level_score,
    calculate_specialized_penalty,
    calculate_view_type_score,
    detect_action,
    detect_conversational_intent,
    detect_target,
    extract_clean_identifier,
    extract_floor_number,
    extract_search_phrase,
    search_elements,
    search_exact_entity_project_scoped,
    search_views,
    understand_query,
)
from backend.gemini_service import fallback_intent_classifier
from backend.main import SESSION_CONTEXT, app, chat, ChatRequest


class TestUniversalAISync(unittest.TestCase):

    def setUp(self):
        SESSION_CONTEXT["project_id"] = None
        SESSION_CONTEXT["results"] = []
        SESSION_CONTEXT["current_level"] = None
        SESSION_CONTEXT["current_view_type"] = None
        SESSION_CONTEXT["current_category"] = None

    # ============================================================
    # 1. NATURAL LANGUAGE EQUIVALENT QUERIES
    # ============================================================
    def test_01_natural_language_variations_level_3(self):
        phrasings = [
            "show me L3",
            "can you show me L3",
            "could you show L3",
            "please show me level 3",
            "I want to see level 3",
            "take me to L3",
            "open L3",
            "find L3",
            "where is L3",
            "can you find the L3 floor plan",
            "show the floor plan for level 3",
            "open the third floor plan",
        ]
        for query in phrasings:
            with self.subTest(query=query):
                info = understand_query(query)
                self.assertEqual(info["floor_number"], "3", f"Failed for query: {query}")
                self.assertIn(info["action"], ["SEARCH", "OPEN"])

    def test_01_natural_language_variations_action_detection(self):
        open_queries = [
            "open L3",
            "take me to L3",
            "could you open the structural plan",
            "can you take me to the foundation drawing",
        ]
        for q in open_queries:
            with self.subTest(query=q):
                self.assertEqual(detect_action(q), "OPEN")

    # ============================================================
    # 2. EXACT IDENTIFIER LOOKUP (C101, SD105, A101, S100, L3)
    # ============================================================
    def test_02_exact_identifier_candidates(self):
        identifiers = [
            ("open C101", "C101"),
            ("show me SD105", "SD105"),
            ("find A101", "A101"),
            ("show me sheet S100", "S100"),
            ("where is E-101", "E-101"),
            ("open L5_SD", "L5_SD"),
        ]
        for query, expected_code in identifiers:
            with self.subTest(query=query):
                candidates = extract_clean_identifier(query)
                self.assertIn(expected_code, candidates)

    @patch("backend.semantic_search.get_db_connection")
    def test_02_exact_identifier_priority_over_semantic(self, mock_db_conn):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock DB returns exact sheet row for C101
        mock_cursor.fetchall.return_value = [
            (10, 1, 5001, "C101 - Site Plan", "DrawingSheet", None, "Site Plan", "Project A", "C:\\ProjectA.rvt", "C101", "Site Plan")
        ]

        results = search_views("open C101", limit=5, project_id=1)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["result_type"], "SHEET")
        self.assertEqual(results[0]["sheet_number"], "C101")
        self.assertEqual(results[0]["exact_match_score"], 100.0)

    # ============================================================
    # 3. CONCEPTUAL SEARCH
    # ============================================================
    def test_03_conceptual_search_understanding(self):
        conceptual_queries = [
            ("show me structural plans", "StructuralPlan"),
            ("find views related to foundations", "VIEW"),
            ("show me drawings for the upper floors", "VIEW"),
        ]
        for query, expected_target in conceptual_queries:
            with self.subTest(query=query):
                info = understand_query(query)
                self.assertIn(info["target"], ["VIEW", "ELEMENT"])

    # ============================================================
    # 4 & 5. PROJECT SWITCHING (A -> B -> A)
    # ============================================================
    @patch("backend.main.get_active_project_id")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    @patch("backend.main.search")
    def test_04_05_project_a_b_a_switching(self, mock_search, mock_classify, mock_get_id):
        # Step 1: Project A (ID 1)
        mock_get_id.return_value = 1
        SESSION_CONTEXT["project_id"] = 1
        SESSION_CONTEXT["results"] = [{"name": "L3 Floor Plan", "project_id": 1}]

        # Step 2: Switch to Project B (ID 2)
        mock_get_id.return_value = 2
        mock_classify.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {"viewType": "FloorPlan"},
            "normalizedQuery": "floor plans",
        }
        mock_search.return_value = {
            "target": "VIEW",
            "results": [{"name": "ProjectB L1", "project_id": 2, "result_type": "VIEW"}],
        }

        resp1 = chat(ChatRequest(message="show me floor plans"))
        self.assertTrue(resp1["success"])
        self.assertEqual(SESSION_CONTEXT["project_id"], 2)

        # Step 3: Switch back to Project A (ID 1)
        mock_get_id.return_value = 1
        mock_search.return_value = {
            "target": "VIEW",
            "results": [{"name": "ProjectA L3", "project_id": 1, "result_type": "VIEW"}],
        }

        resp2 = chat(ChatRequest(message="show me L3"))
        self.assertTrue(resp2["success"])
        self.assertEqual(SESSION_CONTEXT["project_id"], 1)

    # ============================================================
    # 6. SEARCH DURING SYNCHRONIZATION
    # ============================================================
    @patch("backend.semantic_search.search_views", return_value=[])
    @patch("backend.semantic_search.get_active_project_info")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    def test_06_search_during_sync_status(self, mock_classify, mock_get_info, mock_search_views):
        mock_classify.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {},
        }
        mock_get_info.return_value = {
            "success": True,
            "project_id": 1,
            "project_name": "Snowdon Towers Structural",
            "synced": False,
        }

        resp = chat(ChatRequest(message="show floor plans"))
        self.assertTrue(resp["success"])
        self.assertIn("not synchronized yet", resp["message"])

    # ============================================================
    # 7. EMBEDDING FAILURE FALLBACK
    # ============================================================
    @patch("backend.semantic_search.create_embedding", return_value=None)
    @patch("backend.semantic_search.get_db_connection")
    def test_07_embedding_failure_fallback(self, mock_db_conn, mock_create_emb):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Mock DB returns missing rows check = [] and project rows for fallback
        mock_cursor.fetchall.side_effect = [
            [],  # missing embedding rows
            [
                (1, 1, 101, "Level 3 Floor Plan", "FloorPlan", "L3", "L3 Floor Plan", None, "Project A", "C:\\ProjectA.rvt")
            ],
        ]

        results = search_views("Level 3 Floor Plan", limit=5, project_id=1)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["name"], "Level 3 Floor Plan")

    # ============================================================
    # 8. FOLLOW-UP QUESTIONS
    # ============================================================
    def test_08_follow_up_selection(self):
        res = fallback_intent_classifier("open the first one")
        self.assertEqual(res["intent"], "FOLLOW_UP")
        self.assertEqual(res["entities"]["resultIndex"], 0)

    def test_08_follow_up_second_one(self):
        res = fallback_intent_classifier("select the second wall")
        self.assertEqual(res["intent"], "FOLLOW_UP")
        self.assertEqual(res["entities"]["resultIndex"], 1)

    # ============================================================
    # 9. AMBIGUOUS QUESTIONS
    # ============================================================
    def test_09_ambiguous_queries(self):
        res = fallback_intent_classifier("open something")
        self.assertIn(res["intent"], ["AMBIGUOUS_PROMPT", "CLARIFICATION_REQUIRED"])

    # ============================================================
    # 10. PROJECT ISOLATION
    # ============================================================
    def test_10_project_isolation(self):
        info1 = understand_query("what project am I working on?")
        self.assertEqual(info1["target"], "PROJECT")

        info2 = understand_query("find walls on L3")
        self.assertEqual(info2["target"], "ELEMENT")

        info3 = understand_query("show me L3 floor plan")
        self.assertEqual(info3["target"], "VIEW")

    # ============================================================
    # 11, 12, 13. RESULT CONTRACTS (VIEW, SHEET, ELEMENT)
    # ============================================================
    @patch("backend.semantic_search.get_active_project_info")
    @patch("backend.semantic_search.get_db_connection")
    def test_11_12_13_result_contracts(self, mock_db_conn, mock_get_info):
        mock_get_info.return_value = {"success": True, "project_name": "Test Project"}

        elements = search_elements("find walls on L3", project_id=1, limit=1)
        self.assertTrue(len(elements) > 0)
        elem = elements[0]
        self.assertEqual(elem["result_type"], "ELEMENT")
        self.assertIn("revit_element_id", elem)
        self.assertIn("category", elem)
        self.assertIn("family_name", elem)
        self.assertIn("type_name", elem)
        self.assertIn("level_name", elem)

    # ============================================================
    # 14, 15, 16, 17. ACTIONS (OPEN, SELECT, HIGHLIGHT, ZOOM)
    # ============================================================
    def test_14_to_17_action_contracts(self):
        self.assertEqual(detect_action("open L3"), "OPEN")
        self.assertEqual(detect_action("show me L3"), "SEARCH")

        elements = search_elements("find doors on L5", project_id=1, limit=1)
        if elements:
            self.assertEqual(elements[0]["action"], "SELECT")


if __name__ == "__main__":
    unittest.main()
