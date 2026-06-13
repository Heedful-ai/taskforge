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

Turn one real GitHub issue/PR into a bounded (~1–2h) **candidate coding task** plus a **trusted
scorecard**, packaged as `task-bundle.zip`. Run this collaboratively with the user. **Deterministic
bundled scripts do the fragile and safety-critical work — run them; do not reimplement their logic.**

Work in a scratch dir (e.g. `./work`). Paths below are relative to the skill root for scripts/refs,
and to the scratch dir for artifacts (`correct/`, `task/`, `*.json`, the zip).

**Copy this checklist into your reply and tick each phase. Never pass a STOP gate without the user.**

- [ ] Phase 0 — Preflight
- [ ] Phase 1 — Interview (STOP: confirm intent)
- [ ] Phase 2 — Carve (STOP: approve the slice)
- [ ] Phase 3 — Validate standalone
- [ ] Phase 3b — Scrub (fail-closed)
- [ ] Phase 4 — Taskify (STOP: approve difficulty)
- [ ] Phase 5 — Re-validate
- [ ] Phase 6 — Brief (STOP: approve)
- [ ] Phase 7 — Package & hand off

If you loop on any phase 3 times with no progress, STOP and propose stopping or narrowing scope.

---

## Phase 0 — Preflight
Run `scripts/preflight.py`. If it exits non-zero, **STOP** and tell the user exactly what to install.
Note the container runtime it found (you'll pass it to validation).

## Phase 1 — Interview
Follow `references/interview.md`. Collect: the role/skills to test; a difficulty/time target
(junior/mid/senior → ~1–2h); the **GitHub issue or PR link**; the language/stack if the repo is
polyglot; and **who is building this task** (operator name, optionally email / `gh` login — this goes
in the scorecard's `created_by`, for the evaluating team's records, never shown to the candidate).
**STOP — read back your understanding and get a yes before continuing.**

## Phase 2 — Carve
Follow `references/carve-guide.md`.
1. With **read-only** `gh` calls, capture the issue (and PR, if any) — title, body, url, and the PR
   diff. Keep these for the scorecard `source` block (evaluation context, not candidate-facing).
2. Choose a coherent, bounded slice and write `carve_plan.json` (files, language, build/test commands,
   vendor strategy, and the captured `source`).
3. Run `python3 scripts/validate_carve.py <repo> carve_plan.json`. Fix any rejection (too big, missing
   files, spans too much).
4. **STOP — show the user the file list and ask them to confirm the slice leaves nothing proprietary
   or sensitive they wouldn't want a candidate to see.** (Secrets are script-gated; "is this OK to
   share" is a human call.)
5. Run `python3 scripts/carve.py <repo> carve_plan.json --out correct`. It copies the slice (no
   `.git`), runs the vendor commands so deps resolve offline, and writes `source_context.json`.

## Phase 3 — Validate standalone
Run `python3 scripts/validate.py --mode break_code --test "<test_command>" [--build "<build>"]
--language <lang> --correct correct` (omit `--task` for the standalone check). It runs the tests in a
`--network=none` container. If it isn't green, the slice isn't self-contained or needs network — loop
with the user (add a missing file, fix the vendor step). Exit 5 means no container runtime → STOP.

## Phase 3b — Scrub (fail-closed)
Save the fetched issue text to a file, then run
`python3 scripts/scrub.py correct --text issue=<issue.txt>`. **Any finding (exit 2 secret / exit 3
refused domain) → STOP, produce nothing.** See `references/safety.md`.

## Phase 4 — Taskify
Follow `references/task-modes.md`. Pick a mode with the user:
- `break_code` — introduce 1–3 small realistic defects; or
- `extend_functionality` — ask the candidate to build something new.

Write `task_plan.json`, then run `python3 scripts/taskify.py correct task_plan.json --out task`. It
produces `task/`, records the mutations, and (for `break_code`) the reference diff; it writes
`taskify_result.json`. **STOP — confirm difficulty: state your solve-time estimate (~1–2h) and the
chosen breakage/ask, and get the user's agreement.**

## Phase 5 — Re-validate
Run `python3 scripts/validate.py --mode <mode> --test "<test_command>" [--build ...] --language <lang>
--correct correct --task task --json > validate_report.json`. It confirms `correct/` is green and
`task/` is in its expected state (`break_code` → red, `extend` → green) offline. If it rejects, return
to Phase 4.

## Phase 6 — Brief
Write `task/BRIEF.md` from `references/readme-template.md`: state the **problem**, not the solution; no
spoilers from the reference diff. Include the run instructions and the no-internet note. **STOP — show
the brief and get approval.**

## Phase 7 — Package & hand off
Assemble `meta.json` (task_id, language, build/test commands, `created_by`, `skill_version` from this
file's frontmatter, `spec_version`, `created_at` from the real clock, optional `reference_summary` and
`notes_for_evaluator`). Then run:
`python3 scripts/package.py --task task --taskify taskify_result.json --source source_context.json
--validate validate_report.json --meta meta.json --out task-bundle.zip`.
It re-scrubs the scorecard prose (fail-closed) and asserts the layout. Show the summary and hand the
user `task-bundle.zip` — tell them `scorecard.json` is trusted and must not be given to the candidate.

---

## References
- `references/interview.md` — the interview script
- `references/carve-guide.md` — carving a bounded standalone slice + per-language defaults
- `references/task-modes.md` — the break_code / extend_functionality playbooks
- `references/readme-template.md` — the candidate `BRIEF.md` template
- `references/scorecard-schema.md` — the trusted `scorecard.json` contract
- `references/safety.md` — the gates and the fail-closed rule
