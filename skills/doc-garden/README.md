# doc-garden

Documentation drift auditor and normalizer for Claude Code projects.

## Problem

You use Claude Code across multiple projects. Each has CLAUDE.md files, memory files, docs/ directories. Over time:

- Memory files get written but never indexed in MEMORY.md
- CLAUDE.md references paths that no longer exist
- Module CLAUDE.md files contradict the root CLAUDE.md
- Code changes but docs don't follow

**doc-garden** detects these drifts and helps fix them.

## How it works

```
project-onboarding    →    doc-garden    →    code-review
    (Day 1)              (ongoing)          (pre-push)
```

doc-garden fills the gap between initial project setup and code review — keeping documentation fresh as code evolves.

### Three modes

| Command | Action |
|---------|--------|
| `/doc-audit` | Report drift, no changes |
| `/doc-audit fix` | Auto-fix deterministic issues (ghost refs in MEMORY.md) |
| `/doc-audit normalize` | Suggest structural fixes, confirm each |

### What it detects

| Drift Type | Description | Status |
|-----------|-------------|--------|
| Memory Index (sunken/ghost) | Files exist but not indexed, or indexed but missing | Available |
| Path Rot | Paths in docs that don't exist on disk | Available |
| Skeleton Check | CLAUDE.md missing required sections per project type | Available |
| Frontmatter Check | Memory files missing YAML frontmatter | Available |
| Cross-Layer Contradiction | Module has IPs not in any environment domain | Available |
| Config Value Drift | Config files have IPs not in environment domains | Available |
| Structure Drift | Module in docs but dir missing, or dir with code but undocumented | Available |
| Staleness | Code updated but CLAUDE.md hasn't followed (git timestamps) | Available |

### Project type adaptation

Automatically detects project type and adapts checks:

| Type | Layer 2 | Cross-layer | Environment domains |
|------|---------|-------------|-------------------|
| Microservice | Multiple module CLAUDE.md | Full check | Yes |
| Monorepo | Some sub-project CLAUDE.md | Partial | Maybe |
| Standalone | None | Skip | Usually no |

## Install

```bash
npx skills add Wubabalala/claude-skills@doc-garden
```

## Architecture

```
SKILL.md                    ← Audit workflow (user-facing)
core/doc_garden_core.py     ← Shared detection engine (all logic here)
tests/                      ← Fixtures + unit tests
```

All detection logic in one place. Skill is a thin consumer.

## Roadmap

- **Phase 1-3** (complete): Audit + normalize + hooks
- **Phase 4** (next): Cross-layer contradiction, config value drift, staleness detection
- **Phase 5**: Polish + publish to marketplace

## Related skills

- [project-onboarding](../project-onboarding/) — Day 1 project setup, generates initial CLAUDE.md + memory
- [code-review](../code-review/) — Pre-push quality gate with project-specific checklist
