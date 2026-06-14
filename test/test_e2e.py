"""End-to-end self-test (U8): drive the whole problem-first pipeline on the fixture repo.

Non-container stages always run (carve, scrub, taskify, package, validate_carve). The offline
container validation (hidden-suite green/red + RED-for-right-reason) runs only when Docker +
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
HIDDEN_CMD = "python3 -m unittest discover -s _hidden"


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

# the real solution body that the stub replaces (exact substring of nesting.py)
SOLUTION_BODY = (
    "    depth = 0\n"
    "    best = 0\n"
    "    for ch in s:\n"
    '        if ch == "(":\n'
    "            depth += 1\n"
    "            if depth > best:\n"
    "                best = depth\n"
    '        elif ch == ")":\n'
    "            depth -= 1\n"
    "    return best"
)

EXAMPLE = ("import unittest\nimport report\n\nclass T(unittest.TestCase):\n"
           "    def test_imports(self):\n        self.assertTrue(hasattr(report, 'summary'))\n")
CORE = ("import unittest\nfrom nesting import max_depth\n\nclass T(unittest.TestCase):\n"
        "    def test_depths(self):\n"
        "        self.assertEqual(max_depth('(())'), 2)\n"
        "        self.assertEqual(max_depth('()()'), 1)\n"
        "        self.assertEqual(max_depth(''), 0)\n")
STRETCH = ("import unittest\nfrom nesting import max_depth\n\nclass T(unittest.TestCase):\n"
           "    def test_deep(self):\n        self.assertEqual(max_depth('((((()))))'), 5)\n")

# problem-first task: gut the solution to a stub the candidate builds; ship a mechanics example test;
# withhold a tiered hidden behaviour suite.
TASK_PLAN = {
    "task_mode": "design (senior): build the depth model + a deep-nesting stretch",
    "mutations": [{"file": "nesting.py", "find": SOLUTION_BODY,
                   "replace": "    raise NotImplementedError  # TODO: compute the max nesting depth",
                   "kind": "stub", "note": "candidate builds the depth computation"}],
    "strip_paths": ["tests/test_nesting.py"],
    "example_tests": [{"path": "tests/test_example.py", "content": EXAMPLE}],
    "hidden_tests": {"core": [{"path": "test_core.py", "content": CORE}],
                     "stretch": [{"path": "test_stretch.py", "content": STRETCH}]},
    "human_rubric": [{"dimension": "approach", "acceptable_approaches": ["counter", "stack"],
                      "what_good_looks_like": "handles unbalanced input gracefully"}],
    "what_to_test": ["correct max depth", "handles flat/empty"],
    "vendored_paths": [],
}

META = {
    "task_id": "nesting-001", "language": "python", "build_command": None, "test_command": TEST_CMD,
    "hidden_test_command": HIDDEN_CMD,
    "created_by": {"operator": "Oskar", "email": None, "gh_login": "oz"},
    "hiring": {"position": "Senior Backend Engineer", "seniority": "senior", "job_description": "", "time_target_hours": 1.5},
    "assessment": {"problem_summary": "compute nesting depth", "test_focus": "depth correctness", "skills_assessed": ["parsing"]},
    "pr_suitability": {"verdict": "recommend", "reasons": ["multiple approaches: counter vs stack"]},
    "skill_version": "0.2.0", "spec_version": "agentskills.io", "created_at": "2026-06-14T12:00:00Z",
    "reference_summary": "a depth counter", "notes_for_evaluator": "",
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

    def test_full_problem_first_pipeline(self):
        # 1. carve plan gate
        gate = validate_carve.validate(self.repo, CARVE_PLAN)
        self.assertTrue(gate["ok"], gate["reasons"])

        # 2. carve -> correct/ (the solution world)
        cv = carve.carve(self.repo, CARVE_PLAN, self.correct)
        self.assertTrue(cv["ok"], cv)
        self.assertTrue(os.path.isfile(os.path.join(self.correct, "nesting.py")))

        # 3. scrub the slice -> clean
        findings, _ = scrub.scan_paths(self.correct)
        self.assertEqual(findings, [])

        # 4. taskify -> task/ (problem world) + sibling hidden/
        tf = taskify.taskify(self.correct, TASK_PLAN, self.task)
        self.assertTrue(tf["ok"], tf.get("error"))
        with open(os.path.join(self.task, "nesting.py")) as fh:
            self.assertIn("NotImplementedError", fh.read())
        self.assertFalse(os.path.isfile(os.path.join(self.task, "tests", "test_nesting.py")))   # team test stripped
        self.assertTrue(os.path.isfile(os.path.join(self.task, "tests", "test_example.py")))    # example shipped
        hidden = tf["hidden_tests_dir"]
        self.assertTrue(os.path.isfile(os.path.join(hidden, "core", "test_core.py")))           # hidden withheld
        self.assertFalse(hidden.startswith(os.path.abspath(self.task) + os.sep))
        self.assertIn("return best", tf["reference_exemplar"])   # exemplar restores the real solution

        # 5. offline validation (container) — correct green, task builds, core RED-by-assertion on task
        validate_report = None
        if DOCKER:
            validate_report = validate.validate(TEST_CMD, None, self.correct, self.task, "python:3.11-slim",
                                                "docker", hidden_dir=hidden, hidden_test_cmd=HIDDEN_CMD)
            self.assertTrue(validate_report["ok"], validate_report.get("reasons"))
            self.assertTrue(validate_report["correct_passed"])
            self.assertTrue(validate_report["task_builds"])       # cross-file stub keeps it building
            self.assertTrue(validate_report["correct_core_passed"])
            self.assertTrue(validate_report["task_core_failed"])

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
            self.assertIn("task/tests/test_example.py", names)                       # example shipped
            self.assertFalse(any("test_core" in n and n.startswith("task/") for n in names))  # hidden NOT shipped
            self.assertTrue(any(n.startswith("task/nesting.py") for n in names))
            card = json.loads(z.read("scorecard.json"))
            man_loaded = json.loads(z.read("manifest.json"))
        self.assertEqual(card["schema_version"], "2")
        self.assertNotIn("task_mode", man_loaded)                                    # receiver can't branch on it
        self.assertIn("test_core.py", [t["path"] for t in card["behavior_suite"]["core"]])
        self.assertIn("return best", card["reference_exemplar"]["diff"])
        self.assertEqual(card["pr_suitability"]["verdict"], "recommend")
        self.assertEqual(card["source"]["pr"]["number"], 5)

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
        big = dict(CARVE_PLAN, files=[f"f{i}.py" for i in range(validate_carve.MAX_FILES + 1)])
        for f in big["files"]:
            p = os.path.join(self.repo, f)
            os.makedirs(os.path.dirname(p), exist_ok=True) if os.path.dirname(f) else None
            open(p, "w").close()
        gate = validate_carve.validate(self.repo, big)
        self.assertFalse(gate["ok"])


if __name__ == "__main__":
    unittest.main()
