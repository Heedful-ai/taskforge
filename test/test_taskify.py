"""Tests for taskify (U4) — free-form problem-first task spec (no mode enum)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import taskify  # noqa: E402


def _correct(d):
    """A tiny working project under <d>/correct with a solution body and a team test."""
    root = os.path.join(d, "correct")
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "tests"))
    with open(os.path.join(root, "src", "history.py"), "w") as fh:
        fh.write("def current_view(entries):\n    return [e for e in entries if not e['deleted']]\n")
    with open(os.path.join(root, "tests", "test_team.py"), "w") as fh:
        fh.write("# the team's own tests — would spoil if shipped\n")
    return root


_STUB = {"file": "src/history.py", "find": "    return [e for e in entries if not e['deleted']]",
         "replace": "    raise NotImplementedError  # TODO: build the history model", "kind": "stub",
         "note": "candidate builds the current view"}
_BUG = {"file": "src/history.py", "find": "not e['deleted']", "replace": "e['deleted']", "kind": "bug",
        "note": "inverted filter"}
_EXAMPLE = {"path": "tests/example_test.py", "content": "# mechanics only: shows how to run\n"}
_HIDDEN_CORE = {"path": "test_core.py", "content": "# core invariant: current view excludes deleted\n"}
_HIDDEN_STRETCH = {"path": "test_scale.py", "content": "# stretch: concurrency\n"}


class FreeFormSpec(unittest.TestCase):
    def test_combined_stub_bug_example_hidden(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            plan = {
                "task_mode": "design+fix+extend (senior)",
                "mutations": [_STUB],
                "strip_paths": ["tests/test_team.py"],
                "example_tests": [_EXAMPLE],
                "hidden_tests": {"core": [_HIDDEN_CORE], "stretch": [_HIDDEN_STRETCH]},
                "extension": {"description": "support reverting to version N", "acceptance_criteria": []},
                "human_rubric": [{"dimension": "model choice", "acceptable_approaches": ["append-only", "snapshots"],
                                  "what_good_looks_like": "justified trade-off"}],
            }
            task = os.path.join(d, "task")
            res = taskify.taskify(correct, plan, task)
            self.assertTrue(res["ok"], res.get("error"))
            # descriptive task_mode, not an enum
            self.assertEqual(res["task_mode"], "design+fix+extend (senior)")
            # example test shipped under task/
            self.assertTrue(os.path.isfile(os.path.join(task, "tests", "example_test.py")))
            # team test stripped from task/
            self.assertFalse(os.path.isfile(os.path.join(task, "tests", "test_team.py")))
            # hidden suite is a SIBLING, tiered, and absent from task/
            hidden = res["hidden_tests_dir"]
            self.assertTrue(os.path.isfile(os.path.join(hidden, "core", "test_core.py")))
            self.assertTrue(os.path.isfile(os.path.join(hidden, "stretch", "test_scale.py")))
            self.assertFalse(hidden.startswith(os.path.abspath(task) + os.sep))
            self.assertEqual(res["hidden_tiers"]["core"], ["test_core.py"])
            self.assertEqual(res["human_rubric"][0]["dimension"], "model choice")
            # reference exemplar restores the gutted region
            self.assertIn("not e['deleted']", res["reference_exemplar"])

    def test_stub_exemplar_restores_correct(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [_STUB]}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            # the exemplar diff (task -> correct) carries the real solution body
            self.assertIn("return [e for e in entries if not e['deleted']]", res["reference_exemplar"])
            self.assertIn("NotImplementedError", res["reference_exemplar"])  # the stub it replaces

    def test_descriptive_mode_derived_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [_STUB], "extension": {"description": "x"}},
                                  os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertIn("build", res["task_mode"])
            self.assertIn("extend", res["task_mode"])


class Symlinks(unittest.TestCase):
    def test_vendored_symlinks_preserved_in_task(self):
        # node_modules/.bin/* are relative symlinks; copytree must preserve them (symlinks=True) or
        # self-resolving CLIs like vitest break in task/. Proven without Docker via islink.
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            binp = os.path.join(correct, "node_modules", ".bin")
            os.makedirs(binp)
            os.makedirs(os.path.join(correct, "node_modules", "vitest"))
            with open(os.path.join(correct, "node_modules", "vitest", "cli.js"), "w") as fh:
                fh.write("// cli\n")
            os.symlink("../vitest/cli.js", os.path.join(binp, "vitest"))  # relative, like npm
            res = taskify.taskify(correct, {"mutations": [_BUG]}, os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            link = os.path.join(d, "task", "node_modules", ".bin", "vitest")
            self.assertTrue(os.path.islink(link), "vendored symlink was dereferenced (vitest would break)")
            self.assertEqual(os.readlink(link), "../vitest/cli.js")


class Guards(unittest.TestCase):
    def test_missing_find_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"mutations": [{"file": "src/history.py", "find": "ZZZ", "replace": "x"}]},
                                  os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("not present", res["error"])

    def test_hidden_under_task_refused(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            # a hidden path that tries to escape into task/ via traversal
            plan = {"mutations": [_BUG], "hidden_tests": {"core": [{"path": "../task/sneaky.py", "content": "x"}]}}
            res = taskify.taskify(correct, plan, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("task/", res["error"])

    def test_nothing_to_do_fails(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            res = taskify.taskify(correct, {"what_to_test": []}, os.path.join(d, "task"))
            self.assertFalse(res["ok"])
            self.assertIn("produces nothing", res["error"])


class Exemplar(unittest.TestCase):
    def test_exemplar_only_covers_mutated_files_not_vendored(self):
        with tempfile.TemporaryDirectory() as d:
            correct = _correct(d)
            os.makedirs(os.path.join(correct, "node_modules", "p"))
            with open(os.path.join(correct, "node_modules", "p", "x.js"), "w") as fh:
                fh.write("module.exports = 1\n")
            res = taskify.taskify(correct, {"mutations": [_BUG], "vendored_paths": ["node_modules"]},
                                  os.path.join(d, "task"))
            self.assertTrue(res["ok"], res.get("error"))
            self.assertNotIn("node_modules", res["reference_exemplar"])
            self.assertIn("src/history.py", res["reference_exemplar"])


if __name__ == "__main__":
    unittest.main()
