# doc-garden.json Configuration Spec

## File Location

`.claude/doc-garden.json` in project root. Generated on first `/doc-audit` run, user confirms before write.

## Schema

```json
{
  "project_type": "microservice | monorepo | standalone",
  "doc_hierarchy": {
    "layer1": "CLAUDE.md",
    "layer2": ["module-a/CLAUDE.md", "module-b/CLAUDE.md"],
    "docs": ["docs/OVERVIEW.md"]
  },
  "doc_patterns": ["CLAUDE.md", "AGENTS.md"],
  "path_resolvers": [
    {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": true},
    {"prefix": "plans/",  "root": "$HOME/.claude/plans", "optional": true}
  ],
  "environment_domains": {
    "环境名": {
      "ips": ["x.x.x.x"],
      "ports_prefix": "97",
      "namespace": "ns-name"
    }
  },
  "staleness_threshold_days": 14,
  "ignore_paths": ["node_modules/", ".git/"],
  "ignore_url_prefixes": ["/api/", "/admin/"],
  "generic_path_fallbacks": ["frontend/src/", "backend/src/main/java/com/example/"],
  "fact_patterns": [
    {
      "name": "file_line_count",
      "regex": "([\\w.-]+\\.(?:java|vue|py))\\s*\\((\\d{3,})\\)",
      "key_group": 1,
      "value_group": 2
    }
  ],
  "entity_patterns": [
    {
      "name": "Controller",
      "source_glob": "backend/src/main/java/com/example/controller/*.java",
      "entity_pattern": "^(\\w+Controller)\\.java$",
      "ref_scope": "docs/references/*.md"
    }
  ],
  "entity_policy_file": ".claude/doc-garden-entity-policy.txt"
}
```

**Required fields**: `project_type`, `doc_hierarchy.layer1`
**Optional fields**: `layer2`, `docs`, `doc_patterns`, `path_resolvers`, `environment_domains`, `staleness_threshold_days`, `ignore_paths`, `ignore_url_prefixes`, `generic_path_fallbacks`, `fact_patterns`, `entity_patterns`, `entity_policy_file`
**Never stored**: memory directory path (derived at runtime from cwd)

### `doc_patterns`

List of filename patterns (basename match, not glob) used to discover doc
files via `os.walk` pruning `ignore_paths`. Union'd with `doc_hierarchy` by
`collect_doc_files(cwd, config)`. Default: `["CLAUDE.md", "AGENTS.md"]`.
Set to just `["CLAUDE.md"]` if you don't want AGENTS.md picked up.

### `path_resolvers`

Ordered list of prefix resolvers. When a path reference in a doc starts
with one of these prefixes, `resolve_reference(path_str, doc_abs, cwd,
config)` substitutes the resolver's `root` and checks for the resolved
path's existence.

Each entry:

| Field | Required | Description |
|-------|----------|-------------|
| `prefix` | yes | Literal string prefix to match (e.g. `"memory/"`). |
| `root` | yes | Root template. See **Placeholders** below. |
| `optional` | no (default `false`) | If `true` and `root` doesn't exist (or an `$ENV:VAR` placeholder is unset), the reference returns status `skip` (no PATH_ROT finding). Use this for cross-environment refs that shouldn't be required on every machine. |

**Placeholders** in `root`:

| Placeholder | Expands to |
|---|---|
| `$CLAUDE_MEMORY_DIR` | `resolve_memory_dir(cwd)` — per-project memory directory |
| `$HOME` | `os.path.expanduser("~")` — user home directory |
| `$ENV:VAR_NAME` | Process environment variable `VAR_NAME`. Extension point for custom roots without touching engine code — e.g. `$ENV:MY_DOCS_ROOT` lets a project set `MY_DOCS_ROOT` once and reference it in config. Unset variable + `optional: true` → `skip`. Unset + `optional: false` → `missing` (reports the resolver as unusable). |
| leading `~` | Also expanded via `os.path.expanduser` |

Resolver outcomes (`ResolveResult.status`):

