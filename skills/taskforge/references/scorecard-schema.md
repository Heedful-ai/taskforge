# scorecard.json — the trusted evaluation record (schema v2)

`scorecard.json` is the **non-candidate-facing** record the evaluating team reads. It ships in
`task-bundle.zip` as a **sibling of `task/`**, never inside it. `package.py` assembles it and re-scrubs
every prose field before zipping. The hidden **behaviour suite is the real grade and rides here** — it
is never shipped to the candidate. Pinned schema (`schema_version: "2"`):

```jsonc
{
  "schema_version": "2",
  "task_id": "string",
  "language": "python",
  "build_command": "string|null",
  "test_command": "string",              // runs the candidate's EXAMPLE tests (mechanics)
  "hidden_test_command": "string",       // runs the hidden behaviour suite (validate composes it in)

  "task_mode": "DESCRIPTIVE string only — carries the calibration anchors, e.g. 'design+fix+extend
                (senior: 1 design choice + core + concurrency stretch)'. NOT an enum, NOT a control
                switch. The receiver MUST NOT branch on it (see docs/jelly-handoff.md).",

  // ONE acceptable solution — score a different-but-correct solution HIGHER, never a similarity target
  "reference_exemplar": { "diff": "unified diff (task -> correct) over the stubbed solution | null",
                          "summary": "what the team's approach was" },

  // THE REAL GRADE — hidden, tiered, trusted-side. Never under task/.
  "behavior_suite": {
    "core":    [ { "path": "core_test.py",  "content": "…invariant tests, expected-pass…" } ],
    "stretch": [ { "path": "scale_test.py", "content": "…extend/scale, informative…" } ]
  },
  "grading": {
    "approach": "behaviour/invariants",
    "partial_credit": "verdict = core-suite pass + how far into stretch + human rubric on design &
                       NOTES; NOT whole-suite-green (the task is intentionally bigger than finishable)",
    "human_rubric": [ { "dimension": "model choice",
                        "acceptable_approaches": ["append-only log","snapshots","temporal table"],
                        "what_good_looks_like": "picks one and justifies the trade-off" } ],
    "notes_evaluation": { "what_to_look_for": "assumptions, alternatives rejected, where AI was wrong" }
  },
  "notes_required": true,                 // NOTES.md is a required, graded artifact

  "pr_suitability": { "verdict": "recommend|flag|refuse", "reasons": ["…from the rubric…"] },

  "acceptance_criteria": [ { "id": "AC_FIX|AC_EXT1", "description": "...", "check": "test_command|manual", "weight": 1 } ],
  "what_to_test": [ "behaviour / quality dimension", "..." ],
  "mutations": [ { "file": "...", "kind": "stub|bug|removal", "note": "..." } ],
  "extension": { "description": "...", "acceptance_criteria": [...] } | null,
  "scale": { "description": "..." } | null,
  "seeded_failure": { "note": "..." } | null,
  "expected_initial_state": { "tests": "red", "builds": true, "matches_expected": true },

  // HIRING CONTEXT (collected at intake)
  "hiring": { "position": "...", "seniority": "senior", "job_description": "...(optional)", "time_target_hours": 1.5 },
  // THE AI'S READ OF THE TASK (proposed at intake, user-confirmed)
  "assessment": { "problem_summary": "...", "test_focus": "...", "skills_assessed": ["..."] },

  // SOURCE CONTEXT (the real PR/issue — evaluation grounding, never candidate-facing).
  // NOTE: source.pr.diff and reference_exemplar.diff are SOLUTION-CLASS — access-control them on the
  // receiving side; never forward to the candidate sandbox/logs (docs/jelly-handoff.md).
  "source": { "repo": "owner/name",
              "pr":    { "number": 0, "title": "", "description": "", "url": "", "diff": "" },
              "issue": { "number": 0, "title": "", "body": "", "url": "" } },
  "created_by": { "operator": "", "email": null, "gh_login": null },
  "skill_version": "string", "spec_version": "string", "created_at": "ISO-8601",
  "notes_for_evaluator": "string"
}
```

## How the evaluator uses it (no task_mode branching)
- Run `behavior_suite.core` (via `hidden_test_command`) against the candidate's submission → that's the
  automated grade. `behavior_suite.stretch` is informative (partial credit).
- Apply `grading.human_rubric` to the design dimension + `grading.notes_evaluation` to `NOTES.md`.
- Treat `reference_exemplar` as **one** acceptable solution, NOT a target — a cleaner different correct
  solution scores higher.
- Grading shape is driven by the presence of `behavior_suite` + `grading.human_rubric`, **never** by
  `task_mode`. See `docs/jelly-handoff.md`.

## manifest.json (sibling, also trusted)
Carries `language`, `build_command`, `test_command`, `file_count`, `total_bytes`, per-file `checksums`
(sha256), and versions. **`task_mode` is intentionally absent** so nothing downstream can branch on it.

## Receiving side (jelly) — required before mounting
The bundle is built on a stranger's machine and may be hand-edited. Before mounting `task/`, the
receiver MUST assert `scorecard.json`/`manifest.json` and the `behavior_suite` are not under `task/`,
hard-fail on `schema_version != "2"`, and guard zip extraction against path traversal. (`package.py`
guarantees the layout at creation; the receiver re-checks.)
