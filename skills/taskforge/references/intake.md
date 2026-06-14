# Intake — get a PR, then propose

The user gives you **one input: a PR.** You do the rest. Don't make them describe the language, the
topic, or what to test — read the PR and figure it out.

## 1. Get the PR — propose, then wait
Ask for a GitHub PR link or number. If they don't have one (or ask you to suggest):
- find candidates: `gh pr list --state merged --limit 20`, and/or `gh search prs --merged`;
- **present 2–4 specific PRs as a short proposal list**, each with a one-line reason it'd make a good,
  self-contained task (a bounded bug fix or small feature on a module with tests — those carve
  cleanly). Avoid giant PRs, pure config, and auth/crypto/payment topics (the scrub refuses those).

**Then STOP and let the user choose.** This is a hard gate: do not fetch the diff, summarize, design a
task, or ask anything about the role until they've picked one of your proposals. Make proposals first
— nothing else.

## 2. Read it (read-only `gh`)
- `gh pr view <n> --json number,title,body,url,files`
- `gh pr diff <n>`
- if the body references an issue (`Closes #123`), `gh issue view 123 --json number,title,body,url`

Keep all of this for the scorecard `source` block.

## 3. Propose task OPTIONS — a menu, not one answer
First, one line: **what the PR was about** + the **stack** (you inferred it; don't ask).

Then, for anything but a trivial PR: a single PR usually contains several distinct, interesting pieces
of engineering. **Identify the 2–4 most substantial ones and present them as separate task options for
the user to choose from.** Do NOT converge on one, and do NOT quietly pick the easiest piece. Cover
genuinely different parts of the PR (different modules/behaviours/angles), not variations of one theme.

For each option, ~2 lines:
- **Which part of the PR** it's built on — name the module / function / behaviour.
- **Mode** — `break_code` (reintroduce a defect to fix) or `extend_functionality` (ask them to build
  something) — and **what you'd test**, plus the **skills assessed** and a rough difficulty/time.

**Offer both modes — never silently default to `break_code`.** For the same piece of logic you can
often frame *either* a break-task *or* an extend-task; where the PR supports it, include at least one
`extend_functionality` option in the menu so the user actually gets to choose the mode, not just the
topic. The mode is the user's decision.

Then **STOP — let the user pick one (or combine).** Their choice (topic **and** mode) becomes
`assessment.problem_summary`, `assessment.test_focus`, `assessment.skills_assessed`. Ask a clarifying
question only if something is genuinely ambiguous.

### Pick by substance, NOT by ease of testing
Choose the options that best represent the PR's **real engineering** — the interesting logic — not
whichever function is easiest to test. The offline constraint is about the **network**
(`--network=none`), **NOT** about avoiding mocks: mocking a database or API client (a Supabase/HTTP/SDK
client, etc.) is standard and runs offline perfectly. **Never downgrade to a shallow slice** (e.g.
"assert the prompt string contains X") just because it has no I/O — that tests almost nothing of the
PR. If the meaty logic needs a mocked client, that's fine — carve it *with* the mock and propose it.

## 4. Collect the hiring metadata (for our records — never candidate-facing)
Once they've confirmed the task, gather:
- **position** — the role title they're hiring for;
- **seniority** — junior / mid / senior;
- **job description** — ask them to paste it or point at a file/URL (optional, but get it if they have it);
- **time target** — intended solve time (~1–2h);
- **operator** — their name (for `created_by`).

Keep these for `meta.json` → the scorecard's `hiring` + `created_by` blocks. This is data we want on
our end to evaluate results well.
