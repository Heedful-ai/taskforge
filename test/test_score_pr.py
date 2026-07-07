"""Tests for score_pr.py (U2) — the deterministic PR-suitability prefilter."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skills", "taskforge", "scripts"))
import score_pr  # noqa: E402


def _f(path, add=10, dele=2):
    return {"path": path, "additions": add, "deletions": dele}


class Classify(unittest.TestCase):
    def test_kinds(self):
        self.assertEqual(score_pr.classify("src/versioning.ts"), "source")
        self.assertEqual(score_pr.classify("tests/test_versioning.py"), "test")
        self.assertEqual(score_pr.classify("src/foo.test.ts"), "test")
        self.assertEqual(score_pr.classify("package-lock.json"), "config")
        self.assertEqual(score_pr.classify("pyproject.toml"), "config")
        self.assertEqual(score_pr.classify("README.md"), "doc")


class HappyPath(unittest.TestCase):
    def test_coherent_domain_slice_with_tests_passes(self):
        files = [_f("src/versioning.ts", 120, 30), _f("src/service.ts", 40, 10),
                 _f("tests/versioning.test.ts", 80, 0)]
        r = score_pr.score(files, diff_text="@@\n+const x = 1\n-const y = 2\n")
        self.assertTrue(r["ok"])
        self.assertFalse(r["hard_refuse"], r["reasons"])
        self.assertEqual(r["signals"]["kind_counts"]["source"], 2)
        self.assertTrue(r["signals"]["has_tests"])
        self.assertEqual(r["signals"]["loc_changed"], 120 + 30 + 40 + 10 + 80)
        self.assertFalse(r["signals"]["spread_flag"])


class Refuse(unittest.TestCase):
    # Domain-based refusal (auth/crypto/payment keyword blocklist) was DELETED 2026-07-07 — a guard
    # for nothing: topics aren't hazards, and the secret/PII scan still hard-fails real leaks.
    def test_auth_domain_is_fine(self):
        files = [_f("src/auth/login.ts"), _f("src/session.ts")]
        r = score_pr.score(files)
        self.assertFalse(r["hard_refuse"])

    def test_config_only_no_carvable_source(self):
        files = [_f("package.json"), _f("package-lock.json"), _f("tsconfig.json")]
        r = score_pr.score(files)
        self.assertTrue(r["hard_refuse"])
        self.assertEqual(r["signals"]["kind_counts"]["source"], 0)
        self.assertTrue(any("no carvable source" in x for x in r["reasons"]))

    def test_docs_only_no_carvable_source(self):
        files = [_f("README.md"), _f("docs/guide.md")]
        r = score_pr.score(files)
        self.assertTrue(r["hard_refuse"])

    def test_pure_rename_hard_refused(self):
        files = [_f("src/a.ts", 0, 0), _f("src/b.ts", 0, 0)]
        diff = "diff --git a/src/a.ts b/src/b.ts\nsimilarity index 100%\nrename from src/a.ts\nrename to src/b.ts\n"
        r = score_pr.score(files, diff_text=diff)
        self.assertTrue(r["hard_refuse"])
        self.assertTrue(r["signals"]["rename_only"])
        self.assertTrue(any("rename" in x for x in r["reasons"]))


class Edge(unittest.TestCase):
    def test_sprawling_pr_flagged_not_refused(self):
        files = [_f(f"area{i}/mod{i}.ts") for i in range(40)]
        r = score_pr.score(files)
        self.assertFalse(r["hard_refuse"])  # has source, not a mechanical disqualifier
        self.assertTrue(r["signals"]["spread_flag"])
        self.assertGreater(r["signals"]["top_dir_count"], 4)

    def test_rename_with_real_edits_not_refused(self):
        files = [_f("src/a.ts", 30, 5)]
        diff = "rename from src/a.ts\nrename to src/b.ts\n@@\n+real change\n"
        r = score_pr.score(files, diff_text=diff)
        self.assertFalse(r["signals"]["rename_only"])  # has +content, so not pure rename
        self.assertFalse(r["hard_refuse"])

    def test_empty_files_list_does_not_throw(self):
        r = score_pr.score([])
        self.assertTrue(r["ok"])
        self.assertTrue(r["hard_refuse"])  # zero source
        self.assertEqual(r["signals"]["file_count"], 0)


if __name__ == "__main__":
    unittest.main()
