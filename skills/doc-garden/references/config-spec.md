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
  "ignore_paths": ["node_modules/", ".git/"]
}
```

**Required fields**: `project_type`, `doc_hierarchy.layer1`
**Optional fields**: `layer2`, `docs`, `doc_patterns`, `path_resolvers`, `environment_domains`, `staleness_threshold_days`, `ignore_paths`
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
three-way (doc location / project root / module root glob).

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
