#!/usr/bin/env python3
"""validate.py — prove the task runs standalone and offline. The gate.

Runs inside a container with `--network=none`, mirroring heedful's egress-locked sandbox (a stdlib
script can't sever egress on macOS). No container runtime → FAIL CLOSED (no bundle).

Checks (no hidden tests — there's nothing hidden):
  - correct/ builds + tests GREEN offline  → the reference solution works and the slice is standalone.
  - task/ is in its expected starting state offline:
      fix task  (a bug + the shipped test):  tests RED  (the planted bug breaks the shipped test)  →  --task-red
      build task (solution stubbed, no tests): the project still builds/runs (GREEN)               →  default

Stdlib only. Usage:
  python3 validate.py --test CMD [--build CMD] [--correct DIR] [--task DIR] [--task-red]
                      [--language python] [--image IMG] [--runtime docker|podman] [--json]
Exit: 0 all pass · 2 a check failed · 5 no container runtime (fail-closed) · 4 usage error.
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
    return {"returncode": proc.returncode, "passed": proc.returncode == 0,
            "stdout_tail": proc.stdout[-2000:], "stderr_tail": proc.stderr[-2000:]}


def validate(test_cmd: str, build_cmd: str | None, correct_dir: str, task_dir: str | None,
             image: str, runtime: str | None, task_red: bool = False) -> dict:
    if runtime is None:
        return {"ok": False, "fail_closed": True,
                "reason": "no container runtime (docker/podman) — cannot verify offline; refusing to ship"}

    reasons: list[str] = []
    correct_run = run_offline(runtime, image, correct_dir, test_cmd, build_cmd)
    correct_passed = correct_run["passed"]
    if not correct_passed:
        reasons.append("correct/ does not build+test green offline (needs network, or the slice isn't standalone)")

    if not task_dir:  # standalone check — only prove the carved project builds+tests offline
        return {"ok": not reasons, "fail_closed": False, "reasons": reasons, "standalone": True,
                "correct_passed": correct_passed, "runtime": runtime, "image": image}

    task_run = run_offline(runtime, image, task_dir, test_cmd, build_cmd)
    task_passed = task_run["passed"]
    if task_red:  # fix task: the planted bug must make the shipped test fail
        if task_passed:
            reasons.append("task tests are GREEN — the planted bug didn't break the shipped test")
        expected = "red"
    else:  # build task: the stubbed project must still build/run
        if not task_passed:
            reasons.append("task does not build/run green — the stub broke the project (it should compile/run)")
        expected = "green"

    return {
        "ok": not reasons and correct_passed,
        "fail_closed": False,
        "reasons": reasons,
        "expected_initial_state": {"tests": expected, "matches_expected": (task_passed == (expected == "green"))},
        "correct_passed": correct_passed,
        "task_passed": task_passed,
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
        print("usage: validate.py --test CMD [--build CMD] [--correct DIR] [--task DIR] [--task-red] "
              "[--language L] [--image IMG] [--runtime R] [--json]", file=sys.stderr)
        return 4
    build_cmd = _arg("--build")
    correct_dir = _arg("--correct", "correct")
    task_dir = _arg("--task", None)
    task_red = "--task-red" in sys.argv[1:]
    language = _arg("--language", "python")
    image = _arg("--image", DEFAULT_IMAGES.get(language, "python:3.11-slim"))
    runtime = _arg("--runtime", detect_runtime())

    report = validate(test_cmd, build_cmd, correct_dir, task_dir, image, runtime, task_red)
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        if report.get("fail_closed"):
            print(f"FAIL-CLOSED: {report['reason']}")
        elif report["ok"]:
            st = report.get("expected_initial_state", {}).get("tests", "ok")
            print(f"ok — correct green; task {st} (offline, {report['image']})")
        else:
            for r in report["reasons"]:
                print(f"reject: {r}")

    if report.get("fail_closed"):
        return 5
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
