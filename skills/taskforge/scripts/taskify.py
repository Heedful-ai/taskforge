#!/usr/bin/env python3
"""taskify.py — turn the verified-correct project into the candidate task (U4, problem-first model).

There is NO controlling mode enum. The agent designs the task (see references/task-design.md) and
hands taskify a free-form spec; taskify mechanically applies it:

  1. copytree correct/ -> task/                  (the "answer world" -> the candidate's tree)
  2. apply `mutations` (find/replace):           stub the solution back to a pre-solution world
       kind "stub"  -> a signature-preserving TODO body (build-it part)
       kind "bug"   -> a planted defect to find and fix
  3. remove `strip_paths` from task/             (e.g. the team's own tests, which would spoil)
  4. write `example_tests` INTO task/            (mechanics-only, contract clarity; shipped)
  5. write `hidden_tests` (core/stretch) into a sibling `hidden/` dir, NEVER under task/  (withheld)
  6. compute `reference_exemplar` = diff(task -> correct) over the mutated solution files: applying
     it to task/ restores the team's solution. ONE acceptable exemplar, never a similarity target.

Hidden-suite LOCATION CONTRACT (U4 owns it; U5/U6/U8 reference it): a `hidden/` directory SIBLING to
task/ at the same output root, split into `hidden/core/` and `hidden/stretch/`. taskify_result.json
records `hidden_tests_dir` + `hidden_tiers`.

Does NOT run tests — that's validate.py, which records expected_initial_state. Stdlib only.

Usage: python3 taskify.py <correct_dir> <task_plan.json> [--out DIR]
Exit: 0 ok · 1 spec could not be applied · 4 usage error.

task_plan.json shape (all keys optional except that *something* must be produced):
  { "task_mode": "design+fix+extend (senior: 1 open design choice, build core, concurrency stretch)",
    "mutations":   [ {"file":"src/v.ts","find":"…body…","replace":"// TODO","kind":"stub","note":"…"} ],
    "strip_paths": ["tests/versioning.test.ts"],
    "example_tests": [ {"path":"tests/example.test.ts","content":"…mechanics only…"} ],
    "hidden_tests": { "core":    [ {"path":"test_core.py","content":"…invariants…"} ],
                      "stretch": [ {"path":"test_scale.py","content":"…"} ] },
    "extension": {"description":"…","acceptance_criteria":[…]},
    "scale": {"description":"…"},
    "seeded_failure": {"note":"…"},
    "human_rubric": [ {"dimension":"…","acceptable_approaches":["…"],"what_good_looks_like":"…"} ],
    "notes_evaluation": {"what_to_look_for":"…"},
    "acceptance_criteria": [ {"id":"AC1","description":"…","check":"test_command","weight":1} ],
    "what_to_test": ["…"],
    "vendored_paths": ["node_modules"] }
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


def diff_files(a_dir: str, b_dir: str, rel_files: list[str]) -> str:
    """Unified diff applying a_dir -> b_dir, restricted to rel_files (e.g. the mutated solution)."""
    chunks: list[str] = []
    for rel in sorted(set(rel_files)):
        a = _read(os.path.join(a_dir, rel))
        b = _read(os.path.join(b_dir, rel))
        if a == b:
            continue
        chunks.extend(difflib.unified_diff(a, b, fromfile=f"a/{rel}", tofile=f"b/{rel}"))
    return "".join(chunks)


def _safe_under(base: str, rel: str) -> str | None:
    """Resolve `rel` under `base`; return the abspath, or None if it escapes base."""
    base_abs = os.path.realpath(base)
    target = os.path.realpath(os.path.join(base_abs, rel))
    if target == base_abs or target.startswith(base_abs + os.sep):
        return target
    return None


def _write_tests(specs: list, dest_root: str, guard_not_under: str) -> tuple[list[str], str | None]:
    """Write [{path, content}] under dest_root. Refuse any path that escapes dest_root or lands
    under guard_not_under (e.g. task/). Returns (written_rel_paths, error)."""
    written: list[str] = []
    for t in specs or []:
        rel, content = t.get("path"), t.get("content", "")
        if not rel:
            return written, "test spec missing 'path'"
        target = _safe_under(dest_root, rel)
        if target is None:
            return written, f"test path escapes its directory: {rel!r}"
        guard_abs = os.path.realpath(guard_not_under)
        if target == guard_abs or target.startswith(guard_abs + os.sep):
            return written, f"hidden test would land under task/: {rel!r}"
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as fh:
            fh.write(content)
        written.append(rel)
    return written, None


def taskify(correct_dir: str, plan: dict, out_dir: str) -> dict:
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    shutil.copytree(correct_dir, out_dir)

    mutations_in = plan.get("mutations", []) or []
    strip_paths = plan.get("strip_paths", []) or []
    example_tests = plan.get("example_tests", []) or []
    hidden = plan.get("hidden_tests", {}) or {}
    extension = plan.get("extension")
    scale = plan.get("scale")
    seeded_failure = plan.get("seeded_failure")

    produces_something = bool(mutations_in or example_tests or hidden.get("core") or hidden.get("stretch")
                             or extension or scale)
    if not produces_something:
        return {"ok": False, "error": "task_plan produces nothing — no mutations, tests, extension, or scale ask"}

    # 1. apply mutations (stub the solution / plant bugs)
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
        mutated_files.append(rel)

    # 2. strip files that would spoil (e.g. the team's own grading tests)
    for rel in strip_paths:
        target = _safe_under(out_dir, rel)
        if target and os.path.isfile(target):
            os.remove(target)

    # 3. ship example tests into task/ (mechanics only)
    example_written, err = _write_tests(example_tests, out_dir, guard_not_under="/dev/null")
    if err:
        return {"ok": False, "error": f"example test: {err}"}

    # 4. withhold the hidden suite into a SIBLING hidden/ dir, tiered, NEVER under task/
    parent = os.path.dirname(os.path.abspath(out_dir)) or "."
    hidden_dir = os.path.join(parent, "hidden")
    if os.path.exists(hidden_dir):
        shutil.rmtree(hidden_dir)
    tiers: dict[str, list[str]] = {"core": [], "stretch": []}
    for tier in ("core", "stretch"):
        dest = os.path.join(hidden_dir, tier)
        written, err = _write_tests(hidden.get(tier, []), dest, guard_not_under=os.path.abspath(out_dir))
        if err:
            return {"ok": False, "error": f"hidden {tier} test: {err}"}
        tiers[tier] = written

    # 5. reference exemplar = how the team filled the stubbed solution (task -> correct, mutated files)
    reference_exemplar = diff_files(out_dir, correct_dir, mutated_files) if mutated_files else None
    if mutated_files and not reference_exemplar:
        return {"ok": False, "error": "mutations produced no change — task == correct on the mutated files"}

    # descriptive task_mode (carries calibration anchors); derive a default if absent
    task_mode = plan.get("task_mode")
    if not task_mode:
        bits = []
        if any(m["kind"] == "stub" for m in applied):
            bits.append("build")
        if any(m["kind"] in ("bug", "removal") for m in applied):
            bits.append("fix")
        if extension or scale:
            bits.append("extend")
        task_mode = "+".join(bits) or "extend"

    acceptance = list(plan.get("acceptance_criteria", []) or [])
    if any(m["kind"] in ("bug", "removal") for m in applied) and not any(c.get("id") == "AC_FIX" for c in acceptance):
        acceptance.append({"id": "AC_FIX", "description": "the planted defect is fixed (behaviour restored)",
                           "check": "test_command", "weight": 1})
    if extension:
        acceptance += list(extension.get("acceptance_criteria", []) or [])

    return {
        "ok": True,
        "out_dir": out_dir,
        "task_mode": task_mode,
        "mutations": applied,
        "example_tests": example_written,
        "hidden_tests_dir": hidden_dir,
        "hidden_tiers": tiers,
        "reference_exemplar": reference_exemplar,
        "extension": extension,
        "scale": scale,
        "seeded_failure": seeded_failure,
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
    print(json.dumps({k: v for k, v in result.items() if k != "reference_exemplar"}, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
