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
  this open; mid/junior: you may narrow the contract.>
- **Fix what's broken.** <If there are planted bugs: "Some behaviour is wrong / tests are failing —
  find and fix it." Describe the symptom, never the cause or location.>
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
- Install nothing — dependencies are included. **There is no internet access** beyond the AI assistant.
- Run the example tests: `<test_command>` — they show the harness and the expected I/O shape. They are
  not the full grade; passing them is a starting point, not "done".
- <build step if any: `<build_command>`>

## What we're looking for
<1–2 lines on judgment, prioritization, clean code that fits the constraints, and clear reasoning in
NOTES.md. Do NOT reveal the design, the bug, or the hidden checks.>
```

## Altitude notes (from `hiring.seniority`)
- **junior / mid** — you may keep the contract tighter and lean on "Fix what's broken" + a bounded
  "Build it"; less open design.
- **senior** — keep "Build it" open (they choose + justify the approach) and include an open-ended
  extend/scale part with no single right answer.

## Checklist before you show it to the user
- [ ] States the **problem + scenarios**, never the solution, its name, a bug location, or hidden checks.
- [ ] No reference-diff content, no source-PR text.
- [ ] **Example tests show mechanics only** — they do NOT assert the key behavioural invariants (those
      stay in the hidden suite; example tests that reveal them spoil the task).
- [ ] Asks for `NOTES.md` and permits AI use.
- [ ] The run/test command matches the offline-validated project; states the no-internet / deps-included
      constraint.
