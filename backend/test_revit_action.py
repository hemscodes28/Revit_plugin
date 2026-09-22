import unittest
from fastapi.testclient import TestClient
from backend.main import app

class TestRevitActionEndpoint(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_revit_action_proxy_format(self):
        payload = {
            "action": "OPEN",
            "name": "P100 - PLAN - L0 SANITARY",
            "type": "sheet",
            "revit_view_id": 1522428,
            "project_id": 5
        }
        res = self.client.post("/revit-action", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("success", data)
        self.assertIn("message", data)

if __name__ == "__main__":
    unittest.main()
