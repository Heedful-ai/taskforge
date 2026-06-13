# Intake — get a PR, then propose

The user gives you **one input: a PR.** You do the rest. Don't make them describe the language, the
topic, or what to test — read the PR and figure it out.

## 1. Get the PR
Ask for a GitHub PR link or number. If they don't have one:
- offer to find candidates: `gh pr list --state merged --limit 20`, and/or `gh search prs --merged`;
- suggest 2–3 that look like **self-contained, testable** changes (a bounded bug fix or a small
  feature on a module with tests) — those carve cleanly. Avoid giant PRs, pure config, and
  auth/crypto/payment topics (the scrub will refuse those anyway).

## 2. Read it (read-only `gh`)
- `gh pr view <n> --json number,title,body,url,files`
- `gh pr diff <n>`
- if the body references an issue (`Closes #123`), `gh issue view 123 --json number,title,body,url`

Keep all of this for the scorecard `source` block.

## 3. Propose — you summarize, the user reacts
Tell the user, in ~3–5 lines:
- **What it was about** — the problem the PR/issue solved, in plain language.
- **Stack** — the language/framework (you inferred it; don't ask).
- **What you'd test and how** — the specific bug you'd reintroduce (`break_code`) or the feature
  you'd ask them to build (`extend_functionality`), and roughly how long it should take.
- **Skills assessed** — e.g. debugging, reading unfamiliar code, date/time correctness, API design.

Ask a clarifying question only if something is genuinely ambiguous. Then **STOP — the user confirms or
corrects.** This becomes `assessment.problem_summary`, `assessment.test_focus`,
`assessment.skills_assessed`.

## 4. Collect the hiring metadata (for our records — never candidate-facing)
Once they've confirmed the task, gather:
- **position** — the role title they're hiring for;
- **seniority** — junior / mid / senior;
- **job description** — ask them to paste it or point at a file/URL (optional, but get it if they have it);
- **time target** — intended solve time (~1–2h);
- **operator** — their name (for `created_by`).

Keep these for `meta.json` → the scorecard's `hiring` + `created_by` blocks. This is data we want on
our end to evaluate results well.
