"""Tests for offline validation (U6). The real-container checks skip when Docker is unavailable."""
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
        subprocess.run(["docker", "image", "inspect", "python:3.11-slim"],
                       capture_output=True, check=True, timeout=15)
        return True
    except Exception:
        return False


DOCKER = _docker_ready()


def _project(root: str, op: str) -> None:
    """A zero-dependency stdlib-unittest project where add() uses operator `op`."""
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "src", "sum.py"), "w") as fh:
        fh.write(f"def add(a, b):\n    return a {op} b\n")
    with open(os.path.join(root, "tests", "test_sum.py"), "w") as fh:
        fh.write(
            "import sys, os\n"
            "sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))\n"
            "import unittest\n"
            "from sum import add\n"
            "class T(unittest.TestCase):\n"
            "    def test_add(self):\n"
            "        self.assertEqual(add(1, 2), 3)\n"
        )


class PureCommandBuild(unittest.TestCase):
    def test_network_none_in_argv(self):
        argv = validate.build_container_cmd("docker", "python:3.11-slim", "/abs/dir", "echo hi")
        self.assertIn("--network=none", argv)
        self.assertIn("/abs/dir:/work", argv)
        self.assertEqual(argv[:3], ["docker", "run", "--rm"])
        self.assertEqual(argv[-4:], ["python:3.11-slim", "sh", "-c", "echo hi"])


class FailClosed(unittest.TestCase):
    def test_no_runtime_fails_closed(self):
        rep = validate.validate("break_code", TEST_CMD, None, "correct", "task", "python:3.11-slim", None)
        self.assertFalse(rep["ok"])
        self.assertTrue(rep["fail_closed"])


@unittest.skipUnless(DOCKER, "docker + python:3.11-slim not available")
class RealOffline(unittest.TestCase):
    def test_break_code_correct_green_task_red(self):
        with tempfile.TemporaryDirectory() as d:
            _project(os.path.join(d, "correct"), "+")  # correct
            _project(os.path.join(d, "task"), "-")     # broken
            rep = validate.validate("break_code", TEST_CMD, None,
                                    os.path.join(d, "correct"), os.path.join(d, "task"),
                                    "python:3.11-slim", "docker")
            self.assertTrue(rep["ok"], rep["reasons"])
            self.assertTrue(rep["correct_passed"])
            self.assertFalse(rep["task_passed"])
            self.assertEqual(rep["expected_initial_state"]["tests"], "red")

    def test_break_code_rejected_when_task_still_green(self):
        with tempfile.TemporaryDirectory() as d:
            _project(os.path.join(d, "correct"), "+")
            _project(os.path.join(d, "task"), "+")  # not actually broken
            rep = validate.validate("break_code", TEST_CMD, None,
                                    os.path.join(d, "correct"), os.path.join(d, "task"),
                                    "python:3.11-slim", "docker")
            self.assertFalse(rep["ok"])
            self.assertTrue(any("GREEN" in r for r in rep["reasons"]))

    def test_extend_requires_task_green(self):
        with tempfile.TemporaryDirectory() as d:
            _project(os.path.join(d, "correct"), "+")
            _project(os.path.join(d, "task"), "+")  # still works
            rep = validate.validate("extend_functionality", TEST_CMD, None,
                                    os.path.join(d, "correct"), os.path.join(d, "task"),
                                    "python:3.11-slim", "docker")
            self.assertTrue(rep["ok"], rep["reasons"])
            self.assertEqual(rep["expected_initial_state"]["tests"], "green")


if __name__ == "__main__":
    unittest.main()