- `exists` — resolved path is present → no finding
- `missing` — resolved path absent → PATH_ROT finding
- `skip` — optional resolver root missing → no finding (intentional
  silence; user authored the ref knowing it doesn't resolve locally)

If no resolver prefix matches, resolution falls back to the generic
three-way (doc location / project root / module root glob) and finally
`generic_path_fallbacks` (see below).

### `ignore_url_prefixes`

List of literal string prefixes; any referenced path starting with one
of these is treated as **not a file** and skipped during PATH_ROT. Useful
for docs that embed API endpoint strings (e.g. `/admin/auth/login`) which
look like file paths but aren't. Default: `[]` (no filtering — opt-in per
project so we don't over-filter docs that genuinely reference files under
a literal `/api/` directory).

Example: `["/api/", "/admin/", "/webhook/", "/actuator/"]`.

### `generic_path_fallbacks`

List of repo-relative directory prefixes tried as a **last-resort fallback**
when `resolve_reference`'s generic candidates (doc location, project root,
module root glob) all fail. Each entry is prepended in order and checked
for existence.

Typical use: monorepo / single-repo projects where docs reference code
with short relative paths (`components/Foo.vue`) but the actual file lives
under a conventional prefix (`frontend/src/components/Foo.vue`). Declaring
the prefix once in config avoids peppering every reference with the long
path.

Example:

```json
"generic_path_fallbacks": [
  "frontend/src/",
  "backend/src/main/java/com/example/",
  "docs/references/"
]
```

Default: `[]`.

**Order matters**: first existing file wins. Typical order is most-common
first (e.g. frontend before backend for a frontend-heavy project).

### `fact_patterns`

Enables the FACT_VALUE_CONFLICT drift check (see drift-taxonomy.md §6.5).
A fact pattern names a regex that extracts a `(key, value)` pair from each
matching line across all docs. When the same `(pattern_name, key)` pair
surfaces in ≥2 distinct docs with ≥2 distinct values, a warning fires.

