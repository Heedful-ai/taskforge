#!/usr/bin/env python3
"""validate_carve.py — the gate before we copy anything (U4).

The agent proposes a `carve_plan.json`; this script is the deterministic gate that keeps the slice
bounded (~1–2h task, not a sprawling repo) and coherent. It NEVER copies — it only judges the plan.
Caps bound *size*; difficulty is a separate human judgment (see carve-guide.md). Stdlib only.

Usage: python3 validate_carve.py <source_repo> <carve_plan.json> [--json]
Exit: 0 ok · 2 plan rejected · 4 usage error.

carve_plan.json shape:
  { "language": "python", "files": ["src/a.py", ...], "entrypoint": "src/a.py",
    "build_command": null, "test_command": "python3 -m unittest", "vendor_commands": [],
    "vendored_paths": [".venv", "node_modules"], "source": {...} }
"""
from __future__ import annotations

import json
import os
import sys

MAX_FILES = 25
MAX_LOC = 1500
MAX_TOP_DIRS = 4  # a slice spanning more than this is grabbing too much of the repo

SENSITIVE_SEGMENTS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "coverage"}


def validate(source_root: str, plan: dict) -> dict:
    reasons: list[str] = []

    files = plan.get("files") or []
    if not isinstance(files, list) or not files:
        reasons.append("plan.files is empty — nothing to carve")
        return {"ok": False, "reasons": reasons}

    if not plan.get("language"):
        reasons.append("plan.language is required (language-as-data)")
    if not plan.get("test_command"):
        reasons.append("plan.test_command is required (the offline acceptance check)")

    # path existence + containment + not-sensitive
    abs_root = os.path.realpath(source_root)
    missing, escaping, sensitive = [], [], []
    total_loc = 0
    for rel in files:
        full = os.path.realpath(os.path.join(source_root, rel))
        if not (full == abs_root or full.startswith(abs_root + os.sep)):
            escaping.append(rel)
            continue
        segs = rel.replace("\\", "/").split("/")
        if any(s in SENSITIVE_SEGMENTS for s in segs):
            sensitive.append(rel)
            continue
        if not os.path.isfile(full):
            missing.append(rel)
            continue
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as fh:
                total_loc += sum(1 for _ in fh)
        except OSError:
            missing.append(rel)

    if missing:
        reasons.append(f"{len(missing)} file(s) do not exist: {', '.join(missing[:5])}")
    if escaping:
        reasons.append(f"{len(escaping)} path(s) escape the repo: {', '.join(escaping[:5])}")
    if sensitive:
        reasons.append(f"{len(sensitive)} path(s) in a dependency/build/.git dir: {', '.join(sensitive[:5])}")

    # caps
    if len(files) > MAX_FILES:
        reasons.append(f"too many files: {len(files)} > {MAX_FILES} cap")
    if total_loc > MAX_LOC:
        reasons.append(f"slice too large: {total_loc} LOC > {MAX_LOC} cap")

    top_dirs = {rel.replace("\\", "/").split("/")[0] for rel in files if "/" in rel.replace("\\", "/")}
    if len(top_dirs) > MAX_TOP_DIRS:
        reasons.append(f"slice spans {len(top_dirs)} top-level dirs > {MAX_TOP_DIRS} (grabbing too much)")

    return {
        "ok": not reasons,
        "reasons": reasons,
        "stats": {"files": len(files), "loc": total_loc, "top_dirs": sorted(top_dirs)},
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("usage: validate_carve.py <source_repo> <carve_plan.json> [--json]", file=sys.stderr)
        return 4
    source_root, plan_path = args[0], args[1]
    try:
        plan = json.load(open(plan_path, encoding="utf-8"))
    except Exception as e:
        print(f"cannot read plan: {e}", file=sys.stderr)
        return 4

    report = validate(source_root, plan)
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            s = report["stats"]
            print(f"ok — {s['files']} files, {s['loc']} LOC, dirs={s['top_dirs']}")
        else:
            for r in report["reasons"]:
                print(f"reject: {r}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
