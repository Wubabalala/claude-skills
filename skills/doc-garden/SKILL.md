---
name: doc-audit
description: >
  Documentation drift auditor and normalizer for multi-layer CLAUDE.md projects.
  Use when the user says "audit docs", "check doc freshness", "doc drift",
  "docs out of date", "文档审计", "文档漂移", "检查文档", "文档同步",
  "memory index", "MEMORY.md check", "normalize docs", "整理文档",
  "更新文档", "update docs", "doc health", "文档健康".
  Also triggers implicitly when user mentions stale docs, wrong ports in
  CLAUDE.md, or missing memory entries.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
---

# Doc Garden — Documentation Drift Audit & Normalization

Audit project documentation against codebase reality. Detect drift, report it, optionally fix.

## NEVER

- Never update a doc based on what the code *should* look like — only sync to what it *actually* is now
- Never fix docs for a section you didn't audit — partial fixes create false confidence
- Never auto-fix non-deterministic issues without user confirmation
- Never modify code based on documentation — docs follow code, not the other way

## Modes

```
/doc-audit                → Report only, no file changes
/doc-audit fix            → Report + auto-fix deterministic issues (ghost refs, path redirects)
/doc-audit normalize      → Report + suggest structural fixes, user confirms each
```

## Two-Layer Architecture

### Layer 1: Universal Audit Core (this file)
Always executed. Project-agnostic drift detection.

### Layer 2: Project-Specific Config (`.claude/doc-garden.json`)
Generated on first run. Records doc hierarchy, environment domains, staleness threshold.

### Config Loading Flow

```
On audit trigger:
1. Call has_config(cwd) to check .claude/doc-garden.json
   - Exists → load_config(cwd), proceed to audit
   - Missing → enter Config Generation Workflow (see below)
2. User says "update config" or "重新生成配置" → re-enter generation workflow
```

### Config Generation Workflow (first run or explicit update)

This is a **guided interactive flow**, not an auto-generate-and-save.

**Step 1: Scan** — call `generate_draft_config(cwd)` which returns:
- Detected project type (heuristic, may be wrong)
- Discovered CLAUDE.md files → proposed layer2 list
- IPs extracted from root CLAUDE.md → attempted env domain grouping
- Discovery metadata (`_discovery` key)

**Step 2: Present** — show the user:
```
I scanned your project and detected:
- Type: {detected_type} ({claude_md_count} CLAUDE.md files found)
- Modules: {layer2 list}
- IPs found: {discovered_ips}
- Environment domains: {auto-parsed or "needs your input"}
- Memory directory: {exists/not found}

Here's the proposed config:
{draft JSON}

Please review:
1. Is the project type correct?
2. Are all modules listed? Any missing or extra?
3. Are the environment domains correctly grouped?
   (If IPs are under "_unorganized", please tell me which
    environment each IP belongs to: test/prod/local)
4. Is 14 days a good staleness threshold for this project?
```

**Step 3: Confirm** — user reviews and provides corrections:
- "Type is wrong, it's a monorepo" → update
- "Add module X" / "Remove module Y" → update layer2
- "8.129.22.14 is test, 47.112.120.194 is prod" → organize domains
- "Threshold should be 30 days" → update

**Step 4: Save** — after explicit user confirmation:
- Remove `_discovery` metadata (internal only, not persisted)
- Remove `_unorganized` / `_note` fields (should be resolved by now)
- Call `save_config(cwd, config)`
- Confirm: "Config saved to .claude/doc-garden.json"

**Step 5: Proceed** — run audit with the confirmed config

**Key principles**:
- **Never save without explicit confirmation** — draft is a proposal, not a decision
- **Never auto-organize IPs** — user knows which IP belongs to which environment
- **Show what was detected and what was guessed** — transparency over magic
- **If table parsing succeeds, still confirm** — parser might misread
- **If table parsing fails, don't block** — fall back to listing IPs for manual grouping

---

## Audit Workflow

### Phase 1: Scan & Index

Batch these reads in parallel:
- `Glob("**/CLAUDE.md")` — find all CLAUDE.md files
- Resolve memory directory (runtime: `cwd → project_name` mapping)
- Load `.claude/doc-garden.json` (or trigger Config Generation Workflow)

### Phase 2: Deep Audit

Run applicable checks from `references/drift-taxonomy.md`:

**Always run** (any project):

1. **Memory Index Drift** — MEMORY.md vs actual files
   - SUNKEN: `.md` exists in memory dir but not referenced in MEMORY.md
   - GHOST: MEMORY.md references a file that doesn't exist
   - For each sunken file: read frontmatter `type` field, guess target section

