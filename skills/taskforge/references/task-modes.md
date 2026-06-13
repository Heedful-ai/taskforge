# Task modes — turning the working project into a task

Two simple modes. Pick one with the user. Both must land a ~1–2h task (estimate the solve-time and
confirm it at the gate — caps bound size, not difficulty).

## `break_code` — they fix what you break
Introduce 1–3 small, realistic defects into the working code; the candidate fixes them. The
reference solution is generated automatically (the inverse of your mutation), so it always matches.

Emit `task_plan.json`:
```jsonc
{
  "mode": "break_code",
  "mutations": [
    { "file": "src/parser.py", "find": "depth + 1", "replace": "depth", "note": "off-by-one in nesting" }
  ],
  "acceptance_criteria": [
    { "id": "AC1", "description": "all tests pass", "check": "test_command", "weight": 1 }
  ],
  "what_to_test": ["correctly fixes the nesting bug", "doesn't break unrelated cases"],
  "vendored_paths": [".venv", "node_modules"]
}
```
- `find` must be an **exact substring** present in the file (the script fails if it isn't — no silent
  no-op). Keep replacements minimal and plausible (a real bug, not a syntax error).
- Good breakages make the existing tests **go red**; the candidate's job is to get them green.
- After taskify, U6 confirms the tests are red and that applying the reference diff makes them green.

## `extend_functionality` — they build something new
The project stays working; the candidate is asked (in `BRIEF.md`) to add a capability. There is **no
reference diff** — it's judged by acceptance criteria (and a `test_command` where you can express the
new behaviour as a hidden/extra test the evaluator runs).

Emit `task_plan.json`:
```jsonc
{
  "mode": "extend_functionality",
  "mutations": [],
  "acceptance_criteria": [
    { "id": "AC1", "description": "adds --json flag that prints valid JSON", "check": "manual", "weight": 1 },
    { "id": "AC2", "description": "existing tests still pass", "check": "test_command", "weight": 1 }
  ],
  "what_to_test": ["clean API for the new flag", "handles empty input", "keeps existing behaviour"],
  "vendored_paths": [".venv", "node_modules"]
}
```

## Then
- Run `scripts/taskify.py correct task_plan.json --out task`.
- **STOP — confirm difficulty with the user** (your solve-time estimate, the chosen mutation/ask).
- Proceed to U6 validation.
