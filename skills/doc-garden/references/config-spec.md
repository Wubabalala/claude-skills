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
**Optional fields**: `layer2`, `docs`, `environment_domains`, `staleness_threshold_days`, `ignore_paths`
**Never stored**: memory directory path (derived at runtime from cwd)

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
- All writes logged to `.claude/doc-garden-last-normalize.json`
