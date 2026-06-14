# Building the task — fix some bugs AND build an extension (default)

**Default task = both:** plant **one or two bugs** for the candidate to find and fix, **and** ask them
to **build a small extension** on the system. Fixing bugs alone is too shallow — it shows debugging but
not whether they can actually build. The combination shows both. Only drop to one half if the user
explicitly wants that.

**Talk to the user in plain language.** Never say "break_code" / "extend_functionality" /
"fix_and_extend" — those are internal labels. Say things like: *"the candidate fixes two planted bugs
in the versioning logic, then adds support for X"*.

You emit a single `task_plan.json` carrying the bug(s) and the extension:

```jsonc
{
  "mutations": [   // the bug(s) to fix — exact-substring edits to the working code
    { "file": "src/versioning.ts", "find": "deleted_at: null", "replace": "deleted_at: undefined",
      "note": "tombstone delete writes the wrong field, so deletes don't take" }
  ],
  "extension": {   // the build-something ask (no code change to correct/ — it's forward-looking)
    "description": "Add a `restoreEntry(id)` that revives a tombstoned entry as a new active version.",
    "acceptance_criteria": [
      { "id": "AC_EXT1", "description": "restoreEntry creates a new active version of a deleted entry", "check": "manual", "weight": 1 },
      { "id": "AC_EXT2", "description": "existing tests still pass", "check": "test_command", "weight": 1 }
    ]
  },
  "what_to_test": ["the fix is minimal and correct", "the extension follows the append-only model", "no regressions"],
  "vendored_paths": ["node_modules"]
}
```

Rules:
- **Bugs (`mutations`):** 1–2 small, realistic defects in the *interesting* logic (not cosmetic). `find`
  must be an **exact substring** in the file (the script fails if it isn't — no silent no-op). A good
  bug makes the existing tests **go red**; the candidate's job is to get them green.
- **Extension:** a bounded "now build X" that fits the same module and the ~1–2h budget. It needs **no
  change to `correct/`** — it's what the candidate adds. Capture it as `extension.description` + its
  own `acceptance_criteria` (use `check: "test_command"` when you can express it as a hidden test the
  evaluator runs, else `manual`).
- The skill derives the internal mode automatically (`fix_and_extend` when both are present). The
  bug-fix reference diff is generated from the mutations; the extension is judged by its criteria.

## Variants (only if the user asks)
- **Bugs only** — omit `extension`. (Shallower; default against this.)
- **Extension only** — omit `mutations`; the project stays green and they build the new thing.

## Then
- Run `scripts/taskify.py correct task_plan.json --out task`.
- **STOP — confirm difficulty in plain terms:** "this should take ~Xh — fixing the Y bug(s) plus
  building Z. Good?" Get the user's agreement.
