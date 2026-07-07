# taskforge

An installable **AI Agent Skill** that turns one of your real merged GitHub PRs into a
bounded, self-contained **candidate coding task** — problem-first, so candidates must design
and justify a solution, not transcribe one — plus a human- and AI-readable grading guide.

You run it inside Claude Code. Working with you, it:

1. scores a real merged PR's task-suitability and pulls it with the `gh` CLI,
2. carves the relevant code into a standalone, runnable project,
3. proves it builds + tests **offline**,
4. turns it into a **problem** — presents the situation and worked scenarios, never the solution,
   and asks the candidate to write a `NOTES.md` explaining their approach and where the AI was wrong,
5. writes a candidate-facing `BRIEF.md` and a grading guide (`EVALUATION.md` with explicit rubric),
6. packages a `task-bundle.zip`.

Fail-closed: never ships a detected secret.

## Install (≈1 minute)

In Claude Code:

```
/plugin marketplace add Heedful-ai/taskforge
/plugin install taskforge
```

Then ask your agent: **"build a candidate coding task from PR &lt;url&gt;"**.

## Requirements

`git`, `gh` (authenticated), `python3` (3.9+), `zip`, and `docker` or `podman` for the offline
build/test check. The skill checks these and tells you what's missing.

## What you get

```
task-bundle.zip
├── task/                  the candidate exercise — this is what you send them
│   ├── BRIEF.md           problem statement (no solution hints)
│   └── <source files>     runnable project with lockfile; deps install from the lockfile
├── EVALUATION.md          grading guide — rubric dimensions, what good looks like, NOTES expectations
├── evaluation/reference/  the team's original solution (one acceptable approach, not the target)
└── context.json           metadata: source PR, role/seniority, run commands, machine-readable rubric
```

Hand the candidate `task/` and grade with `EVALUATION.md` by hand. Or use
**[heedful.ai](https://heedful.ai)** to run it properly.

## Going further with heedful.ai

Upload the `task-bundle.zip` to [heedful.ai](https://heedful.ai) and you get:

- **Send a link** — candidates get a VS Code environment in the browser with your task pre-loaded,
  a Claude budget to work with, and a time limit. No setup on their end.
- **Recording + timeline** — every action is captured. You see a structured timeline of what they
  did, not just the final result.
- **AI collaboration grade** — evaluates *how* they used AI: did they understand what it produced,
  catch its mistakes, drive it with intent? Graded across four dimensions with evidence from the
  session.
- **Solution comparison** — candidate's result is automatically compared to the `evaluation/reference/`
  solution from the bundle, so you see exactly where they landed relative to the team's approach.

The task bundle is the portable unit — generate it once, use it however you want.

## Development

Scripts are Python 3 (standard library only). Run the tests — including a real `--network=none`
container check when Docker is available:

```bash
python3 -m unittest discover -s test
```

## License

MIT — see [LICENSE](LICENSE).
