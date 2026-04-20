# Drift Taxonomy

Eight categories of documentation drift, with detection algorithms and severity.

## 1. Memory Index Drift

**What**: MEMORY.md index doesn't match actual memory files.

| Subtype | Detection | Severity | Auto-fixable |
|---------|-----------|----------|-------------|
| SUNKEN | File exists in `memory/` but no `[text](file.md)` link in MEMORY.md | WARNING | No (semi-auto: suggest section) |
| GHOST | MEMORY.md links `file.md` but file doesn't exist | WARNING | Yes (delete reference) |

**Truth source**: filesystem

**Algorithm**:
1. List all `*.md` in memory dir (excluding MEMORY.md)
2. Parse MEMORY.md for `[text](file.md)` links
3. Set difference: actual - linked = sunken; linked - actual = ghost
4. For sunken: read frontmatter `type`, guess target MEMORY.md section by filename prefix + type mapping

## 2. Path Rot

**What**: File paths referenced in documentation don't exist on disk.

| Severity | Condition |
|----------|-----------|
| WARNING | Path in backticks or markdown link doesn't resolve |

**Truth source**: filesystem

**Algorithm**:
1. Extract paths from CLAUDE.md: backtick patterns and markdown links `[text](path)`
2. Filter out: URLs, anchors, `ignore_paths`, server absolute paths (`/opt/`, `/apps/`), Windows drive paths (`C:/`, git-bash `/c/` `/d/`), branch names (`devlop/`), timezone strings (`Asia/`), content inside fenced code blocks, plus per-project `ignore_url_prefixes` (HTTP endpoint prefixes), `ignore_path_patterns` (fnmatch globs for templates / plan-future / competitor paths), plus bare filenames without `/` when `skip_bare_filenames: true`
3. Resolve in this order:
   a. `path_resolvers` prefix match (memory/, plans/, or user-defined)
   b. Generic fallback: doc location, project root, module root glob
   c. User-configured `generic_path_fallbacks` prefixes (e.g. `frontend/src/`, `backend/src/main/java/com/example/`)
4. If none resolves → PATH_ROT finding

## 3. Cross-Layer Contradiction

**What**: Module CLAUDE.md contains IPs/values not recognized by any configured environment domain and not present in root CLAUDE.md.

| Severity | Condition |
|----------|-----------|
| WARNING | Module IP not in any `environment_domains` AND not in root CLAUDE.md |

**Truth source**: `environment_domains` config (user-defined known IPs per environment)

**Algorithm**:
1. Collect all known IPs from `environment_domains` config
2. Extract IPs from root CLAUDE.md (baseline)
3. For each module CLAUDE.md: extract IPs
4. Flag IPs that are in module but NOT in any domain AND NOT in root doc
5. Exclude `127.0.0.1` / `0.0.0.0` (always legitimate)

**Verification path** (in fix_suggestion):
1. Check actual running config on server (ssh → cat bootstrap.yml)
2. If IP is current → add to `doc-garden.json` environment_domains
3. If IP is stale → update module CLAUDE.md to match root

**Why environment-domain-aware**: Root CLAUDE.md legitimately lists different IPs for test/prod/local. Module CLAUDE.md might reference any of them. Comparing across domains would produce false positives. Only flag when an IP belongs to NO domain.

## 4. Config Value Drift

**What**: Actual config files (bootstrap.yml, .env, docker-compose.yml) contain IPs not in any configured environment domain.

