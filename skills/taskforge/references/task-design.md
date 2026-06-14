# Designing the task — principles, not a template

You (the agent) design the candidate task. There is **no fixed recipe and no mode enum** — you reason
from the principles below and compose a task that fits *this* PR and *this* role. The old "plant a bug
+ ask for an extension" formula is one shape among many, not the rule.

Your job: turn a real merged PR into a task that measures **engineering judgment**, not transcription.

---

## 1. Present the problem, never the solution

The single most important decision is the **altitude** of the brief, and it sets the seniority you
measure.

- **Bad (transcription):** name the solution and list its rules — *"implement an append-only log:
  entry_id stable across versions, per-brief version clock, tombstone deletes, distinct-on-latest…"*.
  That asks the candidate to type out a design **we already chose**. It's a ~40-line afternoon and a
  junior signal.
- **Good (engineering):** present the **problem + constraints + worked input→output scenarios +
  business motivation**, and let the candidate **design and justify** the approach.

A senior's defining skill is to **evaluate multiple solutions and choose one**. Naming the solution
strips exactly the judgment you wanted to test. Give the problem; let them reach for append-only log
vs. snapshots vs. a temporal/bitemporal table vs. a separate audit trail vs. event sourcing — and
explain why.

> If the PR's domain has only one reasonable solution, it's a weaker source for a senior task — see
> `references/pr-suitability.md`.

---

## 2. Fill the time; don't expect them to finish

