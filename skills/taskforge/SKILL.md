---
name: taskforge
description: >-
  Build a bounded, self-contained candidate coding task (and a trusted evaluation scorecard) from
  one of the user's real GitHub issues or pull requests. Use this whenever the user wants to create,
  prepare, or generate an interview / take-home / candidate coding task, hiring task, or evaluation
  task from their repo, an issue, or a PR. Collaborative and fail-closed: it interviews the user,
  carves a standalone runnable project, turns it into a task (break working code or ask to extend
  functionality), verifies it runs offline, and packages a task-bundle.zip.
license: MIT
compatibility: Requires git, gh (authenticated), python3 (>=3.9), zip, and a container runtime (docker or podman).
metadata:
  version: "0.1.0"
  spec: agentskills.io
  homepage: https://github.com/taskforge/taskforge
---

# taskforge — build a candidate coding task from a real issue/PR

This skill turns one real GitHub issue/PR into a bounded (~1–2h) **candidate coding task** plus a
**trusted scorecard**, packaged as `task-bundle.zip`. You drive it collaboratively with the user;
deterministic bundled scripts do the fragile and safety-critical work.

> Full orchestration (the phase-by-phase instructions, checkpoints, and which script to run when)
> is authored in U2. This skeleton fixes the spec-conformant frontmatter and the phase outline so
> the skill validates and is discoverable while the scripts are built.

## Workflow at a glance

Copy this checklist into your working notes and tick each phase off; do not skip a STOP gate.

- [ ] **Phase 0 — Preflight.** Run `scripts/preflight.py`. If anything required is missing, STOP and
      tell the user exactly what to install.
- [ ] **Phase 1 — Interview.** See `references/interview.md`. Gather role, difficulty/time target,
      language, the issue/PR link, and who is building the task. STOP: confirm intent.
- [ ] **Phase 2 — Carve.** See `references/carve-guide.md`. Propose `carve_plan.json`; run
      `scripts/validate_carve.py`; STOP: user approves the slice (confirm nothing proprietary leaves);
      run `scripts/carve.py`.
- [ ] **Phase 3 — Validate standalone.** Run `scripts/validate.py` on `correct/` (offline). Loop with
      the user until it builds + tests green.
- [ ] **Phase 3b — Scrub.** Run `scripts/scrub.py` over the slice + fetched issue text. Any finding →
      STOP, fail-closed (no bundle).
- [ ] **Phase 4 — Taskify.** See `references/task-modes.md`. Propose `task_plan.json` (break_code or
      extend_functionality); STOP: user approves difficulty/mutations; run `scripts/taskify.py`.
- [ ] **Phase 5 — Re-validate.** Run `scripts/validate.py` to confirm the task is in its expected
      state and (break_code) the answer key reproduces green offline.
- [ ] **Phase 6 — Brief.** Write `task/BRIEF.md` from `references/readme-template.md`. STOP: user
      approves (de-spoilered: problem, not solution).
- [ ] **Phase 7 — Package.** Run `scripts/package.py` (re-scrubs the scorecard prose, asserts layout).
      Show the summary; hand the user `task-bundle.zip`.

## References

- `references/interview.md` — the interview script
- `references/carve-guide.md` — how to carve a standalone slice + the size caps
- `references/task-modes.md` — the break_code / extend_functionality playbooks
- `references/readme-template.md` — the candidate `BRIEF.md` template
- `references/scorecard-schema.md` — the trusted `scorecard.json` contract
- `references/safety.md` — the gates and the fail-closed rule
