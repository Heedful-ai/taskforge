"""Tests for packaging + the scorecard contract (U7)."""
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import package  # noqa: E402


def _task(d):
    root = os.path.join(d, "task")
    os.makedirs(os.path.join(root, "src"))
    with open(os.path.join(root, "src", "sum.py"), "w") as fh:
        fh.write("def add(a, b):\n    return a - b\n")
    with open(os.path.join(root, "BRIEF.md"), "w") as fh:
        fh.write("# Fix the bug\n")
    return root


def _taskify(**kw):
    base = {"mode": "break_code", "mutations": [{"file": "src/sum.py", "kind": "bug", "note": "op"}],
            "reference_diff": "--- a/src/sum.py\n+++ b/src/sum.py\n@@ -2 +2 @@\n-    return a - b\n+    return a + b\n",
            "acceptance_criteria": [{"id": "AC1", "description": "tests pass", "check": "test_command", "weight": 1}],
            "what_to_test": ["fixes operator"]}
    base.update(kw)
    return base


def _meta(**kw):
    base = {"task_id": "t1", "language": "python", "build_command": None,
            "test_command": "python3 -m unittest", "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
            "hiring": {"position": "Senior Backend Engineer", "seniority": "senior",
                       "job_description": "Build resilient services.", "time_target_hours": 1.5},
            "assessment": {"problem_summary": "off-by-one in a date window",
                           "test_focus": "reintroduce the boundary bug; test inclusive end",
                           "skills_assessed": ["debugging", "date/time correctness"]},
            "skill_version": "0.1.0", "spec_version": "agentskills.io", "created_at": "2026-06-13T00:00:00Z",
            "notes_for_evaluator": ""}
    base.update(kw)
    return base


SOURCE = {"repo": "o/n", "pr": {"number": 12, "title": "fix", "description": "real fix", "url": "u", "diff": "d"},
          "issue": {"number": 9, "title": "bug", "body": "it breaks", "url": "u"}}


class Assemble(unittest.TestCase):
    def test_scorecard_shape(self):
        sc = package.assemble_scorecard(_taskify(), SOURCE, {"expected_initial_state": {"tests": "red"}}, _meta())
        self.assertEqual(sc["task_mode"], "break_code")
        self.assertEqual(sc["source"]["pr"]["number"], 12)
        self.assertEqual(sc["created_by"]["operator"], "Oskar")
        self.assertEqual(sc["expected_initial_state"]["tests"], "red")
        self.assertIn("a + b", sc["reference_solution"]["diff"])
        self.assertEqual(sc["hiring"]["position"], "Senior Backend Engineer")
        self.assertEqual(sc["hiring"]["time_target_hours"], 1.5)
        self.assertIn("debugging", sc["assessment"]["skills_assessed"])
        self.assertTrue(sc["assessment"]["problem_summary"])


class Package(unittest.TestCase):
    def test_bundle_layout_and_scorecard_outside_task(self):
        with tempfile.TemporaryDirectory() as d:
            task = _task(d)
            sc = package.assemble_scorecard(_taskify(), SOURCE, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "bundle.zip")
            res = package.write_bundle(task, sc, man, out)
            self.assertTrue(res["ok"], res)
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
                self.assertIn("scorecard.json", names)
                self.assertIn("manifest.json", names)
                self.assertIn("task/BRIEF.md", names)
                self.assertIn("task/src/sum.py", names)
                self.assertFalse(any(n.startswith("task/scorecard") for n in names))
                man_loaded = json.loads(z.read("manifest.json"))
                self.assertEqual(man_loaded["file_count"], 2)
                self.assertIn("src/sum.py", man_loaded["checksums"])

    def test_secret_in_scorecard_prose_blocks_packaging(self):
        with tempfile.TemporaryDirectory() as d:
            task = _task(d)
            bad_source = json.loads(json.dumps(SOURCE))
            bad_source["issue"]["body"] = 'leaked AKIA1234567890ABCDEF in the ticket'
            sc = package.assemble_scorecard(_taskify(), bad_source, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "bundle.zip")
            res = package.write_bundle(task, sc, man, out)
            self.assertFalse(res["ok"])
            self.assertFalse(os.path.exists(out))  # fail-closed: no zip written

    def test_email_in_source_prose_is_redacted_not_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            task = _task(d)
            src = json.loads(json.dumps(SOURCE))
            src["pr"]["description"] = "Co-Authored-By: Someone <real.person@company.com>"
            sc = package.assemble_scorecard(_taskify(), src, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "bundle.zip")
            res = package.write_bundle(task, sc, man, out)
            self.assertTrue(res["ok"], res)              # not blocked
            self.assertGreaterEqual(res["pii_redactions"], 1)
            with zipfile.ZipFile(out) as z:
                card = json.loads(z.read("scorecard.json"))
            self.assertNotIn("real.person@company.com", card["source"]["pr"]["description"])
            self.assertIn("redacted", card["source"]["pr"]["description"])

    def test_extend_mode_null_diff_packages(self):
        with tempfile.TemporaryDirectory() as d:
            task = _task(d)
            tf = _taskify(mode="extend_functionality", mutations=[], reference_diff=None)
            sc = package.assemble_scorecard(tf, SOURCE, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "bundle.zip")
            res = package.write_bundle(task, sc, man, out)
            self.assertTrue(res["ok"], res)
            self.assertIsNone(sc["reference_solution"]["diff"])


if __name__ == "__main__":
    unittest.main()
