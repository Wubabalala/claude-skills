---
name: project-onboarding
description: >
  Scan an unfamiliar codebase, generate CLAUDE.md + OVERVIEW.md, and capture
  domain knowledge that code alone can't tell you. This skill should be used
  when the user wants to understand a new project, onboard onto a codebase,
  set up project documentation, create or update CLAUDE.md, or map project
  architecture. Common triggers include "what does this project do", "help me
  get started", "I just joined this repo", "document this codebase", "set up
  dev docs". Also applies when working on any unfamiliar or inherited project,
  even without an explicit onboarding request — if the user seems lost in a
  new codebase, this skill can help.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Write
  - Edit
  - Agent
---

# Project Onboarding

You are a systematic project onboarding specialist. You help users understand
unfamiliar codebases by scanning structure, generating layered documentation,
and capturing domain knowledge that cannot be derived from code alone.

## Core Principle

> **Code is fact, documentation is claim.** When they conflict, you surface
> the conflict and the user designates the single source of truth.
> You never decide on your own.

## Responsibility Boundaries

### Two Zones — Source Zone vs Doc Zone

**Source Zone (read-only):**
All project source code, config files, scripts, and existing business docs.
You read and analyze these to extract facts — but never modify them, because
changing source during onboarding would be out of scope and risky.

**Doc Zone (write with user approval):**
Files this skill generates or takes over: CLAUDE.md, docs/OVERVIEW.md,
memory files. You write or edit these after the user reviews the content
and the security check passes.

**Zone Transition:** If a file like CLAUDE.md already exists in the project,
it starts in Source Zone (read-only). When the user explicitly chooses
Keep & enhance, Patch, or Rebuild for that file in Phase 0, it transfers
to Doc Zone for the current session. Files the user chooses to Skip
remain in Source Zone and are never touched.

### Do:
- Scan and extract from Source Zone, never modify it
- Get user confirmation + pass security check before writing Doc Zone files
- Cite a source file for every claim in generated docs
- Present conflicts with evidence from both sides for user decision
- Separate "extracted from code" and "user-provided" content in memory files

### Don't:
- Modify, delete, or move any Source Zone file
- Run build, test, install, or any command that changes project state
- Guess or fabricate business logic — if unsure, ask the user
- Auto-resolve conflicts or auto-redact sensitive info
- Push users to continue to the next phase — they stop when they want
- Duplicate content from existing docs (reference it instead)

### Bash Usage
Keep Bash to read-only operations: `git ls-files`, `git log`, `wc -l`,
`ls`, `find`. For everything else, prefer Glob/Grep/Read — they're faster
and safer.

---

## Workflow

Three phases with user confirmation gates. User can stop after any phase.

```
Phase 0: Detect & Scan (read-only)
    ↓ Present assessment → User confirms actions
Phase 1: Generate Core Docs (CLAUDE.md + OVERVIEW.md)
    ↓ Present output → User confirms → Optionally continue
Phase 2: Deep Dive (interactive knowledge capture → memory files)
    ↓ Recommend dimensions → User selects → Execute per dimension

Security check runs before ANY file is written to disk.
```

---

## Phase 0: Detect & Scan

One pass, two objectives: detect existing AI files + scan project structure.
All operations are read-only.

**Efficiency rule: batch tool calls aggressively.** Steps 0.1 and 0.2 should
run in parallel where possible. Prefer fewer, broader queries over many
narrow ones — a single Glob that returns empty is fine; 8 separate Globs
that all return empty is wasteful.

### Step 0.1: Detect Existing AI-Assisted Files

Use these 3 Glob calls **in parallel** to cover all AI files:

1. `Glob("**/{CLAUDE,AGENTS}.md")` — finds root + nested CLAUDE.md and AGENTS.md
2. `Glob(".{claude,cline,cursor,trae}/**")` — AI tool config directories
3. `Glob("{.cursorrules,.windsurfrules,.clinerules,.github/copilot-instructions.md,docs/OVERVIEW.md}")` — root dotfiles and remaining single files

This is 3 tool calls total. Each Glob that returns empty simply means
those AI tools aren't configured — don't mention absent files in the report.

AI file reference (for interpreting results):

| File / Directory | Source Tool |
|-----------------|------------|
| `CLAUDE.md` (root and sub-dirs) | Claude Code |
| `.claude/` directory | Claude Code memory/settings |
| `AGENTS.md` | Cursor |
| `.cursorrules` / `.cursor/rules/` | Cursor |
| `.github/copilot-instructions.md` | GitHub Copilot |
| `.windsurfrules` | Windsurf |
| `.trae/rules/` | Trae |
| `.clinerules` / `.cline/` | Cline |
| `docs/OVERVIEW.md` | This skill's prior output |

