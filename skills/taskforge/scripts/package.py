#!/usr/bin/env python3
"""package.py — assemble the task-bundle.zip deliverable.

Bundle layout (simple, no hidden tests, no scorecard blob, no manifest, no vendored deps):
  task-bundle.zip
    task/                   the exercise the candidate works on (source + lockfile; NO node_modules)
    EVALUATION.md           human + AI readable grading guide
    evaluation/reference/   the team's solution for the files the candidate builds/fixes
    context.json            app metadata (who, which PR, discussion summary, role)

`node_modules`/`.venv`/etc. are NOT shipped — they're vendored only for the offline validate step.
Whoever runs the task installs deps (heedful at ingest before egress-lock; a human via `npm install`).

Before zipping, the assembled prose (EVALUATION.md + context.json) is scrubbed for secrets
(fail-closed) and PII is redacted. Stdlib only.

Usage:
  python3 package.py --task DIR --correct DIR --taskify F --meta F [--source F] --out bundle.zip
Exit: 0 ok · 2 prose tripped the scrub (no zip) · 4 usage/error.
"""
from __future__ import annotations

import json
import os
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scrub  # noqa: E402

# vendored / build dirs never shipped in task/ — the lockfile is enough to reinstall
EXCLUDE_DIRS = {"node_modules", ".venv", "venv", ".git", "dist", "build", ".next", "coverage", "__pycache__"}


# Per-language default install command, so the bundle is fully install-driven (heedful's KTD3 runs
# this in a throwaway container; a human runs it by hand). Override via meta["install_command"].
DEFAULT_INSTALL = {"node": "npm ci", "python": "pip install -r requirements.txt", "ruby": "bundle install"}


def build_context(taskify: dict, source: dict, meta: dict) -> dict:
    asmt = meta.get("assessment") or {}
    language = meta.get("language", "")
    context = {
        "task_id": meta.get("task_id", ""),
        "created_at": meta.get("created_at", ""),
        "created_by": meta.get("created_by", {}),
        "source": source or {},
        "summary": meta.get("summary") or asmt.get("problem_summary", ""),
        "assessment": {
            "problem_summary": asmt.get("problem_summary", ""),
            "test_focus": asmt.get("test_focus", ""),
            "skills_assessed": asmt.get("skills_assessed", []),
        },
        "hiring": meta.get("hiring") or {},
        "pr_suitability": meta.get("pr_suitability") or {},
        # Machine-readable rubric so heedful's eval reads it structurally instead of parsing
        # EVALUATION.md prose. Same shape EVALUATION.md renders from (taskify.human_rubric).
        "rubric": taskify.get("human_rubric") or [],
        "task_mode": taskify.get("task_mode", ""),
        "language": language,
        "build_command": meta.get("build_command"),
        "install_command": meta.get("install_command") or DEFAULT_INSTALL.get(language),
        "test_command": meta.get("test_command", ""),
        "skill_version": meta.get("skill_version", ""),
        "spec_version": meta.get("spec_version", ""),
    }
    # Frontend declaration (optional): dev_command + preview_port make it a frontend task —
    # heedful serves the dev server through its preview proxy. Absent ⇒ backend task, and the
    # keys must not appear at all (field-less bundles stay field-less). validate_bundle.py
    # enforces coherence (both fields together, basePath/port agreement).
    if meta.get("dev_command") is not None or meta.get("preview_port") is not None:
        context["dev_command"] = meta.get("dev_command")
        context["preview_port"] = meta.get("preview_port")
    return context


