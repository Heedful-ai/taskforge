#!/usr/bin/env python3
"""preflight.py — check the host has what taskforge needs, before any work starts.

The skill runs on a stranger's machine; failing fast with an exact "install X" message beats
discovering a missing tool halfway through carving. Exits non-zero if a REQUIRED tool is absent.
Stdlib only. Usage: python3 preflight.py [--json]
"""
import json
import shutil
import subprocess
import sys


def _ok(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def _gh_authed() -> bool:
    if not _ok("gh"):
        return False
    try:
        subprocess.run(["gh", "auth", "status"], capture_output=True, timeout=15, check=True)
        return True
    except Exception:
        return False


def _python_ok() -> bool:
    return sys.version_info >= (3, 9)


def _container_runtime() -> str | None:
    """The offline build/test gate runs inside `--network=none`; we need docker or podman."""
    for rt in ("docker", "podman"):
        if _ok(rt):
            return rt
    return None


def check() -> dict:
    rt = _container_runtime()
    checks = [
        # (key, ok, required, hint)
        ("git", _ok("git"), True, "install git"),
        ("gh", _ok("gh"), True, "install GitHub CLI (https://cli.github.com)"),
        ("gh_auth", _gh_authed(), False, "run `gh auth login` (else paste issue text manually)"),
        ("python3>=3.9", _python_ok(), True, f"python {sys.version.split()[0]} too old; need >=3.9"),
        ("zip", _ok("zip"), True, "install zip"),
        ("container_runtime", rt is not None, True, "install docker or podman (offline validation needs it)"),
    ]
    results = [
        {"name": n, "ok": ok, "required": req, "hint": (None if ok else hint)}
        for (n, ok, req, hint) in checks
    ]
    missing_required = [r["name"] for r in results if r["required"] and not r["ok"]]
    return {
        "ok": not missing_required,
        "container_runtime": rt,
        "checks": results,
        "missing_required": missing_required,
    }


def main() -> int:
    report = check()
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        for c in report["checks"]:
            mark = "ok " if c["ok"] else ("MISSING" if c["required"] else "warn")
            line = f"[{mark}] {c['name']}"
            if c["hint"]:
                line += f"  — {c['hint']}"
            print(line)
        if report["missing_required"]:
            print(f"\nSTOP: missing required tools: {', '.join(report['missing_required'])}")
        else:
            print(f"\nReady. Container runtime: {report['container_runtime']}.")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
