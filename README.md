# claude-skills

A collection of Claude Code skills for real-world development workflows.

## Install

```bash
# Install a specific skill
npx skills add hyc-deep/claude-skills@project-onboarding
```

## Available Skills

| Skill | Description | Status |
|-------|-------------|--------|
| [project-onboarding](skills/project-onboarding/) | Systematic project onboarding — scan codebase, generate CLAUDE.md + OVERVIEW.md, capture domain knowledge | v1.0 |

## Principles

Every skill in this collection follows these principles:

- **Source-safe** — never modifies source code; only writes documentation
- **User confirms all writes** — nothing touches disk without approval
- **Practical over theoretical** — born from real project workflows, not templates

## Adding a New Skill

Each skill lives in `skills/{skill-name}/` with at minimum a `SKILL.md` file.

```
skills/
  project-onboarding/
    SKILL.md          # Skill prompt (required)
  {next-skill}/
    SKILL.md
```

## License

MIT