| Severity | Condition |
|----------|-----------|
| INFO | Config file has unknown IP AND also has at least one known domain IP (so it's environment-relevant) |

**Truth source**: config files in repository (code-level truth)

**Algorithm**:
1. Glob for config files: `**/bootstrap.yml`, `**/.env`, `**/docker-compose.yml`, `**/application.yml`
2. Extract all IPs from each file
3. Compare against known IPs from `environment_domains`
4. Only flag if the file ALSO contains at least one known IP (ensures it's environment-relevant, not a random test fixture)

**Verification path**: Check if IP is actively used by running service → add to domains or update config

## 5. Structure Drift

**What**: CLAUDE.md's module list doesn't match actual directory structure.

| Subtype | Detection | Severity |
|---------|-----------|----------|
| GHOST MODULE | Module in `doc_hierarchy.layer2` but directory doesn't exist | WARNING |
| UNDOCUMENTED MODULE | Directory with code but no entry in layer2 | INFO |

**Truth source**: filesystem (directories are reality)

**Algorithm**:
1. Extract documented module names from `layer2` paths (e.g., `api/CLAUDE.md` → `api`)
2. Scan project root for directories containing code indicators (`src/`, `lib/`, `pom.xml`, `package.json`, `pyproject.toml`, `CLAUDE.md`, etc.)
3. Skip non-code directories (`.git`, `node_modules`, `docs`, `scripts`, etc.)
4. Set difference: documented - actual = ghost modules; actual - documented = undocumented

**Verification path**:
- Ghost: Was module renamed or removed? → Update layer2 config
- Undocumented: Is this a real module? → Create CLAUDE.md + add to layer2

## 6. Staleness

**What**: CLAUDE.md's last git commit is significantly older than its code directory's last commit.

| Severity | Condition |
|----------|-----------|
| INFO | Gap > threshold but < 2× threshold |
| WARNING | Gap > 2× threshold |

**Truth source**: git commit timestamps

**Algorithm**:
1. Check if project is a git repo (`git rev-parse --is-inside-work-tree`)
2. For each (CLAUDE.md, code_dir) pair:
   - Root CLAUDE.md → project root
   - Module CLAUDE.md → module directory
3. Get last commit time: `git log -1 --format=%at -- <path>`
4. If code_time - doc_time > `staleness_threshold_days` × 86400 → STALENESS finding

**Silently skips**: non-git projects, untracked files (including previously-committed files that were subsequently `git rm`'d and added to `.gitignore` — `_is_git_tracked` checks current tracking status via `git ls-files --error-unmatch`, not historical commits), files with no git history

## 6.5 Fact Value Conflict

**What**: A configured fact key (e.g. file line count, version pin, port) is cited in multiple docs with different values.

| Severity | Condition |
|----------|-----------|
| WARNING | Same `(pattern_name, key)` found in ≥2 distinct docs with ≥2 distinct values |

**Truth source**: user-configured `fact_patterns` — each with `{name, regex, key_group, value_group}`

**Algorithm**:
1. For each entry in `fact_patterns`, compile the regex
2. For each doc in `collect_doc_files(cwd, config)`: read line-by-line, apply regex, extract `(key, value)` via the configured group indices
3. Group observations by `(pattern_name, key)` → `{value: [(doc, line), ...]}`
4. If a key has ≥2 distinct values AND participants span ≥2 distinct docs → emit finding
5. Intra-doc repetition (same key multiple times in a single file) never triggers a finding — only cross-doc divergence counts

**Example fact_pattern** (file line count drift):

```json
{
  "name": "file_line_count",
  "regex": "([\\w.-]+\\.(?:java|vue|py|js|ts))\\s*\\((\\d{3,})\\)",
  "key_group": 1,
  "value_group": 2
}
```

**Verification path** (in fix_suggestion):
1. Pick the authoritative source (usually the file whose line count is most-recently auto-computed)
2. Update the other docs to match, or have them reference the canonical source instead of duplicating the value

**Why not a custom hook**: this pattern is common enough (line counts, versions, ports, URLs) that a regex-driven config is cheaper than implementing per-project Python. Custom hooks remain available for facts where regex can't express the semantic.

## 6.6 Entity Coverage (reverse coverage)

**What**: A code-side entity (Controller, Handler, Route, etc.) exists on disk but is never mentioned in any configured reference doc.

| Severity | Condition |
|----------|-----------|
| WARNING | Entity extracted from `source_glob` not found in `ref_scope` text, and not policy-classified |
| INFO | `ref_scope` glob matches 0 files (likely misconfiguration — emits one finding, not N per entity) |

**Truth source**: source-code filesystem (entities are real; refs must catch up)

**Algorithm**:
1. For each `entity_patterns` entry:
   a. Glob `source_glob` (recursive) under `cwd`
   b. Apply `entity_pattern` regex to each **basename**; group 1 = entity name
   c. Concatenate every doc matching `ref_scope` into one text blob
   d. For each entity: if name appears as substring in blob → covered, skip
2. Consult `entity_policy_file` (default `.claude/doc-garden-entity-policy.txt`):
   - `IGNORED: EntityName # reason` → silent (test-only / dev-only / non-business)
   - `KNOWN_UNDOCUMENTED: EntityName # reason` → silent in v1 (future verbose mode)
   - Absent from policy → ENTITY_COVERAGE WARNING

**Policy file format**:

```
# comment
IGNORED: TestController     # dev-only endpoint, no business logic
KNOWN_UNDOCUMENTED: MemoController  # edge feature, pending docs
```

Malformed policy lines are silently skipped to avoid drowning the report in policy-typo noise.

**Example entity_patterns entry**:

```json
{
  "name": "Controller",
  "source_glob": "backend/src/main/java/com/example/controller/*.java",
  "entity_pattern": "^(\\w+Controller)\\.java$",
  "ref_scope": "docs/references/*.md"
}
```

**Verification path** (in fix_suggestion):
1. Add the entity to a relevant ref (expand existing, or create a new one)
2. If genuinely not worth documenting, classify in policy file WITH a reason

**Why not a custom hook**: reverse-coverage is a common pattern (Java Controller classes, FastAPI `@router`, Vue views) where the entity name is extractable from a filename glob. Patterns + policy file express 90% of real cases without code.

## 7. Missing Skeleton Sections (normalize)

**What**: CLAUDE.md lacks required sections for its project type.

| Project Type | Root Required | Module Required |
|-------------|---------------|-----------------|
| microservice | 模块速查, 分支策略, 部署流程, 环境信息 | 技术栈, 常用命令 |
| standalone | 技术栈, 常用命令 | — |

**Truth source**: skeleton definitions in `SKELETONS` dict

**Algorithm**:
1. Extract `## ` section titles from CLAUDE.md
2. Compare against required sections using bilingual alias matching (e.g., "技术栈" matches "Tech Stack", "Development Environment")
3. Missing required section → suggest adding

## 8. Missing Frontmatter (normalize)

**What**: Memory files lack YAML frontmatter (`---` block with name/description/type).

| Severity | Condition |
|----------|-----------|
| — (normalize item) | File doesn't start with `---` |

**Truth source**: file content

**Algorithm**:
1. Scan all `*.md` in memory directory (excluding MEMORY.md)
2. Check if first line is `---`
3. Missing → suggest adding frontmatter template

**Semi-auto**: Agent generates frontmatter based on filename + content, user confirms before writing.
