#!/usr/bin/env python3
"""taskify.py — turn the verified-correct project into the candidate task.

There are no hidden tests and no mode enum. A task is built from a free-form spec the agent designs
(see references/task-design.md). taskify mechanically applies it:

  1. copytree correct/ -> task/                  (the solution world -> the candidate's tree)
  2. apply `mutations` (find/replace):
       kind "bug"   -> a planted defect; the test that catches it SHIPS in task/ (it's the task)
       kind "stub"  -> gut a solution region to a signature-preserving TODO; the candidate builds it
  3. remove `strip_paths` from task/             (e.g. the team's tests for a build task — you can't
                                                  ship tests for code that isn't written yet)

The team's solution for the mutated files (the reference answer) is recorded in `reference_files`;
package.py copies those (from correct/) into `evaluation/reference/`.

Does NOT run tests — that's validate.py. Stdlib only.

Usage: python3 taskify.py <correct_dir> <task_plan.json> [--out DIR]
Exit: 0 ok · 1 spec could not be applied · 4 usage error.

task_plan.json shape (all optional except that *something* is produced):
  { "task_mode": "build (senior): design the durable runner; plus a planted bug to fix",
    "mutations":   [ {"file":"src/x.ts","find":"…body…","replace":"// TODO","kind":"stub","note":"…"} ],
    "strip_paths": ["tests/team.test.ts"],
    "extension": {"description":"…"}, "scale": {"description":"…"}, "seeded_failure": {"note":"…"},
    "reference_summary": "how the team solved it",
    "human_rubric": [ {"dimension":"…","acceptable_approaches":["…"],"what_good_looks_like":"…"} ],
    "notes_evaluation": {"what_to_look_for":"…"},
    "acceptance_criteria": [...], "what_to_test": ["…"] }
"""
from __future__ import annotations

import json
import os
import shutil
import sys


def _arg(flag: str, default: str) -> str:
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def _safe_under(base: str, rel: str) -> str | None:
    base_abs = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_abs, rel))
    if target == base_abs or target.startswith(base_abs + os.sep):
        return target
    return None


def taskify(correct_dir: str, plan: dict, out_dir: str) -> dict:
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    # symlinks=True: preserve vendored node_modules/.bin/* relative symlinks (else self-resolving
    # CLIs like vitest break in task/).
    shutil.copytree(correct_dir, out_dir, symlinks=True)

    mutations_in = plan.get("mutations", []) or []
    strip_paths = plan.get("strip_paths", []) or []
    extension = plan.get("extension")
    scale = plan.get("scale")

    if not (mutations_in or strip_paths or extension or scale):
        return {"ok": False, "error": "task_plan produces nothing — no mutations, strips, extension, or scale ask"}

    applied: list[dict] = []
    mutated_files: list[str] = []
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
        kind = mut.get("kind") or ("bug" if repl.strip() else "stub")
        applied.append({"file": rel, "kind": kind, "note": mut.get("note", "")})
        if rel not in mutated_files:
            mutated_files.append(rel)

    for rel in strip_paths:
        target = _safe_under(out_dir, rel)
        if target and os.path.isfile(target):
            os.remove(target)

    task_mode = plan.get("task_mode")
    if not task_mode:
        bits = []
        if any(m["kind"] == "stub" for m in applied):
            bits.append("build")
        if any(m["kind"] in ("bug", "removal") for m in applied):
            bits.append("fix")
        if extension or scale:
            bits.append("extend")
        task_mode = "+".join(bits) or "build"

    acceptance = list(plan.get("acceptance_criteria", []) or [])
    if any(m["kind"] in ("bug", "removal") for m in applied) and not any(c.get("id") == "AC_FIX" for c in acceptance):
        acceptance.append({"id": "AC_FIX", "description": "the planted defect is fixed (the shipped test passes)",
                           "check": "test_command", "weight": 1})

    return {
        "ok": True,
        "out_dir": out_dir,
        "task_mode": task_mode,
        "mutations": applied,
        "reference_files": sorted(mutated_files),   # the team's answer lives at correct/<file>
        "extension": extension,
        "scale": scale,
        "seeded_failure": plan.get("seeded_failure"),
        "reference_summary": plan.get("reference_summary", ""),
        "human_rubric": plan.get("human_rubric", []) or [],
        "notes_evaluation": plan.get("notes_evaluation", {}) or {},
        "acceptance_criteria": acceptance,
        "what_to_test": plan.get("what_to_test", []) or [],
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
    if result.get("ok"):
        parent = os.path.dirname(os.path.abspath(out_dir)) or "."
        with open(os.path.join(parent, "taskify_result.json"), "w") as fh:
            json.dump(result, fh, indent=2)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
