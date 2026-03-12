# Memory File Specification

## File Format

Each dimension produces one memory file. Use `type: project` for knowledge
about this project's design/workflows/decisions. Use `type: reference` for
pointers to external systems (e.g., "bugs tracked in Linear project X",
"monitoring dashboard at grafana.internal/d/xxx").

```markdown
---
name: {dimension name}
description: {one-line description for future retrieval}
type: {project | reference}
source: project-onboarding skill
created: {YYYY-MM-DD}
---

## Extracted from Code
{Factual findings with file path citations.
Example: "Service A calls Service B via Feign (see `src/feign/ServiceBClient.java:15`)"}

## Supplemental Knowledge
{User-provided context that is NOT in the code.
Example: "Dual auth exists because legal required SSO for external users
while internal admin needed lightweight JWT for faster iteration."}
```

## Storage Location

Use a fallback chain to determine where to store memory files:

1. **Existing memory dir** — if `.claude/projects/.../memory/` or
   `.claude/memory/` already exists, use it
2. **Project-level .claude** — if `.claude/` exists at project root, create
   `memory/` inside it
3. **Fallback** — create `.project-memory/` at project root (tool-agnostic,
   easy to gitignore)

Ask user to confirm the chosen path before writing the first memory file.
If creating a new directory, suggest adding it to `.gitignore` — memory
files may contain team-specific context not suited for version control.

After writing memory files, update or create `MEMORY.md` index in the same
directory with one-line links to each memory file.
