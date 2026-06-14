"""Tests for validate — correct green + task red(fix)/green(build), offline. No hidden suite."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import validate  # noqa: E402

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


def _project(root, body):
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "src", "sum.py"), "w") as fh:
        fh.write(body)
    with open(os.path.join(root, "tests", "test_sum.py"), "w") as fh:
        fh.write("import sys, os\nsys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))\n"
                 "import unittest\nfrom sum import add\n"
                 "class T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(1, 2), 3)\n")


GOOD = "def add(a, b):\n    return a + b\n"
BUG = "def add(a, b):\n    return a - b\n"
BROKEN = "def add(a, b)\n    return a + b\n"  # syntax error


class PureCommandBuild(unittest.TestCase):
    def test_network_none_argv(self):
        argv = validate.build_container_cmd("docker", "python:3.11-slim", "/abs/x", "echo hi")
        self.assertIn("--network=none", argv)
        self.assertEqual(argv[:3], ["docker", "run", "--rm"])
        self.assertIn("/abs/x:/work", argv)


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

    def _run(self, task_body, task_red):
        correct = os.path.join(self.d, "correct")
        task = os.path.join(self.d, "task")
        _project(correct, GOOD)
        _project(task, task_body)
        return validate.validate(TEST_CMD, None, correct, task, "python:3.11-slim", "docker", task_red=task_red)

    def test_fix_task_bug_makes_red(self):
        r = self._run(BUG, task_red=True)
        self.assertTrue(r["ok"], r["reasons"])
        self.assertTrue(r["correct_passed"])
        self.assertFalse(r["task_passed"])
        self.assertEqual(r["expected_initial_state"]["tests"], "red")

    def test_fix_task_rejected_when_task_still_green(self):
        r = self._run(GOOD, task_red=True)  # no real bug
        self.assertFalse(r["ok"])
        self.assertTrue(any("GREEN" in x for x in r["reasons"]))

    def test_build_task_must_stay_green(self):
        r = self._run(GOOD, task_red=False)  # stub project still builds/runs
        self.assertTrue(r["ok"], r["reasons"])
        self.assertEqual(r["expected_initial_state"]["tests"], "green")

    def test_build_task_rejected_when_broken(self):
        r = self._run(BROKEN, task_red=False)  # stub broke the project
        self.assertFalse(r["ok"])
        self.assertTrue(any("stub broke" in x for x in r["reasons"]))


if __name__ == "__main__":
    unittest.main()
