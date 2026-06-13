#!/usr/bin/env python3
"""validate.py — prove the task runs standalone and offline, and is solvable (U6). The gate.

Runs build+test inside a container with `--network=none`, mirroring jelly's egress-locked sandbox —
NOT a best-effort env trick (a stdlib script can't sever egress on macOS). If no container runtime is
available, it FAILS CLOSED (no bundle) rather than passing an unverified check.

Checks:
  - correct/ builds + tests GREEN offline  → the reference solution reproduces (correct is what the
    difflib reference_diff reconstructs from task, so a green correct == a green answer key);
  - task/ is in its expected initial state: break_code → tests RED; extend_functionality → GREEN;
  - records expected_initial_state for the scorecard.

Stdlib only. Usage:
  python3 validate.py --mode break_code --test "python3 -m unittest" [--build CMD]
                      [--correct DIR] [--task DIR] [--language python] [--image IMG]
                      [--runtime docker|podman] [--json]
Exit: 0 all checks pass · 2 a check failed · 5 no container runtime (fail-closed) · 4 usage error.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

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


def validate(mode: str, test_cmd: str, build_cmd: str | None, correct_dir: str, task_dir: str,
             image: str, runtime: str | None) -> dict:
    if runtime is None:
        return {"ok": False, "fail_closed": True,
                "reason": "no container runtime (docker/podman) — cannot verify offline; refusing to ship"}

    reasons: list[str] = []
    correct_run = run_offline(runtime, image, correct_dir, test_cmd, build_cmd)
    if not correct_run["passed"]:
        reasons.append("correct/ does not build+test green offline (needs network, or the slice isn't standalone)")

    task_run = run_offline(runtime, image, task_dir, test_cmd, build_cmd)
    if mode == "break_code":
        expected = "red"
        if task_run["passed"]:
            reasons.append("break_code task tests are GREEN — the breakage didn't make tests fail")
    else:  # extend_functionality
        expected = "green"
        if not task_run["passed"]:
            reasons.append("extend_functionality task tests are RED — the project should still work")

    expected_initial_state = {
        "tests": "red" if not task_run["passed"] else "green",
        "matches_expected": (task_run["passed"]) == (expected == "green"),
    }

    return {
        "ok": not reasons,
        "fail_closed": False,
        "reasons": reasons,
        "expected_initial_state": expected_initial_state,
        "correct_passed": correct_run["passed"],
        "task_passed": task_run["passed"],
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
    mode = _arg("--mode")
    test_cmd = _arg("--test")
    if not mode or not test_cmd:
        print("usage: validate.py --mode break_code|extend_functionality --test CMD [...]", file=sys.stderr)
        return 4
    build_cmd = _arg("--build")
    correct_dir = _arg("--correct", "correct")
    task_dir = _arg("--task", "task")
    language = _arg("--language", "python")
    image = _arg("--image", DEFAULT_IMAGES.get(language, "python:3.11-slim"))
    runtime = _arg("--runtime", detect_runtime())

    report = validate(mode, test_cmd, build_cmd, correct_dir, task_dir, image, runtime)
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        if report.get("fail_closed"):
            print(f"FAIL-CLOSED: {report['reason']}")
        elif report["ok"]:
            print(f"ok — correct green, task {report['expected_initial_state']['tests']} (offline, {report['image']})")
        else:
            for r in report["reasons"]:
                print(f"reject: {r}")

    if report.get("fail_closed"):
        return 5
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
