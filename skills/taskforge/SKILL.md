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
- [ ] Phase 1 — Get a PR (a link, or offer to search)
- [ ] Phase 2 — Propose & confirm (AI summarizes + proposes the test; user confirms; collect hiring metadata)
- [ ] Phase 3 — Carve (STOP: approve the slice)
- [ ] Phase 4 — Validate standalone
- [ ] Phase 4b — Scrub (fail-closed)
- [ ] Phase 5 — Taskify (STOP: approve difficulty)
- [ ] Phase 6 — Re-validate
- [ ] Phase 7 — Brief (STOP: approve)
- [ ] Phase 8 — Package & hand off

If you loop on any phase 3 times with no progress, STOP and propose stopping or narrowing scope.

---

## Phase 0 — Preflight
Run `scripts/preflight.py`. If it exits non-zero, **STOP** and tell the user exactly what to install.
Note the container runtime it found (you'll pass it to validation).

## Phase 1 — Get a PR
The user gives **one thing: a GitHub PR.**
- If they name a PR (link or number), use it.
- If they ask you to suggest one (or have none in mind): list candidates with `gh pr list --state
  merged` / `gh search prs`, then **present 2–4 specific PRs as proposals**, each with a one-line
  reason it'd make a good self-contained task. **STOP and let the user pick one.**

**Hard rule: propose, then wait.** Until the user has chosen a PR, do NOT fetch its diff, summarize it,
design a task, or ask about the role/position. One step at a time — proposals first, nothing else.
Don't interrogate them about language/topic/stack either; you'll infer that yourself. Follow
`references/intake.md`.

## Phase 2 — Propose & confirm (+ collect hiring metadata)
1. With **read-only** `gh` calls, fetch the PR and its linked issue: `gh pr view <n> --json
   number,title,body,url`, `gh pr diff <n>`, and the issue if referenced. Keep these for the scorecard
   `source` block.
2. **You summarize, the user reacts.** Tell the user, in 3–5 lines: what the PR/issue was about, what
   language/stack it is, and **what you'd test and how** (the bug to reintroduce, or the extension to
   ask for) and the skills it assesses. Ask clarifying questions only if something is genuinely
   unclear. **STOP — the user confirms or corrects.**
3. **Collect the hiring metadata we need on our end** (for the scorecard, never candidate-facing):
   the **position** they're hiring for, **seniority**, a **job description** (ask them to paste it or
   point at a file/URL — optional), and the **time target** (~1–2h). Plus the operator's name.
Carry all of this into `meta.json` at Phase 8 (`hiring` + `assessment` + `created_by`).

## Phase 3 — Carve
Follow `references/carve-guide.md`.
1. Choose a coherent, bounded slice (usually the files the PR touched + what's needed to run them) and
   write `carve_plan.json` (files, language, build/test commands, vendor strategy, and the captured
   `source`).
2. Run `python3 scripts/validate_carve.py <repo> carve_plan.json`. Fix any rejection (too big, missing
   files, spans too much).
3. **STOP — show the user the file list and ask them to confirm the slice leaves nothing proprietary
   or sensitive they wouldn't want a candidate to see.** (Secrets are script-gated; "is this OK to
   share" is a human call.)
4. Run `python3 scripts/carve.py <repo> carve_plan.json --out correct`. It copies the slice (no
   `.git`), runs the vendor commands so deps resolve offline, and writes `source_context.json`.
   **Note (native-dep languages like Node):** vendor in the *target container*, not on the host — a
   macOS `node_modules` won't run in the Linux validation container. Set `vendor_commands` to run
   inside the image, or vendor via the container.

## Phase 4 — Validate standalone
Run `python3 scripts/validate.py --mode break_code --test "<test_command>" [--build "<build>"]
--language <lang> --correct correct` (omit `--task` for the standalone check). It runs the tests in a
`--network=none` container. If it isn't green, the slice isn't self-contained or needs network — loop
with the user (add a missing file, fix the vendor step). Exit 5 means no container runtime → STOP.

## Phase 4b — Scrub (fail-closed)
Save the fetched issue text to a file, then run
`python3 scripts/scrub.py correct --text issue=<issue.txt>`. **Any finding (exit 2 secret / exit 3
refused domain) → STOP, produce nothing.** See `references/safety.md`.

## Phase 5 — Taskify
Follow `references/task-modes.md`. Use the mode you already proposed and the user confirmed in Phase 2:
- `break_code` — introduce 1–3 small realistic defects; or
- `extend_functionality` — ask the candidate to build something new.

Write `task_plan.json`, then run `python3 scripts/taskify.py correct task_plan.json --out task`. It
produces `task/`, records the mutations, and (for `break_code`) the reference diff; it writes
`taskify_result.json`. **STOP — confirm difficulty: state your solve-time estimate (~1–2h) and the
chosen breakage/ask, and get the user's agreement.**

## Phase 6 — Re-validate
Run `python3 scripts/validate.py --mode <mode> --test "<test_command>" [--build ...] --language <lang>
--correct correct --task task --json > validate_report.json`. It confirms `correct/` is green and
`task/` is in its expected state (`break_code` → red, `extend` → green) offline. If it rejects, return
to Phase 5.

## Phase 7 — Brief
Write `task/BRIEF.md` from `references/readme-template.md`: state the **problem**, not the solution; no
spoilers from the reference diff. Include the run instructions and the no-internet note. **STOP — show
the brief and get approval.**

## Phase 8 — Package & hand off
Assemble `meta.json` from what you gathered:
- `task_id`, `language`, `build_command`, `test_command`;
- `hiring`: `{ position, seniority, job_description, time_target_hours }` (Phase 2);
- `assessment`: `{ problem_summary, test_focus, skills_assessed }` (your Phase 2 summary, as confirmed);
- `created_by`: `{ operator, email, gh_login }`; `skill_version` (frontmatter), `spec_version`,
  `created_at` (real clock); optional `reference_summary`, `notes_for_evaluator`.
Then run:
`python3 scripts/package.py --task task --taskify taskify_result.json --source source_context.json
--validate validate_report.json --meta meta.json --out task-bundle.zip`.
It re-scrubs the scorecard prose (fail-closed) and asserts the layout. Show the summary and hand the
user `task-bundle.zip` — tell them `scorecard.json` is trusted and must not be given to the candidate.

---

## References
- `references/intake.md` — get a PR, propose the task, collect hiring metadata
- `references/carve-guide.md` — carving a bounded standalone slice + per-language defaults
- `references/task-modes.md` — the break_code / extend_functionality playbooks
- `references/readme-template.md` — the candidate `BRIEF.md` template
- `references/scorecard-schema.md` — the trusted `scorecard.json` contract
- `references/safety.md` — the gates and the fail-closed rule
