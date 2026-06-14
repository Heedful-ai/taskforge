#!/usr/bin/env python3
"""validate.py — prove the task runs standalone, offline, and is genuinely solvable (U5).

Runs inside a container with `--network=none`, mirroring jelly's egress-locked sandbox (a stdlib
script can't sever egress on macOS). No container runtime → FAIL CLOSED (no bundle).

Problem-first contract (replaces the old mode→red/green coupling). Using the hidden-suite location
from taskify (a sibling `hidden/core` + `hidden/stretch`):

  1. correct/ builds + tests GREEN offline           → the answer world is sound and self-contained.
  2. task/ builds + EXAMPLE tests GREEN offline       → "RED for the right reason": example tests are
     mechanics-only, so green here proves task/ imports/builds. If this is RED, the stub broke the
     build — reject, don't accept a forged RED.
  3. hidden `core` GREEN composed with correct/        → the suite captures behaviour the solution meets.
  4. hidden `core` RED composed with task/             → the problem is genuinely unsolved. Because (2)
     already proved task/ builds, this RED is unsolved-behaviour, not a broken build.
  5. hidden `stretch` on correct/                      → recorded, informative (partial-credit tier).

`ok` requires 1 ∧ 2 ∧ 3 ∧ 4. Hidden tests are composed into a DISPOSABLE copy and never touch the
real task/ or correct/. Stdlib only.

Usage:
  python3 validate.py --test CMD [--build CMD] [--correct DIR] [--task DIR]
                      [--hidden DIR] [--hidden-test CMD] [--language python] [--image IMG]
                      [--runtime docker|podman] [--json]
Exit: 0 all pass · 2 a check failed · 5 no container runtime (fail-closed) · 4 usage error.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

DEFAULT_IMAGES = {
    "python": "python:3.11-slim",
    "node": "node:20-slim",
    "go": "golang:1.22",
    "ruby": "ruby:3.3",
    "rust": "rust:1",
    "php": "php:8.3-cli",
}


def detect_runtime() -> str | None:
    for rt in ("docker", "podman"):
        if shutil.which(rt):
            return rt
    return None


def build_container_cmd(runtime: str, image: str, abs_dir: str, shell_cmd: str) -> list[str]:
    """The exact argv used to run a command offline in a container. Pure — unit-tested without Docker."""
    return [runtime, "run", "--rm", "--network=none", "-v", f"{abs_dir}:/work", "-w", "/work",
            image, "sh", "-c", shell_cmd]


def _shell(build_cmd: str | None, test_cmd: str) -> str:
    return f"{build_cmd} && {test_cmd}" if build_cmd else test_cmd


def run_offline(runtime: str, image: str, target_dir: str, test_cmd: str, build_cmd: str | None) -> dict:
    argv = build_container_cmd(runtime, image, os.path.realpath(target_dir), _shell(build_cmd, test_cmd))
    proc = subprocess.run(argv, capture_output=True, text=True)
    return {
        "returncode": proc.returncode,
        "passed": proc.returncode == 0,
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-2000:],
    }


def run_with_hidden(runtime: str, image: str, base_dir: str, hidden_tier_dir: str,
                    hidden_test_cmd: str, build_cmd: str | None) -> dict:
    """Compose base_dir + the hidden tier into a DISPOSABLE tree (the hidden suite at `_hidden/`),
    run hidden_test_cmd there offline, then discard. Never mutates base_dir."""
    tmp = tempfile.mkdtemp(prefix="taskforge-validate-")
    try:
        work = os.path.join(tmp, "work")
        shutil.copytree(base_dir, work)
        if os.path.isdir(hidden_tier_dir):
            shutil.copytree(hidden_tier_dir, os.path.join(work, "_hidden"))
        return run_offline(runtime, image, work, hidden_test_cmd, build_cmd)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def validate(test_cmd: str, build_cmd: str | None, correct_dir: str, task_dir: str | None,
             image: str, runtime: str | None, hidden_dir: str | None = None,
             hidden_test_cmd: str | None = None) -> dict:
    if runtime is None:
        return {"ok": False, "fail_closed": True,
                "reason": "no container runtime (docker/podman) — cannot verify offline; refusing to ship"}

    reasons: list[str] = []

    # 1. correct/ builds + tests green offline (self-contained answer world)
    correct_run = run_offline(runtime, image, correct_dir, test_cmd, build_cmd)
    correct_passed = correct_run["passed"]
    if not correct_passed:
        reasons.append("correct/ does not build+test green offline (needs network, or the slice isn't standalone)")

    # Phase-4 standalone check: no task yet — only prove the carved project builds+tests offline.
    if not task_dir:
        return {"ok": not reasons, "fail_closed": False, "reasons": reasons, "standalone": True,
                "correct_passed": correct_passed, "runtime": runtime, "image": image}

    # 2. task/ builds + example tests green → "RED for the right reason" gate
    task_run = run_offline(runtime, image, task_dir, test_cmd, build_cmd)
    task_builds = task_run["passed"]
    if not task_builds:
        reasons.append("task/ does not build/run its example tests green — the stub broke the build, "
                       "or the example tests assert invariants they shouldn't (mechanics-only)")

    correct_core_passed = None
    task_core_failed = None
    stretch_on_correct = None
    core_dir = os.path.join(hidden_dir, "core") if hidden_dir else None
    has_hidden = bool(core_dir and hidden_test_cmd and os.path.isdir(core_dir))

    if has_hidden:
        # 3. hidden core GREEN on correct/
        cc = run_with_hidden(runtime, image, correct_dir, core_dir, hidden_test_cmd, build_cmd)
        correct_core_passed = cc["passed"]
        if not correct_core_passed:
            reasons.append("hidden core suite FAILS on correct/ — the team solution doesn't satisfy its "
                           "own behaviour suite (suite is wrong, or correct/ is incomplete)")
        # 4. hidden core RED on task/ (given task builds, this is unsolved-behaviour, not a broken build)
        tc = run_with_hidden(runtime, image, task_dir, core_dir, hidden_test_cmd, build_cmd)
        task_core_failed = not tc["passed"]
        if not task_core_failed:
            reasons.append("hidden core suite PASSES on task/ — the problem isn't actually unsolved "
                           "(the solution wasn't stubbed out)")
        # 5. stretch tier on correct/ — informative, not a gate
        stretch_dir = os.path.join(hidden_dir, "stretch")
        if os.path.isdir(stretch_dir) and os.listdir(stretch_dir):
            stretch_on_correct = run_with_hidden(runtime, image, correct_dir, stretch_dir, hidden_test_cmd, build_cmd)["passed"]
    elif hidden_dir:
        reasons.append("hidden suite present but no --hidden-test command given — cannot prove solvability")

    expected_initial_state = {
        "tests": "red" if task_core_failed else ("green" if task_core_failed is False else "unknown"),
        "builds": task_builds,
        "matches_expected": bool(task_builds and task_core_failed),
    }

    ok = (not reasons) and correct_passed and task_builds
    if has_hidden:
        ok = ok and correct_core_passed is True and task_core_failed is True

    return {
        "ok": bool(ok),
        "fail_closed": False,
        "reasons": reasons,
        "expected_initial_state": expected_initial_state,
        "correct_passed": correct_passed,
        "task_builds": task_builds,
        "correct_core_passed": correct_core_passed,
        "task_core_failed": task_core_failed,
        "stretch_on_correct": stretch_on_correct,
        "runtime": runtime,
        "image": image,
    }


def _arg(flag: str, default=None):
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def main() -> int:
    test_cmd = _arg("--test")
    if not test_cmd:
        print("usage: validate.py --test CMD [--build CMD] [--correct DIR] [--task DIR] "
              "[--hidden DIR] [--hidden-test CMD] [--language L] [--image IMG] [--runtime R] [--json]",
              file=sys.stderr)
        return 4
    build_cmd = _arg("--build")
    correct_dir = _arg("--correct", "correct")
    task_dir = _arg("--task", None)  # omit for the Phase-4 standalone check (correct-only)
    hidden_dir = _arg("--hidden", None)
    hidden_test_cmd = _arg("--hidden-test", None)
    language = _arg("--language", "python")
    image = _arg("--image", DEFAULT_IMAGES.get(language, "python:3.11-slim"))
    runtime = _arg("--runtime", detect_runtime())

    report = validate(test_cmd, build_cmd, correct_dir, task_dir, image, runtime, hidden_dir, hidden_test_cmd)
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        if report.get("fail_closed"):
            print(f"FAIL-CLOSED: {report['reason']}")
        elif report["ok"]:
            st = report.get("expected_initial_state", {})
            print(f"ok — correct green; task builds + core RED (offline, {report['image']}); state={st}")
        else:
            for r in report["reasons"]:
                print(f"reject: {r}")

    if report.get("fail_closed"):
        return 5
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
