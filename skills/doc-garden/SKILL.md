---
name: doc-audit
description: >
  Documentation drift auditor and normalizer for CLAUDE.md / AGENTS.md
  projects (supports Claude Code, Codex, and any project using agent
  instruction files at root and/or per module).
  Use when the user says "audit docs", "check doc freshness", "doc drift",
  "docs out of date", "文档审计", "文档漂移", "检查文档", "文档同步",
  "memory index", "MEMORY.md check", "normalize docs", "整理文档",
  "更新文档", "update docs", "doc health", "文档健康".
  Also triggers implicitly when user mentions stale docs, wrong ports in
  CLAUDE.md / AGENTS.md, or missing memory entries.
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

`load_config()` `deep_merge`s the user's file on top of `DEFAULT_CONFIG`, so a
stale config missing newer fields (e.g. `doc_patterns`, `path_resolvers`)
inherits sensible defaults automatically. User values always win; lists are
replaced wholesale (not concatenated); an explicit empty `doc_hierarchy: {}`
is respected as opt-out of declared hierarchy (pattern discovery still
applies).

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

> **If `_discovery.warning` is present** (typically "no CLAUDE.md or AGENTS.md
> found at root — layer1 defaulted to 'CLAUDE.md' but the file does not
> exist"), the warning is **stripped by `save_config` at persist time and
> does not survive to disk**. Do not ignore it on the way past: prompt the
> user to create a root doc (CLAUDE.md or AGENTS.md) before saving, or
> acknowledge that downstream checks (structure/staleness) will report the
> missing root as long as it stays absent.

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

**Step 1 (MANDATORY): Invoke the engine first.** Before any manual Glob /
Read exploration, call `run_audit()` and parse the structured findings. This
catches the classes of drift the engine is designed for (path rot, memory
index, schema errors, custom CONTENT_DRIFT) deterministically and fast.

```python
from pathlib import Path
from core.doc_garden_core import run_audit, format_report, load_config
cfg = load_config(cwd)
findings = run_audit(cwd, cfg)
print(format_report(findings, project_name=Path(cwd).name))
```

Only after digesting the report do manual follow-up for engine blind spots:
semantic audit (below), overlap review, or anything content-specific the
custom hook hasn't modelled. The 2026-04-20 incident that motivated this
rule: skill was invoked but the operator did manual Grep instead of running
`run_audit`, produced 5 false-positive PATH_ROT readings from reading the
docs by hand, and missed the actual CONTENT_DRIFT that the engine would
have surfaced with the custom hook in place.

Supporting context reads (after Step 1):
- Memory directory: `resolve_memory_dir(cwd)` resolves the per-project
  location; existence is not guaranteed.
- `.claude/doc-garden.json`: `has_config(cwd)` tells whether user has
  committed to a config. If missing, enter Config Generation Workflow.
- Doc files actually scanned: `collect_doc_files(cwd, cfg)` returns the
  exact list the engine will audit — union of `doc_hierarchy.layer1/layer2/docs`
  and pattern discovery via `doc_patterns`.

### Phase 2: Deep Audit

Run applicable checks from `references/drift-taxonomy.md`:

**Always run** (any project):

1. **Memory Index Drift** — MEMORY.md vs actual files
   - SUNKEN: `.md` exists in memory dir but not referenced in MEMORY.md
   - GHOST: MEMORY.md references a file that doesn't exist
   - For each sunken file: read frontmatter `type` field, guess target section

2. **Path Rot** — file paths in doc files that don't exist on disk
   - Scans every doc returned by `collect_doc_files(cwd, config)` (union of
     `doc_hierarchy` entries and `doc_patterns` walk discovery)
   - Extracts paths from backtick blocks and markdown links (skips URLs and
     fenced code blocks)
   - Delegates to `resolve_reference(path_str, doc_abs, cwd, config)` which:
     - Matches configured `path_resolvers` by prefix (default: `memory/` →
       `$CLAUDE_MEMORY_DIR`, `optional`). `plans/` is NOT a default resolver —
       too many projects use `plans/` for their own `docs/plans/` layout and
       the resolver would hijack those refs. Users who rely on claude-code
       global plans can add it explicitly.
     - `optional: true` resolver whose root doesn't exist → status `skip`
       (no finding; intentional for cross-environment authoring)
     - Matched resolver whose root exists → builds candidate and checks
     - No prefix match → falls back to generic resolution (doc location,
       project root, module glob)
   - Emits PATH_ROT only when status is `missing`; `exists` and `skip`
     produce nothing
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

**Idempotency**: All checks verify current state before acting. Running twice produces no additional changes.

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

### Authoring Tips: Avoiding Path Rot False Positives

Path Rot assumes paths in backticks or markdown links point to **local repository files**. When you need to reference something that isn't — an external repo, a cross-repo filename, a conceptual path — use one of these forms so the check skips it cleanly.

| You want to reference | Anti-pattern (triggers PATH_ROT) | Clean form | Why it works |
|---|---|---|---|
| External GitHub repo | `` `duanyytop/agents-radar` `` | Already handled — 2-segment slash paths with no extension in the final segment are skipped as org/repo refs | regex excludes |
| File inside an external repo | `` `highlights.json` `` | `` `agents-radar:highlights.json` `` or markdown link `[highlights.json](https://github.com/.../highlights.json)` | `:` is not in the path character class; `http(s)://` is filtered upstream |
| File in shell docs / example output | `` `/var/log/app.log` `` | Already handled — `/var/`, `/opt/`, `/etc/` etc. are recognized as server absolute paths | regex excludes |
| Glob or pattern, not a real file | `` `src/**/*.py` `` | Already handled — `/**/` is filtered | regex excludes |
| Git branch / remote | `` `origin/main` `` | Already handled — `origin/`, `devlop/`, `main`, `master` are filtered | regex excludes |

**Rule of thumb**: if the token **is** a real file living in this repo, leave it. Otherwise, wrap it in a URL or add a scheme-like prefix (`repo:file` / `upstream:file` / `external:file`). The checker keeps working as a strict file-existence guard and you keep authoring flexibility.

Extending the filter: if a whole class of paths legitimately appears in your docs but shouldn't be checked (e.g. a deployment path prefix specific to your infra), add it to `ignore_paths` in `.claude/doc-garden.json` — that's the per-project escape hatch.

---

## Custom Project Checks (`.claude/doc-garden-checks.py`)

Mechanical audit catches generic drift (broken paths, missing memory index,
bad config schema). Some drift is **project-specific content divergence**
the engine cannot know about — e.g. "CLAUDE.md declares primary target
LlamaIndex but `memory/project_plan.md` still says Dubbo". Wire these into
the audit via a custom hook at `<project>/.claude/doc-garden-checks.py`.

### Contract

```python
# <project>/.claude/doc-garden-checks.py
from core.doc_garden_core import Finding, DriftType, Severity

def run_custom_checks(cwd: str, config: dict) -> list[Finding]:
    """Return a list of Finding instances. Empty list is fine."""
    findings = []
    # ... your cross-file / content drift logic ...
    # findings.append(Finding(drift_type=DriftType.CONTENT_DRIFT, ...))
    return findings
```

**The import line is non-negotiable.** `isinstance(item, Finding)` in the
runner is module-identity-sensitive: if a custom check imports `Finding`
via a `sys.path` hack or a different module path, Python treats it as a
different class object and the runner rejects every finding it returns.
`from core.doc_garden_core import Finding` — verbatim — is the only form
that works.

### Failure isolation

The runner wraps the entire load + invocation in defensive layers. If the
custom file:

- Doesn't exist → silently skipped.
- Raises on import or execution → one `CUSTOM_CHECK_ERROR` finding, audit
  continues.
- Returns a non-list → one `CUSTOM_CHECK_ERROR` finding.
- Returns a list with non-Finding items → one `CUSTOM_CHECK_ERROR` per
  bad item; valid Finding items are still kept.

You do not need defensive `try/except` inside check functions. If you want
to distinguish "check ran, found nothing" from "check crashed", catch your
own errors and return `[]`.

### What belongs in a custom check

Project-specific content drift the engine can't generically model:

- CLAUDE.md declares a fact (version, port, primary target, schedule
  budget) that a sibling doc also claims differently.
- A module doc's tech stack pin differs from the root index.
- A README's copy-pasted quickstart no longer matches the actual script.

**Do not** reimplement checks the engine already provides:

- Path existence → use `path_resolvers` in config, not a custom check.
- Memory index sunken/ghost → built-in.
- Staleness against git → built-in.

See `examples/doc-garden-checks.example.py` for a template with detailed
inline notes.

---

## Semantic Audit (human-in-the-loop)

Triggered by: `/doc-audit-semantic`, or when user says "semantic drift", "语义漂移", "语义审计".

Complements the mechanical checks above. Mechanical checks catch broken paths and missing indices — cheap, deterministic, should run first. Semantic audit catches **doc claims that contradict actual code behaviour** — things only a human or LLM reader can judge.

### Motivating examples (real findings from dogfooding this skill)

- SKILL.md promised `save_config` strips `_discovery` metadata before writing; the function actually `json.dump`ed the full dict. No path was broken, so `path_rot_check` saw nothing.
- SKILL.md described Path Rot as checking "doc location and project root" (2 candidates); the implementation actually walks 5+ candidates including `memory/` runtime prefix. Behaviour vs description drift.

Neither is catchable by regex-based detection.

### When to use

- Before a milestone commit or release (spot-check docs still describe reality)
- After a refactor touched code that docs talk about
- Periodic (e.g. monthly) sanity pass on long-lived CLAUDE.md / memory
- Not every run — semantic audit is expensive; keep it deliberate

### Workflow (Claude executes, user reviews)

1. **Select scope** — ask user which docs to audit. Default: root CLAUDE.md + memory/*.md + `docs/*` relevant to recent changes. Bound at ~20 assertions per run (a human-reviewable budget).
2. **Extract assertions** — read each doc, list verifiable claims. Each claim is:
   ```
   { source: "<file>:<line>", claim: "<verbatim quote>", verify_path: "grep symbol | read function | check file" }
   ```
   Skip aspirational / subjective claims; only keep ones where code can refute.
3. **Verify each claim** — read the referenced code location. Compare quote against code reality.
4. **Classify** into three buckets:
   - **ALIGNED**: doc claim matches code behaviour
   - **DRIFTED**: concrete divergence — cite both sides verbatim with line numbers
   - **UNVERIFIABLE / AMBIGUOUS**: requires human judgement (design intent, external behaviour, runtime-only)
5. **Report** — show user only DRIFTED and UNVERIFIABLE (ALIGNED is noise). For each DRIFTED, propose a fix direction (update doc / fix code / change design) — do NOT auto-apply.

### Rules

- **Never edit doc or code based on semantic audit alone** — always present findings to user first. Semantic drift often has multiple valid resolutions.
- **Quote both sides verbatim** — doc claim vs code snippet. Paraphrase hides drift.
- **Budget ~20 assertions per run**. Scaling beyond is noise; prefer targeted re-runs over exhaustive scans.
- **Honesty about limits**: if a claim can't be verified without running code, touching network, or external context, mark UNVERIFIABLE — don't guess.

### What this does NOT do

- Does not replace mechanical checks (cheap; run them first)
- Does not auto-fix anything (drift resolution is a human call)
- Does not cross-check doc-vs-doc consistency (e.g. SKILL.md vs README.md disagreeing) — separate workflow

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
- `path_rot_check(cwd, config)` → dead path findings (uses `resolve_reference`)
- `check_skeleton(cwd, config)` → missing sections/docs
- `check_frontmatter(cwd)` → missing YAML frontmatter
- `run_normalize(cwd, config)` → all normalize checks
- `generate_root_skeleton(type)` → CLAUDE.md template
- `detect_project_type(cwd, config=None)` → heuristic type + doc files list (uses `doc_patterns`; `config=None` falls back to `DEFAULT_CONFIG`)
- `resolve_memory_dir(cwd)` → runtime memory path
- `resolve_reference(path_str, doc_abs, cwd, config)` → `ResolveResult(status, candidates, reason)` — the pluggable path resolver honoring `path_resolvers`
- `collect_doc_files(cwd, config)` → union of `doc_hierarchy` + `doc_patterns` walk, deduped and stably sorted
- `deep_merge(default, user)` → config layering (lists replace, dicts recurse, `doc_hierarchy: {}` respected as opt-out)
- `load_config(cwd)` → deep-merged config from `.claude/doc-garden.json` over `DEFAULT_CONFIG`
- `validate_config(config)` → list of error strings (schema + field presence)
- `run_audit(cwd, config=None)` → all applicable drift checks; auto-loads config if omitted; runs `validate_config` + schema findings + built-in checks + custom hook (see Custom Project Checks section)
- `format_report(findings, project_name="")` → audit markdown table
- `format_normalize_report(items)` → normalize markdown table

Data types:
- `Severity` — `CRITICAL` / `WARNING` / `INFO`
- `DriftType` — `MEMORY_INDEX_SUNKEN` / `MEMORY_INDEX_GHOST` / `PATH_ROT` / `CONFIG_VALUE_DRIFT` / `CROSS_LAYER_CONTRADICTION` / `STRUCTURE_DRIFT` / `STALENESS` / `CONTENT_DRIFT` / `CUSTOM_CHECK_ERROR` / `CONFIG_SCHEMA_WARNING`
- `Finding(drift_type, severity, file, detail, fix_suggestion="", auto_fixable=False, section_hint="")`
- `ResolveResult(status: "exists" | "missing" | "skip", candidates: list[str], reason: str)`
