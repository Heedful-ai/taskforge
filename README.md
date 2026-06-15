# taskforge

An installable **AI Agent Skill** that turns one of your real merged GitHub PRs into a
bounded, self-contained **candidate coding task** — problem-first, so a senior candidate must
design and justify a solution, not transcribe one — plus a grading guide for whoever
evaluates the result.

You run it inside your own coding agent (Claude Code, Codex, …). Working with you, it:

1. interviews you about the role and what you want to test,
2. scores a real merged PR's task-suitability and pulls it with the `gh` CLI,
3. carves the relevant code into a standalone, runnable project,
4. proves that project builds + tests **offline**,
5. turns it into a **problem the candidate must design and solve** — it presents the problem +
   worked scenarios (never the solution) and asks for a `NOTES.md` explaining their approach and
   where the AI was wrong,
6. writes a candidate-facing `BRIEF.md` and a grading guide (`EVALUATION.md`),
7. packages a `task-bundle.zip` — hand the candidate `task/` and grade by hand, or send it to a
   platform for automated grading.

It is **fail-closed**: it refuses auth/crypto/payment tasks and never ships a detected secret.

## Install (≈1 minute)

Works in any agent that supports the [Agent Skills](https://agentskills.io) standard.

```bash
# Universal (Claude Code, Codex, Cursor, …) — no global install
npx openskills install Heedful-ai/taskforge

# or manual: copy the skill into your agent's skills dir
git clone https://github.com/Heedful-ai/taskforge
cp -r taskforge/skills/taskforge ~/.claude/skills/      # Claude Code
cp -r taskforge/skills/taskforge ~/.agents/skills/      # Codex & others
```

Then ask your agent: **"build a candidate coding task from PR <url>"**.

## Requirements

`git`, `gh` (authenticated), `python3` (3.9+), `zip`, and a container runtime (`docker` or
`podman`) for the offline build/test check. The skill checks these first and tells you what's
missing.

## What you get

```
task-bundle.zip
├── task/                  # the candidate exercise + BRIEF.md (this is what they receive)
├── EVALUATION.md          # grading guide — readable by a human or an eval agent
├── evaluation/reference/  # the team's solution (one acceptable approach)
└── context.json           # metadata: who made it, source PR, role, run commands
```

Hand the candidate `task/` and grade with `EVALUATION.md`, or send the whole bundle to a platform for
automated grading. See [docs/heedful-handoff.md](docs/heedful-handoff.md) for the automated-ingest contract.

## Development

Scripts are Python 3 (standard library only). Run the test suite — including a real
`--network=none` container check when Docker is available — with:

```bash
python3 -m unittest discover -s test
```

## License

MIT — see [LICENSE](LICENSE).
