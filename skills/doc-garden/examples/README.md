# doc-garden examples

Copy-paste templates for common project integrations. None of these files are loaded by the skill at runtime — they're reference material.

| File | What it is |
|---|---|
| `doc-garden.json` | Example config for a microservice project (multi-module + environment domains) |
| `doc-garden-checks.example.py` | Example `.claude/doc-garden-checks.py` custom-hook showing the `Finding` / `DriftType` contract |
| `doc-audit.example.sh` | Shell entry point that runs `run_audit()` and returns git-friendly exit codes. Designed to live at `<project>/scripts/doc-audit.sh` |
| `install-hooks.example.sh` | Installs a git `pre-commit` hook into each module that calls `doc-audit.sh` when staged `.md` files change. Designed for multi-module repos where the top-level dir is not a git repo |

## Typical integration (multi-module repo)

```bash
# 1. In your project root, create scripts/ and copy the two shell examples
mkdir -p scripts
cp path/to/doc-garden/examples/doc-audit.example.sh scripts/doc-audit.sh
cp path/to/doc-garden/examples/install-hooks.example.sh scripts/install-hooks.sh
chmod +x scripts/*.sh

# 2. Edit scripts/install-hooks.sh: populate MODULES=(...) with your module dirs
#    OR just use --auto to scan for any .git directories

# 3. First-time setup: generate .claude/doc-garden.json (interactively via
#    the /doc-audit skill, or copy examples/doc-garden.json and edit)

# 4. Install hooks
bash scripts/install-hooks.sh              # from MODULES list
bash scripts/install-hooks.sh --auto       # auto-scan .git dirs
bash scripts/install-hooks.sh --dry        # preview first
```

## Single-repo project

If the project root IS a git repo, simplify: copy just `doc-audit.example.sh` to `scripts/doc-audit.sh`, then create `.githooks/pre-commit` that calls it, and `git config core.hooksPath .githooks`. The install-hooks script is overkill for this case.

## Environment setup

`doc-audit.sh` needs to find the doc-garden skill directory. It tries a few common locations and respects `$DOC_GARDEN_PATH`. If your layout is unusual:

```bash
export DOC_GARDEN_PATH=/your/path/to/claude-skills/skills/doc-garden
```

Add that to your shell profile to make it permanent.

## What the hook does NOT do

- It does not modify code or docs
- It does not auto-fix drift
- It does not run `/doc-audit normalize` or `/doc-audit fix` (those are interactive, not suitable for hooks)
- It only blocks commits when drift is found; "environment errors" (missing Python, missing skill path) exit 2 and do NOT block

Blocking on drift is the intended contract: forcing the author to either fix the doc, add an ignore rule to config, or explicitly bypass with `--no-verify`.
