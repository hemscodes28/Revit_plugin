"""
Unit test for backend/main.py /chat API endpoint.
Tests conversational intent responses (GREETING, CAPABILITY_HELP, GENERAL_THANKS, AMBIGUOUS_PROMPT).
"""

import unittest
from fastapi.testclient import TestClient
from backend.main import app


class TestMainApi(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_chat_greeting_hello_revit(self):
        response = self.client.post("/chat", json={"message": "hello revit"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["results"], [])
        self.assertIn("RevitAI Assistant", data["response"])

    def test_chat_greeting_hello_revitai(self):
        response = self.client.post("/chat", json={"message": "hello RevitAI"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["results"], [])

    def test_chat_capability_help(self):
        response = self.client.post("/chat", json={"message": "what can you do revit?"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["results"], [])
        self.assertIn("search", data["response"].lower())

    def test_chat_general_thanks(self):
        response = self.client.post("/chat", json={"message": "thanks revit"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["type"], "message")
        self.assertEqual(data["results"], [])

    def test_chat_ambiguous_prompt(self):
        response = self.client.post("/chat", json={"message": "open something"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["type"], ["search_results", "clarification"])



if __name__ == "__main__":
    unittest.main()
