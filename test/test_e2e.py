"""End-to-end self-test (U8): drive the whole deterministic pipeline on the fixture repo.

Non-container stages always run (carve, scrub, taskify, package, validate_carve). The offline
container validation runs only when Docker + python:3.11-slim are available.
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
    "files": ["src/nesting.py", "tests/test_nesting.py", "pyproject.toml"],
    "entrypoint": "src/nesting.py",
    "build_command": None,
    "test_command": TEST_CMD,
    "vendor_commands": [],
    "vendored_paths": [],
    "source": {
        "repo": "demo/nesting",
        "pr": {"number": 7, "title": "fix nesting depth", "description": "the team's real fix", "url": "u", "diff": "diff"},
        "issue": {"number": 5, "title": "wrong nesting depth", "body": "max_depth is off", "url": "u"},
    },
}

TASK_PLAN = {
    "mode": "break_code",
    "mutations": [{"file": "src/nesting.py", "find": "depth += 1", "replace": "depth -= 1", "note": "inverted increment"}],
    "acceptance_criteria": [{"id": "AC1", "description": "all tests pass", "check": "test_command", "weight": 1}],
    "what_to_test": ["restores correct nesting depth", "keeps flat/empty cases"],
    "vendored_paths": [],
}

META = {
    "task_id": "nesting-001", "language": "python", "build_command": None, "test_command": TEST_CMD,
    "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
    "skill_version": "0.1.0", "spec_version": "agentskills.io", "created_at": "2026-06-13T12:00:00Z",
    "reference_summary": "restore the depth increment", "notes_for_evaluator": "",
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

    def test_full_pipeline_break_code(self):
        # 1. carve plan gate
        gate = validate_carve.validate(self.repo, CARVE_PLAN)
        self.assertTrue(gate["ok"], gate["reasons"])

        # 2. carve -> correct/
        cv = carve.carve(self.repo, CARVE_PLAN, self.correct)
        self.assertTrue(cv["ok"], cv)
        self.assertTrue(os.path.isfile(os.path.join(self.correct, "src/nesting.py")))

        # 3. scrub the slice -> clean
        findings, _ = scrub.scan_paths(self.correct)
        self.assertEqual(findings, [])

        # 4. taskify (break_code) -> task/
        tf = taskify.taskify(self.correct, TASK_PLAN, self.task)
        self.assertTrue(tf["ok"], tf.get("error"))
        self.assertIn("depth -= 1", open(os.path.join(self.task, "src/nesting.py")).read())
        self.assertIn("depth += 1", tf["reference_diff"])  # the fix the candidate should reach

        # 5. offline validation (container) — correct green, task red
        validate_report = None
        if DOCKER:
            validate_report = validate.validate("break_code", TEST_CMD, None, self.correct, self.task,
                                                "python:3.11-slim", "docker")
            self.assertTrue(validate_report["ok"], validate_report.get("reasons"))
            self.assertTrue(validate_report["correct_passed"])
            self.assertFalse(validate_report["task_passed"])

        # 6. package -> bundle.zip
        sc = package.assemble_scorecard(tf, CARVE_PLAN["source"], validate_report, META)
        man = package.build_manifest(sc, self.task)
        out = os.path.join(self.d, "task-bundle.zip")
        res = package.write_bundle(self.task, sc, man, out)
        self.assertTrue(res["ok"], res)

        # 7. assert the bundle contract
        with zipfile.ZipFile(out) as z:
            names = z.namelist()
            self.assertIn("scorecard.json", names)
            self.assertIn("manifest.json", names)
            # note: BRIEF.md is authored by the agent in Phase 6, not by the scripts, so it's absent here
            self.assertTrue(any(n.startswith("task/src/nesting.py") for n in names))
            self.assertFalse(any("scorecard" in n and n.startswith("task/") for n in names))
            card = json.loads(z.read("scorecard.json"))
        self.assertEqual(card["task_mode"], "break_code")
        self.assertEqual(card["source"]["pr"]["number"], 7)
        self.assertEqual(card["created_by"]["operator"], "Oskar")
        self.assertIn("depth += 1", card["reference_solution"]["diff"])

    def test_planted_secret_blocks_bundle(self):
        carve.carve(self.repo, CARVE_PLAN, self.correct)
        tf = taskify.taskify(self.correct, TASK_PLAN, self.task)
        bad_source = json.loads(json.dumps(CARVE_PLAN["source"]))
        bad_source["issue"]["body"] = "see token ghp_" + "a" * 36
        sc = package.assemble_scorecard(tf, bad_source, None, META)
        man = package.build_manifest(sc, self.task)
        out = os.path.join(self.d, "bundle.zip")
        res = package.write_bundle(self.task, sc, man, out)
        self.assertFalse(res["ok"])
        self.assertFalse(os.path.exists(out))

    def test_over_cap_carve_rejected(self):
        big = dict(CARVE_PLAN, files=[f"src/f{i}.py" for i in range(validate_carve.MAX_FILES + 1)])
        for f in big["files"]:
            p = os.path.join(self.repo, f)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, "w").close()
        gate = validate_carve.validate(self.repo, big)
        self.assertFalse(gate["ok"])


if __name__ == "__main__":
    unittest.main()