def build_evaluation_md(taskify: dict, source: dict, meta: dict) -> str:
    asmt = meta.get("assessment") or {}
    hiring = meta.get("hiring") or {}
    muts = taskify.get("mutations", []) or []
    has_bug = any(m.get("kind") in ("bug", "removal") for m in muts)
    has_build = any(m.get("kind") == "stub" for m in muts) or taskify.get("extension") or taskify.get("scale")
    pr = (source or {}).get("pr") or {}
    repo = (source or {}).get("repo", "")

    L: list[str] = []
    L.append(f"# Evaluation guide — {meta.get('task_id','')}\n")
    src = f"{repo} PR #{pr.get('number')}" if pr.get("number") else repo
    L.append(f"Grading guide for a take-home generated from {src}. Grade it by hand with this, or feed "
             f"it to an eval agent. The candidate's exercise is in `task/`; one reference solution is in "
             f"`evaluation/reference/`.\n")

    L.append("## The problem")
    L.append((asmt.get("problem_summary") or "_(not recorded)_") + "\n")

    L.append("## What we're assessing")
    if asmt.get("test_focus"):
        L.append(asmt["test_focus"])
    if asmt.get("skills_assessed"):
        L.append(f"Skills: {', '.join(asmt['skills_assessed'])}")
    role = hiring.get("position") or ""
    sen = hiring.get("seniority") or ""
    tt = hiring.get("time_target_hours")
    L.append(f"Role: {role} ({sen}) · target ~{tt}h\n" if role else "")

    L.append("## How to grade")
    if has_bug:
        L.append("- **Fix:** the candidate fixes the planted bug(s); the test shipped in `task/` should "
                 "pass. The fix is shown in `evaluation/reference/`.")
    if has_build:
        L.append("- **Build:** the candidate designs and implements the solution. There are **no provided "
                 "tests** for it — judge the result against the problem, the rubric below, and their "
                 "`NOTES.md`. `evaluation/reference/` shows ONE acceptable approach — a cleaner, different, "
                 "correct solution should score *higher*, not be penalized.")
    L.append("")

    rubric = taskify.get("human_rubric") or []
    if rubric:
        L.append("## Rubric")
        for r in rubric:
            L.append(f"### {r.get('dimension','')}")
            if r.get("acceptable_approaches"):
                L.append(f"- Acceptable approaches: {', '.join(r['acceptable_approaches'])}")
            if r.get("what_good_looks_like"):
                L.append(f"- Good looks like: {r['what_good_looks_like']}")
        L.append("")

    ne = taskify.get("notes_evaluation") or {}
    L.append("## NOTES.md — what to look for")
    L.append(ne.get("what_to_look_for") or
             "Assumptions; the approach chosen and why (+ alternatives rejected); edge cases; and where "
             "their AI assistant was wrong and what they changed.")
    L.append("")

    bugs = [m for m in muts if m.get("kind") in ("bug", "removal")]
    if bugs:
        L.append("## Planted bugs")
        for m in bugs:
            L.append(f"- `{m.get('file')}`: {m.get('note','')} — fix shown in `evaluation/reference/{m.get('file')}`")
        L.append("")

    if taskify.get("reference_summary"):
        L.append("## Reference approach")
        L.append(taskify["reference_summary"] + "\n")

    return "\n".join(L).rstrip() + "\n"


