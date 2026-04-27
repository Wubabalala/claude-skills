# Architecture Traps Integration

## Purpose

`architecture-traps.md` is the authoritative source for project-specific regression knowledge.

The skill may consume traps from:

- repo-level: `<repo_root>/docs/architecture-traps.md`
- module-level: `<module_root>/docs/architecture-traps.md`

The generated `.claude/review-checklist.md` is a derived review view, not the source of truth.

## Discovery and Merge Rules

The skill MUST use these fixed rules:

1. Load repo-level traps first from `<repo_root>/docs/architecture-traps.md`, if it exists.
2. For each file in the current review scope, walk upward to find the nearest module root.
3. For each unique module root found in step 2, load `<module_root>/docs/architecture-traps.md` if it exists.
4. Do NOT scan all modules in the repository. Only load module traps for modules touched by this review scope.
5. If the same `trap_id` appears at multiple levels, module-level overrides repo-level because closer scope wins.

If no traps file exists at any level, skip silently.

## Module Root Heuristics

Treat the nearest ancestor directory containing any of these files as a module root:

- `pom.xml`
- `package.json`
- `pyproject.toml`
- `Cargo.toml`
- `go.mod`
- `build.gradle`
- `build.gradle.kts`

These heuristics exist only to locate module-level `docs/architecture-traps.md`. They do not change the review scope itself.

## Required: Anti-pattern Signature Block

Each trap entry that wants automated regression detection MUST include a fenced YAML block:

```yaml
trap_id: B2
title: "Case-sensitive contains() in domain check"
severity: P0
scope: project
frequency: chronic
signatures:
  - grep: 'contains\("[a-z0-9.]+\.com"\)'
  - file_pattern: '*.java'
```

Without this block, the trap is human-readable only. The skill cannot regression-check it. This is intentional: contracts must be explicit.

Supported signature keys:

- `grep`
- `file_pattern`

Additional keys may exist in the human-readable document, but they are ignored unless the skill is explicitly taught to consume them later.

## trap_id Namespacing

- Repo-level traps use bare ids like `B1`, `B2`, `B3`
- Module-level findings should be annotated with their module path, for example:
  - `traps#root.B2`
  - `traps#auto-submit-api/B7`

Module trap ids may shadow repo trap ids when they describe a closer-scope rule. This is resolved by the discovery precedence above, not by merging two definitions.

## Backfill Guidance

When the reviewer confirms a new trap candidate:

- Write it only to the selected `architecture-traps.md`
- Prefer the nearest module traps file when all matches are in one module
- Prefer repo-level traps when the pattern spans multiple modules
- Do not write the same rule directly into `.claude/review-checklist.md`
