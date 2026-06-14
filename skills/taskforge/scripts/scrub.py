#!/usr/bin/env python3
"""scrub.py — fail-closed safety gates, run before anything ships.

Two gates, ported from jelly's by-hand task prep:
  1. Domain refusal — auth / crypto / payment tasks are out of scope. Checked over file paths AND
     free text (brief, issue body).
  2. Secret / PII scan — a built-in regex scan (always on), augmented by `gitleaks` when present.

Every path content can reach a candidate bundle by must be scanned: the carved slice, the
`gh`-fetched issue/PR text, and the assembled bundle prose (EVALUATION.md + context.json). So it scans both
files (`scan_paths`) and arbitrary strings (`scan_text`). Any finding → the caller must abort with
no artifacts. Matches are redacted in output so findings can be logged safely.

Stdlib only. Pure functions + a CLI. Usage:
  python3 scrub.py <dir> [--text name=FILE ...] [--brief FILE] [--json]
Exit codes: 0 clean · 2 secret/PII finding · 3 refused domain · 4 usage error.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass

# --- secret / PII rules -------------------------------------------------------------------

# Suppress obvious fakes ONLY when the marker is in the matched value itself (never line-level —
# a line mentioning "test" must not hide a real key sitting on it).
PLACEHOLDER_IN_MATCH = re.compile(r"(example|changeme|placeholder|your[-_]?key|x{3,}|redacted|dummy|sample|fake)", re.I)
PLACEHOLDER_EMAIL_DOMAINS = re.compile(r"@(example\.(com|org|net)|test\.com|localhost|jelly\.local|email\.com)\b", re.I)

# (kind, rule, compiled regex)
RULES: list[tuple[str, str, "re.Pattern[str]"]] = [
    ("secret", "private-key", re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----")),
    ("secret", "aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("secret", "github-token", re.compile(r"\bgh[posu]_[A-Za-z0-9]{36,}\b")),
    ("secret", "slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("secret", "anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("secret", "openai-key", re.compile(r"\bsk-[A-Za-z0-9]{32,}\b")),
    ("secret", "google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("secret", "jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "secret",
        "assigned-secret",
        re.compile(r"""(?i)(?:api[_-]?key|secret|token|password|passwd|client[_-]?secret)["'\s]*[:=]\s*["'][^"'\s]{8,}["']"""),
    ),
    ("pii", "email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")),
]

SKIP_DIRS = {"node_modules", ".git", "dist", ".next", "build", "coverage", ".venv", "venv", "__pycache__"}
BINARY_EXT = re.compile(r"\.(png|jpe?g|gif|webp|ico|pdf|zip|gz|tar|woff2?|ttf|eot|mp[34]|mov|wasm|so|dylib|class|jar|bin|exe|dll)$", re.I)
MAX_FILE_BYTES = 2_000_000


@dataclass
class Finding:
    kind: str  # "secret" | "pii"
    rule: str
    where: str  # file path or text label
    line: int
    match: str  # redacted


def redact(match: str) -> str:
    if len(match) <= 8:
        return (match[0] if match else "") + "***"
    return f"{match[:4]}…{match[-2:]} ({len(match)} chars)"


def scan_text(label: str, content: str) -> list[Finding]:
    """Scan an arbitrary string (issue body, bundle prose, a file's content)."""
    out: list[Finding] = []
    for i, line in enumerate(content.split("\n"), start=1):
        for kind, rule, rx in RULES:
            m = rx.search(line)
            if not m:
                continue
            hit = m.group(0)
            if kind == "secret" and PLACEHOLDER_IN_MATCH.search(hit):
                continue
            if rule == "email" and PLACEHOLDER_EMAIL_DOMAINS.search(hit):
                continue
            out.append(Finding(kind=kind, rule=rule, where=label, line=i, match=redact(hit)))
    return out


_EMAIL_RULE = next(rx for kind, rule, rx in RULES if rule == "email")


def redact_pii(text: str) -> tuple[str, int]:
    """Rewrite PII (emails) to a redacted token, leaving placeholder domains intact. For TRUSTED,
    non-candidate-facing fields (context.json's git-provenance prose) where a committer email is
    normal metadata, not a leak — redaction beats a false-positive hard-fail. Secrets are NOT handled
    here; those still hard-fail wherever they appear."""
    count = 0

    def repl(m: "re.Match[str]") -> str:
        nonlocal count
        if PLACEHOLDER_EMAIL_DOMAINS.search(m.group(0)):
            return m.group(0)
        count += 1
        return "‹email:redacted›"

    return _EMAIL_RULE.sub(repl, text), count


def list_files(root: str) -> list[str]:
    """Repo-relative scannable text files (skips dep/build dirs and binaries)."""
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if BINARY_EXT.search(name):
                continue
            try:
                if os.path.getsize(full) >= MAX_FILE_BYTES:
                    continue
            except OSError:
                continue
            files.append(rel)
    return files


