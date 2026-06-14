"""Tests for the bundle: task/ (no node_modules) + EVALUATION.md + evaluation/reference/ + context.json."""
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import package  # noqa: E402


def _correct(d):
    root = os.path.join(d, "correct")
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "node_modules", "x"))
    with open(os.path.join(root, "src", "history.py"), "w") as fh:
        fh.write("def current_view(entries):\n    return [e for e in entries if not e['deleted']]\n")
    with open(os.path.join(root, "node_modules", "x", "big.js"), "w") as fh:
        fh.write("// vendored junk\n")
    return root


def _task(d):
    root = os.path.join(d, "task")
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "node_modules", "x"))
    with open(os.path.join(root, "src", "history.py"), "w") as fh:
        fh.write("def current_view(entries):\n    raise NotImplementedError  # TODO\n")
    with open(os.path.join(root, "package-lock.json"), "w") as fh:
        fh.write("{}\n")
    with open(os.path.join(root, "node_modules", "x", "big.js"), "w") as fh:
        fh.write("// vendored junk\n")
    with open(os.path.join(root, "BRIEF.md"), "w") as fh:
        fh.write("# Build the history model\n")
    return root


def _taskify(**kw):
    base = {"task_mode": "build (senior)",
            "mutations": [{"file": "src/history.py", "kind": "stub", "note": "build the view"}],
            "reference_files": ["src/history.py"],
            "extension": None, "scale": None, "seeded_failure": None,
            "reference_summary": "an append-only model",
            "human_rubric": [{"dimension": "model choice", "acceptable_approaches": ["append-only", "snapshots"],
                              "what_good_looks_like": "justified trade-off"}],
            "notes_evaluation": {"what_to_look_for": "alternatives considered"},
            "acceptance_criteria": [], "what_to_test": ["reconstruct history"]}
    base.update(kw)
    return base


def _meta(**kw):
    base = {"task_id": "hist-1", "language": "node", "build_command": None, "test_command": "npm test",
            "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
            "summary": "discussed making brief history auditable",
            "hiring": {"position": "Senior Backend Engineer", "seniority": "senior",
                       "job_description": "Build resilient services.", "time_target_hours": 1.5},
            "assessment": {"problem_summary": "history lost on edits", "test_focus": "reconstruct + recover",
                           "skills_assessed": ["data modelling"]},
            "pr_suitability": {"verdict": "recommend", "reasons": ["multiple plausible approaches"]},
            "skill_version": "0.3.0", "spec_version": "agentskills.io", "created_at": "2026-06-14T00:00:00Z"}
    base.update(kw)
    return base


SOURCE = {"repo": "o/n", "pr": {"number": 5, "title": "versioning", "description": "the real fix", "url": "u", "diff": "d"},
          "issue": {"number": 3, "title": "history lost", "body": "edits destroy history", "url": "u"}}


class Context(unittest.TestCase):
    def test_context_shape(self):
        ctx = package.build_context(_taskify(), SOURCE, _meta())
        self.assertEqual(ctx["task_id"], "hist-1")
        self.assertEqual(ctx["created_by"]["operator"], "Oskar")
        self.assertEqual(ctx["source"]["pr"]["number"], 5)
        self.assertIn("auditable", ctx["summary"])
        self.assertEqual(ctx["hiring"]["seniority"], "senior")
        self.assertEqual(ctx["pr_suitability"]["verdict"], "recommend")
        self.assertEqual(ctx["test_command"], "npm test")
        self.assertNotIn("behavior_suite", ctx)
        self.assertNotIn("reference_exemplar", ctx)


class Evaluation(unittest.TestCase):
    def test_evaluation_md_content(self):
        md = package.build_evaluation_md(_taskify(), SOURCE, _meta())
        self.assertIn("# Evaluation guide", md)
        self.assertIn("history lost on edits", md)
        self.assertIn("**Build:**", md)            # stub → build wording
        self.assertIn("model choice", md)          # rubric
        self.assertIn("NOTES.md", md)
        self.assertIn("evaluation/reference/", md)

    def test_evaluation_md_fix_wording(self):
        tf = _taskify(mutations=[{"file": "src/history.py", "kind": "bug", "note": "off-by-one"}])
        md = package.build_evaluation_md(tf, SOURCE, _meta())
        self.assertIn("**Fix:**", md)
        self.assertIn("Planted bugs", md)


class Bundle(unittest.TestCase):
    def _bundle(self, d, taskify=None, meta=None, source=None):
        correct, task = _correct(d), _task(d)
        tf = taskify or _taskify()
        ctx = package.build_context(tf, source or SOURCE, meta or _meta())
        md = package.build_evaluation_md(tf, source or SOURCE, meta or _meta())
        out = os.path.join(d, "bundle.zip")
        return package.write_bundle(task, correct, tf, ctx, md, out), out

    def test_layout_no_node_modules_reference_present(self):
        with tempfile.TemporaryDirectory() as d:
            res, out = self._bundle(d)
            self.assertTrue(res["ok"], res)
            with zipfile.ZipFile(out) as z:
                names = z.namelist()
            self.assertIn("task/src/history.py", names)
            self.assertIn("task/package-lock.json", names)
            self.assertIn("EVALUATION.md", names)
            self.assertIn("context.json", names)
            self.assertIn("evaluation/reference/src/history.py", names)
            self.assertFalse(any("node_modules" in n for n in names))   # vendored deps excluded
            # the reference (the answer) is the solved version, not the stub
            with zipfile.ZipFile(out) as z:
                ref = z.read("evaluation/reference/src/history.py").decode()
                task_src = z.read("task/src/history.py").decode()
            self.assertIn("not e['deleted']", ref)          # solved
            self.assertIn("NotImplementedError", task_src)  # stubbed

    def test_secret_in_prose_blocks_zip(self):
        with tempfile.TemporaryDirectory() as d:
            meta = _meta(assessment={"problem_summary": "leaked AKIA1234567890ABCDEF here",
                                     "test_focus": "x", "skills_assessed": []})
            res, out = self._bundle(d, meta=meta)
            self.assertFalse(res["ok"])
            self.assertFalse(os.path.exists(out))

    def test_email_in_source_redacted_not_blocked(self):
        with tempfile.TemporaryDirectory() as d:
            src = json.loads(json.dumps(SOURCE))
            src["pr"]["description"] = "Co-Authored-By: Someone <real.person@company.com>"
            res, out = self._bundle(d, source=src)
            self.assertTrue(res["ok"], res)
            self.assertGreaterEqual(res["pii_redactions"], 1)
            with zipfile.ZipFile(out) as z:
                ctx = json.loads(z.read("context.json"))
            self.assertNotIn("real.person@company.com", ctx["source"]["pr"]["description"])


if __name__ == "__main__":
    unittest.main()