2. **Path Rot** — file paths in CLAUDE.md that don't exist on disk
   - Extract paths from backtick blocks and markdown links
   - Check existence relative to doc location and project root
   - Skip paths matching `ignore_paths` from config

**Microservice/monorepo only** (when `layer2` + `environment_domains` defined):

3. **Cross-Layer Contradiction** — module CLAUDE.md contains IPs not in any configured environment domain and not in root CLAUDE.md
4. **Config Value Drift** — config files (bootstrap.yml, .env, docker-compose.yml) contain IPs not in any environment domain

**All projects**:

5. **Structure Drift** — module in docs but directory missing (ghost), or directory with code but not documented (undocumented)
6. **Staleness** — CLAUDE.md's last git commit is older than code directory's by more than threshold

### Phase 3: Report

Output format:

```markdown
## Documentation Audit Report

**Project**: {name}
**Scanned**: {N} CLAUDE.md files, {M} memory files
**Drift found**: {count} issues

### MEMORY_INDEX_SUNKEN (N)
| Severity | File | Issue | Fix |
|----------|------|-------|-----|

### PATH_ROT (N)
| Severity | File | Issue | Fix |
|----------|------|-------|-----|
```

### Fix Mode

**Auto-fix** (`/doc-audit fix`):
- Delete ghost references from MEMORY.md (indexed file doesn't exist → remove reference)

### Normalize Mode

**`/doc-audit normalize`** — structural normalization with user confirmation.

**Workflow**:
1. **Skeleton check**: Compare CLAUDE.md files against target skeleton for project type
   - Microservice root: must have 模块速查/分支策略/部署流程/环境信息
   - Standalone root: must have 技术栈/常用命令
   - Module: must have 技术栈/常用命令
   - Missing sections → suggest adding
   - Missing CLAUDE.md → suggest generating skeleton

2. **Frontmatter check**: Scan all memory files for YAML frontmatter
   - Files without `---` frontmatter → suggest adding name/description/type
   - User confirms each before writing

3. **Sunken index fix**: Insert unindexed memory files into MEMORY.md
   - Guess target section by filename prefix and frontmatter type
   - Present suggested position → user confirms before insert

**Output**:

```markdown
## Normalize Report

**Project**: {name}
**Issues**: {count}

### Missing Required Sections (N)
| File | Issue | Suggestion | Level |
|------|-------|------------|-------|

### Missing Frontmatter (N)
| File | Issue | Suggestion | Level |
|------|-------|------------|-------|

### Unindexed Memory Files (N)
| File | Issue | Suggestion | Level |
|------|-------|------------|-------|
```

**Levels**: `auto` (no confirmation), `semi-auto` (confirm each), `suggest` (user decides)

**Idempotency**: All checks verify current state before acting. Running twice produces no additional changes. Actions logged to `.claude/doc-garden-last-normalize.json`.

### Target Skeletons

See `references/config-spec.md` for full skeleton definitions per project type. Key principle:

| Dimension | Enforced | Recommended | Free |
|-----------|----------|-------------|------|
| Root CLAUDE.md exists | Yes | | |
| Module CLAUDE.md exists (microservice) | Yes | | |
| MEMORY.md indexes all files | Yes | | |
| Memory files have frontmatter | Yes | | |
| Section ordering | | Yes | |
| docs/ structure | | | Yes |

---

## Memory Directory Resolution

Memory directory is **never stored in config**. Resolved at runtime using the same algorithm as existing `memory_health_check.sh`:

```
cwd.replace(":", "-").replace("/", "-").replace("\\", "-")
→ ~/.claude/projects/{project_name}/memory/
```

---

## Detection Engine

All detection logic lives in `core/doc_garden_core.py`. This skill and hooks are thin consumers.

Key functions:
- `memory_index_check(cwd)` → sunken/ghost findings
- `path_rot_check(cwd, config)` → dead path findings
- `check_skeleton(cwd, config)` → missing sections/docs
- `check_frontmatter(cwd)` → missing YAML frontmatter
- `run_normalize(cwd, config)` → all normalize checks
- `generate_root_skeleton(type)` → CLAUDE.md template
- `detect_project_type(cwd)` → heuristic type + CLAUDE.md list
- `resolve_memory_dir(cwd)` → runtime memory path
- `run_audit(cwd, config)` → all applicable drift checks
- `format_report(findings)` → audit markdown table
- `format_normalize_report(items)` → normalize markdown table
