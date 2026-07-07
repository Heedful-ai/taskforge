#!/usr/bin/env python3
"""score_pr.py — deterministic PR-suitability *prefilter*.

The agent is the primary suitability judge (it reads the PR and applies
`references/pr-suitability.md`). This script only surfaces the mechanical signals the agent can't
eyeball reliably, and *hard-refuses* clear disqualifiers so a bad PR never reaches carving. The fuzzy,
high-value judgments — genuine multi-approach design content, AI-resistance, a real invariant — are
left to the agent.

Input: the PR's changed files + (optionally) the unified diff and PR/issue text.
Output: { ok, signals, hard_refuse, reasons }. `ok` is True unless input is malformed.
`hard_refuse=True` only for mechanical disqualifiers: no carvable source, or a
pure config/dependency/rename change with no real logic.

Stdlib only. Pure functions + a CLI. Usage:
  python3 score_pr.py <pr.json> [--json]
where pr.json is { "files": [{"path","additions","deletions"}], "diff": "<unified diff>",
                   "text": "<pr+issue prose>" }  (gh pr view --json files,additions,deletions shape).
Exit codes: 0 ok (read signals) · 4 usage/parse error. (hard_refuse is in the report, not the exit
code — it's a judgment surfaced to the agent, not a safety abort like scrub.)
"""
from __future__ import annotations

import json
import os
import re
import sys


# --- file classification ------------------------------------------------------------------

CONFIG_NAMES = {
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "tsconfig.json",
    "requirements.txt", "go.sum", "go.mod", "gemfile", "gemfile.lock", "cargo.toml", "cargo.lock",
    "dockerfile", ".gitignore", ".dockerignore", ".npmrc", ".nvmrc", "makefile",
}
CONFIG_EXT = re.compile(r"\.(lock|cfg|ini|toml|ya?ml|env|properties|gradle)$", re.I)
DOC_EXT = re.compile(r"\.(md|rst|txt|adoc)$", re.I)
LICENSE_RE = re.compile(r"(?i)^(license|notice|copying|changelog|authors)\b")
TEST_RE = re.compile(r"(?i)(^|/)(tests?|specs?|__tests__)(/|$)|(_test|\.test|\.spec|_spec)\.")
CODE_EXT = re.compile(r"\.(py|ts|tsx|js|jsx|mjs|cjs|go|rb|rs|php|java|kt|kts|swift|scala|c|cc|cpp|h|hpp|cs|ex|exs|clj|sql)$", re.I)


def classify(path: str) -> str:
    base = os.path.basename(path).lower()
    if TEST_RE.search(path):
        return "test"
    if base in CONFIG_NAMES or CONFIG_EXT.search(base) or base.startswith(".eslintrc") or base.startswith(".prettierrc"):
        return "config"
    if DOC_EXT.search(base) or LICENSE_RE.search(base):
        return "doc"
    if CODE_EXT.search(base):
        return "source"
    return "other"


# diff markers for renames / pure-move commits
_RENAME = re.compile(r"^(rename from |rename to |similarity index )", re.M)
_HUNK_ADD = re.compile(r"^\+(?!\+\+)", re.M)
_HUNK_DEL = re.compile(r"^-(?!--)", re.M)


def score(files: list[dict], diff_text: str = "", pr_text: str = "") -> dict:
    """Compute mechanical suitability signals + hard-refuse disqualifiers.

    files: [{"path": str, "additions": int?, "deletions": int?}]  (gh pr view --json files shape).
    """
    paths = [f.get("path", "") for f in files if f.get("path")]
    kinds = [classify(p) for p in paths]
    counts = {k: kinds.count(k) for k in ("source", "test", "config", "doc", "other")}

    loc = sum(int(f.get("additions", 0) or 0) + int(f.get("deletions", 0) or 0) for f in files)
    top_dirs = sorted({(p.split("/", 1)[0] if "/" in p else ".") for p in paths})

    # pure rename / whitespace-move: the diff is only rename metadata, no added/removed content lines.
    rename_only = bool(diff_text) and bool(_RENAME.search(diff_text)) and not (
        _HUNK_ADD.search(diff_text) or _HUNK_DEL.search(diff_text)
    )

    reasons: list[str] = []
    if counts["source"] == 0:
        which = "config/dependency" if counts["config"] else "docs/tests"
        reasons.append(f"no carvable source: PR changes only {which}, no domain logic to carve")
    if rename_only:
        reasons.append("pure rename/move: no behavioural content changed")

    hard_refuse = bool(counts["source"] == 0 or rename_only)

    signals = {
        "file_count": len(paths),
        "loc_changed": loc,
        "top_dir_count": len(top_dirs),
        "top_dirs": top_dirs,
        "kind_counts": counts,
        "has_tests": counts["test"] > 0,
        "spread_flag": len(top_dirs) > 4 or len(paths) > 25,  # advisory: likely too sprawling to carve whole
        "rename_only": rename_only,
    }
    return {"ok": True, "signals": signals, "hard_refuse": hard_refuse, "reasons": reasons}


# --- CLI ----------------------------------------------------------------------------------

def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        print("usage: score_pr.py <pr.json> [--json]", file=sys.stderr)
        return 4
    try:
        with open(args[0], encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"could not read PR json: {e}", file=sys.stderr)
        return 4

    files = data.get("files") or []
    if not isinstance(files, list):
        print("'files' must be a list of {path, additions?, deletions?}", file=sys.stderr)
        return 4

    report = score(files, data.get("diff", "") or "", data.get("text", "") or "")

    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        s = report["signals"]
        print(f"files={s['file_count']} loc={s['loc_changed']} top_dirs={s['top_dir_count']} "
              f"source={s['kind_counts']['source']} tests={s['has_tests']} spread={s['spread_flag']}")
        if report["hard_refuse"]:
            print("HARD REFUSE — " + "; ".join(report["reasons"]))
        elif report["reasons"]:
            print("flags — " + "; ".join(report["reasons"]))
        else:
            print("no mechanical disqualifiers — agent applies pr-suitability.md rubric")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
