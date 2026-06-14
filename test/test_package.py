"""Tests for packaging + the scorecard contract (U6, schema v2 problem-first model)."""
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import package  # noqa: E402


def _task(d):
    """A candidate task tree with an example test (mechanics-only)."""
    root = os.path.join(d, "task")
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "history.py"), "w") as fh:
        fh.write("def current_view(entries):\n    raise NotImplementedError  # TODO\n")
    with open(os.path.join(root, "tests", "example_test.py"), "w") as fh:
        fh.write("import history\n")
    with open(os.path.join(root, "BRIEF.md"), "w") as fh:
        fh.write("# Build the history model\n")
    return root


def _hidden(d, core_content="# core: current view excludes deleted\n", stretch_content="# stretch\n"):
    """A sibling hidden/ dir as taskify writes it; returns (dir, tiers)."""
    root = os.path.join(d, "hidden")
    os.makedirs(os.path.join(root, "core"))
    os.makedirs(os.path.join(root, "stretch"))
    with open(os.path.join(root, "core", "core_test.py"), "w") as fh:
        fh.write(core_content)
    with open(os.path.join(root, "stretch", "scale_test.py"), "w") as fh:
        fh.write(stretch_content)
    return root, {"core": ["core_test.py"], "stretch": ["scale_test.py"]}


def _taskify(hidden_dir, tiers, **kw):
    base = {
        "task_mode": "design+fix+extend (senior: 1 design choice + core + concurrency stretch)",
        "mutations": [{"file": "history.py", "kind": "stub", "note": "candidate builds the view"}],
        "example_tests": ["tests/example_test.py"],
        "hidden_tests_dir": hidden_dir,
        "hidden_tiers": tiers,
        "reference_exemplar": "--- a/history.py\n+++ b/history.py\n@@ -1 +1 @@\n-raise\n+return ...\n",
        "extension": {"description": "support reverting to version N", "acceptance_criteria": []},
        "scale": {"description": "two concurrent edits"},
        "seeded_failure": None,
        "human_rubric": [{"dimension": "model choice", "acceptable_approaches": ["append-only", "snapshots"],
                          "what_good_looks_like": "justified trade-off"}],
        "notes_evaluation": {"what_to_look_for": "alternatives considered"},
        "acceptance_criteria": [{"id": "AC_FIX", "description": "behaviour restored", "check": "test_command", "weight": 1}],
        "what_to_test": ["reconstruct past versions"],
    }
    base.update(kw)
    return base


def _meta(**kw):
    base = {"task_id": "hist-1", "language": "python", "build_command": None,
            "test_command": "python3 -m unittest discover -s tests -p '*_test.py'",
            "hidden_test_command": "python3 -m unittest discover -s _hidden -p '*_test.py'",
            "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
            "hiring": {"position": "Senior Backend Engineer", "seniority": "senior",
                       "job_description": "Build resilient services.", "time_target_hours": 1.5},
            "assessment": {"problem_summary": "brief history lost on edits",
                           "test_focus": "reconstruct + recover", "skills_assessed": ["data modelling"]},
            "pr_suitability": {"verdict": "recommend", "reasons": ["multiple plausible approaches"]},
            "skill_version": "0.1.0", "spec_version": "agentskills.io", "created_at": "2026-06-14T00:00:00Z",
            "notes_for_evaluator": ""}
    base.update(kw)
    return base


SOURCE = {"repo": "o/n", "pr": {"number": 5, "title": "versioning", "description": "the real fix", "url": "u", "diff": "d"},
          "issue": {"number": 3, "title": "history lost", "body": "edits destroy history", "url": "u"}}


class Assemble(unittest.TestCase):
    def test_scorecard_shape_v2(self):
        with tempfile.TemporaryDirectory() as d:
            hid, tiers = _hidden(d)
            sc = package.assemble_scorecard(_taskify(hid, tiers), SOURCE,
                                            {"expected_initial_state": {"tests": "red", "builds": True}}, _meta())
            self.assertEqual(sc["schema_version"], "2")
            self.assertIn("reference_exemplar", sc)
            self.assertNotIn("reference_solution", sc)
            self.assertEqual(sc["behavior_suite"]["core"][0]["path"], "core_test.py")
            self.assertIn("current view excludes deleted", sc["behavior_suite"]["core"][0]["content"])
            self.assertTrue(sc["behavior_suite"]["stretch"])
            self.assertTrue(sc["notes_required"])
            self.assertEqual(sc["grading"]["human_rubric"][0]["dimension"], "model choice")
            self.assertIn("NOT whole-suite-green", sc["grading"]["partial_credit"])
            self.assertEqual(sc["pr_suitability"]["verdict"], "recommend")
            self.assertIn("senior", sc["task_mode"])
            self.assertEqual(sc["source"]["pr"]["number"], 5)
            self.assertEqual(sc["hiring"]["seniority"], "senior")
            self.assertEqual(sc["expected_initial_state"]["tests"], "red")

    def test_manifest_has_no_task_mode(self):
        with tempfile.TemporaryDirectory() as d:
            hid, tiers = _hidden(d)
            task = _task(d)
            sc = package.assemble_scorecard(_taskify(hid, tiers), SOURCE, None, _meta())
            man = package.build_manifest(sc, task)
            self.assertNotIn("task_mode", man)


