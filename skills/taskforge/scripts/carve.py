#!/usr/bin/env python3
"""carve.py — copy the planned slice into a clean standalone project + vendor deps + capture context.

Runs AFTER validate_carve.py passes AND the user approves the slice. It:
  1. copies each planned file into <out>/ (default ./correct), preserving relative paths, no .git;
  2. runs the plan's vendor_commands in <out>/ so dependencies resolve OFFLINE later (this runs on
     the user's machine, which HAS network now — the resulting tree is what must run offline);
  3. writes source_context.json from the plan's captured PR/issue (folded into context.json at packaging).

Stdlib only. Usage: python3 carve.py <source_repo> <carve_plan.json> [--out DIR]
Exit: 0 ok · 1 vendor command failed · 4 usage error.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys


def _arg(flag: str, default: str) -> str:
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def carve(source_root: str, plan: dict, out_dir: str) -> dict:
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    copied = []
    for rel in plan.get("files", []):
        src = os.path.join(source_root, rel)
        dst = os.path.join(out_dir, rel)
        os.makedirs(os.path.dirname(dst) or out_dir, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append(rel)

    vendor_log = []
    for cmd in plan.get("vendor_commands", []) or []:
        proc = subprocess.run(cmd, shell=True, cwd=out_dir, capture_output=True, text=True)
        vendor_log.append({"cmd": cmd, "returncode": proc.returncode,
                           "stderr_tail": proc.stderr[-500:] if proc.stderr else ""})
        if proc.returncode != 0:
            return {"ok": False, "copied": copied, "vendor_log": vendor_log,
                    "error": f"vendor command failed: {cmd}"}

    # capture source context for context.json (evaluation-side; never enters task/)
    source_ctx = plan.get("source", {})
    ctx_path = os.path.join(os.path.dirname(os.path.abspath(out_dir)) or ".", "source_context.json")
    with open(ctx_path, "w", encoding="utf-8") as fh:
        json.dump(source_ctx, fh, indent=2)

    return {"ok": True, "out_dir": out_dir, "copied": copied,
            "vendor_log": vendor_log, "source_context": ctx_path}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("usage: carve.py <source_repo> <carve_plan.json> [--out DIR]", file=sys.stderr)
        return 4
    source_root, plan_path = args[0], args[1]
    out_dir = _arg("--out", "correct")
    try:
        plan = json.load(open(plan_path, encoding="utf-8"))
    except Exception as e:
        print(f"cannot read plan: {e}", file=sys.stderr)
        return 4

    result = carve(source_root, plan, out_dir)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
