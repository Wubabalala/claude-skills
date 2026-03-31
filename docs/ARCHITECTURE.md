# Architecture

## Project Purpose

Production-born Claude Code skills. Each skill is extracted from real workflows, not generated from templates.

## Directory Structure

```
skills/                     — One directory per skill
  ├── SKILL.md              — Core workflow (target ≤2500 words)
  ├── README.md             — User-facing docs: install, comparison, examples
  └── references/           — On-demand detail files (optional)
      └── *.md              — Loaded by agent only when needed

docs/                       — Developer-facing guides
  ├── ARCHITECTURE.md       — This file (project map)
  └── skill-development-guide.md — Methodology + scoring + publish checklist

scripts/                    — Tooling
  └── validate-skills.sh    — Structure validator (frontmatter, word count, references)
      └── test-fixtures/    — Minimal failure cases for validator self-test
```

## Design Principles

1. **Progressive disclosure** — SKILL.md is the entry point; `references/` files are loaded on demand, not upfront. This keeps per-invocation token cost low.
2. **Infer before Ask** — AI infers from code first, marks confidence level, only asks the user for low-confidence items.
3. **Confirmation gates** — Write operations require explicit user approval. Read and write phases are separated.
4. **Token budget** — SKILL.md body target is ≤2500 words. Every word loaded into context has a cost that compounds in long sessions.
5. **Template is maximum, not minimum** — Sections are skipped when not applicable; no placeholder filler.

## Boundary: docs/ vs skills/

| Directory | Audience | Contains | Does NOT contain |
|-----------|----------|----------|-----------------|
| `docs/` | Skill developers | How to build and validate skills | Runtime logic, user-facing content |
| `skills/` | Skill users | What skills do, how to invoke them | Development methodology |

These do not cross: `docs/` never holds skill runtime logic; `skills/` never holds development guides.

## Adding a New Skill

1. Read `docs/skill-development-guide.md` (5 steps: position → design → write → disclose → test)
2. Run `bash scripts/validate-skills.sh` before committing
3. Pass the publish checklist and differentiation questions in the guide
