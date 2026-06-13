"""Tests for taskify (U5)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import taskify  # noqa: E402


def _correct(d):
    """A tiny working project under <d>/correct."""
    root = os.path.join(d, "correct")
    os.makedirs(os.path.join(root, "src"))
    with open(os.path.join(root, "src", "sum.py"), "w") as fh:
        fh.write("def add(a, b):\n    return a + b\n")
    return root


def _apply_unified(diff_text, base_dir):
    """Apply a unified diff (a/ -> b/) to base_dir using `patch`-free manual application via difflib
    is complex; instead re-derive: we assert the diff transforms task's content into correct's by
    checking the diff is non-empty and references the changed file."""
    return diff_text


class BreakCode(unittest.TestCase):
    def test_applies_mutation_and_makes_reference_diff(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {
                "mode": "break_code",
                "mutations": [{"file": "src/sum.py", "find": "a + b", "replace": "a - b", "note": "op"}],
                "acceptance_criteria": [{"id": "AC1", "description": "tests pass", "check": "test_command", "weight": 1}],
                "what_to_test": ["fixes the operator"],
            }
            out = os.path.join(d, "task")
            res = taskify.taskify(correct, plan, out)
            self.assertTrue(res["ok"], res.get("error"))
            # task/ has the broken version
            self.assertIn("a - b", open(os.path.join(out, "src/sum.py")).read())
            # reference diff transforms task -> correct (mentions the fix)
            self.assertIn("a + b", res["reference_diff"])
            self.assertIn("src/sum.py", res["reference_diff"])
            self.assertEqual(res["mutations"][0]["kind"], "bug")

    def test_missing_find_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {"mode": "break_code",
                    "mutations": [{"file": "src/sum.py", "find": "NOT THERE", "replace": "x"}]}
            res = taskify.taskify(correct, plan, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("not present", res["error"])

    def test_no_change_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {"mode": "break_code", "mutations": []}
            res = taskify.taskify(correct, plan, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("no change", res["error"])


class ExtendFunctionality(unittest.TestCase):
    def test_task_equals_correct_and_null_diff(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {
                "mode": "extend_functionality",
                "acceptance_criteria": [{"id": "AC1", "description": "adds flag", "check": "manual", "weight": 1}],
                "what_to_test": ["clean api"],
            }
            out = os.path.join(d, "task")
            res = taskify.taskify(correct, plan, out)
            self.assertTrue(res["ok"], res.get("error"))
            self.assertIsNone(res["reference_diff"])
            self.assertEqual(res["mutations"], [])
            self.assertEqual(open(os.path.join(out, "src/sum.py")).read(),
                             open(os.path.join(correct, "src/sum.py")).read())
            self.assertTrue(res["acceptance_criteria"])


class UnknownMode(unittest.TestCase):
    def test_rejects_unknown_mode(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mode": "nope"}, os.path.join(d, "task"))
            self.assertFalse(res["ok"])


class DiffExcludesVendored(unittest.TestCase):
    def test_vendored_paths_excluded_from_reference_diff(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            os.makedirs(os.path.join(correct, "node_modules", "p"))
            with open(os.path.join(correct, "node_modules", "p", "x.js"), "w") as fh:
                fh.write("module.exports = 1\n")
            plan = {"mode": "break_code",
                    "mutations": [{"file": "src/sum.py", "find": "a + b", "replace": "a - b"}],
                    "vendored_paths": ["node_modules"]}
            res = taskify.taskify(correct, plan, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertNotIn("node_modules", res["reference_diff"])


if __name__ == "__main__":
    unittest.main()
