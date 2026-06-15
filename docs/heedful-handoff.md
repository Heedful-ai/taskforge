# Receiving a task-bundle (heedful's ingest)

> Reference for heedful's side — how the platform ingests a bundle for **automated** grading. (The skill
> is dual-use: a user can also grade by hand with `EVALUATION.md`. This doc is just heedful's pipeline.)

`taskforge` produces `task-bundle.zip`. The bundle is built on a stranger's machine and may be
hand-edited, so treat it as **untrusted input** at ingest.

## Layout
```
task-bundle.zip
├── task/                  mount into the recorder sandbox (the candidate's exercise)
│   ├── BRIEF.md
│   ├── <source>           a fix task ships its failing test; a build task ships none for the built part
│   └── package-lock.json  deps are NOT vendored — install them at ingest (you have network), then lock egress
├── EVALUATION.md          the grading guide (feed to the eval agent)
├── evaluation/reference/  the team's solution — ONE acceptable approach, never a similarity target
└── context.json           app metadata (provenance, source PR/issue, hiring context, run commands)
```

## Required pre-mount checks
1. **Install deps at ingest, before egress-lock.** `node_modules` isn't shipped; run `npm ci` (or the
   language equivalent from `context.json.test_command`/`build_command`) while you still have network,
   then lock egress for the candidate run.
2. **Guard extraction against path traversal / zip-slip** — refuse any entry whose normalized path
   escapes the extraction root.
3. **The reference answer is candidate-poison.** `evaluation/reference/` and `context.json.source.*`
   (the PR diff/description) are the solution and context — **never** mount them into the candidate
   sandbox or surface them in a candidate-visible log/webhook. Mount only `task/`.
4. (Recommended) **Re-run the scrub** on the received bundle — the producer-side gate ran on a machine
   we don't control.

## Grading
- **Fix task:** the candidate's submission should make the shipped test pass.
- **Build task:** there are no provided tests — grade the result against `EVALUATION.md` (the rubric +
  NOTES expectations), using `evaluation/reference/` as one acceptable approach. A cleaner,
  different, correct solution scores **higher**, not lower.
- `NOTES.md` (required of the candidate) is where the design reasoning lives — weight it.
- The task is intentionally bigger than finishable; grade the core result + how far they got + the
  reasoning, not "did everything pass."
- `context.json` is metadata for your app (who/which-PR/role) — not grading input.
