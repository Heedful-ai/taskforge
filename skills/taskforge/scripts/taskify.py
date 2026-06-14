#!/usr/bin/env python3
"""taskify.py — turn the verified-correct project into the candidate task (U5).

Two simple modes:
  break_code            — apply the plan's mutations to a copy of correct/ -> task/, and compute the
                          reference solution diff as (task/ -> correct/): applying it to task/
                          reproduces correct/. Guaranteed to match the task.
  extend_functionality  — task/ == correct/ (working); the BRIEF asks the candidate to build
                          something new; no reference diff (judged by acceptance_criteria).

Does NOT run tests — that's validate.py (U6), which records expected_initial_state. Stdlib only.

Usage: python3 taskify.py <correct_dir> <task_plan.json> [--out DIR]
Exit: 0 ok · 1 mutation could not be applied · 4 usage error.

task_plan.json shape:
  { "mode": "break_code",
    "mutations": [ { "file": "src/a.py", "find": "a + b", "replace": "a - b", "note": "off-by-op" } ],
    "acceptance_criteria": [ {"id":"AC1","description":"...","check":"test_command","weight":1} ],
    "what_to_test": ["..."],
    "vendored_paths": [".venv", "node_modules"] }
"""
from __future__ import annotations

import difflib
import json
import os
import shutil
import sys

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "dist", "build", ".next", "coverage", "__pycache__"}


def _arg(flag: str, default: str) -> str:
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def _walk_rel(root: str, extra_exclude: set[str]) -> list[str]:
    excl = SKIP_DIRS | set(extra_exclude)
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in excl]
        for name in filenames:
            out.append(os.path.relpath(os.path.join(dirpath, name), root))
    return sorted(out)


def _read(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()
    except OSError:
        return []


def diff_dirs(a_dir: str, b_dir: str, exclude: set[str]) -> str:
    """Unified diff applying a_dir -> b_dir, over the union of non-excluded files."""
    files = sorted(set(_walk_rel(a_dir, exclude)) | set(_walk_rel(b_dir, exclude)))
    chunks: list[str] = []
    for rel in files:
        a = _read(os.path.join(a_dir, rel))
        b = _read(os.path.join(b_dir, rel))
        if a == b:
            continue
        chunks.extend(difflib.unified_diff(a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(chunks)


def taskify(correct_dir: str, plan: dict, out_dir: str) -> dict:
    """A task can carry BOTH bugs to fix AND an extension to build (the default). Derives the mode:
    fix_and_extend (both) · fix_bugs (bugs only) · extend (extension only)."""
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(correct_dir, out_dir)

    excluded = set(plan.get("vendored_paths", []) or [])
    mutations_in = plan.get("mutations", []) or []      # the bug(s) to fix
    extension = plan.get("extension")                   # {description, acceptance_criteria} or None
    if not mutations_in and not extension:
        return {"ok": False, "error": "task_plan has neither bugs (mutations) nor an extension — nothing to do"}

    applied: list[dict] = []
    for mut in mutations_in:
        rel, find, repl = mut.get("file"), mut.get("find"), mut.get("replace", "")
        target = os.path.join(out_dir, rel or "")
        if not rel or not os.path.isfile(target) or find is None:
            return {"ok": False, "error": f"mutation target invalid: {mut}"}
        with open(target, encoding="utf-8") as fh:
            content = fh.read()
        if find not in content:
            return {"ok": False, "error": f"mutation 'find' not present in {rel}: {find!r}"}
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(content.replace(find, repl, 1))
        applied.append({"file": rel, "kind": "bug" if repl else "removal", "note": mut.get("note", "")})

    reference_diff = None
    if applied:
        reference_diff = diff_dirs(out_dir, correct_dir, excluded)  # task -> correct (the bug fix)
        if not reference_diff:
            return {"ok": False, "error": "the bug mutations produced no change — task == correct"}

    mode = "fix_and_extend" if applied and extension else "fix_bugs" if applied else "extend"

    acceptance = list(plan.get("acceptance_criteria", []) or [])
    if applied and not acceptance:
        acceptance.append({"id": "AC_FIX", "description": "all existing tests pass (the planted bug is fixed)",
                           "check": "test_command", "weight": 1})
    if extension:
        acceptance += list(extension.get("acceptance_criteria", []) or [])

    return {
        "ok": True,
        "out_dir": out_dir,
        "mode": mode,
        "mutations": applied,
        "reference_diff": reference_diff,
        "extension": extension,
        "acceptance_criteria": acceptance,
        "what_to_test": plan.get("what_to_test", []),
    }


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) < 2:
        print("usage: taskify.py <correct_dir> <task_plan.json> [--out DIR]", file=sys.stderr)
        return 4
    correct_dir, plan_path = args[0], args[1]
    out_dir = _arg("--out", "task")
    try:
        plan = json.load(open(plan_path, encoding="utf-8"))
    except Exception as e:
        print(f"cannot read plan: {e}", file=sys.stderr)
        return 4

    result = taskify(correct_dir, plan, out_dir)
    # write the result next to task/ for package.py to assemble
    if result.get("ok"):
        with open(os.path.join(os.path.dirname(os.path.abspath(out_dir)) or ".", "taskify_result.json"), "w") as fh:
            json.dump(result, fh, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "reference_diff"}, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
