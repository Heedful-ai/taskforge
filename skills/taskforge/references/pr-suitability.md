# Is this PR a good task source? — the suitability rubric

**Most merged PRs make terrible tasks** (trivial, sprawling, the hard part lived in a Slack thread, or
one-shottable). Don't rely on cherry-picking. Score every candidate PR against this rubric **before**
you carve, and **refuse or flag** the weak ones.

Two layers:

1. **`scripts/score_pr.py`** (mechanical prefilter) — run it first. It returns `signals` +
   `hard_refuse` (no carvable source, pure config/rename) → automatic drop — don't propose it. Feed `signals` (file count, LOC, top-dir spread, test presence)
   into your judgment below.
2. **You (the agent)** — apply the rubric. This is the primary judgment; the script can't see design
   content or AI-resistance.

Run it like:
```
gh pr view <n> --json files,additions,deletions > /tmp/pr.json   # add "diff" and "text" if you have them
python3 scripts/score_pr.py /tmp/pr.json --json
```

## The rubric — rate each, with a reason

For each criterion, give a short verdict + reason. A PR needs to clear **all** the must-haves to be
worth proposing.

- **Genuine multi-approach design content (must-have for senior).** Did the PR solve a problem where
  *several reasonable approaches exist* with real trade-offs? If a senior on the team couldn't name at
  least two approaches they considered, it's not senior material. Reject config bumps, dependency
  upgrades, pure renames, and trivial one-line fixes.
- **Self-contained / carvable (must-have).** Can you express it as an observable input→output contract
  that doesn't need the whole repo? A coherent bounded slice (not 30 files across the codebase) that
  can be made standalone and run offline. `score_pr.py`'s `spread_flag` warns when it's likely too
  sprawling.
- **Transferable domain logic (must-have).** Real logic/invariants (ordering, versioning, retry,
  caching, state machines), not glue/UI wiring or config. `score_pr.py` counts source vs test/config
  files; zero source → hard refuse.
- **Observable correctness contract (must-have).** Can you state "done" *behaviourally* and write 3–5
  invariant/example tests a correct solution must pass (for a fix task), or describe "done" clearly
  enough to grade a build by hand? If you can't, you can't grade it objectively. Pure refactors/style/
  comment PRs fail here.
- **AI-resistance.** Is it more than one-shottable from a one-paragraph description? Generic tasks
  (implement a queue, a REST endpoint) are trivially produced by a model. A specialized domain with an
  unusual constraint (a custom ordering invariant, a non-obvious concurrency model) is naturally more
  resistant — the real codebase context helps. If it's one-shottable, lean on raised altitude +
  `NOTES.md` + a seeded-wrong starter (see `references/task-design.md`) or pick a better PR.
- **Scope ~1–2h after carving.** Estimate by *complexity*, not lines: a 300-line PR encoding a subtle
  invariant beats a 50-line mechanical transform. If the original author spent the time on the *design
  decision*, that's the signal.
  exposure.

## Output

A short **recommend / flag / refuse** per PR, with the criterion-level reasons, recorded into the
`context.json`'s `pr_suitability.reasons[]`. Surface these when you propose the 2–4 PR options (intake) so
the choice is grounded, not hopeful.

## The contrarian tension (resolve it, don't ignore it)

The more *realistic* the task, the easier it is to AI-complete (Anthropic's own hiring team concluded
realism and AI-resistance trade off). We don't resolve this by abandoning realism — we resolve it with
the **reasoning artifact** (`NOTES.md`: where the AI was wrong and what you changed) and an optional
**seeded-wrong starter**, plus raised altitude. So a PR can be AI-adjacent and still make a good task if
the design judgment and the NOTES requirement carry the signal.

## Don't rubber-stamp

If you run a batch of *random* recent merged PRs through this and recommend nearly all of them, the
rubric isn't discriminating — most merged PRs genuinely *are* bad task sources. Refusing the majority is
the expected, healthy outcome.
