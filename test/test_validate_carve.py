"""Tests for the carve-plan gate (U4)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import validate_carve  # noqa: E402
import carve  # noqa: E402


class _Repo:
    def __init__(self, d):
        self.d = d

    def write(self, rel, content="x\n"):
        p = os.path.join(self.d, rel)
        os.makedirs(os.path.dirname(p) or self.d, exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(content)


def _plan(**kw):
    base = {"language": "python", "files": ["src/a.py"], "test_command": "python3 -m unittest"}
    base.update(kw)
    return base


class ValidateCarve(unittest.TestCase):
    def test_accepts_in_caps_plan(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("src/a.py")
            r.write("tests/test_a.py")
            res = validate_carve.validate(d, _plan(files=["src/a.py", "tests/test_a.py"]))
            self.assertTrue(res["ok"], res["reasons"])

    def test_rejects_missing_file(self):
        with tempfile.TemporaryDirectory() as d:
            res = validate_carve.validate(d, _plan(files=["src/ghost.py"]))
            self.assertFalse(res["ok"])
            self.assertTrue(any("do not exist" in r for r in res["reasons"]))

    def test_rejects_over_file_count(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            files = [f"src/f{i}.py" for i in range(validate_carve.MAX_FILES + 1)]
            for f in files:
                r.write(f)
            res = validate_carve.validate(d, _plan(files=files))
            self.assertFalse(res["ok"])
            self.assertTrue(any("too many files" in r for r in res["reasons"]))

    def test_rejects_over_loc(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("src/big.py", "x\n" * (validate_carve.MAX_LOC + 1))
            res = validate_carve.validate(d, _plan(files=["src/big.py"]))
            self.assertFalse(res["ok"])
            self.assertTrue(any("too large" in r for r in res["reasons"]))

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as d:
            res = validate_carve.validate(d, _plan(files=["../../etc/passwd"]))
            self.assertFalse(res["ok"])
            self.assertTrue(any("escape" in r for r in res["reasons"]))

    def test_rejects_dependency_dir(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("node_modules/pkg/index.js")
            res = validate_carve.validate(d, _plan(files=["node_modules/pkg/index.js"]))
            self.assertFalse(res["ok"])
            self.assertTrue(any("dependency/build" in r for r in res["reasons"]))

    def test_requires_test_command(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("src/a.py")
            res = validate_carve.validate(d, _plan(test_command=""))
            self.assertFalse(res["ok"])


class Carve(unittest.TestCase):
    def test_copies_slice_and_writes_source_context(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("src/a.py", "def a():\n    return 1\n")
            out = os.path.join(d, "out", "correct")
            plan = _plan(files=["src/a.py"], source={"repo": "o/n", "issue": {"number": 5}})
            res = carve.carve(d, plan, out)
            self.assertTrue(res["ok"])
            self.assertTrue(os.path.isfile(os.path.join(out, "src/a.py")))
            self.assertFalse(os.path.exists(os.path.join(out, ".git")))
            self.assertTrue(os.path.isfile(res["source_context"]))

    def test_vendor_command_failure_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            r = _Repo(d)
            r.write("src/a.py")
            out = os.path.join(d, "out", "correct")
            plan = _plan(files=["src/a.py"], vendor_commands=["exit 7"])
            res = carve.carve(d, plan, out)
            self.assertFalse(res["ok"])
            self.assertIn("vendor command failed", res["error"])


if __name__ == "__main__":
    unittest.main()
