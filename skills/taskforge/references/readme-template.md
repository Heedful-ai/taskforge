# Candidate BRIEF.md template

`task/BRIEF.md` is the only instruction the candidate sees. **Present the problem + constraints +
worked scenarios — never the solution.** Don't name the design, don't paste the reference diff or the
source-PR description, don't reveal a bug's location. See `references/task-design.md` for *why* (problem-
first measures seniority; naming the solution makes it transcription).

The BRIEF is composed, not filled in from a fixed mould — the parts below are building blocks. Use the
ones the task needs, at the altitude the role needs (junior/mid → more guided; senior → problem-only +
design choice). Aim for a task that's **bigger than finishable** — prioritization is part of the signal.

## Template

```markdown
# <task title — name the area, not the solution, e.g. "Brief history">

## Context
<1–3 sentences: what this small project does and the business motivation — why this problem matters.
Plain, candidate-facing.>

## The problem
<Describe the problem and the constraints, NOT the solution or its name. Give the observable symptoms
and the requirements as outcomes: "we need to (a)…, (b)…, (c)…">

### Worked scenarios
<2–4 concrete input→expected-output examples that pin the contract without prescribing the design.
e.g. "After edits E1,E2,E3 then deleting entry X: the current view shows …; the view at version 2
shows …; X can be recovered as …">

## Your task
<Compose the asks the task needs — examples:>
- **Build it.** Implement a model/solution that satisfies the scenarios above. **You choose the
  approach** — there are several reasonable ones; pick one and justify it in NOTES.md. <senior: keep
  this open; mid/junior: you may narrow the contract.> <No tests are provided for this — you decide how
  to verify it.>
- **Fix what's broken.** <If there are planted bugs: "A test is failing — find the bug and fix it."
  Describe the symptom, never the cause or location. The failing test ships with the task.>
- **Then extend / scale.** <A forward-looking harder part: a new requirement, concurrency, large
  inputs, recovery. State it as an outcome.>

You are **not expected to finish everything.** Prioritize, and note in NOTES.md what you'd do next and
why.

## NOTES.md (required)
Add a `NOTES.md` with:
- assumptions you made;
- the approach you chose **and why** — and the alternatives you considered and rejected;
- edge cases you handled or knowingly skipped;
- **where your AI assistant was wrong or unhelpful, and what you changed.**
Using an AI assistant is expected and fine — we want your judgment about it.

## Running it
- Install dependencies: `<install command, e.g. npm install>`.
- <Run the tests: `<test_command>` — only if the task ships a test (a fix task does; a pure build task
  doesn't).>
- <build/run step if any: `<build_command>`>

<!-- FRONTEND TASKS ONLY: when the bundle declares `dev_command`, the run instruction below is
     rendered FROM that field — never write a different command here (the field and what the
     candidate is told must not drift). Include all four notes; the first two save candidates
     from wrongly concluding the environment is broken. -->
- Start the dev server: `<dev_command, e.g. npm run dev>`, then click **Open preview** in the
  status bar (or use the Ports view) to open the app in a browser tab.
- The **first page load can take a couple of minutes** while the dev server compiles — that's
  normal, not a broken environment. Later loads and hot reload are fast.
- The app is served **under a proxy path** on port `<preview_port>` (you'll see something like
  `/absproxy/<preview_port>/` in the URL) — that's expected; the project is pre-configured for it
  and you don't need to change any config.
- You may see a few 404s from the dev overlay in the browser console — a known cosmetic Next.js
  issue behind a path prefix. Harmless; ignore them.

## What we're looking for
<1–2 lines on judgment, prioritization, clean code that fits the constraints, and clear reasoning in
NOTES.md. Do NOT reveal the design or the bug's location.>
```

> **Do not mention the sandbox.** The candidate may run this anywhere with normal internet — don't write
> "no internet access" or "runs offline" (that's *our* eval sandbox, not a task requirement, and it
> reads as "build an offline-first app"). Just normal setup: install deps, run it.

## Altitude notes (from `hiring.seniority`)
- **junior / mid** — you may keep the contract tighter and lean on "Fix what's broken" + a bounded
  "Build it"; less open design.
- **senior** — keep "Build it" open (they choose + justify the approach) and include an open-ended
  extend/scale part with no single right answer.

## Checklist before you show it to the user
- [ ] States the **problem + scenarios**, never the solution, its name, or a bug's location.
- [ ] No reference-diff content, no source-PR text.
- [ ] A **fix** task ships its failing test; a **build** task ships no tests for the part being built.
- [ ] No "offline / no internet" language — that's the eval sandbox, not the candidate's concern.
- [ ] Asks for `NOTES.md` and permits AI use.
