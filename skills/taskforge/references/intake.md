# Intake — get a PR, score it, then propose

The user gives you **one input: a PR.** You do the rest. Don't make them describe the language, the
topic, or what to test — read the PR and figure it out.

## 1. Get the PR + score suitability — propose, then wait
Ask for a GitHub PR link or number. If they don't have one (or ask you to suggest):
- find candidates: `gh pr list --state merged --limit 20`, and/or `gh search prs --merged`;
- **score each before proposing.** `gh pr view <n> --json files,additions,deletions > /tmp/pr.json`
  then `python3 scripts/score_pr.py /tmp/pr.json --json`. Drop any `hard_refuse` (refused domain, no
  carvable source, pure config/rename). Apply `references/pr-suitability.md` to the survivors.
- **present 2–4 specific PRs as a short proposal list**, each with a one-line reason it'd make a good,
  self-contained task — grounded in the suitability signals + rubric (multi-approach design content,
  carvable, real domain logic, gradeable, ~1–2h). Avoid giant/sprawling PRs and refused domains.

**Then STOP and let the user choose.** This is a hard gate: do not design a task or ask about the role
until they've picked one. Make proposals first — nothing else.

> Most merged PRs make bad tasks. Refusing the majority is the healthy outcome, not a failure — see
> `references/pr-suitability.md`.

## 2. Read it (read-only `gh`)
- `gh pr view <n> --json number,title,body,url,files`
- `gh pr diff <n>`
- if the body references an issue (`Closes #123`), `gh issue view 123 --json number,title,body,url`

Keep all of this for `context.json`'s `source` block. The diff is an **authoring aid** — never shipped
in `task/`.

## 3. Propose task OPTIONS — a menu, not one answer (problem-first)
First, one line: **what the PR was about** + the **stack** (you inferred it; don't ask).

Then present the **2–4 most substantial parts** of the PR as separate task options. Cover genuinely
different parts (different modules/behaviours/angles), not variations of one theme. **Ground every
option in `references/task-design.md`:**

- Each option presents a **problem the PR solved** — the pre-solution world + what's needed — and asks
  the candidate to **design and solve it.** **Never name the solution** (say "make brief history
  auditable + recoverable", not "implement an append-only log").
- Make it **time-filling and seniority-appropriate**: typically a build-it core + a planted bug or two
  + an extend/scale part — the candidate isn't expected to finish everything (prioritization is signal).
  Altitude follows `hiring.seniority` (junior/mid → more guided; senior → open design choice).
- For each, ~2 lines in **plain language**: which part of the PR, what the candidate designs/builds/
  fixes, the **skills assessed**, and a rough difficulty/time.

Then **STOP — let the user pick one (or combine, or adjust altitude).** Their choice becomes
`assessment.problem_summary`, `assessment.test_focus`, `assessment.skills_assessed`.

### Pick by substance, NOT by ease of testing
Choose the options that best represent the PR's **real engineering** — the interesting logic — not
whichever function is easiest to test. The offline constraint is about the **network**
(`--network=none`), **NOT** about avoiding mocks: mocking a database or API client is standard and runs
offline. **Never downgrade to a shallow slice** (e.g. "assert the prompt string contains X") just
because it has no I/O. If the meaty logic needs a mocked client, carve it *with* the mock.

## 4. Collect the hiring metadata (for our records — never candidate-facing)
Once they've confirmed the task, gather:
- **position** — the role title;
- **seniority** — junior / mid / senior (drives task altitude);
- **job description** — paste or point at a file/URL (optional);
- **time target** — intended solve time (~1–2h);
- **operator** — their name (for `created_by`).

Also record your **suitability verdict + reasons** (`pr_suitability`). Keep all of this for `meta.json`
→ `context.json`'s `hiring` + `assessment` + `pr_suitability` + `created_by` blocks. (Derive the
operator name from `git config user.name` / `gh api user` — don't ask the user for it.)
