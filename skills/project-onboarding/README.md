# project-onboarding

The fastest way to understand an unfamiliar codebase with Claude Code.

```bash
npx skills add Wubabalala/claude-skills@project-onboarding
```

## What It Does

1. **Detects existing AI files** — CLAUDE.md, .cursorrules, AGENTS.md, .windsurfrules, .trae/rules, .cline, Copilot instructions
2. **Cross-checks docs against code** — finds stale commands, wrong ports, outdated tech stack claims
3. **Generates layered documentation** — root CLAUDE.md + per-module CLAUDE.md (monorepo) + docs/OVERVIEW.md
4. **Captures domain knowledge** — asks "why was it designed this way?" to capture what code can't tell you
5. **Security scan** — blocks writes if passwords, API keys, or IPs detected

## Usage

In Claude Code, type `/onboard` or say "help me understand this project".

Three phases, each with a confirmation gate. Stop anytime.

| Phase | What Happens | Output |
|-------|-------------|--------|
| 0 - Detect & Scan | Finds AI files, scans structure, checks for conflicts | Scan report with action choices |
| 1 - Generate Docs | Creates CLAUDE.md + OVERVIEW.md from code evidence | Documentation files (user approves before write) |
| 2 - Deep Dive | Recommends knowledge dimensions, asks "why" | Memory files separating facts from context |

## Key Features

- **Patch mode** — fix stale docs without full rebuild (targeted before/after diffs)
- **Monorepo auto-detection** — generates per-module CLAUDE.md
- **Source Zone / Doc Zone** — never touches source code, only writes documentation
- **Coarse-to-fine scanning** — count first, then files, then content (saves tokens)
- **Idempotent** — safe to re-run, detects changes since last onboarding

## Works With

Claude Code, Cursor, Trae, Gemini CLI, Codex, Cline, Amp, and more.