class Package(unittest.TestCase):
    def _bundle(self, d, taskify=None, meta=None, source=None):
        hid, tiers = _hidden(d)
        task = _task(d)
        sc = package.assemble_scorecard(taskify or _taskify(hid, tiers), source or SOURCE, None, meta or _meta())
        man = package.build_manifest(sc, task)
        out = os.path.join(d, "bundle.zip")
        return package.write_bundle(task, sc, man, out), out, sc

    def test_layout_and_hidden_not_in_task(self):
        with tempfile.TemporaryDirectory() as d:
            res, out, sc = self._bundle(d)
            self.assertTrue(res["ok"], res)
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
            self.assertIn("scorecard.json", names)
            self.assertIn("manifest.json", names)
            self.assertIn("task/tests/example_test.py", names)        # example test shipped
            self.assertNotIn("task/core_test.py", names)              # hidden suite NOT shipped
            self.assertFalse(any("core_test" in n and n.startswith("task/") for n in names))

    def test_secret_in_each_new_field_blocks_zip(self):
        secret = "AKIA1234567890ABCDEF"
        # behaviour_suite case: the secret rides in the hidden test source on disk
        with tempfile.TemporaryDirectory() as d:
            hid, tiers = _hidden(d, core_content=f"# leaked key {secret} here\n")
            task = _task(d)
            sc = package.assemble_scorecard(_taskify(hid, tiers), SOURCE, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "b.zip")
            res = package.write_bundle(task, sc, man, out)
            self.assertFalse(res["ok"], "secret in hidden test source must block")
            self.assertFalse(os.path.exists(out))

        for field, meta_mut, taskify_mut in [
            ("grading.partial_credit", {"grading": {"partial_credit": f"grade like {secret}"}}, {}),
            ("pr_suitability.reasons", {"pr_suitability": {"verdict": "recommend", "reasons": [f"see {secret}"]}}, {}),
            ("human_rubric", {}, {"human_rubric": [{"dimension": "x", "acceptable_approaches": [f"use {secret}"],
                                                    "what_good_looks_like": "y"}]}),
        ]:
            with tempfile.TemporaryDirectory() as d:
                hid, tiers = _hidden(d)
                task = _task(d)
                sc = package.assemble_scorecard(_taskify(hid, tiers, **taskify_mut), SOURCE, None, _meta(**meta_mut))
                man = package.build_manifest(sc, task)
                out = os.path.join(d, "b.zip")
                res = package.write_bundle(task, sc, man, out)
                self.assertFalse(res["ok"], f"secret in {field} must block")
                self.assertFalse(os.path.exists(out), f"no zip when {field} leaks")

    def test_email_in_source_redacted_not_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            src = json.loads(json.dumps(SOURCE))
            src["pr"]["description"] = "Co-Authored-By: Someone <real.person@company.com>"
            res, out, sc = self._bundle(d, source=src)
            self.assertTrue(res["ok"], res)
            self.assertGreaterEqual(res["pii_redactions"], 1)
            with zipfile.ZipFile(out) as z:
                card = json.loads(z.read("scorecard.json"))
            self.assertNotIn("real.person@company.com", card["source"]["pr"]["description"])

    def test_hidden_suite_path_colliding_with_task_is_caught(self):
        with tempfile.TemporaryDirectory() as d:
            hid, tiers = _hidden(d)
            task = _task(d)
            # simulate a leak: a file in task/ with the same relative path as a hidden core test
            with open(os.path.join(task, "core_test.py"), "w") as fh:
                fh.write("# accidentally shipped\n")
            sc = package.assemble_scorecard(_taskify(hid, tiers), SOURCE, None, _meta())
            man = package.build_manifest(sc, task)
            out = os.path.join(d, "b.zip")
            with self.assertRaises(AssertionError):
                package.write_bundle(task, sc, man, out)


if __name__ == "__main__":
    unittest.main()
