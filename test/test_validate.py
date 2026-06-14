"""Tests for validate (U5) — hidden-suite solvability, offline, with the RED-for-right-reason gate."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import validate  # noqa: E402


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
TEST_CMD = "python3 -m unittest discover -s tests -p '*_test.py'"
HIDDEN_CMD = "python3 -m unittest discover -s _hidden -p '*_test.py'"

# mechanics-only example test: imports the module, never asserts the invariant → green even when stubbed
EXAMPLE = ("import history\nimport unittest\n\nclass T(unittest.TestCase):\n"
           "    def test_imports(self):\n        self.assertTrue(hasattr(history, 'current_view'))\n")
# hidden core: asserts the behaviour → green on correct, red on the stub
CORE = ("from history import current_view\nimport unittest\n\nclass T(unittest.TestCase):\n"
        "    def test_excludes_deleted(self):\n"
        "        self.assertEqual(current_view([{'id':1,'deleted':False},{'id':2,'deleted':True}]),"
        " [{'id':1,'deleted':False}])\n")
SOLUTION = "def current_view(entries):\n    return [e for e in entries if not e['deleted']]\n"
STUB = "def current_view(entries):\n    raise NotImplementedError  # TODO\n"
BROKEN = "import nonexistent_module_zzz\n\ndef current_view(entries):\n    return []\n"


def _proj(root, history_src):
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "history.py"), "w") as fh:
        fh.write(history_src)
    with open(os.path.join(root, "tests", "example_test.py"), "w") as fh:
        fh.write(EXAMPLE)


def _hidden(root, core_src=CORE):
    os.makedirs(os.path.join(root, "core"))
    os.makedirs(os.path.join(root, "stretch"))
    with open(os.path.join(root, "core", "core_test.py"), "w") as fh:
        fh.write(core_src)


class PureCommandBuild(unittest.TestCase):
    def test_network_none_argv(self):
        argv = validate.build_container_cmd("docker", "python:3.11-slim", "/abs/x", "echo hi")
        self.assertIn("--network=none", argv)
        self.assertEqual(argv[:3], ["docker", "run", "--rm"])
        self.assertIn("/abs/x:/work", argv)
        self.assertEqual(argv[-4:], ["python:3.11-slim", "sh", "-c", "echo hi"])


class FailClosed(unittest.TestCase):
    def test_no_runtime_fails_closed(self):
        r = validate.validate(TEST_CMD, None, "correct", "task", "python:3.11-slim", runtime=None)
        self.assertTrue(r["fail_closed"])
        self.assertFalse(r["ok"])


@unittest.skipUnless(DOCKER, "docker + python:3.11-slim required")
class RealOffline(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def _run(self, task_history, core_src=CORE):
        correct = os.path.join(self.d, "correct")
        task = os.path.join(self.d, "task")
        hid = os.path.join(self.d, "hidden")
        _proj(correct, SOLUTION)
        _proj(task, task_history)
        _hidden(hid, core_src)
        return validate.validate(TEST_CMD, None, correct, task, "python:3.11-slim", "docker",
                                 hidden_dir=hid, hidden_test_cmd=HIDDEN_CMD)

    def test_solvable_task_passes(self):
        r = self._run(STUB)
        self.assertTrue(r["ok"], r["reasons"])
        self.assertTrue(r["correct_passed"])
        self.assertTrue(r["task_builds"])
        self.assertTrue(r["correct_core_passed"])
        self.assertTrue(r["task_core_failed"])
        self.assertEqual(r["expected_initial_state"]["tests"], "red")

    def test_non_trivial_guard_solution_not_stubbed(self):
        # task still has the real solution → hidden core PASSES on task → reject
        r = self._run(SOLUTION)
        self.assertFalse(r["ok"])
        self.assertFalse(r["task_core_failed"])
        self.assertTrue(any("isn't actually unsolved" in x for x in r["reasons"]))

    def test_solvability_guard_correct_fails_own_suite(self):
        bad_core = ("from history import current_view\nimport unittest\n\nclass T(unittest.TestCase):\n"
                    "    def test_impossible(self):\n        self.assertEqual(current_view([]), ['nope'])\n")
        r = self._run(STUB, core_src=bad_core)
        self.assertFalse(r["ok"])
        self.assertFalse(r["correct_core_passed"])
        self.assertTrue(any("doesn't satisfy its own behaviour suite" in x for x in r["reasons"]))

    def test_red_for_right_reason_broken_stub_rejected(self):
        # the stub breaks import → example tests fail → task_builds False → reject (not a forged RED)
        r = self._run(BROKEN)
        self.assertFalse(r["ok"])
        self.assertFalse(r["task_builds"])
        self.assertTrue(any("stub broke the build" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main()
