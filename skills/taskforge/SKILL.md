---
name: taskforge
description: >-
  Build a bounded, self-contained candidate coding task (and a trusted evaluation scorecard) from
  one of the user's real GitHub pull requests. Use this whenever the user wants to create, prepare,
  or generate an interview / take-home / candidate coding task, hiring task, or evaluation task from
  their repo or a PR. Collaborative and fail-closed: it scores the PR's suitability, carves a
  standalone runnable project, and turns it into a PROBLEM the candidate must design and solve
  (problem-first, not a spec to transcribe) — with hidden behaviour grading, an offline solvability
  proof, and a packaged task-bundle.zip.
license: MIT
compatibility: Requires git, gh (authenticated), python3 (>=3.9), zip, and a container runtime (docker or podman).
metadata:
  version: "0.2.0"
  spec: agentskills.io
  homepage: https://github.com/taskforge/taskforge
---

# taskforge — build a candidate coding task from a real PR

Turn one real GitHub PR into a bounded (~1–2h) **candidate coding task** plus a **trusted scorecard**,
packaged as `task-bundle.zip`. The task **presents a problem and asks the candidate to design and solve
it** — it does NOT hand them the solution. Run this collaboratively. **Deterministic bundled scripts do
the fragile and safety-critical work — run them; do not reimplement their logic.** You (the agent)
design the *task* — grounded in `references/task-design.md`, not a fixed formula.

> **What you produce.** A self-contained take-home generated from a PR, plus an answer key
> (`scorecard.json` — hidden tests, reference solution, rubric). It's **dual-use**: the user can hand
> the task to a candidate and grade it themselves with the answer key, **or** send the whole bundle to
> **jelly** for automated grading. Your job is just to generate a good task + a correct answer key.
> Don't editorialize about grading, don't emit a "how to grade" walkthrough, don't generate a grading
> script — producing the bundle is the whole job.

**Output location:** ask the user where to write output, **defaulting to the current directory**. Do
the work in a subdir there (e.g. `./taskforge-<repo>-pr<N>/`) and leave the final `task-bundle.zip` in
that location. **Never use `/tmp`** — the user should be able to find what you made. Paths below are
relative to the skill root for scripts/refs, and to that working subdir for artifacts (`correct/`,
`task/`, `hidden/`, `*.json`, the zip).

**Copy this checklist into your reply and tick each phase. Never pass a STOP gate without the user.**

- [ ] Phase 0 — Preflight
- [ ] Phase 1 — Get a PR + score suitability (STOP: user picks)
- [ ] Phase 2 — Propose problem-first task options & confirm (+ collect hiring metadata)
- [ ] Phase 3 — Carve (STOP: approve the slice)
- [ ] Phase 4 — Validate standalone
- [ ] Phase 4b — Scrub (fail-closed)
- [ ] Phase 5 — Taskify (design the spec; STOP: approve difficulty)
- [ ] Phase 6 — Re-validate (hidden-suite solvability)
- [ ] Phase 7 — Brief (STOP: approve — no spoilers)
- [ ] Phase 8 — Package & hand off

If you loop on any phase 3 times with no progress, STOP and propose stopping or narrowing scope.

---