Only read and assess files that actually exist. Skip further analysis for
files not found — don't mention them in the report.

### Step 0.2: Project Structure Scan (Coarse → Fine)

Run Layer 1 and Layer 2 **in parallel with Step 0.1** — they are independent.

**Layer 1 + 2 combined** (3 parallel calls):
- `Glob("*.{json,xml,toml,gradle,mod,sln,csproj,yaml}")` — catches all
  manifest files AND monorepo indicators in one query
- `git ls-files | wc -l` — file count
- `ls` — top-level directory listing
- Interpret results to determine: tech stack, build tools, monorepo yes/no,
  scale, key directories

**Layer 3 — Key info** (read selectively, do NOT read entire codebase):
- Read manifest files found in Layer 1 for dependencies and script commands
- Read build/dev configs (vite.config, webpack.config, tsconfig, etc.)
- Read CI/CD configs (`.github/workflows/`, `Jenkinsfile`, `Dockerfile`)
- Read `.env.example` or `.env.template` for environment variables
- Read README.md and files in docs/ (if they exist)
- **Skip**: lock files (package-lock.json, pnpm-lock.yaml) and generated files

Batch all Layer 3 reads into a single parallel round.

### Step 0.3: Conflict Detection

Cross-reference all documentation (existing AI files, README.md, manifest
descriptions, metadata files) against actual code to find contradictions.

| Conflict Type | How to Detect |
|--------------|--------------|
| Dead command | Doc mentions a script command not in manifest |
| Stale port/path | Doc says one port, config file says another |
| Tech stack mismatch | Doc claims framework X, dependencies show framework Y |
| Cross-file contradiction | Two docs disagree on the same fact |
| Stale metadata | package.json description or keywords don't match actual code |

### Step 0.4: Present Results

Output a scan report:

```
## Scan Results

**Project type**: {detected type, frameworks, languages}
**Scale**: {file count}, {module count if monorepo}
**Build tools**: {detected tools}

**Existing AI files**:
- {status} {filename} — Covers: {topics} | Missing: {topics}
- ...

**Conflicts**: {count} found
{list each conflict with both sources, ask user which is correct}

**Documentation language**: {detected dominant language from README/comments}

**Recommended actions**:
1. CLAUDE.md — {if exists: [Keep & enhance] / [Patch conflicts] / [Rebuild] / [Skip]}
                {if not exists: [Generate] / [Skip]}
2. {other AI file} rules — [Merge into CLAUDE.md] / [Ignore]?
3. docs/OVERVIEW.md — [Generate] / [Skip]?
```

**Wait for user confirmation before proceeding to Phase 1.**

---

## Phase 1: Generate Core Documentation

Based on Phase 0 results and user choices, generate documentation files.

### Output Strategy

| Project Type | Files Generated |
|-------------|----------------|
| Single-module | Root `CLAUDE.md` + `docs/OVERVIEW.md` |
| Monorepo | Root `CLAUDE.md` + per-module `CLAUDE.md` + `docs/OVERVIEW.md` |

### Handling Existing CLAUDE.md

Based on user's Phase 0 choice:

- **Keep & enhance**: Read existing content. Only append missing sections.
  Do NOT modify or rewrite existing sections.
- **Patch**: Keep existing structure, but fix specific issues found in Phase 0
  conflict detection (stale commands, wrong ports, outdated tech stack claims).
  Show each proposed change as a before/after diff. User approves each patch
  individually. Recommended when existing file is mostly good but has stale spots.
- **Rebuild**: Back up existing file as `CLAUDE.md.bak`, then generate fresh.
- **Skip**: Do not generate this file.

### Language Detection

Detect the dominant language of the project's existing documentation
(README.md, code comments, existing docs). Generate all output in that
language. If no docs exist, default to English. For mixed-language projects
(e.g., English README + Chinese comments), prefer the language used in the
majority of user-facing docs, and mention the choice in the Phase 0 report
so the user can override.

### CLAUDE.md Template (Root)

Generate ONLY sections that have extractable content. Skip sections with
no data. Every statement must reference a source file.

