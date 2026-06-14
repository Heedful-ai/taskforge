"""Tests for taskify — free-form spec, no hidden/example tests."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import taskify  # noqa: E402


def _correct(d):
    root = os.path.join(d, "correct")
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "src", "history.py"), "w") as fh:
        fh.write("def current_view(entries):\n    return [e for e in entries if not e['deleted']]\n")
    with open(os.path.join(root, "tests", "test_team.py"), "w") as fh:
        fh.write("# team test\n")
    return root


_STUB = {"file": "src/history.py", "find": "    return [e for e in entries if not e['deleted']]",
         "replace": "    raise NotImplementedError  # TODO", "kind": "stub", "note": "build the view"}
_BUG = {"file": "src/history.py", "find": "not e['deleted']", "replace": "e['deleted']", "kind": "bug",
        "note": "inverted filter"}


class BuildTask(unittest.TestCase):
    def test_stub_strips_team_tests_and_records_reference(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {"task_mode": "build (senior)", "mutations": [_STUB], "strip_paths": ["tests/test_team.py"],
                    "human_rubric": [{"dimension": "model", "acceptable_approaches": ["a"], "what_good_looks_like": "x"}]}
            task = os.path.join(d, "task")
            res = taskify.taskify(correct, plan, task)
            self.assertTrue(res["ok"], res.get("error"))
            self.assertEqual(res["task_mode"], "build (senior)")
            with open(os.path.join(task, "src/history.py")) as fh:
                self.assertIn("NotImplementedError", fh.read())
            self.assertFalse(os.path.isfile(os.path.join(task, "tests/test_team.py")))  # no tests for unwritten code
            self.assertEqual(res["reference_files"], ["src/history.py"])
            self.assertEqual(res["mutations"][0]["kind"], "stub")
            self.assertEqual(res["human_rubric"][0]["dimension"], "model")


class FixTask(unittest.TestCase):
    def test_bug_keeps_test_and_adds_ac_fix(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            # a fix task keeps the shipped test (it's the task) — no strip_paths
            res = taskify.taskify(correct, {"mutations": [_BUG]}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertTrue(os.path.isfile(os.path.join(d, "task", "tests/test_team.py")))  # test ships
            self.assertEqual(res["mutations"][0]["kind"], "bug")
            self.assertTrue(any(c["id"] == "AC_FIX" for c in res["acceptance_criteria"]))
            self.assertIn("src/history.py", res["reference_files"])
            self.assertIn("fix", res["task_mode"])


class Guards(unittest.TestCase):
    def test_missing_find_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [{"file": "src/history.py", "find": "ZZZ", "replace": "x"}]},
                                  os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("not present", res["error"])

    def test_nothing_to_do_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"what_to_test": []}, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("produces nothing", res["error"])


class Symlinks(unittest.TestCase):
    def test_vendored_symlinks_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            binp = os.path.join(correct, "node_modules", ".bin")
            os.makedirs(binp)
            os.makedirs(os.path.join(correct, "node_modules", "vitest"))
            with open(os.path.join(correct, "node_modules", "vitest", "cli.js"), "w") as fh:
                fh.write("// cli\n")
            os.symlink("../vitest/cli.js", os.path.join(binp, "vitest"))
            res = taskify.taskify(correct, {"mutations": [_BUG]}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            link = os.path.join(d, "task", "node_modules", ".bin", "vitest")
            self.assertTrue(os.path.islink(link))
            self.assertEqual(os.readlink(link), "../vitest/cli.js")


if __name__ == "__main__":
    unittest.main()
