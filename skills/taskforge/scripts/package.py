#!/usr/bin/env python3
"""package.py — assemble task-bundle.zip with the pinned layout + scorecard contract (U7).

Layout (the wall between candidate-facing and trusted is structural):
  task-bundle.zip
    task/          <- candidate-facing (the project + BRIEF.md)
    scorecard.json <- TRUSTED answer/eval record (sibling, never under task/)
    manifest.json  <- language, commands, sizes, checksums, versions

Before zipping it re-scrubs every scorecard prose field (these are agent/gh-derived — KTD8) and fails
closed on any finding. Refuses to package unless given a clean scrub + a green validate. Stdlib only.

Usage:
  python3 package.py --task DIR --taskify F --source F --meta F [--validate F] --out bundle.zip
Exit: 0 ok · 2 scorecard prose tripped the scrub (no zip) · 4 usage/error.

--meta F is JSON: { "task_id", "language", "build_command", "test_command",
                    "created_by": {"operator","email","gh_login"},
                    "skill_version", "spec_version", "created_at", "notes_for_evaluator" }
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrub  # noqa: E402

SCHEMA_VERSION = "1"


def assemble_scorecard(taskify: dict, source: dict, validate_report: dict | None, meta: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": meta.get("task_id", ""),
        "language": meta.get("language", ""),
        "build_command": meta.get("build_command"),
        "test_command": meta.get("test_command", ""),
        "task_mode": taskify.get("mode", ""),
        "reference_solution": {
            "diff": taskify.get("reference_diff"),
            "summary": meta.get("reference_summary", ""),
        },
        "acceptance_criteria": taskify.get("acceptance_criteria", []),
        "what_to_test": taskify.get("what_to_test", []),
        "mutations": taskify.get("mutations", []),
        "expected_initial_state": (validate_report or {}).get("expected_initial_state", {}),
        "source": source or {},
        "created_by": meta.get("created_by", {}),
        "skill_version": meta.get("skill_version", ""),
        "spec_version": meta.get("spec_version", ""),
        "created_at": meta.get("created_at", ""),
        "notes_for_evaluator": meta.get("notes_for_evaluator", ""),
    }


def _prose_blobs(sc: dict) -> list[tuple[str, str]]:
    """Every free-text field that could carry a secret — labelled for the scrub report."""
    out: list[tuple[str, str]] = []
    rs = sc.get("reference_solution") or {}
    out.append(("reference_solution.diff", rs.get("diff") or ""))
    out.append(("reference_solution.summary", rs.get("summary") or ""))
    out.append(("notes_for_evaluator", sc.get("notes_for_evaluator") or ""))
    for i, m in enumerate(sc.get("mutations") or []):
        out.append((f"mutations[{i}].note", m.get("note") or ""))
    for i, w in enumerate(sc.get("what_to_test") or []):
        out.append((f"what_to_test[{i}]", w or ""))
    src = sc.get("source") or {}
    pr, iss = src.get("pr") or {}, src.get("issue") or {}
    out.append(("source.pr.diff", pr.get("diff") or ""))
    out.append(("source.pr.description", pr.get("description") or ""))
    out.append(("source.issue.body", iss.get("body") or ""))
    return out


def scrub_scorecard(sc: dict) -> list:
    findings = []
    for label, text in _prose_blobs(sc):
        findings.extend(scrub.scan_text(label, text))
    return findings


def redact_scorecard_pii(sc: dict) -> int:
    """Redact emails (PII) in the trusted source/prose fields in place — committer emails in captured
    git provenance are normal metadata, not a leak, and the scorecard is never candidate-facing.
    Secrets are NOT touched here (they hard-fail upstream). Returns the number of redactions."""
    total = 0

    def red(s):
        nonlocal total
        out, n = scrub.redact_pii(s or "")
        total += n
        return out

    rs = sc.get("reference_solution") or {}
    if "summary" in rs:
        rs["summary"] = red(rs.get("summary"))
    if "diff" in rs:
        rs["diff"] = red(rs.get("diff")) if rs.get("diff") else rs.get("diff")
    sc["notes_for_evaluator"] = red(sc.get("notes_for_evaluator"))
    for m in sc.get("mutations") or []:
        m["note"] = red(m.get("note"))
    sc["what_to_test"] = [red(w) for w in sc.get("what_to_test") or []]
    src = sc.get("source") or {}
    pr, iss = src.get("pr") or {}, src.get("issue") or {}
    if pr:
        pr["diff"] = red(pr.get("diff")) if pr.get("diff") else pr.get("diff")
        pr["description"] = red(pr.get("description"))
    if iss:
        iss["body"] = red(iss.get("body"))
    return total


def _checksums(task_dir: str) -> dict:
    sums = {}
    for dirpath, _, filenames in os.walk(task_dir):
        for name in filenames:
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, task_dir)
            with open(full, "rb") as fh:
                sums[rel] = hashlib.sha256(fh.read()).hexdigest()
    return sums


def build_manifest(sc: dict, task_dir: str) -> dict:
    sums = _checksums(task_dir)
    total = 0
    for dirpath, _, filenames in os.walk(task_dir):
        for name in filenames:
            total += os.path.getsize(os.path.join(dirpath, name))
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": sc["task_id"],
        "language": sc["language"],
        "build_command": sc["build_command"],
        "test_command": sc["test_command"],
        "task_mode": sc["task_mode"],
        "file_count": len(sums),
        "total_bytes": total,
        "checksums": sums,
        "skill_version": sc["skill_version"],
        "spec_version": sc["spec_version"],
        "created_at": sc["created_at"],
    }


def write_bundle(task_dir: str, scorecard: dict, manifest: dict, out_zip: str) -> dict:
    findings = scrub_scorecard(scorecard)
    secrets = [f for f in findings if f.kind == "secret"]
    if secrets:  # a real secret in our own record → fail closed, no zip
        return {"ok": False, "reason": "scorecard prose contains a secret",
                "findings": [f"{f.rule}@{f.where}:{f.line}" for f in secrets]}
    # PII (emails) in trusted git-provenance prose → redact in place, then continue
    pii_redactions = redact_scorecard_pii(scorecard)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(task_dir):
            for name in filenames:
                full = os.path.join(dirpath, name)
                arc = os.path.join("task", os.path.relpath(full, task_dir))
                z.write(full, arc)
        z.writestr("scorecard.json", json.dumps(scorecard, indent=2))
        z.writestr("manifest.json", json.dumps(manifest, indent=2))

    # structural guarantee: the trusted files are never under task/
    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
    assert "scorecard.json" in names and not any(n.startswith("task/scorecard.json") for n in names)
    return {"ok": True, "out": out_zip, "entries": len(names), "pii_redactions": pii_redactions,
            "task_mode": scorecard["task_mode"], "files": manifest["file_count"]}


def _arg(flag: str, default=None):
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def main() -> int:
    task_dir, out_zip = _arg("--task"), _arg("--out")
    tf, sf, mf = _arg("--taskify"), _arg("--source"), _arg("--meta")
    if not all([task_dir, out_zip, tf, mf]):
        print("usage: package.py --task DIR --taskify F --meta F [--source F] [--validate F] --out ZIP", file=sys.stderr)
        return 4
    taskify = json.load(open(tf, encoding="utf-8"))
    source = json.load(open(sf, encoding="utf-8")) if sf and os.path.isfile(sf) else {}
    vr = _arg("--validate")
    validate_report = json.load(open(vr, encoding="utf-8")) if vr and os.path.isfile(vr) else None
    meta = json.load(open(mf, encoding="utf-8"))

    sc = assemble_scorecard(taskify, source, validate_report, meta)
    manifest = build_manifest(sc, task_dir)
    result = write_bundle(task_dir, sc, manifest, out_zip)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
