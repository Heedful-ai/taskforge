#!/usr/bin/env python3
"""package.py — assemble task-bundle.zip with the pinned layout + scorecard contract (U6).

Layout (the wall between candidate-facing and trusted is structural):
  task-bundle.zip
    task/          <- candidate-facing (the project + example tests + BRIEF.md)
    scorecard.json <- TRUSTED eval record (sibling, never under task/) — carries the HIDDEN suite
    manifest.json  <- language, commands, sizes, checksums, versions

Problem-first model (schema v2): the scorecard carries the hidden `behavior_suite` (the real grade,
tiered core/stretch), the `reference_exemplar` (ONE acceptable solution, not a similarity target), a
`grading` block (behaviour + partial-credit + human rubric + NOTES eval), and `pr_suitability`.
`task_mode` is a descriptive string only (NOT in the manifest — nothing downstream may branch on it).

Before zipping it re-scrubs every scorecard prose field — including the largest new blob, the hidden
test source — and fails closed on any secret. Stdlib only.

Usage:
  python3 package.py --task DIR --taskify F --meta F [--source F] [--validate F] --out bundle.zip
Exit: 0 ok · 2 scorecard prose tripped the scrub (no zip) · 4 usage/error.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrub  # noqa: E402

SCHEMA_VERSION = "2"


def _load_hidden(taskify: dict) -> dict:
    """Read the withheld suite files from taskify's sibling hidden/ dir into the scorecard.
    Returns {core:[{path,content}], stretch:[...]}. Empty when no hidden suite was authored."""
    out = {"core": [], "stretch": []}
    hidden_dir = taskify.get("hidden_tests_dir")
    tiers = taskify.get("hidden_tiers") or {}
    if not hidden_dir:
        return out
    for tier in ("core", "stretch"):
        for rel in tiers.get(tier, []) or []:
            full = os.path.join(hidden_dir, tier, rel)
            try:
                with open(full, encoding="utf-8") as fh:
                    out[tier].append({"path": rel, "content": fh.read()})
            except OSError:
                out[tier].append({"path": rel, "content": ""})
    return out


def assemble_scorecard(taskify: dict, source: dict, validate_report: dict | None, meta: dict) -> dict:
    grading_meta = meta.get("grading") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": meta.get("task_id", ""),
        "language": meta.get("language", ""),
        "build_command": meta.get("build_command"),
        "test_command": meta.get("test_command", ""),
        "hidden_test_command": meta.get("hidden_test_command", ""),
        # descriptive ONLY — carries the calibration anchors; never a control-flow switch (U9)
        "task_mode": taskify.get("task_mode", ""),
        # ONE acceptable solution — score different-but-correct HIGHER, never a similarity target
        "reference_exemplar": {
            "diff": taskify.get("reference_exemplar"),
            "summary": meta.get("reference_summary", ""),
        },
        # the real grade — tiered, hidden, trusted-side
        "behavior_suite": _load_hidden(taskify),
        "grading": {
            "approach": "behaviour/invariants",
            "partial_credit": grading_meta.get("partial_credit",
                "verdict = core-suite pass + how far into stretch + human rubric on design & NOTES; "
                "NOT whole-suite-green (the task is intentionally bigger than finishable)"),
            "human_rubric": taskify.get("human_rubric", []) or [],
            "notes_evaluation": taskify.get("notes_evaluation", {}) or {},
        },
        "notes_required": True,
        "pr_suitability": meta.get("pr_suitability") or {"verdict": "", "reasons": []},
        "acceptance_criteria": taskify.get("acceptance_criteria", []),
        "what_to_test": taskify.get("what_to_test", []),
        "mutations": taskify.get("mutations", []),
        "extension": taskify.get("extension"),
        "scale": taskify.get("scale"),
        "seeded_failure": taskify.get("seeded_failure"),
        "expected_initial_state": (validate_report or {}).get("expected_initial_state", {}),
        "hiring": {
            "position": (meta.get("hiring") or {}).get("position", ""),
            "seniority": (meta.get("hiring") or {}).get("seniority", ""),
            "job_description": (meta.get("hiring") or {}).get("job_description", ""),
            "time_target_hours": (meta.get("hiring") or {}).get("time_target_hours"),
        },
        "assessment": {
            "problem_summary": (meta.get("assessment") or {}).get("problem_summary", ""),
            "test_focus": (meta.get("assessment") or {}).get("test_focus", ""),
            "skills_assessed": (meta.get("assessment") or {}).get("skills_assessed", []),
        },
        "source": source or {},
        "created_by": meta.get("created_by", {}),
        "skill_version": meta.get("skill_version", ""),
        "spec_version": meta.get("spec_version", ""),
        "created_at": meta.get("created_at", ""),
        "notes_for_evaluator": meta.get("notes_for_evaluator", ""),
    }


def _prose_blobs(sc: dict) -> list[tuple[str, str]]:
    """Every free-text field that could carry a secret — labelled. Every new v2 field is enumerated
    here in lockstep; a field omitted here is silently skipped by the scrub (a real leak path)."""
    out: list[tuple[str, str]] = []
    rx = sc.get("reference_exemplar") or {}
    out.append(("reference_exemplar.diff", rx.get("diff") or ""))
    out.append(("reference_exemplar.summary", rx.get("summary") or ""))
    # the hidden behaviour suite — the LARGEST new blob; test source can carry a copied key
    bs = sc.get("behavior_suite") or {}
    for tier in ("core", "stretch"):
        for i, t in enumerate(bs.get(tier) or []):
            out.append((f"behavior_suite.{tier}[{i}]", t.get("content") or ""))
    grd = sc.get("grading") or {}
    out.append(("grading.partial_credit", grd.get("partial_credit") or ""))
    out.append(("grading.notes_evaluation", json.dumps(grd.get("notes_evaluation") or {})))
    for i, r in enumerate(grd.get("human_rubric") or []):
        out.append((f"grading.human_rubric[{i}].what_good_looks_like", r.get("what_good_looks_like") or ""))
        for j, a in enumerate(r.get("acceptable_approaches") or []):
            out.append((f"grading.human_rubric[{i}].acceptable_approaches[{j}]", a or ""))
    prs = sc.get("pr_suitability") or {}
    for i, r in enumerate(prs.get("reasons") or []):
        out.append((f"pr_suitability.reasons[{i}]", r or ""))
    out.append(("notes_for_evaluator", sc.get("notes_for_evaluator") or ""))
    ext = sc.get("extension") or {}
    out.append(("extension.description", ext.get("description") or ""))
    hir = sc.get("hiring") or {}
    out.append(("hiring.job_description", hir.get("job_description") or ""))
    asmt = sc.get("assessment") or {}
    out.append(("assessment.problem_summary", asmt.get("problem_summary") or ""))
    out.append(("assessment.test_focus", asmt.get("test_focus") or ""))
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
    """Redact emails (PII) in trusted prose in place. Secrets are NOT touched here (they hard-fail
    upstream). Covers the same field set as _prose_blobs. Returns the redaction count."""
    total = 0

    def red(s):
        nonlocal total
        out, n = scrub.redact_pii(s or "")
        total += n
        return out

    rx = sc.get("reference_exemplar") or {}
    if "summary" in rx:
        rx["summary"] = red(rx.get("summary"))
    if rx.get("diff"):
        rx["diff"] = red(rx.get("diff"))
    bs = sc.get("behavior_suite") or {}
    for tier in ("core", "stretch"):
        for t in bs.get(tier) or []:
            t["content"] = red(t.get("content"))
    grd = sc.get("grading") or {}
    if "partial_credit" in grd:
        grd["partial_credit"] = red(grd.get("partial_credit"))
    for r in grd.get("human_rubric") or []:
        if "what_good_looks_like" in r:
            r["what_good_looks_like"] = red(r.get("what_good_looks_like"))
        if r.get("acceptable_approaches"):
            r["acceptable_approaches"] = [red(a) for a in r["acceptable_approaches"]]
    prs = sc.get("pr_suitability") or {}
    if prs.get("reasons"):
        prs["reasons"] = [red(x) for x in prs["reasons"]]
    sc["notes_for_evaluator"] = red(sc.get("notes_for_evaluator"))
    ext = sc.get("extension") or {}
    if "description" in ext:
        ext["description"] = red(ext.get("description"))
    hir = sc.get("hiring") or {}
    if "job_description" in hir:
        hir["job_description"] = red(hir.get("job_description"))
    asmt = sc.get("assessment") or {}
    if "problem_summary" in asmt:
        asmt["problem_summary"] = red(asmt.get("problem_summary"))
    if "test_focus" in asmt:
        asmt["test_focus"] = red(asmt.get("test_focus"))
    for m in sc.get("mutations") or []:
        m["note"] = red(m.get("note"))
    sc["what_to_test"] = [red(w) for w in sc.get("what_to_test") or []]
    src = sc.get("source") or {}
    pr, iss = src.get("pr") or {}, src.get("issue") or {}
    if pr:
        if pr.get("diff"):
            pr["diff"] = red(pr.get("diff"))
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
        # NOTE: task_mode is intentionally NOT in the manifest — the receiver must not branch on it (U9).
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
    pii_redactions = redact_scorecard_pii(scorecard)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for dirpath, _, filenames in os.walk(task_dir):
            for name in filenames:
                full = os.path.join(dirpath, name)
                arc = os.path.join("task", os.path.relpath(full, task_dir))
                z.write(full, arc)
        z.writestr("scorecard.json", json.dumps(scorecard, indent=2))
        z.writestr("manifest.json", json.dumps(manifest, indent=2))

    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
    # structural guarantees: trusted files never under task/, and the hidden suite never shipped to task/
    assert "scorecard.json" in names and not any(n.startswith("task/scorecard.json") for n in names)
    task_names = {n[len("task/"):] for n in names if n.startswith("task/")}
    bs = scorecard.get("behavior_suite") or {}
    for tier in ("core", "stretch"):
        for t in bs.get(tier) or []:
            assert t["path"] not in task_names, f"hidden suite leaked into task/: {t['path']}"
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
