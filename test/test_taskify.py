"""Tests for taskify (U5) — combined fix+extend model."""
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


_BUG = {"file": "src/sum.py", "find": "a + b", "replace": "a - b", "note": "op"}
_EXT = {"description": "Add a subtract() function.",
        "acceptance_criteria": [{"id": "AC_EXT1", "description": "subtract works", "check": "manual", "weight": 1}]}


class FixBugs(unittest.TestCase):
    def test_applies_bug_and_makes_reference_diff(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [_BUG], "what_to_test": ["op"]}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertEqual(res["mode"], "fix_bugs")
            self.assertIn("a - b", open(os.path.join(d, "task", "src/sum.py")).read())
            self.assertIn("a + b", res["reference_diff"])
            self.assertEqual(res["mutations"][0]["kind"], "bug")
            self.assertIsNone(res["extension"])
            self.assertTrue(any(c["id"] == "AC_FIX" for c in res["acceptance_criteria"]))

    def test_missing_find_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [{"file": "src/sum.py", "find": "ZZZ", "replace": "x"}]},
                                  os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("not present", res["error"])


class FixAndExtend(unittest.TestCase):
    def test_default_combined_task(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [_BUG], "extension": _EXT}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertEqual(res["mode"], "fix_and_extend")
            self.assertIn("a + b", res["reference_diff"])          # the fix
            self.assertEqual(res["extension"]["description"], _EXT["description"])
            ids = [c["id"] for c in res["acceptance_criteria"]]
            self.assertIn("AC_FIX", ids)       # the bug-fix criterion
            self.assertIn("AC_EXT1", ids)      # the extension criterion


class ExtendOnly(unittest.TestCase):
    def test_extension_only(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"extension": _EXT}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertEqual(res["mode"], "extend")
            self.assertIsNone(res["reference_diff"])
            self.assertEqual(res["mutations"], [])
            self.assertEqual(open(os.path.join(d, "task", "src/sum.py")).read(),
                             open(os.path.join(correct, "src/sum.py")).read())
            self.assertIn("AC_EXT1", [c["id"] for c in res["acceptance_criteria"]])


class NothingToDo(unittest.TestCase):
    def test_empty_plan_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"what_to_test": []}, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("nothing to do", res["error"])


class DiffExcludesVendored(unittest.TestCase):
    def test_vendored_paths_excluded_from_reference_diff(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            os.makedirs(os.path.join(correct, "node_modules", "p"))
            with open(os.path.join(correct, "node_modules", "p", "x.js"), "w") as fh:
                fh.write("module.exports = 1\n")
            res = taskify.taskify(correct, {"mutations": [_BUG], "vendored_paths": ["node_modules"]},
                                  os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertNotIn("node_modules", res["reference_diff"])


if __name__ == "__main__":
    unittest.main()
