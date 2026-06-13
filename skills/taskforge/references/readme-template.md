# Candidate BRIEF.md template

`task/BRIEF.md` is the only instruction the candidate sees. State the **problem**, never the
solution. Do not paste anything from the reference diff or the source PR description. Keep it short.

## break_code template

```markdown
# <task title — name the symptom, not the fix>

## Context
<1–3 sentences: what this small project does. Plain, candidate-facing.>

## Your task
Something here is broken. <Describe the observable symptom: failing tests / wrong output / a bug
report — NOT the cause or the fix.> Find it and fix it. Keep your change focused.

## Running it
- Install nothing — dependencies are included. **There is no internet access** beyond the AI
  assistant; everything you need is in this folder.
- Run the tests: `<test_command>`
- <build step if any: `<build_command>`>

## What we're looking for
<1–2 lines on the qualities being assessed: a correct, minimal fix; clear reasoning; doesn't break
unrelated behaviour. Do NOT reveal the specific bug.>
```

## extend_functionality template

```markdown
# <task title — name the capability to add>

## Context
<1–3 sentences: what this small project does today.>

## Your task
Add the following: <clear, bounded description of the new behaviour / feature / flag>. <Acceptance in
the candidate's words: "running X should produce Y".>

## Running it
- Install nothing — dependencies are included. **There is no internet access** beyond the AI
  assistant.
- Run the tests: `<test_command>`
- <build step if any>

## What we're looking for
<1–2 lines: clean design, handles edge cases, keeps existing behaviour, adds tests.>
```

Checklist before you show it to the user:
- [ ] No solution, no fix location, no reference-diff content, no source-PR text.
- [ ] The run/test command is correct and matches the offline-validated project.
- [ ] States the no-internet / deps-included constraint.
