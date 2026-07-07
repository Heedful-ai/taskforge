"""Tests for the scrub safety gates (U3)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import scrub  # noqa: E402


def _write(root: str, rel: str, content: str) -> None:
    p = os.path.join(root, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(content)


class ScanText(unittest.TestCase):
    def test_clean_text_no_findings(self):
        self.assertEqual(scrub.scan_text("x", "just some normal code\nreturn a + b\n"), [])

    def test_detects_secrets(self):
        cases = [
            'AWS = "AKIA1234567890ABCDEF"',
            "tok = ghp_" + "a" * 36,
            "key = sk-" + "a" * 40,
            "-----BEGIN RSA PRIVATE KEY-----",
            "jwt = eyJabcdefghij.eyJabcdefghij.signature99",
        ]
        for c in cases:
            self.assertTrue(scrub.scan_text("f", c), f"should flag: {c}")

    def test_placeholder_suppressed_but_real_key_on_test_line_caught(self):
        self.assertEqual(scrub.scan_text("f", 'key = "your-key-here"'), [])
        self.assertEqual(scrub.scan_text("f", 'token = "example-placeholder"'), [])
        # "test" on the line must NOT hide a real key sitting on it
        self.assertTrue(scrub.scan_text("f", 'test_key = "AKIA1234567890ABCDEF"'))

    def test_placeholder_email_domain_suppressed(self):
        self.assertEqual(scrub.scan_text("f", "contact a@example.com"), [])
        self.assertTrue(scrub.scan_text("f", "contact alice@realcorp.io"))

    def test_redaction_hides_the_value(self):
        f = scrub.scan_text("f", "key = sk-" + "b" * 40)[0]
        self.assertNotIn("bbbbbbbb", f.match)
        self.assertIn("chars", f.match)


class ScanPaths(unittest.TestCase):
    def test_clean_dir(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "src/sum.py", "def add(a, b):\n    return a + b\n")
            findings, skipped = scrub.scan_paths(d)
            self.assertEqual(findings, [])
            self.assertEqual(skipped, [])

    def test_secret_in_file(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "config.py", 'AWS = "AKIA1234567890ABCDEF"\n')
            findings, _ = scrub.scan_paths(d)
            self.assertTrue(any(f.rule == "aws-access-key" for f in findings))

    def test_dependency_binaries_ignored_source_binaries_surfaced(self):
        with tempfile.TemporaryDirectory() as d:
            _write(d, "node_modules/pkg/blob.so", "x")   # vendored binary — ignored
            _write(d, "assets/logo.png", "x")            # source binary — surfaced
            _write(d, "src/app.py", "print('hi')\n")
            findings, skipped = scrub.scan_paths(d)
            self.assertEqual(findings, [])
            self.assertIn("assets/logo.png", skipped)
            self.assertTrue(all("node_modules" not in s for s in skipped))



if __name__ == "__main__":
    unittest.main()