A good take-home carries **more work than the candidate can finish** in the window. How they
**prioritize** — what they build first, what they consciously skip, what they note as "next" — is a
first-class signal, especially for senior roles. Do **not** count tasks ("two bugs for mid, three for
senior") — that's the rigid thinking we're removing.

Compose depth with the **make-it-work → extend → scale/edge** escalation:

- **Core** — get a working version of the problem (this is what gets graded if they run out of time).
- **Extend** — a new requirement on top (a second behaviour, a new case).
- **Scale / edge** — the genuinely hard part (concurrency, large inputs, recovery, a subtle invariant).

Mid candidates are differentiated by how cleanly they finish the core; seniors by how far they get into
extend/scale and how well they handle the constraints. You can mix building (from a stubbed
pre-solution world) with a planted bug or two elsewhere, plus an open extend/scale ask. Use whatever
combination best exercises the PR's real engineering.

---

## 3. Seniority sets altitude (guidance, not arithmetic)

Drive altitude from the `hiring.seniority` metadata — as **guidance**, never a formula:

- **junior / mid** → more scaffolding, a clearer contract, a tighter problem; a planted bug or two plus
  a bounded build is fine. Less "choose the architecture", more "implement this well".
- **senior** → problem-only; at least one **open design choice** with several plausible approaches that
  they pick and justify; an open-ended scale/edge part with no single right answer.

### Calibration anchors (so tasks stay comparable)

Principles-only design risks every task being a snowflake — two candidates for the same role getting
wildly different bars. Hold a small set of altitude invariants **constant per tier** even as the
surface task varies. Suggested anchors:

- **senior** = at least one open design choice (≥3 plausible approaches) + one build-it core + one
  human-graded scale/edge part.
- **mid** = one clear core build + a planted bug or two + a bounded extend; design space narrower.
- **junior** = a guided core with a clear contract + a bug to find; minimal open design.

Record which anchors a task was calibrated to in the scorecard's descriptive `task_mode` string, so the
evaluator knows **what bar this task represents**.

---

## 4. Assume the candidate uses AI

They will. Design for it instead of pretending otherwise.

- **Raise altitude to design/judgment** (§1) — a closed, fully-specified, single-file task is
  one-shotted by a model and discrimination collapses (careful humans can even score *below*
  blind-pasters). The real codebase context from the PR is naturally out-of-distribution and resists
  one-shotting better than a generic algorithm.
- **Require `NOTES.md`** (see `references/readme-template.md`) — assumptions; the approach chosen **and
  why** (+ alternatives rejected); edge cases; and **where the AI assistant was wrong and what they
  changed.** This artifact *is* the 2026 skill and cannot be produced without the judgment you're
  testing.
- **Optionally seed a subtly-wrong starter** — a plausible-but-incorrect partial implementation (the
  kind a model hallucinates confidently). Candidates who spot and correct it show genuine
  comprehension; AI-only completions tend to reproduce or mis-"fix" it. Verify the catch via the hidden
  suite.
- **Depth beats breadth** — several independent sub-problems with real depth reduce the chance a single
  AI insight determines the outcome.

---

## 5. Grade behaviour, hide the suite, ship only examples

- **Grade observable invariants/behaviour**, not similarity to the team's diff. There are many ways to
  be a good engineer; a cleaner, different, correct solution should score **higher**, not be penalized.
  The team's PR diff is **one reference exemplar**, never a similarity target.
- **Keep the full grading suite hidden** (trusted-side). Shipping the grading tests spoils the task.
- **Ship a few example tests** in `task/` for **contract clarity only** — they show the harness, how to
  run, and the I/O shape. They must **not** assert the key behavioural invariants, or a candidate can
  reverse-engineer the hidden suite and you've spoiled the design space.
- **Author the hidden suite from the BRIEF's worked scenarios** — the invariant the candidate was
  *given* — not from the team's specific implementation. A suite that encodes the team's particular
  choice will mark a defensibly-different correct solution wrong (the exact grading sin we're avoiding).
  When you package, a human reviews the suite asking: *does this assert the invariant, or the team's
  implementation?*
- **Tier the suite** into `core` (expected-pass — the make-it-work invariants) and `stretch`
  (informative — extend/scale/edge). Because the task is deliberately bigger than finishable (§2),
  grading is **not** "did the whole suite go green": it's core-pass + how far into stretch + the human
  rubric on design and `NOTES.md`.
- **Open design dimension → human rubric** with multiple acceptable approaches; automated tests alone
  can't judge whether a different architecture is equally valid.

---

## 6. Position it honestly

This is **one structured async signal** — execution + judgment on realistic work. It does **not**
measure communication, collaboration, ownership, or reading/changing large existing systems. A **FAIL
is more informative than a PASS.** Don't over-claim validity: a per-candidate-unique task hasn't earned
work-sample-test validity numbers — those come from standardized instruments. Position outputs to
support a hiring conversation, not to replace it.

---

## The building blocks you can mix (not an enum)

Compose freely from these; a task uses whichever fit the PR:

- **Stub-the-solution build** — gut the PR's solution back to a *pre-solution world* (signature-
  preserving stubs/TODOs) so the candidate builds it from the problem. (Mechanics: `references/
  carve-guide.md` + the taskify spec.)
- **Planted bug(s)** — one or two realistic defects in the interesting logic for them to find and fix.
- **Extend / scale ask** — a forward-looking "now also handle X" (often human-graded).
- **Seeded-wrong starter** — §4, optional.
- **Example tests** (ship, mechanics-only) vs **hidden suite** (withhold, `core`/`stretch`).

These are recorded in the task spec the scripts apply (`taskify`), but **how you combine them is your
design call**, grounded in §1–§6 — there is no controlling mode.

---

## Worked example — `superlistapp/anchor` PR #5

The PR added **append-only entry versioning** (view a brief at any past version, recover deleted
entries, keep a fast current view) on top of a mutable `entries` table.

- **BAD task:** *"implement an append-only log with these 6 rules."* → transcription, mid signal. We
  handed over the solution.
- **GOOD task:** *"Brief entries are stored in a mutable table — rows get UPDATEd and DELETEd in place,
  so history is lost. We need: (a) view the brief as it was at any past version, (b) recover an entry
  that was deleted, (c) keep a fast 'current' view. Here are 4 scenarios of edits with their expected
  current + historical views. Design and implement a model that supports this; then handle two
  concurrent edits to the same entry. In NOTES.md, explain your approach and the alternatives you
  considered and rejected."* → the candidate chooses append-only log vs snapshots vs temporal table vs
  audit trail and justifies it. **Senior signal.** We grade behaviour (reconstruct past versions +
  current view + recover deletes) via the hidden `core` suite; concurrency is `stretch`/human-graded;
  the team's append-only diff is one reference exemplar, not the required answer.
