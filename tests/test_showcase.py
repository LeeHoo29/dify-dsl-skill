from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CODE_ROOT = ROOT / "showcase" / "customer-feedback-triage" / "code-nodes"


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, CODE_ROOT / filename)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ANALYZE = load_module("showcase_analyze_feedback", "analyze_feedback.py")
FOLLOW_UP = load_module("showcase_format_follow_up", "format_follow_up.py")
ARCHIVE = load_module("showcase_format_archive", "format_archive.py")
INVALID = load_module("showcase_format_invalid", "format_invalid.py")


class ShowcaseTests(unittest.TestCase):
    def test_urgent_feedback_routes_to_follow_up(self) -> None:
        result = ANALYZE.main("C-1042", "Package arrived damaged; I need a refund.", 1)
        self.assertTrue(result["can_continue"])
        self.assertTrue(result["needs_follow_up"])
        self.assertEqual("high", result["priority"])
        formatted = FOLLOW_UP.main(
            result["category"],
            "C-1042",
            result["normalized_feedback"],
            result["priority"],
        )
        self.assertIn("PRIORITY FOLLOW-UP", formatted["result"])

    def test_positive_feedback_routes_to_standard_review(self) -> None:
        result = ANALYZE.main("C-1043", "Setup was clear and the product works well.", 5)
        self.assertTrue(result["can_continue"])
        self.assertFalse(result["needs_follow_up"])
        self.assertEqual("positive", result["category"])
        formatted = ARCHIVE.main(
            result["category"],
            "C-1043",
            result["normalized_feedback"],
            result["priority"],
        )
        self.assertIn("STANDARD REVIEW", formatted["result"])

    def test_invalid_rating_returns_actionable_error(self) -> None:
        result = ANALYZE.main("C-1044", "Rating was entered incorrectly.", 8)
        self.assertFalse(result["can_continue"])
        self.assertEqual("rating must be between 1 and 5", result["error_message"])
        formatted = INVALID.main("C-1044", result["error_message"])
        self.assertIn("INPUT REJECTED", formatted["result"])
        self.assertIn("submit", formatted["action"].lower())


if __name__ == "__main__":
    unittest.main()
