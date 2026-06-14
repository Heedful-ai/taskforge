# Candidate BRIEF.md template

`task/BRIEF.md` is the only instruction the candidate sees. State the **problem**, never the solution.
Do not paste anything from the reference diff or the source PR description. Keep it short.

The default task has **two parts** — fix the bug(s), then build the extension.

## Default template (fix + extend)

```markdown
# <task title — name the area, e.g. "Brief versioning">

## Context
<1–3 sentences: what this small project does. Plain, candidate-facing.>

## Part 1 — Fix what's broken
The test suite is failing. <Describe the observable symptom — failing tests / wrong behaviour — NOT
the cause or the fix.> Find the bug(s) and fix them. Keep your changes focused; don't change the tests.

## Part 2 — Build an extension
Then add the following: <clear, bounded description of the new capability>. <Acceptance in the
candidate's words: "calling X should do Y".> Add tests for your new behaviour.

## Running it
- Install nothing — dependencies are included. **There is no internet access** beyond the AI assistant.
- Run the tests: `<test_command>`
- <build step if any: `<build_command>`>

## What we're looking for
<1–2 lines: a correct, minimal fix; a clean extension that fits the existing design; no regressions.
Do NOT reveal the specific bug.>
```

## Single-part variants (only if the user chose one)
- **Bugs only** — keep Context + Part 1 + Running + What we're looking for; drop Part 2.
- **Extension only** — keep Context + Part 2 (rename to "Your task") + Running; drop Part 1.

Checklist before you show it to the user:
- [ ] No solution, no fix location, no reference-diff content, no source-PR text.
- [ ] The run/test command matches the offline-validated project.
- [ ] States the no-internet / deps-included constraint.
