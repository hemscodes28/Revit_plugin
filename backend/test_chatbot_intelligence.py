"""
Comprehensive automated test suite for RevitAI Chatbot Intelligence, Gemini classification,
typo tolerance, multi-turn context, and false-positive search prevention.
"""

import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from backend.gemini_service import fallback_intent_classifier, classify_intent_with_gemini, normalize_query
from backend.main import app


class TestChatbotIntelligence(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    # ============================================================
    # 1. FALSE-POSITIVE TESTS (searchRevitModel MUST NOT BE CALLED)
    # ============================================================

    def test_false_positives_never_trigger_search(self):
        conversational_phrases = [
            "hello",
            "hi",
            "hey",
            "helo",
            "helllo",
            "ello",
            "hii",
            "hiii",
            "heyy",
            "how are you",
            "how are u",
            "how r u",
            "how was ur day",
            "how was your day",
            "whats up",
            "wats up",
            "are you okay",
            "r u ok",
            "tell me about yourself",
            "tell me abt yourself",
            "what is your name?",
            "who are you?",
            "what can you do?",
            "good morning",
            "good afternoon",
            "good evening",
            "thanks",
            "thank you",
            "okay",
            "ok",
            "nice",
            "great",
            "bye",
            "goodbye",
            "I need help",
            "can you help me?",
            "tell me something",
        ]

        with patch("backend.main.search") as mock_search:
            for phrase in conversational_phrases:
                with self.subTest(phrase=phrase):
                    mock_search.reset_mock()
                    response = self.client.post("/chat", json={"message": phrase})
                    self.assertEqual(response.status_code, 200)
                    data = response.json()

                    # Verify search was NEVER called
                    mock_search.assert_not_called()

                    # Verify response format
                    self.assertTrue(data.get("success"))
                    self.assertIn(data.get("type"), ["message", "clarification"])
                    self.assertNotEqual(data.get("type"), "search_results")
                    self.assertEqual(data.get("results"), [])

    # ============================================================
    # 2. TYPO NORMALIZATION & ENTITY EXTRACTION
    # ============================================================

    def test_typo_normalization(self):
        self.assertEqual(normalize_query("ello"), "hello")
        self.assertEqual(normalize_query("helo"), "hello")
        self.assertEqual(normalize_query("helllo"), "hello")
        self.assertEqual(normalize_query("hii"), "hi")
        self.assertEqual(normalize_query("heyy"), "hey")

        self.assertEqual(normalize_query("flor"), "floor")
        self.assertEqual(normalize_query("roms"), "rooms")
        self.assertEqual(normalize_query("wal"), "wall")
        self.assertEqual(normalize_query("saftey"), "safety")
        self.assertEqual(normalize_query("toilt"), "toilet")

    def test_typo_intent_classification(self):
        # Conversational typos stay GENERAL_CONVERSATION
        for typo in ["ello", "helo", "helllo", "hii", "heyy"]:
            res = fallback_intent_classifier(typo)
            self.assertEqual(res["intent"], "GENERAL_CONVERSATION")

        # Revit typos trigger REVIT_SEARCH
        res_wall = fallback_intent_classifier("show me l3 wal plan")
        self.assertEqual(res_wall["intent"], "REVIT_SEARCH")
        self.assertEqual(res_wall["entities"]["level"], "L3")
        self.assertEqual(res_wall["entities"]["category"], "wall")

        res_room = fallback_intent_classifier("find roms l5")
        self.assertEqual(res_room["intent"], "REVIT_SEARCH")
        self.assertEqual(res_room["entities"]["level"], "L5")
        self.assertIn(res_room["entities"]["category"], ["room", "rooms"])


    # ============================================================
    # 3. REVIT SEARCH POSITIVE TESTS
    # ============================================================

    def test_revit_search_triggers_search_function(self):
        search_phrases = [
            "show me L3 floor plan",
            "find L3 wall plans",
            "show me rooms on L5",
            "find life safety plan",
            "show me toilet views",
        ]

        with patch("backend.main.search") as mock_search:
            mock_search.return_value = {
                "target": "VIEW",
                "results": [
                    {
                        "result_type": "view",
                        "name": "L3 Floor Plan",
                        "view_type": "FloorPlan",
                        "level_name": "L3",
                        "revit_view_id": 12345,
                        "project_id": 1,
                    }
                ],
            }

            for phrase in search_phrases:
                with self.subTest(phrase=phrase):
                    mock_search.reset_mock()
                    response = self.client.post("/chat", json={"message": phrase})
                    self.assertEqual(response.status_code, 200)
                    data = response.json()

                    # Verify search WAS called
                    mock_search.assert_called_once()

                    # Verify response payload
                    self.assertTrue(data.get("success"))
                    self.assertEqual(data.get("type"), "search_results")
                    self.assertGreater(len(data.get("results")), 0)

    # ============================================================
    # 5. VIEW RANKING & PENALTY VERIFICATION
    # ============================================================

    def test_l3_wall_plans_scoring_ranking(self):
        from backend.semantic_search import (
            understand_query,
            calculate_view_type_score,
            calculate_level_score,
            calculate_keyword_score,
            calculate_specialized_penalty,
        )

        info = understand_query("L3 wall plans")
        self.assertEqual(info["floor_number"], "3")
        self.assertEqual(info["view_type"], "FloorPlan")

        # Candidate 1: L3 Wall Base (FloorPlan, L3)
        vt_score1 = calculate_view_type_score(info, "FloorPlan", "L3 Wall Base")
        lvl_score1 = calculate_level_score(info, "L3 Wall Base", "Level 3")
        kw_score1 = calculate_keyword_score(info, "L3 Wall Base", "Level 3", "")
        pen1 = calculate_specialized_penalty(info, "L3 Wall Base")
        score1 = vt_score1 + lvl_score1 + kw_score1 + pen1

        # Candidate 2: L3 Ceiling Plan (CeilingPlan, L3)
        vt_score2 = calculate_view_type_score(info, "CeilingPlan", "L3 Ceiling Plan")
        lvl_score2 = calculate_level_score(info, "L3 Ceiling Plan", "Level 3")
        kw_score2 = calculate_keyword_score(info, "L3 Ceiling Plan", "Level 3", "")
        pen2 = calculate_specialized_penalty(info, "L3 Ceiling Plan")
        score2 = vt_score2 + lvl_score2 + kw_score2 + pen2

        # Verify L3 Wall Base outscores L3 Ceiling Plan by at least 25 points
        self.assertGreater(score1, score2 + 25.0)


    # ============================================================
    # 6. EXPLICIT VIEW NAME SEARCH TESTS
    # ============================================================

    def test_explicit_view_name_search_no_match(self):
        from backend.semantic_search import understand_query, extract_explicit_view_name

        q_info = understand_query("show me the view named Hello")
        self.assertEqual(q_info["explicit_view_name"], "Hello")

        q_info2 = understand_query("find the view called Hello")
        self.assertEqual(q_info2["explicit_view_name"], "Hello")

        q_info3 = understand_query("open the view named Hello")
        self.assertEqual(q_info3["explicit_view_name"], "Hello")

        with patch("backend.main.search") as mock_search:
            mock_search.return_value = {
                "target": "VIEW",
                "query_info": {"explicit_view_name": "Hello"},
                "results": [],
            }
            response = self.client.post("/chat", json={"message": "show me the view named Hello"})
            self.assertEqual(response.status_code, 200)
            data = response.json()

            self.assertTrue(data.get("success"))
            self.assertEqual(data.get("type"), "clarification")
            self.assertEqual(data.get("results"), [])
            self.assertIn("couldn't find an entity named 'Hello'", data.get("message"))


if __name__ == "__main__":
    unittest.main()