## Phase 0 — Preflight
Run `scripts/preflight.py`. If it exits non-zero, **STOP** and tell the user exactly what to install.
Note the container runtime it found (you'll pass it to validation).

## Phase 1 — Get a PR + score its suitability
The user gives **one thing: a GitHub PR.**
- If they name a PR (link or number), use it. If they ask you to suggest one: list candidates with
  `gh pr list --state merged` / `gh search prs`.
- **Score suitability before proposing.** For each candidate, `gh pr view <n> --json
  files,additions,deletions > /tmp/pr.json` and run `python3 scripts/score_pr.py /tmp/pr.json --json`.
  **Drop any `hard_refuse` PR** (refused domain, no carvable source, pure config/rename) with a
  plain-language reason. Apply the rubric in `references/pr-suitability.md` to the survivors.
- **Present 2–4 suitable PRs as proposals**, each with a one-line reason it makes a good task (grounded
  in the suitability signals/rubric, not a hunch). **STOP and let the user pick one.**

**Hard rule: propose, then wait.** Until the user picks a PR, do NOT design a task or ask about the
role. Don't interrogate them about language/stack — infer it. See `references/intake.md`.

## Phase 2 — Propose problem-first task options & confirm (+ hiring metadata)
1. With **read-only** `gh` calls, fetch the PR and its linked issue (`gh pr view <n> --json
   number,title,body,url`, `gh pr diff <n>`, the issue if referenced). Keep these for the scorecard
   `source` block. Note: the PR diff is an **authoring aid** — never shown to the candidate.
2. **Propose task OPTIONS in plain language — a menu, not one answer.** Ground them in
   `references/task-design.md`. Each option presents a **problem the PR solved** (the pre-solution
   world + what's needed), at the altitude the role needs, and is **time-filling**: typically a build-it
   core + a planted bug or two + an extend/scale part — *the candidate isn't expected to finish all of
   it*. **Never name the solution** (don't say "implement an append-only log"; say "make brief history
   auditable and recoverable"). Cover genuinely different parts of the PR. Give skills + rough
   difficulty. **STOP — let the user pick / combine / adjust.** Choose by **substance, not ease of
   testing** (offline = `--network=none`, NOT no-mocks — mock a DB/API client and carve the meaty logic).
3. **Collect hiring metadata** (for the scorecard, never candidate-facing): **position**, **seniority**
   (drives task altitude), **job description** (paste/URL, optional), **time target** (~1–2h), operator
   name. Also record your **suitability verdict + reasons** for `pr_suitability`.
Carry all of this into `meta.json` at Phase 8.

## Phase 3 — Carve
Follow `references/carve-guide.md`. Carve the **solution world** (`correct/`) — the PR's merged state,
the "answer" the hidden suite will verify.
1. Write `carve_plan.json` (files, language, build/test commands, vendor strategy, captured `source`).
2. Run `python3 scripts/validate_carve.py <repo> carve_plan.json`. Fix any rejection.
3. **STOP — slice approval. Show the TASK, not just files.** Present (a) a short **draft of the
   candidate BRIEF** (`references/readme-template.md`) — the problem + what they design, so the user
   judges the real task; (b) the carved file list; (c) what you checked for safety. Confirm **two**
   things: *is this the right task?* and *is the slice OK to share?* Don't proceed on a file list alone.
4. Run `python3 scripts/carve.py <repo> carve_plan.json --out correct`. Copies the slice (no `.git`),
   vendors deps for offline, writes `source_context.json`. **Native-dep languages (Node):** vendor in
   the *target container*, not the host.

## Phase 4 — Validate standalone
Run `python3 scripts/validate.py --test "<test_command>" [--build "<build>"] --language <lang>
--correct correct` (omit `--task` for the standalone check). Runs in a `--network=none` container. If
not green, the slice isn't self-contained — loop with the user. Exit 5 = no runtime → STOP.

## Phase 4b — Scrub (fail-closed)
Save the fetched issue text to a file, then run `python3 scripts/scrub.py correct --text
issue=<issue.txt>`. **Any finding (exit 2 secret / exit 3 refused domain) → STOP, produce nothing.**
See `references/safety.md`.

## Phase 5 — Taskify — design the spec
Design the task per `references/task-design.md`, then express it as `task_plan.json` and run
`python3 scripts/taskify.py correct task_plan.json --out task`. The spec is **free-form** (no mode
enum); compose what the task needs:
- `mutations` — `kind:"stub"` gutters the solution to a **signature-preserving, still-compiling** TODO
  (the build-it part; gut schema/fixtures too if referenced); `kind:"bug"` plants a defect to fix.
- `strip_paths` — remove the team's own tests (they'd spoil and break the build proof).
- `example_tests` — `[{path,content}]` shipped in `task/`, **mechanics-only** (harness/IO shape, never
  the invariants).
- `hidden_tests` — `{core:[…], stretch:[…]}` authored **from the BRIEF's worked scenarios** (the
  invariant, not the team's implementation); withheld to a sibling `hidden/`.
- optional `extension`/`scale` (human-graded), `seeded_failure`, `human_rubric`, `notes_evaluation`, and
  a descriptive `task_mode` string carrying the calibration anchors.

taskify writes `task/` (problem world + example tests), the sibling `hidden/` suite, the
`reference_exemplar`, and `taskify_result.json`. **STOP — confirm difficulty in plain terms** (e.g.
"~Xh: design the history model, fix a bug, then handle concurrency") and get agreement.

## Phase 6 — Re-validate (solvability, offline)
Run `python3 scripts/validate.py --test "<test_command>" --hidden hidden --hidden-test
"<hidden_test_command>" [--build ...] --language <lang> --correct correct --task task --json >
validate_report.json`. It proves offline: `correct/` green; `task/` builds + example tests green
(RED-for-right-reason); hidden `core` GREEN on `correct/` and RED on `task/`. If it rejects (e.g. the
stub broke the build, or the suite over-fits), return to Phase 5.

## Phase 7 — Brief
Write `task/BRIEF.md` from `references/readme-template.md`: state the **problem + constraints + worked
scenarios**, never the solution; require `NOTES.md`. **STOP — show the brief and get approval.** The
no-spoiler check covers: no solution/bug-location/hidden-checks; **example tests are mechanics-only**
(don't reveal invariants); and confirm the **hidden suite asserts the invariant, not the team's
specific implementation** (a different correct solution must pass it).

## Phase 8 — Package & hand off
Assemble `meta.json`:
- `task_id`, `language`, `build_command`, `test_command`, **`hidden_test_command`**;
- `hiring`: `{ position, seniority, job_description, time_target_hours }`;
- `assessment`: `{ problem_summary, test_focus, skills_assessed }`;
- **`pr_suitability`**: `{ verdict, reasons }`; optional `grading.partial_credit`;
- `created_by`, `skill_version`, `spec_version`, `created_at` (real clock), optional `reference_summary`,
  `notes_for_evaluator`.
Then run `python3 scripts/package.py --task task --taskify taskify_result.json --source
source_context.json --validate validate_report.json --meta meta.json --out task-bundle.zip`. It embeds
the hidden suite + rubric into `scorecard.json` (trusted sibling), re-scrubs all prose (fail-closed),
and asserts the layout (hidden suite never under `task/`).

**Hand off.** Tell the user where `task-bundle.zip` is and, in one line, what's inside: `task/` is the
candidate-facing exercise (this is what you'd send a candidate); `scorecard.json` is the answer key
(reference solution + hidden tests + rubric) — grade with it yourself, or send the whole bundle to jelly
for automated grading. One practical heads-up: if you send the task to a candidate, send them `task/`,
not the scorecard. Then stop — no grading walkthrough.

---

## References
- `references/intake.md` — get a PR, score suitability, propose problem-first options, collect metadata
- `references/pr-suitability.md` — the suitability rubric (+ how `score_pr.py` feeds it)
- `references/task-design.md` — **how to design a problem-first, time-filling, seniority-appropriate task**
- `references/carve-guide.md` — carving a bounded standalone slice + per-language defaults
- `references/readme-template.md` — the candidate `BRIEF.md` template (+ required NOTES.md)
- `references/scorecard-schema.md` — the trusted `scorecard.json` contract (schema v2)
- `references/safety.md` — the gates and the fail-closed rule
