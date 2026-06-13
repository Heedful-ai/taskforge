# scorecard.json — the trusted evaluation record

`scorecard.json` is the **non-candidate-facing** record the evaluating team reads. It ships in
`task-bundle.zip` as a **sibling of `task/`**, never inside it. `package.py` assembles it and
re-scrubs every prose field before zipping. Pinned schema (`schema_version: "1"`):

```jsonc
{
  "schema_version": "1",
  "task_id": "string",
  "language": "python",
  "build_command": "string|null",
  "test_command": "string",
  "task_mode": "break_code | extend_functionality",

  // THE EXPECTATION
  "reference_solution": {
    "diff": "unified diff (task -> correct) | null",   // null for extend_functionality
    "summary": "what the intended fix / extension is"
  },
  "acceptance_criteria": [ { "id": "AC1", "description": "...", "check": "test_command|manual", "weight": 1 } ],
  "what_to_test": [ "behaviour / quality dimension", "..." ],
  "mutations": [ { "file": "...", "kind": "bug|removal", "note": "..." } ],   // [] for extend
  "expected_initial_state": { "tests": "red|green", "matches_expected": true },

  // SOURCE CONTEXT (the real PR/issue — evaluation grounding, never candidate-facing)
  "source": {
    "repo": "owner/name",
    "pr":    { "number": 0, "title": "", "description": "", "url": "", "diff": "" },
    "issue": { "number": 0, "title": "", "body": "", "url": "" }
  },
  // WHO BUILT IT
  "created_by": { "operator": "", "email": null, "gh_login": null },

  "skill_version": "string",
  "spec_version": "string",
  "created_at": "ISO-8601",            // from the host clock, never invented
  "notes_for_evaluator": "string"
}
```

## How the evaluator uses it
- `break_code`: compare the candidate's final diff against `reference_solution.diff`; run
  `test_command` for the binary checks in `acceptance_criteria`.
- `extend_functionality`: no reference diff — judge against `acceptance_criteria` + `what_to_test`
  (and any hidden `test_command` the team adds).
- `source` lets a human judge the candidate's work *against what the team actually did*.

## manifest.json (sibling, also trusted)
Carries `language`, `build_command`, `test_command`, `task_mode`, `file_count`, `total_bytes`,
per-file `checksums` (sha256), and `skill_version`/`spec_version`/`created_at` — so the receiving
side knows what to run and can verify integrity.

## Receiving side (jelly) — required before mounting
The bundle is built on a stranger's machine and may be hand-edited. Before mounting `task/`, the
receiver MUST assert `scorecard.json`/`manifest.json` are not under `task/` and guard zip extraction
against path traversal. (`package.py` guarantees the layout at creation; the receiver re-checks.)
