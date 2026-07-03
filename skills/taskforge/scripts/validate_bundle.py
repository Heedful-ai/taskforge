#!/usr/bin/env python3
"""validate_bundle.py — consistency gate over an assembled bundle (dir or task-bundle.zip).

Backend bundles (no `dev_command`/`preview_port` in context.json) pass untouched — the frontend
checks simply don't apply. A FRONTEND bundle (declares a dev server) must be internally coherent:
  - `dev_command` and `preview_port` come together (one without the other is a broken declaration)
  - `preview_port` is a real TCP port (int, 1–65535)
  - `test_command` is present and runnable-looking (heedful's schema hard-requires it, and a build
    task's suite is the only automated check the template ships)
  - the baked basePath in `task/next.config.*` is exactly `/absproxy/<preview_port>` — the one
    cross-field invariant nothing else catches: if the port and the baked path disagree, the HUD
    "Open preview" button, the Ports-view links, and every root-relative asset all break.

Stdlib only. Usage:
  python3 validate_bundle.py <bundle_dir | task-bundle.zip> [--json]
Exit: 0 ok · 2 rejected · 4 usage error.
"""
from __future__ import annotations

import json
import os
import re
import sys
import zipfile

NEXT_CONFIG_NAMES = ("next.config.ts", "next.config.js", "next.config.mjs")


def _read_bundle(path: str) -> tuple[dict | None, str | None, str | None, list[str]]:
    """Return (context, next_config_text, next_config_name, reasons) from a dir or a zip."""
    reasons: list[str] = []
    context = None
    cfg_text = cfg_name = None

    if os.path.isfile(path) and path.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            names = set(z.namelist())
            if "context.json" not in names:
                reasons.append("bundle has no context.json at the root")
            else:
                context = json.loads(z.read("context.json"))
            for name in NEXT_CONFIG_NAMES:
                arc = f"task/{name}"
                if arc in names:
                    cfg_text, cfg_name = z.read(arc).decode("utf-8", errors="replace"), arc
                    break
    elif os.path.isdir(path):
        ctx_path = os.path.join(path, "context.json")
        if not os.path.isfile(ctx_path):
            reasons.append("bundle has no context.json at the root")
        else:
            with open(ctx_path, encoding="utf-8") as fh:
                context = json.load(fh)
        for name in NEXT_CONFIG_NAMES:
            full = os.path.join(path, "task", name)
            if os.path.isfile(full):
                with open(full, encoding="utf-8", errors="replace") as fh:
                    cfg_text = fh.read()
                cfg_name = f"task/{name}"
                break
    else:
        reasons.append(f"not a bundle dir or .zip: {path}")

    return context, cfg_text, cfg_name, reasons


def _baked_base_path(config_text: str) -> str | None:
    """The basePath the config falls back to when no env override is set — the last string
    literal in the basePath expression (e.g. `process.env.X ?? "/absproxy/3000"` → the literal)."""
    m = re.search(r"basePath\s*:\s*([^,\n]+)", config_text)
    if not m:
        return None
    literals = re.findall(r"""["'](/[^"']*)["']""", m.group(1))
    return literals[-1] if literals else None


def validate(bundle_path: str) -> dict:
    context, cfg_text, cfg_name, reasons = _read_bundle(bundle_path)
    if context is None:
        return {"ok": False, "frontend": False, "reasons": reasons}

    dev_command = context.get("dev_command")
    preview_port = context.get("preview_port")
    frontend = dev_command is not None or preview_port is not None
    if not frontend:  # backend bundle — nothing changes, frontend checks don't apply
        return {"ok": not reasons, "frontend": False, "reasons": reasons}

    if dev_command is None:
        reasons.append("preview_port declared without dev_command — a preview needs the command that serves it")
    elif not (isinstance(dev_command, str) and dev_command.strip()):
        reasons.append("dev_command must be a non-empty string")

    if preview_port is None:
        reasons.append("dev_command declared without preview_port — the proxy chain needs the port")
    elif not (isinstance(preview_port, int) and not isinstance(preview_port, bool)
              and 1 <= preview_port <= 65535):
        reasons.append(f"preview_port must be an integer TCP port (1–65535), got {preview_port!r}")

    test_command = context.get("test_command")
    if not (isinstance(test_command, str) and test_command.strip()):
        reasons.append("frontend bundle needs a runnable test_command — heedful hard-requires it, "
                       "and the template's suite is the only automated check it ships")

    # The cross-field invariant: baked basePath must be /absproxy/<preview_port>.
    if isinstance(preview_port, int) and not isinstance(preview_port, bool):
        if cfg_text is None:
            reasons.append("frontend bundle has no task/next.config.(ts|js|mjs) — the template must "
                           "bake basePath for the proxy chain")
        else:
            expected = f"/absproxy/{preview_port}"
            baked = _baked_base_path(cfg_text)
            if baked is None:
                reasons.append(f"{cfg_name} has no baked basePath string — expected a "
                               f'"{expected}" fallback')
            elif baked != expected:
                reasons.append(f"{cfg_name} bakes basePath {baked!r} but preview_port is {preview_port} — "
                               f"they must agree ({expected!r}) or the preview button, Ports links and "
                               f"assets all break")

    return {"ok": not reasons, "frontend": True, "reasons": reasons}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print("usage: validate_bundle.py <bundle_dir | task-bundle.zip> [--json]", file=sys.stderr)
        return 4

    report = validate(args[0])
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        if report["ok"]:
            kind = "frontend" if report["frontend"] else "backend"
            print(f"ok — {kind} bundle is coherent")
        else:
            for r in report["reasons"]:
                print(f"reject: {r}")
    return 0 if report["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
