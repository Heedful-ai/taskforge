"""End-to-end self-test: carve -> scrub -> taskify -> validate -> package, on the fixture repo.

Non-container stages always run. The offline container validation runs only when Docker +
python:3.11-slim are available.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "skills", "taskforge", "scripts"))
import carve  # noqa: E402
import scrub  # noqa: E402
import taskify  # noqa: E402
import validate  # noqa: E402
import package  # noqa: E402
import validate_carve  # noqa: E402

FIXTURE = os.path.join(HERE, "..", "fixtures", "sample-repo")
TEST_CMD = "python3 -m unittest discover -s tests"


def _docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=15)
        subprocess.run(["docker", "image", "inspect", "python:3.11-slim"], capture_output=True, check=True, timeout=15)
        return True
    except Exception:
        return False


DOCKER = _docker_ready()

CARVE_PLAN = {
    "language": "python",
    "files": ["nesting.py", "report.py", "tests/test_nesting.py", "pyproject.toml"],
    "entrypoint": "nesting.py",
    "build_command": None,
    "test_command": TEST_CMD,
    "vendor_commands": [],
    "vendored_paths": [],
    "source": {
        "repo": "demo/nesting",
        "pr": {"number": 5, "title": "nesting depth model", "description": "the team's real solution", "url": "u", "diff": "d"},
        "issue": {"number": 3, "title": "need nesting depth", "body": "compute max nesting depth", "url": "u"},
    },
}

SOLUTION_BODY = (
    "    depth = 0\n    best = 0\n    for ch in s:\n"
    '        if ch == "(":\n            depth += 1\n            if depth > best:\n                best = depth\n'
    '        elif ch == ")":\n            depth -= 1\n    return best'
)

# build task: gut the solution to a stub the candidate builds; strip the team's tests (no tests for
# code that isn't written yet).
TASK_PLAN = {
    "task_mode": "build (senior): design the depth model",
    "mutations": [{"file": "nesting.py", "find": SOLUTION_BODY,
                   "replace": "    raise NotImplementedError  # TODO: compute the max nesting depth",
                   "kind": "stub", "note": "candidate builds the depth computation"}],
    "strip_paths": ["tests/test_nesting.py"],
    "reference_summary": "a single-pass depth counter",
    "human_rubric": [{"dimension": "approach", "acceptable_approaches": ["counter", "stack"],
                      "what_good_looks_like": "handles unbalanced input"}],
    "notes_evaluation": {"what_to_look_for": "alternatives considered"},
    "what_to_test": ["correct max depth"],
}

META = {
    "task_id": "nesting-001", "language": "python", "build_command": None, "test_command": TEST_CMD,
    "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
    "summary": "make nesting-depth computation a design task",
    "hiring": {"position": "Senior Backend Engineer", "seniority": "senior", "job_description": "", "time_target_hours": 1.5},
    "assessment": {"problem_summary": "compute nesting depth", "test_focus": "depth correctness", "skills_assessed": ["parsing"]},
    "pr_suitability": {"verdict": "recommend", "reasons": ["counter vs stack"]},
    "skill_version": "0.3.0", "spec_version": "agentskills.io", "created_at": "2026-06-14T12:00:00Z",
}


class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()
        self.repo = os.path.join(self.d, "repo")
        shutil.copytree(FIXTURE, self.repo)
        self.correct = os.path.join(self.d, "correct")
        self.task = os.path.join(self.d, "task")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_full_pipeline(self):
        gate = validate_carve.validate(self.repo, CARVE_PLAN)
        self.assertTrue(gate["ok"], gate["reasons"])

        cv = carve.carve(self.repo, CARVE_PLAN, self.correct)
        self.assertTrue(cv["ok"], cv)

        findings, _ = scrub.scan_paths(self.correct)
        self.assertEqual(findings, [])

        tf = taskify.taskify(self.correct, TASK_PLAN, self.task)
        self.assertTrue(tf["ok"], tf.get("error"))
        with open(os.path.join(self.task, "nesting.py")) as fh:
            self.assertIn("NotImplementedError", fh.read())
        self.assertFalse(os.path.isfile(os.path.join(self.task, "tests", "test_nesting.py")))  # tests stripped
        self.assertEqual(tf["reference_files"], ["nesting.py"])

        if DOCKER:
            vr = validate.validate(TEST_CMD, None, self.correct, self.task, "python:3.11-slim", "docker", task_red=False)
            self.assertTrue(vr["ok"], vr.get("reasons"))
            self.assertTrue(vr["correct_passed"])
            self.assertTrue(vr["task_passed"])  # stub still builds/runs (no tests to fail)

        ctx = package.build_context(tf, CARVE_PLAN["source"], META)
        md = package.build_evaluation_md(tf, CARVE_PLAN["source"], META)
        out = os.path.join(self.d, "task-bundle.zip")
        res = package.write_bundle(self.task, self.correct, tf, ctx, md, out)
        self.assertTrue(res["ok"], res)

        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            self.assertIn("task/nesting.py", names)
            self.assertIn("EVALUATION.md", names)
            self.assertIn("context.json", names)
            self.assertIn("evaluation/reference/nesting.py", names)
            self.assertFalse(any("node_modules" in n for n in names))
            ref = z.read("evaluation/reference/nesting.py").decode()
            ctx_loaded = json.loads(z.read("context.json"))
            evalmd = z.read("EVALUATION.md").decode()
        self.assertIn("return best", ref)               # reference is the solved version
        self.assertEqual(ctx_loaded["source"]["pr"]["number"], 5)
        self.assertEqual(ctx_loaded["pr_suitability"]["verdict"], "recommend")
        self.assertIn("**Build:**", evalmd)

    def test_planted_secret_blocks_bundle(self):
        carve.carve(self.repo, CARVE_PLAN, self.correct)
        tf = taskify.taskify(self.correct, TASK_PLAN, self.task)
        bad_source = json.loads(json.dumps(CARVE_PLAN["source"]))
        bad_source["issue"]["body"] = "see token ghp_" + "a" * 36
        ctx = package.build_context(tf, bad_source, META)
        md = package.build_evaluation_md(tf, bad_source, META)
        out = os.path.join(self.d, "bundle.zip")
        res = package.write_bundle(self.task, self.correct, tf, ctx, md, out)
        self.assertFalse(res["ok"])
        self.assertFalse(os.path.exists(out))

    def test_over_cap_carve_rejected(self):
        big = dict(CARVE_PLAN, files=[f"f{i}.py" for i in range(validate_carve.MAX_FILES + 1)])
        for f in big["files"]:
            open(os.path.join(self.repo, f), "w").close()
        gate = validate_carve.validate(self.repo, big)
        self.assertFalse(gate["ok"])


if __name__ == "__main__":
    unittest.main()
