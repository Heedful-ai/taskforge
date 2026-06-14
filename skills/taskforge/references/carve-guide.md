# Carve guide — turning a repo + issue into a standalone slice

Goal: a **small, self-contained, runnable** project that captures one coherent piece of the codebase
— not a dump of the repo. The candidate should be able to `cd` into it and run the tests with no
other setup.

## 1. Understand the source (read-only `gh`)
From the issue/PR the user gave you, gather — using **read-only** `gh` calls only:
- the issue: `gh issue view <n> --json number,title,body,url`
- the PR (if any): `gh pr view <n> --json number,title,body,url` and its diff: `gh pr diff <n>`

Keep this for `context.json`'s `source` block (the original PR diff/description + issue are evaluation
context — they are NOT shipped in `task/`). Never run `gh` commands that write.

## 2. Choose a coherent, bounded slice
Pick the module/feature the issue is about, plus only what it needs to build and run its tests. Stay
within the caps (`validate_carve.py` enforces them):
- **≤ 25 files**, **≤ 1500 LOC**, **≤ 4 top-level dirs** (e.g. `src/` + `tests/` + a couple of config files).
Prefer one module + its tests + the minimal config to run them. If it won't fit, narrow the feature.

**Caps bound size, not difficulty.** Separately estimate how long a competent candidate would take to
solve the task you'll create (Phase 4) and aim for ~1–2h. Surface that estimate at the taskify gate.

## 3. Emit `carve_plan.json`
```jsonc
{
  "language": "python",                       // LanguageProfile id
  "files": ["src/parser.py", "tests/test_parser.py", "pyproject.toml"],
  "entrypoint": "src/parser.py",
  "build_command": null,                      // or e.g. "npm ci && npm run build"
  "test_command": "python3 -m unittest discover -s tests",
  "vendor_commands": [],                       // commands that make deps resolve OFFLINE (run now, online)
  "vendored_paths": [".venv", "node_modules", "vendor"],   // excluded from the reference diff
  "source": {
    "repo": "owner/name",
    "pr":    { "number": 0, "title": "", "description": "", "url": "", "diff": "" },
    "issue": { "number": 0, "title": "", "body": "", "url": "" }
  }
}
```

### Per-language defaults (starting points — adjust to the repo)
| language | test_command | vendor_commands | vendored_paths |
|----------|--------------|-----------------|----------------|
| python (stdlib tests) | `python3 -m unittest discover -s tests` | `[]` | `[]` |
| python (pip deps) | `python3 -m pytest -q` | `["python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"]` | `[".venv"]` |
| node | `npm test` | `["npm ci"]` | `["node_modules"]` |
| go | `go test ./...` | `["go mod vendor"]` | `["vendor"]` |

The MVP ships and proves one language end-to-end; others are appended without changing the scripts.

## 4. Gate, then carve
- Run `scripts/validate_carve.py <repo> carve_plan.json`. Fix rejections (too big, missing files, …).
- **STOP — slice approval. Show the user the TASK, not just files.** A file list alone doesn't tell
  them whether it's the right task. Present, at this gate:
  1. **What the candidate will actually be asked to do** — a short draft of the candidate README
     (`references/readme-template.md`): the context + the "Your task" framing + how they run it. This
     is the candidate's experience; the user judges *the task* here, not a file list.
  2. **What they'll receive** — the carved file list (candidate-visible files; note `node_modules`/
     deps are vendored but omitted from the listing).
  3. **Safety** — what you checked (no secrets/PII, no proprietary branding/data, monorepo coupling
     stubbed out), and that the full PR diff lives only in `context.json`/`evaluation/`, never in `task/`.
  Ask the user to confirm **two** things: *is this the right task?* and *is the slice OK to share
  (nothing proprietary/sensitive)?* Don't proceed on file approval alone.
- Run `scripts/carve.py <repo> carve_plan.json --out correct`. It copies the slice (no `.git`), runs
  the vendor commands so deps are present offline, and writes `source_context.json`.
