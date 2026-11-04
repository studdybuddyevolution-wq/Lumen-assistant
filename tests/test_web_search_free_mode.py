from __future__ import annotations

import unittest
from unittest.mock import patch

import actions.web_search as web_search_module


class FreeSearchModeTests(unittest.TestCase):
    @patch("actions.web_search._gemini_search")
    @patch("actions.web_search._ddg_search")
    def test_free_research_uses_duckduckgo_without_gemini(self, ddg_search, gemini_search):
        ddg_search.return_value = [{
            "title": "Official Canvas API guide",
            "snippet": "Primary documentation for Canvas.",
            "url": "https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API",
        }]
        result = web_search_module.web_search({
            "query": "Canvas animation API",
            "mode": "free_research",
        })
        self.assertIn("developer.mozilla.org", result)
        ddg_search.assert_called_once_with("Canvas animation API", max_results=12)
        gemini_search.assert_not_called()

    @patch("actions.web_search._gemini_search")
    @patch("actions.web_search._ddg_search")
    def test_free_search_uses_smaller_duckduckgo_result_set(self, ddg_search, gemini_search):
        ddg_search.return_value = [{
            "title": "Canvas reference",
            "snippet": "API reference.",
            "url": "https://example.org/canvas",
        }]
        result = web_search_module.web_search({
            "query": "Canvas",
            "mode": "free_search",
        })
        self.assertIn("example.org/canvas", result)
        ddg_search.assert_called_once_with("Canvas", max_results=6)
        gemini_search.assert_not_called()


if __name__ == "__main__":
    unittest.main()
