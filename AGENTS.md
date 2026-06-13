# Repository guidance for coding agents

This repo **is** an Agent Skill. Its real entry point is [`skills/taskforge/SKILL.md`](skills/taskforge/SKILL.md).

When a user asks to build / create / prepare a candidate coding task (or interview task) from a
GitHub issue or PR, use the `taskforge` skill and follow its phased workflow. Do not improvise the
task-building steps — the skill bundles deterministic scripts for the safety-critical and
destructive operations (secret scan, carve, validate, package). Run those scripts; don't reimplement
their logic inline.

Scripts are Python 3 (standard library only) under `skills/taskforge/scripts/`. Tests use the
standard-library `unittest` runner: `python3 -m unittest discover -s test`.
