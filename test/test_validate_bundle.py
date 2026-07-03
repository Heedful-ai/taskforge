"""Tests for validate_bundle — frontend fields (dev_command/preview_port) + the basePath invariant."""
import json
import os
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import validate_bundle  # noqa: E402

NEXT_CONFIG = """import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  basePath: process.env.HEEDFUL_BASE_PATH ?? "/absproxy/3000",
  allowedDevOrigins: [process.env.HEEDFUL_PREVIEW_HOST ?? "localhost"],
};

export default nextConfig;
"""


def _context(**kw):
    base = {"task_id": "t-1", "language": "node", "test_command": "npm test",
            "build_command": None, "install_command": "npm ci", "task_mode": "build (senior)"}
    base.update(kw)
    return base


def _bundle(d, context, next_config=NEXT_CONFIG):
    os.makedirs(os.path.join(d, "task"), exist_ok=True)
    with open(os.path.join(d, "context.json"), "w") as fh:
        json.dump(context, fh)
    with open(os.path.join(d, "task", "BRIEF.md"), "w") as fh:
        fh.write("# Task\n")
    if next_config is not None:
        with open(os.path.join(d, "task", "next.config.ts"), "w") as fh:
            fh.write(next_config)
    return d


class BackendBundles(unittest.TestCase):
    def test_field_less_backend_bundle_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            r = validate_bundle.validate(_bundle(d, _context(), next_config=None))
        self.assertTrue(r["ok"], r)
        self.assertFalse(r["frontend"])

    def test_backend_bundle_ignores_next_config(self):
        # a backend task may happen to contain a next.config — without the fields it's not a frontend task
        with tempfile.TemporaryDirectory() as d:
            r = validate_bundle.validate(_bundle(d, _context(), next_config="basePath: '/somewhere/else'"))
        self.assertTrue(r["ok"], r)


class FrontendBundles(unittest.TestCase):
    def test_frontend_bundle_with_matching_basepath_accepted(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _context(dev_command="npm run dev", preview_port=3000)
            r = validate_bundle.validate(_bundle(d, ctx))
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["frontend"])

    def test_rejects_basepath_port_mismatch(self):
        # the one cross-field invariant nothing else catches: baked basePath must be /absproxy/<preview_port>
        with tempfile.TemporaryDirectory() as d:
            ctx = _context(dev_command="npm run dev", preview_port=3001)
            r = validate_bundle.validate(_bundle(d, ctx))  # config still bakes /absproxy/3000
        self.assertFalse(r["ok"])
        self.assertTrue(any("basePath" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_missing_next_config(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _context(dev_command="npm run dev", preview_port=3000)
            r = validate_bundle.validate(_bundle(d, ctx, next_config=None))
        self.assertFalse(r["ok"])
        self.assertTrue(any("next.config" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_config_without_basepath(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _context(dev_command="npm run dev", preview_port=3000)
            r = validate_bundle.validate(_bundle(d, ctx, next_config="export default {};\n"))
        self.assertFalse(r["ok"])
        self.assertTrue(any("basePath" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_missing_test_command(self):
        with tempfile.TemporaryDirectory() as d:
            ctx = _context(dev_command="npm run dev", preview_port=3000, test_command="")
            r = validate_bundle.validate(_bundle(d, ctx))
        self.assertFalse(r["ok"])
        self.assertTrue(any("test_command" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_dev_command_without_preview_port(self):
        with tempfile.TemporaryDirectory() as d:
            r = validate_bundle.validate(_bundle(d, _context(dev_command="npm run dev")))
        self.assertFalse(r["ok"])
        self.assertTrue(any("preview_port" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_preview_port_without_dev_command(self):
        with tempfile.TemporaryDirectory() as d:
            r = validate_bundle.validate(_bundle(d, _context(preview_port=3000)))
        self.assertFalse(r["ok"])
        self.assertTrue(any("dev_command" in x for x in r["reasons"]), r["reasons"])

    def test_rejects_bad_preview_port(self):
        for bad in (0, 70000, "3000", 3000.5):
            with tempfile.TemporaryDirectory() as d:
                ctx = _context(dev_command="npm run dev", preview_port=bad)
                r = validate_bundle.validate(_bundle(d, ctx))
            self.assertFalse(r["ok"], f"port {bad!r} should be rejected")
            self.assertTrue(any("preview_port" in x for x in r["reasons"]), r["reasons"])


class ZipBundles(unittest.TestCase):
    def test_accepts_frontend_zip(self):
        with tempfile.TemporaryDirectory() as d:
            root = _bundle(os.path.join(d, "b"), _context(dev_command="npm run dev", preview_port=3000))
            out = os.path.join(d, "task-bundle.zip")
            with zipfile.ZipFile(out, "w") as z:
                for dirpath, _, filenames in os.walk(root):
                    for name in filenames:
                        full = os.path.join(dirpath, name)
                        z.write(full, os.path.relpath(full, root))
            r = validate_bundle.validate(out)
        self.assertTrue(r["ok"], r)
        self.assertTrue(r["frontend"])

    def test_rejects_mismatched_zip(self):
        with tempfile.TemporaryDirectory() as d:
            root = _bundle(os.path.join(d, "b"), _context(dev_command="npm run dev", preview_port=4000))
            out = os.path.join(d, "task-bundle.zip")
            with zipfile.ZipFile(out, "w") as z:
                for dirpath, _, filenames in os.walk(root):
                    for name in filenames:
                        full = os.path.join(dirpath, name)
                        z.write(full, os.path.relpath(full, root))
            r = validate_bundle.validate(out)
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