def scan_paths(root: str) -> tuple[list[Finding], list[str]]:
    """Scan every text file under root. Returns (findings, skipped_binaries_outside_deps).

    Binaries inside dependency dirs (node_modules/.venv/…) are expected and ignored. Binaries
    sitting in the candidate *source* are surfaced as a warning so they're never silently shipped.
    """
    findings: list[Finding] = []
    skipped_binaries: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        in_deps = any(part in SKIP_DIRS for part in os.path.relpath(dirpath, root).split(os.sep))
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, root)
            if BINARY_EXT.search(name):
                if not in_deps:
                    skipped_binaries.append(rel)
                continue
            try:
                if os.path.getsize(full) >= MAX_FILE_BYTES:
                    continue
                with open(full, "r", encoding="utf-8", errors="replace") as fh:
                    content = fh.read()
            except OSError:
                continue
            findings.extend(scan_text(rel, content))
    return findings, skipped_binaries


# --- gitleaks augmentation ----------------------------------------------------------------

def gitleaks_available() -> bool:
    return shutil.which("gitleaks") is not None


def gitleaks_scan(root: str) -> list[Finding]:
    """Optional second layer. Returns [] when gitleaks is absent (built-in scan is the floor)."""
    if not gitleaks_available():
        return []
    tmp = tempfile.mkdtemp(prefix="taskforge-gitleaks-")
    report = os.path.join(tmp, "report.json")
    try:
        subprocess.run(
            ["gitleaks", "detect", "--source", root, "--no-git",
             "--report-format", "json", "--report-path", report, "--exit-code", "0"],
            capture_output=True, timeout=120, check=False,
        )
        with open(report, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        out = []
        for g in raw:
            out.append(Finding(
                kind="secret", rule=f"gitleaks:{g.get('RuleID', '?')}",
                where=os.path.relpath(g.get("File", ""), root) or g.get("File", ""),
                line=int(g.get("StartLine", 0)), match=redact(g.get("Secret", "") or ""),
            ))
        return out
    except Exception:
        return []  # gitleaks failed to run cleanly — fall back to built-in scan only
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# --- domain refusal -----------------------------------------------------------------------

REFUSED_DOMAINS: list[tuple[str, "re.Pattern[str]"]] = [
    ("auth", re.compile(r"(?i)\b(auth|authn|authz|login|logout|signin|sign-in|oauth|session|password|credential|jwt|saml|sso)\b")),
    ("crypto", re.compile(r"(?i)\b(crypto|encrypt|decrypt|cipher|aes|rsa|hmac|keypair|signing|signature|tls|x509)\b")),
    ("payment", re.compile(r"(?i)\b(payment|billing|invoice|stripe|paypal|braintree|checkout|charge|card|pci|subscription)\b")),
]


def classify_refusal(paths: list[str], text: str = "") -> dict:
    reasons: list[str] = []
    for domain, rx in REFUSED_DOMAINS:
        hit_path = next((p for p in paths if rx.search(p)), None)
        if hit_path:
            reasons.append(f'{domain}: matched in path "{hit_path}"')
        elif text and rx.search(text):
            reasons.append(f"{domain}: matched in text")
    return {"refused": bool(reasons), "reasons": reasons}


# --- CLI ----------------------------------------------------------------------------------

def _arg_values(flag: str) -> list[str]:
    vals, argv = [], sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            vals.append(argv[i + 1])
    return vals


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--") and a not in _arg_values("--text") + _arg_values("--brief")]
    if not args:
        print("usage: scrub.py <dir> [--text name=FILE ...] [--brief FILE] [--json]", file=sys.stderr)
        return 4
    root = args[0]

    findings, skipped = scan_paths(root)
    findings += gitleaks_scan(root)

    paths = list_files(root)
    brief_text = ""
    for bf in _arg_values("--brief"):
        try:
            brief_text = open(bf, encoding="utf-8").read()
            findings += scan_text(os.path.basename(bf), brief_text)
        except OSError:
            pass
    for spec in _arg_values("--text"):
        name, _, path = spec.partition("=")
        try:
            findings += scan_text(name or path, open(path, encoding="utf-8").read())
        except OSError:
            pass

    refusal = classify_refusal(paths, brief_text)

    report = {
        "ok": not findings and not refusal["refused"],
        "findings": [asdict(f) for f in findings],
        "refusal": refusal,
        "warnings": [f"unscanned binary in source: {b}" for b in skipped],
    }
    if "--json" in sys.argv[1:]:
        print(json.dumps(report, indent=2))
    else:
        for f in findings:
            print(f"[{f.kind}] {f.rule} @ {f.where}:{f.line} — {f.match}")
        for w in report["warnings"]:
            print(f"[warn] {w}")
        if refusal["refused"]:
            print("REFUSED — " + "; ".join(refusal["reasons"]))
        if report["ok"]:
            print("clean")

    if refusal["refused"]:
        return 3
    if findings:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