Each entry:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Label used in the finding detail (e.g. `"file_line_count"`, `"backend_port"`). |
| `regex` | yes | Python regex compiled once per check run. Must capture `key_group` and `value_group`. Invalid regex → schema error, pattern skipped. |
| `key_group` | yes | 1-based regex group index identifying the fact *key* (what's being described — e.g. a filename or service name). |
| `value_group` | yes | 1-based regex group index identifying the fact *value* (the number/string that must agree across docs). |

Intra-doc repetition is ignored: only cross-doc divergence triggers a
finding. A finding names every `(doc:line, value)` site so the user can
decide which is authoritative.

Default: `[]` (check disabled).

**Typical uses**:

- File line counts (`PaymentService.java (1497)` vs `(1200)`)
- Port pins, version pins repeated across module docs
- Environment URL / domain cited in summaries

Example:

```json
"fact_patterns": [
  {
    "name": "file_line_count",
    "regex": "([\\w.-]+\\.(?:java|vue|py|js|ts))\\s*\\((\\d{3,})\\)",
    "key_group": 1,
    "value_group": 2
  },
  {
    "name": "backend_port",
    "regex": "(backend|api).{0,20}?port[:= ]+(\\d{4,5})",
    "key_group": 1,
    "value_group": 2
  }
]
```

### `entity_patterns` and `entity_policy_file`

Enables the ENTITY_COVERAGE drift check (see drift-taxonomy.md §6.6).
Catches source-side entities (Controllers, Handlers, Vue views, etc.)
that exist on disk but are not mentioned in any reference doc.

Each `entity_patterns` entry:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Label for the entity class, used in findings (e.g. `"Controller"`, `"Handler"`). |
| `source_glob` | yes | Repo-relative glob (passed to `glob.glob` with `recursive=True`) identifying source files. Basenames feed `entity_pattern`. |
| `entity_pattern` | yes | Python regex applied to each basename. **Group 1 is the entity name.** Files that don't match are silently skipped (not every file under the glob is necessarily an entity). |
| `ref_scope` | yes | Repo-relative glob for reference docs. The concatenated text of every match is searched for each entity name as a plain substring. |

If `ref_scope` matches 0 files, a single INFO finding is emitted instead
of flooding with N false positives — this is typically a misconfiguration
(wrong glob, or refs not yet created).

**Policy file** (`entity_policy_file`, default `.claude/doc-garden-entity-policy.txt`):

Per-line format:

```
# comments start with '#'
LEVEL: EntityName  # reason
```

| Level | Effect in v1 |
|-------|--------------|
| `IGNORED` | Entity is skipped silently (dev/test-only, not a business surface) |
| `KNOWN_UNDOCUMENTED` | Silent in v1 (planned: shown only in a future verbose mode) |
| (absent from policy) | Default path → emit ENTITY_COVERAGE finding |

Malformed policy lines are silently skipped; a typo in a classification
should not fill the audit report with noise. Validate the policy file
manually when adding entries.

**Convention**: every `IGNORED` / `KNOWN_UNDOCUMENTED` entry carries a
reason after `#`. Entries without reasons are not rejected by the
parser, but reviewers should reject them at code review.

Example setup:

```json
"entity_patterns": [
  {
    "name": "Controller",
    "source_glob": "backend/src/main/java/com/example/controller/*.java",
    "entity_pattern": "^(\\w+Controller)\\.java$",
    "ref_scope": "docs/references/*.md"
  },
  {
    "name": "AdminController",
    "source_glob": "backend/src/main/java/com/example/admin/**/*.java",
    "entity_pattern": "^(Admin\\w+Controller)\\.java$",
    "ref_scope": "docs/references/admin-*.md"
  }
]
```

Policy example:

```
IGNORED: HealthCheckController     # liveness probe, no business surface
IGNORED: MetricsController         # Prometheus scrape endpoint
KNOWN_UNDOCUMENTED: MemoController # edge feature, planned for content-ref
```

## Target Skeletons by Project Type

### Microservice

**Root CLAUDE.md**:

| Section | Level | Purpose |
|---------|-------|---------|
| 模块速查 | Required | Module name, tech stack, port, CLAUDE.md path |
| 分支策略 | Required | Branch names, merge direction |
| 部署流程 | Required | Commands + environment differences |
| 环境信息 | Required | IP/port/namespace table by environment |
| 踩坑记录 | Recommended | Problem-cause-solution |

**Module CLAUDE.md**:

| Section | Level | Purpose |
|---------|-------|---------|
| 技术栈 | Required | Language version + framework + build tool |
| 常用命令 | Required | Start/build/test/deploy |
| 架构概览 | Recommended | Key directories + core classes |
| 注意事项 | Recommended | Module-specific traps |

### Standalone

**CLAUDE.md** (single file):

| Section | Level |
|---------|-------|
| 技术栈 | Required |
| 常用命令 | Required |
| 架构概览 | Recommended (when >5 source files) |

### Memory (all project types)

- Every `.md` in memory dir must have YAML frontmatter (`---` block with name, description, type)
- MEMORY.md must index every memory file (0 sunken tolerance)
- MEMORY.md organized by semantic sections (`## 模块文档`, `## 用户偏好`, etc.)

## Normalization Rules

| Current State | Action | Level |
|---------------|--------|-------|
| Root CLAUDE.md missing | Generate skeleton template | suggest |
| Module CLAUDE.md missing | Generate skeleton (scan code for tech stack) | suggest |
| Required section missing | Suggest adding section | suggest |
| Memory file lacks frontmatter | Generate frontmatter template | semi-auto |
| MEMORY.md missing sunken file | Suggest insert position by section | semi-auto |
| MEMORY.md has ghost reference | Delete reference | auto |

## Idempotency

Running normalize twice must produce no additional changes:
- Skeleton: check section existence before suggesting
- Frontmatter: check for `---` first line before suggesting
- Index: check filename in MEMORY.md before suggesting
