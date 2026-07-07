# Safety gates (fail-closed)

Two gates protect every bundle. **Both are hard-fail: if either trips, STOP and produce no zip.**
Never work around a finding to "make the bundle go through" — a blocked task must leave no artifacts.

Run the gates by executing `scripts/scrub.py`; do not eyeball the code yourself.


## The gate — secrets / PII
A built-in regex scan (AWS / GitHub / Slack / Anthropic / OpenAI / Google keys, private keys, JWTs,
assigned `secret = "…"`, emails) runs always; `gitleaks` augments it when installed. Obvious
placeholders (`your-key`, `example.com`) are suppressed only when the marker is in the matched value
itself. Any real finding → STOP. Exit code `2`.

## What must be scanned (every path into the bundle)
- the carved slice **and** the post-vendor `task/` (a secret in a vendored package config must not ship);
- the candidate `BRIEF.md` (`--brief`);
- the **`gh`-fetched issue/PR text** (`--text issue=FILE`) — issue bodies routinely carry pasted tokens;
- the assembled **bundle prose** — `EVALUATION.md` + `context.json` (re-scanned at packaging — `scripts/package.py` does this).

Binaries inside dependency dirs are ignored; a binary sitting in the candidate *source* is surfaced
as a warning (`warnings[]`) so it's never silently shipped — review it before continuing.

## Two classes of safety
- **Safe by construction** (script-gated): secrets, PII. The scripts enforce these.
- **Safe by approval** (human gate): which proprietary code leaves, and whether the brief leaks the
  solution. The scripts cannot judge these — the carve and brief STOP gates explicitly ask the user
  to confirm nothing proprietary or spoilery is going out.