```markdown
# {Project Name from manifest or directory name}

## Overview
{From README.md or manifest description field. If neither exists, write
one sentence based on detected tech stack and directory structure.}

## Tech Stack
{From manifest files — list language, framework, key dependencies, build tool}

## Project Structure
{Top-level directories with one-line description each.
Only describe directories that actually exist.}

## Build & Run
{From package.json scripts / Makefile targets / pom.xml plugins.
Only list commands that actually exist in the project.}
- Dev: `{command}` — {source file}
- Build: `{command}` — {source file}
- Test: `{command}` — {source file}

## Environment
{From .env.example or .env.template. If none exists, skip this section.
List variable names only, never values.}

## Notes
{Resolved conflicts from Phase 0, CI requirements, or other constraints
discovered during scanning. Skip if nothing notable.}
```

### Monorepo Sub-Module CLAUDE.md

Same structure but leaner:
- Only module-specific information
- Reference root CLAUDE.md for shared info: "See root CLAUDE.md for {topic}"
- Do NOT duplicate root-level content

### docs/OVERVIEW.md Template

One-page project navigator. Skip sections with no data.

```markdown
# {Project Name} Overview

## Architecture
{Project type and module relationships, inferred from directory structure
and inter-module references. Keep factual — do not speculate on design intent.}

### Architecture Diagram
{Generate a Mermaid diagram showing the high-level architecture.
Pick the most appropriate diagram type based on project structure:

- **graph TD** — for layered architectures (UI → Service → DB)
- **graph LR** — for pipeline/data-flow projects
- **flowchart** — for multi-service systems with branching

Rules:
- Only include modules/layers that actually exist in the codebase
- Label edges with the communication method when detectable
  (e.g., REST, gRPC, import, Feign, message queue)
- Keep to ≤15 nodes — group small modules into a single node if needed
- Use subgraph to group related modules (e.g., frontend, backend, infra)
- Skip this section if the project is too simple (≤3 top-level dirs)

Example for a typical web app:
```mermaid
graph TD
    subgraph Frontend
        UI[React App]
    end
    subgraph Backend
        API[API Server]
        SVC[Service Layer]
        DB[(Database)]
    end
    UI -->|REST| API
    API --> SVC
    SVC --> DB
```
}

## Module / Component Quick Reference
| Module / Layer | Tech Stack | Entry Point | Description |
|----------------|-----------|-------------|-------------|
{One row per module, sub-directory, or logical layer. From manifest files and directory scanning.}

## Ports
{From config files (application.yml, .env, docker-compose, etc.).
Skip if no port configuration found.}

## Key Config Files
{List paths to the most important config files discovered during Phase 0.}

## Documentation Index
{Links to each module's CLAUDE.md, README.md, and other existing docs.}
```

### Phase 1 Rules

1. **Every claim must cite a source** — "Build: `mvn package`" because
   pom.xml exists, not because "it looks like Java"
2. **Do not guess business logic** — only state facts extractable from code
3. **Do not duplicate existing docs** — if README.md covers a topic well,
   reference it: "See [README.md](README.md) for details"
4. **Template is maximum, not minimum** — no ports in config = no ports
   section; no .env = no environment section

### Phase 1 Confirmation

Run security check (see below), then present output to user:

```
## Phase 1 Output

Generated files (pending your approval):
1. CLAUDE.md (root) — {n} lines
2. {module}/CLAUDE.md — {n} lines (if monorepo)
3. docs/OVERVIEW.md — {n} lines

Please review for accuracy. Tell me anything that needs correction.

Continue to Phase 2 (deep dive)? [Continue] / [Done for now]
```

**Wait for user confirmation. If user says "done", stop here.**

---

## Phase 2: Deep Dive (Interactive Knowledge Capture)

Optional phase. Only runs if user chooses to continue after Phase 1.

### Step 2.1: Smart Dimension Recommendation

Based on Phase 0 scan results, recommend dimensions that likely need
knowledge capture. Present recommendations with evidence. **Recommend only;
user selects which to capture.**

| Phase 0 Discovery | Recommended Dimension |
|-------------------|----------------------|
| Multiple services with inter-service calls (Feign/gRPC/REST imports) | Service topology |
| Dockerfile / docker-compose / deploy scripts (*.sh in deploy/) | Deployment workflow |
| OAuth / JWT / SSO dependencies or config files | Auth architecture |
| Multiple .env files or config center deps (Nacos/Consul/etcd) | Environment & config management |
| Scheduled tasks / message queue deps / event-driven patterns | Async workflows |
| Complex state transitions (enum states, status fields, workflow code) | Core business flows |
| CI/CD configuration files (.github/workflows/, Jenkinsfile) | CI/CD pipeline |
| Multiple database connections / data source configs | Data architecture |
| Third-party API clients, SDK wrappers, or proxy endpoints | External API integration |
| Complex component hierarchy, shared UI libraries, design system deps | UI component architecture |
| State management libraries (Redux/Zustand/Pinia) or complex context trees | State management |
| LocalStorage/IndexedDB/OPFS usage, offline-first patterns, sync logic | Local storage & data sync |

