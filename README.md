# taskforge

An installable **AI Agent Skill** that turns one of your real GitHub issues/PRs into a
bounded, self-contained **candidate coding task** — and a trusted scorecard for the people
evaluating the result.

You run it inside your own coding agent (Claude Code, Codex, …). Working with you, it:

1. interviews you about the role and what you want to test,
2. pulls a real issue/PR with the `gh` CLI,
3. carves the relevant code into a standalone, runnable project,
4. proves that project builds + tests **offline**,
5. turns it into a task — either **breaks working code** to be fixed, or asks the candidate to
   **extend functionality**,
6. writes a candidate-facing `BRIEF.md`,
7. packages a `task-bundle.zip` you hand off for evaluation.

It is **fail-closed**: it refuses auth/crypto/payment tasks and never ships a detected secret.

## Install (≈1 minute)

Works in any agent that supports the [Agent Skills](https://agentskills.io) standard.

```bash
# Universal (Claude Code, Codex, Cursor, …) — no global install
npx openskills install <org>/taskforge

# or manual: copy the skill into your agent's skills dir
git clone https://github.com/<org>/taskforge
cp -r taskforge/skills/taskforge ~/.claude/skills/      # Claude Code
cp -r taskforge/skills/taskforge ~/.agents/skills/      # Codex & others
```

Then ask your agent: **"build a candidate coding task from issue <url>"**.

## Requirements

`git`, `gh` (authenticated), `python3` (3.9+), `zip`, and a container runtime (`docker` or
`podman`) for the offline build/test check. The skill checks these first and tells you what's
missing.

## What you get

```
task-bundle.zip
├── task/                 # the candidate project + BRIEF.md (this is what they receive)
├── scorecard.json        # trusted evaluation record — never give this to the candidate
└── manifest.json         # language, build/test commands, sizes, checksums, versions
```

## License

MIT — see [LICENSE](LICENSE).
