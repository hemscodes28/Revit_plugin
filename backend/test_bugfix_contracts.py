import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.main import app, SESSION_CONTEXT
from backend.semantic_search import (
    search_views,
    search_elements,
    search,
    normalize_file_path,
    extract_explicit_view_name,
)

client = TestClient(app)

class TestBugfixContracts(unittest.TestCase):
    def setUp(self):
        SESSION_CONTEXT["project_id"] = None
        SESSION_CONTEXT["results"] = []
        SESSION_CONTEXT["current_level"] = None
        SESSION_CONTEXT["current_view_type"] = None
        SESSION_CONTEXT["current_category"] = None

    @patch("backend.semantic_search.get_active_project_id")
    def test_view_and_element_same_project_id(self, mock_get_proj_id):
        mock_get_proj_id.return_value = 1

        v_res = search_views(query="show me L3", project_id=1)
        e_res = search_elements(query="find walls on L3", project_id=1)

        if v_res:
            self.assertEqual(v_res[0]["project_id"], 1)
        if e_res:
            self.assertEqual(e_res[0]["project_id"], 1)
            if v_res:
                self.assertEqual(v_res[0]["project_id"], e_res[0]["project_id"])

    @patch("backend.semantic_search.get_active_project_id")
    def test_view_result_contract(self, mock_get_proj_id):
        mock_get_proj_id.return_value = 1
        res = search_views(query="show me L3", project_id=1)
        if res:
            first = res[0]
            self.assertIn("result_type", first)
            self.assertEqual(first["result_type"], "VIEW")
            self.assertIn("revit_view_id", first)
            self.assertIn("project_id", first)
            self.assertEqual(first["project_id"], 1)

    @patch("backend.semantic_search.get_active_project_id")
    def test_element_result_contract(self, mock_get_proj_id):
        mock_get_proj_id.return_value = 1
        res = search_elements(query="find walls on L3", project_id=1)
        self.assertTrue(len(res) > 0)
        first = res[0]
        self.assertEqual(first["result_type"], "ELEMENT")
        self.assertIn("revit_element_id", first)
        self.assertNotIn("revit_view_id", first)
        self.assertEqual(first["project_id"], 1)

    @patch("backend.gemini_service.classify_intent_with_gemini")
    @patch("backend.semantic_search.get_active_project_id")
    @patch("backend.main.get_active_project_id")
    def test_chat_normalizes_element_fields(self, mock_main_proj_id, mock_sem_proj_id, mock_gemini):
        mock_main_proj_id.return_value = 1
        mock_sem_proj_id.return_value = 1
        mock_gemini.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {"action": "SEARCH", "category": "Walls", "level": "L3"},
            "normalizedQuery": "find walls on L3",
        }

        response = client.post("/chat", json={"message": "find walls on L3"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(len(data["results"]) > 0)
        elem = data["results"][0]
        self.assertEqual(elem["result_type"], "ELEMENT")
        self.assertEqual(elem["project_id"], 1)
        self.assertIsNotNone(elem.get("revit_element_id"))
        self.assertEqual(elem.get("category"), "Walls")

    def test_normalize_file_path_behavior(self):
        path1 = "C:/Program Files/Autodesk/Revit 2024/Samples/Snowdon Towers Sample Architectural.rvt"
        path2 = "c:\\program files\\autodesk\\revit 2024\\samples\\snowdon towers sample architectural.rvt"
        norm1 = normalize_file_path(path1)
        norm2 = normalize_file_path(path2)
        self.assertEqual(norm1, norm2)

    @patch("backend.gemini_service.classify_intent_with_gemini")
    @patch("backend.semantic_search.get_active_project_id")
    @patch("backend.main.get_active_project_id")
    def test_project_context_switching_architectural_structural(self, mock_main_proj_id, mock_sem_proj_id, mock_gemini):
        mock_gemini.return_value = {
            "intent": "REVIT_SEARCH",
            "confidence": 0.95,
            "entities": {"action": "SEARCH"},
            "normalizedQuery": "show plans",
        }

        # Step 1: Active project is 1 (Architectural)
        mock_main_proj_id.return_value = 1
        mock_sem_proj_id.return_value = 1
        r1 = client.post("/chat", json={"message": "show plans"})
        self.assertEqual(SESSION_CONTEXT["project_id"], 1)

        # Step 2: Switch active project to 2 (Structural)
        mock_main_proj_id.return_value = 2
        mock_sem_proj_id.return_value = 2
        r2 = client.post("/chat", json={"message": "show plans"})
        self.assertEqual(SESSION_CONTEXT["project_id"], 2)

        # Step 3: Switch back to 1 (Architectural)
        mock_main_proj_id.return_value = 1
        mock_sem_proj_id.return_value = 1
        r3 = client.post("/chat", json={"message": "show plans"})
        self.assertEqual(SESSION_CONTEXT["project_id"], 1)

    @patch("backend.semantic_search.get_active_project_id")
    def test_all_model_element_categories_return_element(self, mock_get_proj_id):
        mock_get_proj_id.return_value = 1
        for query, cat in [
            ("find walls on L3", "Walls"),
            ("find doors on L3", "Doors"),
            ("find windows on L3", "Windows"),
        ]:
            res = search_elements(query=query, project_id=1)
            self.assertTrue(len(res) > 0)
            self.assertEqual(res[0]["result_type"], "ELEMENT")
            self.assertIn("revit_element_id", res[0])
            self.assertNotIn("revit_view_id", res[0])

    def test_explicit_view_name_extraction(self):
        self.assertEqual(extract_explicit_view_name("show me the view named L1"), "L1")
        self.assertEqual(extract_explicit_view_name("find view called L1"), "L1")
        self.assertEqual(extract_explicit_view_name("show me the view named XYZ_TEST_999"), "XYZ_TEST_999")

    @patch("backend.gemini_service.classify_intent_with_gemini")
    def test_greetings_do_not_trigger_search(self, mock_gemini):
        mock_gemini.return_value = {
            "intent": "GENERAL_CONVERSATION",
            "confidence": 0.99,
            "conversationalResponse": "Hello! How can I help you?",
        }
        for greeting in ["hello", "hi", "hey", "how are you?"]:
            response = client.post("/chat", json={"message": greeting})
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["intent"], "GENERAL_CONVERSATION")
            self.assertEqual(len(data["results"]), 0)


    @patch("backend.semantic_search.get_active_project_id")
    def test_file_l3_queries_resolve_to_view_search(self, mock_get_proj_id):
        mock_get_proj_id.return_value = 1
        for query in ["ok can u show the file l3", "show me the file L3", "open the file L3"]:
            search_res = search(query=query, limit=5)
            self.assertEqual(search_res["target"], "VIEW")
            if search_res.get("results"):
                self.assertEqual(search_res["results"][0]["result_type"], "VIEW")


if __name__ == "__main__":
    unittest.main()
