import os
import sys
import unittest
from unittest.mock import patch

# Ensure root directory is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.semantic_search import (
    search,
    search_exact_entity_project_scoped,
    extract_clean_identifier,
    understand_query,
)
from backend.gemini_service import fallback_intent_classifier


class TestGenericExactIdentity(unittest.TestCase):
    def setUp(self):
        os.environ["REVITAI_PROJECT_ID"] = "1"
        self.patcher = patch("backend.semantic_search.get_active_project_id", return_value=1)
        self.mock_proj_id = self.patcher.start()


    def tearDown(self):
        self.patcher.stop()


    def test_extract_clean_identifier(self):
        self.assertIn("sd105", [x.lower() for x in extract_clean_identifier("open sd105")])
        self.assertIn("sd105", [x.lower() for x in extract_clean_identifier("can you open sd105")])
        self.assertIn("a101", [x.lower() for x in extract_clean_identifier("please show me A101")])
        self.assertIn("s100", [x.lower() for x in extract_clean_identifier("open the sheet S100")])
        self.assertIn("l5_sd", [x.lower() for x in extract_clean_identifier("show me the view L5_SD")])
        self.assertIn("e-101", [x.lower() for x in extract_clean_identifier("open E-101")])

    def test_exact_sheet_over_semantic(self):
        """CRITICAL REGRESSION: 'open sd105' MUST return SD105 sheet, NOT L5_SD."""
        res = search("open sd105", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open sd105")
        top_name = results[0]["name"]
        self.assertIn("SD105", top_name.upper(), f"Top result must be SD105 sheet, got: {top_name}")
        self.assertNotEqual(top_name, "L5_SD", "Top result MUST NOT be L5_SD for query 'open sd105'")

    def test_exact_view_name(self):
        """CRITICAL REGRESSION: 'open L5_SD' MUST return exact view L5_SD."""
        res = search("open L5_SD", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open L5_SD")
        top_name = results[0]["name"]
        self.assertEqual(top_name, "L5_SD", f"Top result must be exact 'L5_SD', got: {top_name}")

    def test_conversational_wrapper_extraction(self):
        res = search("can you open sd105", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertIn("SD105", results[0]["name"].upper())

    def test_conceptual_query_falls_to_semantic(self):
        res = search("show me structural plans", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(res["target"], "VIEW")

    def test_element_query_target(self):
        res = search("find walls on L3", limit=5)
        self.assertEqual(res["target"], "ELEMENT")
        results = res.get("results", [])
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["result_type"], "ELEMENT")

    def test_k101_sheet_match(self):
        """Test 'open k101' returns exact K101 sheet."""
        res = search("open k101", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open k101")
        top_name = results[0]["name"]
        self.assertIn("K101", top_name.upper(), f"Top result must be K101 sheet, got: {top_name}")

    def test_c101_sheet_match(self):
        """Test 'open c101' returns exact C101 sheet with SHEET result_type."""
        res = search("open c101", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open c101")
        top_name = results[0]["name"]
        self.assertIn("C101", top_name.upper(), f"Top result must be C101 sheet, got: {top_name}")
        self.assertEqual(results[0]["result_type"], "SHEET", "Result type for C101 must be SHEET")

    def test_a502_sheet_match(self):
        """Test 'open a502' returns exact A502 sheet (Partition Types)."""
        res = search("open a502", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open a502")
        top_name = results[0]["name"]
        self.assertIn("A502", top_name.upper(), f"Top result must be A502 sheet, got: {top_name}")
        self.assertEqual(results[0]["result_type"], "SHEET", "Result type for A502 must be SHEET")

    def test_a404_sheet_match(self):
        """Test 'open a404' returns exact A404 sheet (Residential Lobby)."""
        res = search("open a404", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open a404")
        top_name = results[0]["name"]
        self.assertIn("A404", top_name.upper(), f"Top result must be A404 sheet, got: {top_name}")

    def test_a403_sheet_match(self):
        """Test 'open a403' returns exact A403 sheet (Enlarged Live/Work Cores)."""
        res = search("open a403", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open a403")
        top_name = results[0]["name"]
        self.assertIn("A403", top_name.upper(), f"Top result must be A403 sheet, got: {top_name}")

    def test_a904_sheet_match(self):
        """Test 'open a904' returns exact A904 sheet (Solar Study)."""
        res = search("open a904", limit=5)
        results = res.get("results", [])
        self.assertTrue(len(results) > 0, "Should return search results for open a904")
        top_name = results[0]["name"]
        self.assertIn("A904", top_name.upper(), f"Top result must be A904 sheet, got: {top_name}")

    def test_p303_sheet_match(self):
        """Test 'open p303' returns exact P303 sheet in Plumbing project."""
        with patch("backend.semantic_search.get_active_project_id", return_value=5):
            res = search("open p303", limit=5)
            results = res.get("results", [])
            self.assertTrue(len(results) > 0, "Should return search results for open p303")
            top_name = results[0]["name"]
            self.assertIn("P303", top_name.upper(), f"Top result must be P303 sheet, got: {top_name}")
            self.assertEqual(results[0]["result_type"], "SHEET", "Result type for P303 must be SHEET")

    def test_p406_sheet_match(self):
        """Test 'open p406' returns exact P406 sheet in Plumbing project."""
        with patch("backend.semantic_search.get_active_project_id", return_value=5):
            res = search("open p406", limit=5)
            results = res.get("results", [])
            self.assertTrue(len(results) > 0, "Should return search results for open p406")
            top_name = results[0]["name"]
            self.assertIn("P406", top_name.upper(), f"Top result must be P406 sheet, got: {top_name}")
            self.assertEqual(results[0]["result_type"], "SHEET", "Result type for P406 must be SHEET")

    def test_non_existent_code_returns_zero_results(self):
        """Test 'open xyz999' returns 0 results instead of false vector matches."""
        res = search("open xyz999", limit=5)
        results = res.get("results", [])
        self.assertEqual(len(results), 0, "Non-existent explicit code xyz999 must return 0 results")

    def test_project_info_fallback(self):
        intent_res = fallback_intent_classifier("What project am I working on?")
        self.assertEqual(intent_res["intent"], "PROJECT_INFO")


if __name__ == "__main__":
    unittest.main()