def _prose_blobs(context: dict, evaluation_md: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = [("EVALUATION.md", evaluation_md)]
    out.append(("context.summary", context.get("summary") or ""))
    asmt = context.get("assessment") or {}
    out.append(("context.assessment.problem_summary", asmt.get("problem_summary") or ""))
    out.append(("context.assessment.test_focus", asmt.get("test_focus") or ""))
    hir = context.get("hiring") or {}
    out.append(("context.hiring.job_description", hir.get("job_description") or ""))
    prs = context.get("pr_suitability") or {}
    for i, r in enumerate(prs.get("reasons") or []):
        out.append((f"context.pr_suitability.reasons[{i}]", r or ""))
    src = context.get("source") or {}
    pr, iss = src.get("pr") or {}, src.get("issue") or {}
    out.append(("context.source.pr.description", pr.get("description") or ""))
    out.append(("context.source.pr.diff", pr.get("diff") or ""))
    out.append(("context.source.issue.body", iss.get("body") or ""))
    return out


def redact_context_pii(context: dict) -> int:
    total = 0

    def red(s):
        nonlocal total
        out, n = scrub.redact_pii(s or "")
        total += n
        return out

    # Null out operator email — gh_login + operator name are enough attribution.
    cb = context.get("created_by")
    if isinstance(cb, dict) and cb.get("email"):
        cb["email"] = None

    if "summary" in context:
        context["summary"] = red(context.get("summary"))
    asmt = context.get("assessment") or {}
    for k in ("problem_summary", "test_focus"):
        if k in asmt:
            asmt[k] = red(asmt.get(k))
    hir = context.get("hiring") or {}
    if "job_description" in hir:
        hir["job_description"] = red(hir.get("job_description"))
    prs = context.get("pr_suitability") or {}
    if prs.get("reasons"):
        prs["reasons"] = [red(x) for x in prs["reasons"]]
    src = context.get("source") or {}
    pr, iss = src.get("pr") or {}, src.get("issue") or {}
    if pr:
        if pr.get("description"):
            pr["description"] = red(pr.get("description"))
        if pr.get("diff"):
            pr["diff"] = red(pr.get("diff"))
    if iss and iss.get("body"):
        iss["body"] = red(iss.get("body"))
    return total


def _add_tree(z: zipfile.ZipFile, root: str, arc_prefix: str) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for name in filenames:
            full = os.path.join(dirpath, name)
            arc = os.path.join(arc_prefix, os.path.relpath(full, root))
            z.write(full, arc)


def write_bundle(task_dir: str, correct_dir: str, taskify: dict, context: dict,
                 evaluation_md: str, out_zip: str) -> dict:
    findings = []
    for label, text in _prose_blobs(context, evaluation_md):
        findings.extend(scrub.scan_text(label, text))
    secrets = [f for f in findings if f.kind == "secret"]
    if secrets:  # a real secret in our prose → fail closed, no zip
        return {"ok": False, "reason": "bundle prose contains a secret",
                "findings": [f"{f.rule}@{f.where}:{f.line}" for f in secrets]}
    pii_redactions = redact_context_pii(context)

    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        _add_tree(z, task_dir, "task")                          # candidate-facing (no node_modules)
        z.writestr("EVALUATION.md", evaluation_md)
        z.writestr("context.json", json.dumps(context, indent=2))
        for rel in taskify.get("reference_files", []) or []:    # the team's answer, as files
            ref = os.path.join(correct_dir, rel)
            if os.path.isfile(ref):
                z.write(ref, os.path.join("evaluation", "reference", rel))

    with zipfile.ZipFile(out_zip) as z:
        names = z.namelist()
    # the reference answer must never land in the candidate-facing task/
    assert not any(n.startswith("task/") and "/evaluation/reference/" in n for n in names)
    return {"ok": True, "out": out_zip, "entries": len(names), "pii_redactions": pii_redactions,
            "task_mode": context.get("task_mode", "")}


def _arg(flag: str, default=None):
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return default


def main() -> int:
    task_dir, correct_dir, out_zip = _arg("--task"), _arg("--correct"), _arg("--out")
    tf, sf, mf = _arg("--taskify"), _arg("--source"), _arg("--meta")
    if not all([task_dir, correct_dir, out_zip, tf, mf]):
        print("usage: package.py --task DIR --correct DIR --taskify F --meta F [--source F] --out ZIP", file=sys.stderr)
        return 4
    taskify = json.load(open(tf, encoding="utf-8"))
    source = json.load(open(sf, encoding="utf-8")) if sf and os.path.isfile(sf) else {}
    meta = json.load(open(mf, encoding="utf-8"))

    context = build_context(taskify, source, meta)
    evaluation_md = build_evaluation_md(taskify, source, meta)
    result = write_bundle(task_dir, correct_dir, taskify, context, evaluation_md, out_zip)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