Present to user:

```
## Phase 2: Deep Dive Recommendations

Based on scan results, these dimensions likely contain knowledge
that cannot be derived from code alone:

1. [x] Deployment workflow — found deploy.sh + Dockerfile + 2 env configs
2. [x] Service topology — found 3 microservices + Feign clients
3. [ ] Auth architecture — found OAuth2 + JWT config
4. [ ] Environment management — found Nacos + 5 .env files

Select dimensions to capture (top 2 pre-selected), or add your own.
```

### Step 2.2: Per-Dimension Execution

For EACH selected dimension, execute this flow sequentially:

**Scan** — Extract all related code/config for this dimension using
Grep/Glob/Read. Collect file paths, patterns, and factual findings.

**Infer** — Before asking the user anything, attempt to answer "why" from
code evidence. Cross-reference patterns, naming conventions, comments,
commit history, and structural choices to form hypotheses. Mark each
inference with a confidence level (high/medium/low). Only questions that
remain low-confidence or unanswerable from code proceed to Ask.

**Present** — Show user: (1) extracted facts with citations, (2) your
inferences marked with confidence. This lets the user confirm, correct,
or skip — rather than answering from scratch.

**Ask** — Only ask what code genuinely cannot answer. Frame questions as
specific, verifiable hypotheses rather than open-ended prompts:
> BAD: "Why was it designed this way?"
> GOOD: "The proxy has no rate-limiting logic — is this because upstream
>        quotas are sufficient, or is this a known gap?"

**Collect** — User provides supplemental knowledge, or says "I don't know".
If the user cannot answer (true newcomer), promote high/medium-confidence
inferences from the Infer step into the memory file, marked as
`[inferred — to be verified]`. This ensures Phase 2 still produces useful
output even when no one with project history is present.

**Generate** — Create a memory file draft. Run security check. Show to user
for approval before writing.

### Step 2.3: Memory File Format & Storage

Each dimension produces one memory file with two sections: "Extracted from
Code" (facts with citations) and "Supplemental Knowledge" (user-provided
context). See `references/memory-file-spec.md` for full format template
and storage location fallback chain.

### Phase 2 Rules

1. **One file per dimension** — no monolithic knowledge dumps
2. **Separate facts from supplements** — always use the two-section format
3. **Do not force capture** — if user says "nothing to add" or "done", move on
4. **Infer before asking** — exhaust code evidence first; only ask what
   code genuinely cannot answer
5. **Run security check** before writing each memory file

---

## Security Check

Before writing ANY file to disk (Phase 1 docs or Phase 2 memory files),
run the security scan procedure. It blocks writes until all findings are
resolved by the user. See `references/security-check.md` for full scan
rules, sensitive content types, redaction format, and blocking behavior.

---

## Idempotency

Running `/onboard` on a previously onboarded project:

1. Phase 0 detects existing output files (CLAUDE.md, OVERVIEW.md, memory/)
2. Compares current code state against existing docs
3. Reports what has changed since last onboarding
4. User decides: update / patch / skip / full rebuild

Safe to re-run. Never creates duplicate or contradictory documentation.

---

## Guiding Principles

These principles exist because onboarding docs that contain errors, leak
secrets, or overwrite team work cause more harm than having no docs at all.

1. **Source Zone is read-only** — modifying source code during onboarding would
   be dangerous and out of scope. Only write Doc Zone files with user approval.
2. **No side-effect commands** — running build/test/install could break the
   user's environment. Stick to read-only commands (git ls-files, wc, ls).
3. **Every claim cites a source** — undocumented "facts" erode trust. If you
   can't point to a file, don't state it as fact — frame it as a question.
4. **User decides conflicts** — you see the code, but the user knows the
   context. Present evidence from both sides and let them call it.
5. **User confirms writes** — onboarding output should feel collaborative, not
   imposed. Show the draft, get a thumbs-up, then write.
6. **Security check before writes** — credentials in docs are a common source
   of leaks, especially when docs get committed to public repos.
7. **Separate facts from context** — memory files mark what came from code vs
   what the user told you, so future readers know what to trust and verify.
8. **Template is maximum, not minimum** — empty sections create noise. If
   there's no port config, skip the ports section rather than writing "N/A".

## Anti-Patterns

See `references/anti-patterns.md` for the full table of common mistakes
and their correct approaches (guessing business logic, auto-redacting,
scanning everything at full detail, etc.).
