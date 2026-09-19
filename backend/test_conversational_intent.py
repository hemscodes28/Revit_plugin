"""
Unit tests for Phase 3.1 Conversational Greeting & Intent Detection.
Verifies all 24 required test cases plus normalization and edge cases.
"""

import unittest
from backend.semantic_search import detect_conversational_intent, understand_query


class TestConversationalIntent(unittest.TestCase):

    # ============================================================
    # 1. GREETINGS (Test cases 1 - 12 + variations)
    # ============================================================

    def test_greeting_1_hello(self):
        self.assertEqual(detect_conversational_intent("hello"), "GREETING")

    def test_greeting_2_hi(self):
        self.assertEqual(detect_conversational_intent("hi"), "GREETING")

    def test_greeting_3_hey(self):
        self.assertEqual(detect_conversational_intent("hey"), "GREETING")

    def test_greeting_4_hello_revit(self):
        self.assertEqual(detect_conversational_intent("hello revit"), "GREETING")

    def test_greeting_5_hi_revit(self):
        self.assertEqual(detect_conversational_intent("hi revit"), "GREETING")

    def test_greeting_6_hey_revit(self):
        self.assertEqual(detect_conversational_intent("hey revit"), "GREETING")

    def test_greeting_7_hello_revitai(self):
        self.assertEqual(detect_conversational_intent("hello RevitAI"), "GREETING")

    def test_greeting_8_good_morning(self):
        self.assertEqual(detect_conversational_intent("good morning"), "GREETING")

    def test_greeting_9_good_morning_revit(self):
        self.assertEqual(detect_conversational_intent("good morning revit"), "GREETING")

    def test_greeting_10_good_afternoon(self):
        self.assertEqual(detect_conversational_intent("good afternoon"), "GREETING")

    def test_greeting_11_good_evening(self):
        self.assertEqual(detect_conversational_intent("good evening"), "GREETING")

    def test_greeting_12_greetings(self):
        self.assertEqual(detect_conversational_intent("greetings"), "GREETING")

    def test_greeting_variations(self):
        variations = [
            ("Hello Revit!", "GREETING"),
            ("HELLO REVIT", "GREETING"),
            ("hello   revit", "GREETING"),
            ("hello, revit", "GREETING"),
            ("hello assistant", "GREETING"),
            ("hi RevitAI", "GREETING"),
            ("hey RevitAI", "GREETING"),
            ("hello there", "GREETING"),
            ("hi there", "GREETING"),
            ("hey there", "GREETING"),
            ("good morning RevitAI", "GREETING"),
            ("hiiii", "GREETING"),
            ("hiii", "GREETING"),
            ("heyyy", "GREETING"),
            ("hellooo", "GREETING"),
            ("hiiii revit", "GREETING"),
        ]
        for phrase, expected in variations:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_conversational_intent(phrase), expected)

    def test_small_talk(self):
        small_talk_cases = [
            "how are u",
            "how are u mr",
            "how are you",
            "how are you bro",
            "how r u",
            "how are you doing",
            "how is it going",
            "whats up",
            "wats up",
            "who are you",
            "hello how are you",
            "hi revit how are u",
            "how was ur day",
            "how was your day",
            "are you okay",
            "r u ok",
            "are u ok",
            "tell me about yourself",
            "tell me abt yourself",
        ]
        for phrase in small_talk_cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_conversational_intent(phrase), "SMALL_TALK")

    # ============================================================
    # 2. CAPABILITY HELP (Test cases 13 - 16)
    # ============================================================

    def test_capability_13_what_can_you_do(self):
        self.assertEqual(detect_conversational_intent("What can you do?"), "CAPABILITY_HELP")

    def test_capability_14_what_can_you_do_revit(self):
        self.assertEqual(detect_conversational_intent("what can you do revit?"), "CAPABILITY_HELP")

    def test_capability_15_help(self):
        self.assertEqual(detect_conversational_intent("help"), "CAPABILITY_HELP")

    def test_capability_16_help_me_with_revit(self):
        self.assertEqual(detect_conversational_intent("help me with Revit"), "CAPABILITY_HELP")

    # ============================================================
    # 3. GENERAL THANKS (Test cases 17 - 19 + variations)
    # ============================================================

    def test_thanks_17_thank_you(self):
        self.assertEqual(detect_conversational_intent("thank you"), "GENERAL_THANKS")

    def test_thanks_18_thanks(self):
        self.assertEqual(detect_conversational_intent("thanks"), "GENERAL_THANKS")

    def test_thanks_19_thanks_revit(self):
        self.assertEqual(detect_conversational_intent("thanks revit"), "GENERAL_THANKS")

    def test_thanks_thank_you_revitai(self):
        self.assertEqual(detect_conversational_intent("thank you RevitAI"), "GENERAL_THANKS")

    # ============================================================
    # 4. AMBIGUOUS REQUESTS
    # ============================================================

    def test_ambiguous_requests(self):
        ambiguous_cases = [
            "open something",
            "open the thing",
            "show me something",
        ]
        for phrase in ambiguous_cases:
            with self.subTest(phrase=phrase):
                self.assertEqual(detect_conversational_intent(phrase), "AMBIGUOUS_PROMPT")

    # ============================================================
    # 5. REGRESSION TESTS (Test cases 20 - 24 + edge cases)
    # ============================================================

    def test_regression_20_open_l1(self):
        info = understand_query("Open L1")
        self.assertIsNone(info["conversational_intent"])
        self.assertEqual(info["action"], "OPEN")
        self.assertEqual(info["floor_number"], "1")

    def test_regression_21_show_level_1(self):
        info = understand_query("Show Level 1")
        self.assertIsNone(info["conversational_intent"])
        self.assertEqual(info["floor_number"], "1")

    def test_regression_22_show_me_the_3d_view(self):
        info = understand_query("Show me the 3D view")
        self.assertIsNone(info["conversational_intent"])
        self.assertEqual(info["view_type"], "ThreeD")

    def test_regression_23_find_elevations(self):
        info = understand_query("Find elevations")
        self.assertIsNone(info["conversational_intent"])
        self.assertEqual(info["view_type"], "Elevation")

    def test_regression_24_find_sections(self):
        info = understand_query("Find sections")
        self.assertIsNone(info["conversational_intent"])
        self.assertEqual(info["view_type"], "Section")

    def test_edge_case_greeting_word_in_search(self):
        info1 = understand_query("Show me the view named Hello")
        self.assertIsNone(info1["conversational_intent"])

        info2 = understand_query("Find the room called Hello")
        self.assertIsNone(info2["conversational_intent"])


if __name__ == "__main__":
    unittest.main()
