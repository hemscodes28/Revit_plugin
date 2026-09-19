import unittest
from unittest.mock import patch, MagicMock

# Patch create_embedding before importing main or semantic_search
with patch("backend.embedding_service.create_embedding", return_value=[0.1] * 384):
    from backend.main import app, SESSION_CONTEXT
    from backend.semantic_search import (
        understand_query,
        calculate_view_type_score,
        calculate_specialized_penalty,
        search_views,
    )
    from backend.gemini_service import fallback_intent_classifier

from fastapi.testclient import TestClient


class TestProductionMasterSuite(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(app)
        SESSION_CONTEXT["project_id"] = None
        SESSION_CONTEXT["results"] = []
        SESSION_CONTEXT["current_level"] = None
        SESSION_CONTEXT["current_view_type"] = None
        SESSION_CONTEXT["current_category"] = None

    # 1. Greetings
    def test_01_conversation_greetings(self):
        for msg in ["hello", "hi", "hey", "greetings"]:
            res = fallback_intent_classifier(msg)
            self.assertEqual(res["intent"], "GENERAL_CONVERSATION")

    # 2. Small Talk
    def test_02_conversation_small_talk(self):
        for msg in ["how are you", "how was your day", "tell me about yourself"]:
            res = fallback_intent_classifier(msg)
            self.assertEqual(res["intent"], "GENERAL_CONVERSATION")

    # 3. Thanks
    def test_03_conversation_thanks(self):
        for msg in ["thanks", "thank you so much"]:
            res = fallback_intent_classifier(msg)
            self.assertEqual(res["intent"], "GENERAL_CONVERSATION")

    # 4. Project Info Queries
    @patch("backend.main.get_active_project_info")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    def test_04_project_info_queries(self, mock_classify, mock_get_info):
        mock_classify.return_value = {
            "intent": "PROJECT_INFO",
            "confidence": 0.99,
            "entities": {},
            "conversationalResponse": None,
        }
        mock_get_info.return_value = {
            "success": True,
            "project_id": 1,
            "project_name": "Snowdon Towers Sample Structural",
            "file_path": "C:\\Snowdon.rvt",
        }

        response = self.client.post("/chat", json={"message": "What project am I working on?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["intent"], "PROJECT_INFO")
        self.assertIn("Snowdon Towers Sample Structural", data["message"])
        self.assertEqual(data["results"], [])

    # 5. Help Queries
    def test_05_help_queries(self):
        for msg in ["help", "what can you do", "commands"]:
            res = fallback_intent_classifier(msg)
            self.assertEqual(res["intent"], "HELP")

    # 6. Level Search
    def test_06_level_search(self):
        info1 = understand_query("show me L1")
        info2 = understand_query("open Level 3")
        self.assertEqual(info1["floor_number"], "1")
        self.assertEqual(info2["floor_number"], "3")

    # 7. View Type FloorPlan
    def test_07_view_type_floorplan(self):
        info = understand_query("show me floor plans")
        self.assertEqual(info["view_type"], "FloorPlan")

    # 8. View Type CeilingPlan
    def test_08_view_type_ceilingplan(self):
        info = understand_query("show me ceiling plans")
        self.assertEqual(info["view_type"], "CeilingPlan")

    # 9. View Type ThreeD
    def test_09_view_type_threed(self):
        info = understand_query("show me 3D views")
        self.assertEqual(info["view_type"], "ThreeD")

    # 10. View Type Elevation
    def test_10_view_type_elevation(self):
        info = understand_query("show me elevations")
        self.assertEqual(info["view_type"], "Elevation")

    # 11. View Type Section
    def test_11_view_type_section(self):
        info = understand_query("find sections")
        self.assertEqual(info["view_type"], "Section")

    # 12. Structural Plans (no schedule contamination)
    def test_12_structural_plans(self):
        info = understand_query("show me structural plans")
        self.assertEqual(info["view_type"], "StructuralPlan")
        score_plan = calculate_view_type_score(info, "StructuralPlan", "L1 Plan")
        score_sched = calculate_view_type_score(info, "Schedule", "Structural Wall Schedule")
        pen_sched = calculate_specialized_penalty(info, "Structural Wall Schedule")
        self.assertGreater(score_plan, score_sched + pen_sched)

    # 13. Structural Schedules (boosts schedules)
    def test_13_structural_schedules(self):
        info = understand_query("show me structural schedules")
        self.assertEqual(info["view_type"], "Schedule")
        score_sched = calculate_view_type_score(info, "Schedule", "Structural Wall Schedule")
        score_plan = calculate_view_type_score(info, "StructuralPlan", "L1 Plan")
        self.assertGreater(score_sched, score_plan)

    # 14. Exact Name Search
    def test_14_exact_name_search(self):
        info = understand_query("show me the view named S100")
        self.assertEqual(info["explicit_view_name"], "S100")

    # 15. Exact Name No Match (DB check)
    @patch("psycopg.connect")
    def test_15_exact_name_no_match(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        results = search_views("show me the view named NonExistent12345", limit=5, project_id=1)
        self.assertEqual(results, [])

    # 16. Follow-up Selection
    def test_16_follow_up_selection(self):
        res = fallback_intent_classifier("open the first one")
        self.assertEqual(res["intent"], "FOLLOW_UP")
        self.assertEqual(res["entities"]["resultIndex"], 0)

    # 17. Follow-up Correction
    def test_17_follow_up_correction(self):
        session_ctx = {"results": [{"name": "L3 Plan"}], "current_level": "L3"}
        res = fallback_intent_classifier("no, I meant L5", session_context=session_ctx)
        self.assertEqual(res["intent"], "FOLLOW_UP")

    # 18. Project Switch Isolation
    @patch("backend.main.get_active_project_id")
    @patch("backend.gemini_service.classify_intent_with_gemini")
    @patch("backend.main.search")
    def test_18_project_switch_isolation(self, mock_search, mock_classify, mock_get_id):
        mock_get_id.return_value = 1
        SESSION_CONTEXT["project_id"] = 1
        SESSION_CONTEXT["results"] = [{"name": "ProjA L1", "project_id": 1}]

        # Switch active project to 2
        mock_get_id.return_value = 2
        mock_classify.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {"viewType": "FloorPlan"},
            "normalizedQuery": "floor plans",
        }
        mock_search.return_value = {
            "target": "VIEW",
            "results": [{"name": "ProjB Ground", "project_id": 2, "result_type": "view"}],
        }

        response = self.client.post("/chat", json={"message": "show floor plans"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SESSION_CONTEXT["project_id"], 2)

    # 19. Typo Tolerance
    def test_19_typo_tolerance(self):
        info = understand_query("strucural plans")
        self.assertEqual(info["view_type"], "StructuralPlan")

    # 20. Clarification Required
    def test_20_clarification_required(self):
        res = fallback_intent_classifier("open something")
        self.assertIn(res["intent"], ["AMBIGUOUS_PROMPT", "CLARIFICATION_REQUIRED"])

    # 21. Explicit Name Parsing: "show me the view named L1" -> L1
    def test_21_explicit_name_parsing_named_l1(self):
        info = understand_query("show me the view named L1")
        self.assertEqual(info["explicit_view_name"], "L1")

    # 22. Explicit Name Parsing: "find the view called L1" -> L1
    def test_22_explicit_name_parsing_called_l1(self):
        info = understand_query("find the view called L1")
        self.assertEqual(info["explicit_view_name"], "L1")

    # 23. Sheet S100 Search
    def test_23_sheet_s100_search(self):
        info = understand_query("show me sheet S100")
        self.assertEqual(info["explicit_view_name"], "S100")

    # 24. S100 Code Search
    def test_24_s100_code_search(self):
        info = understand_query("show me S100")
        self.assertEqual(info["explicit_view_name"], "S100")

    # 25. Find Walls on L3 (Element Search)
    def test_25_find_walls_on_l3(self):
        info = understand_query("find walls on L3")
        self.assertEqual(info["target"], "ELEMENT")
        self.assertEqual(info["floor_number"], "3")

    # 26. Find Doors on L3 (Element Search)
    def test_26_find_doors_on_l3(self):
        info = understand_query("find doors on L3")
        self.assertEqual(info["target"], "ELEMENT")
        self.assertEqual(info["floor_number"], "3")

    # 27. Ordinary Floor Plan Ranking
    def test_27_ordinary_floor_plan_ranking(self):
        info = understand_query("show me floor plans")
        pen_ordinary = calculate_specialized_penalty(info, "L1")
        pen_safety = calculate_specialized_penalty(info, "L5 Life Safety Plan")
        self.assertGreater(pen_ordinary, pen_safety)

    # 28. Specialized Life Safety Plan Ranking
    def test_28_specialized_life_safety_ranking(self):
        info = understand_query("show me life safety plans")
        pen_safety = calculate_specialized_penalty(info, "L5 Life Safety Plan")
        self.assertEqual(pen_safety, 0.0)

    # 29. Explicit View Named Hello (No Match & Not Greeting)
    def test_29_explicit_view_named_hello(self):
        res = fallback_intent_classifier("show me the view named Hello")
        self.assertNotEqual(res["intent"], "GENERAL_CONVERSATION")
        info = understand_query("show me the view named Hello")
        self.assertEqual(info["explicit_view_name"], "Hello")


if __name__ == "__main__":
    unittest.main()
