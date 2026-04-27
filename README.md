# claude-skills

> ⭐ If you find these skills useful, [star this repo](https://github.com/Wubabalala/claude-skills) — it helps others discover them!

Practical Claude Code skills born from real production projects, not templates.

## Skills

### project-onboarding

**The fastest way to understand an unfamiliar codebase with Claude Code.**

```bash
npx skills add Wubabalala/claude-skills@project-onboarding
```

Then in Claude Code:
```
/onboard
```

#### The Problem

You join a new project. You spend hours reading scattered docs, guessing build commands, figuring out which configs matter. Existing "onboarding" tools dump a directory listing and call it done.

#### What This Skill Actually Does

```
Phase 0: Detect & Scan
  ├── Finds existing AI files (CLAUDE.md, .cursorrules, AGENTS.md, .windsurfrules...)
  ├── Scans project structure coarse-to-fine (type → scale → key info)
  ├── Cross-checks docs against code — surfaces stale commands, wrong ports, outdated claims
  └── You decide: keep / patch / rebuild / skip each file

Phase 1: Generate Core Docs
  ├── CLAUDE.md — every claim backed by a source file path
  ├── Per-module CLAUDE.md (monorepo auto-detected)
  ├── docs/OVERVIEW.md — one-page project navigator
  └── Security scan blocks writes if credentials detected

Phase 2: Deep Dive (optional)
  ├── Recommends dimensions based on what it found (deploy scripts → ask about deployment)
  ├── Asks "WHY was it designed this way?" — captures what code can't tell you
  └── Writes memory files with clear fact vs user-knowledge separation
```

#### Why Not Just Read the Code?

Code tells you **what** exists. It doesn't tell you:
- Why there are two auth systems (legal required SSO for one, JWT for the other)
- Why deploys must run macOS before Windows
- Which config change broke prod last month
- That the `test` script in package.json hasn't worked since the migration

This skill extracts facts from code, then **asks you the questions that matter**.

#### How It's Different from Other Onboarding Skills

| | project-onboarding (this) | agent-studio | goodvibes |
|---|---|---|---|
| Detects existing AI files | 8 tools (.cursorrules, AGENTS.md, .windsurfrules...) | memory dir only | no |
| Finds stale/wrong docs | yes, cross-checks against code | no | no |
| Fixes stale docs | Patch mode (targeted before/after diffs) | no | no |
| Captures domain knowledge | Phase 2: asks "why", separates facts from context | no | no |
| Security scan | blocks writes if passwords/keys/IPs found | no | no |
| Monorepo support | auto-detected, per-module CLAUDE.md | no | partial |
| Source code safety | Source Zone / Doc Zone model, never touches code | not defined | not defined |

#### Example Output

After running `/onboard` on a microservices project:

```
Scan Results

Project type: Java (Spring Cloud) + Next.js + Python (FastAPI)
Scale: 1,247 files, 7 modules
Build tools: Maven, pnpm, uv

Existing AI files:
  CLAUDE.md (root) — Covers: build commands | Missing: service topology, deployment
  .cursorrules — Covers: code style | Conflict: claims React, project uses Vue

Conflicts: 1 found
  .cursorrules says "React", package.json has "vue": "^3.4" → Which is correct? [Code] / [Doc]

Recommended actions:
  1. CLAUDE.md — [Keep & enhance] / [Patch conflicts] / [Rebuild] / [Skip]?
  2. .cursorrules — [Merge into CLAUDE.md] / [Ignore]?
  3. docs/OVERVIEW.md — [Generate] / [Skip]?
```

#### Design Principles

- **Code is fact, documentation is claim** — conflicts surfaced, user decides
- **Source-safe** — never modifies source code or configs; only writes doc files
- **User confirms all writes** — nothing touches disk without approval
- **Template is maximum, not minimum** — sections skipped if not applicable
- **Ask "why", not "what"** — code scanning is commodity; asking the right questions is the value

---

### code-review

**Pragmatic code review & pre-push quality gate, with a machine-readable verdict.**

```bash
npx skills add Wubabalala/claude-skills@code-review
```

Then in Claude Code:
```
/code-review
```

#### What It Does

Risk-based code review that catches real bugs (not style nitpicks) and produces output that both humans and machines can trust:

```
Universal Layer 1 checks (always)
  ├── P0 Security (hardcoded secrets, SQL injection, XSS, auth removal)
  ├── P0 Transaction Safety (cross-table atomicity, rollback-only catches)
  ├── P0 Logging Secrets Leakage (runtime print + client-side persistence)
  ├── P1 Logic Bugs (crashes, race, return/build mismatch)
  ├── P1 API Input Validation (NPE on missing fields, parse-without-try)
  ├── P2 Robustness (N+1, empty catch, ORM pitfalls)
  └── P3 Maintainability

Project Layer 2 checks (optional, per-project)
  └── .claude/review-checklist.md — auto-generated from your CLAUDE.md and docs

Output (every report ends with a machine-readable sentinel):
  <!--CODE_REVIEW_GATE_BEGIN-->
  REVIEW_GATE=PASS|FAIL
  REVIEW_P0_COUNT=<int>
  ... (P1/P2/P3 counts)
  REVIEW_VERSION=2.1
  <!--CODE_REVIEW_GATE_END-->
```

#### Two Run Modes

| Mode | When to use | Behavior |
|------|-------------|----------|
| `--mode=interactive` (default) | Human-invoked review | Full markdown report, may ask for confirmation, may offer auto-fix |
| `--mode=gate` | Pre-push hook / CI | Read-only, never waits for input, never writes files, emits only the sentinel + optional ≤200-word summary |

Unknown `--mode=` values fall back to `interactive`.

#### Why the Sentinel Matters

Without a stable machine-parseable verdict, any pre-push hook that greps `[ NEEDS FIXES ]` from natural-language output will eventually misparse — false positives block clean code, false negatives let regressions through. The sentinel block fixes that:

- HTML-comment wrapped (invisible in rendered markdown, greppable by hooks)
- Fixed schema, fixed field names, fixed position (always last)
- v2.2 hook (planned) will consume `^REVIEW_GATE=(PASS|FAIL)$` directly

#### Roadmap (non-binding, subject to change)

- **v2.1 (this release)**: machine-readable verdict layer + secrets-in-logs P0
- **v2.2 (planned)**: pre-push git hook (sentinel-driven, read-only, install/uninstall scripts)
- **v2.3 (planned)**: architecture-traps two-way binding + 3-dimensional rule metadata

---

### playwright-web-automation

**Browser automation that goes beyond recording — render diagrams, automate interactions, export screenshots.**

```bash
npx skills add Wubabalala/claude-skills@playwright-web-automation
```

#### Two Modes

| Mode | When to use | How it works |
|------|-------------|--------------|
| **A: Record** | Unknown page, need to explore | `npx playwright codegen <URL>` → paste recorded code → parameterize |
| **B: Direct** | Known workflow or render-to-image | Write script directly, skip recording |

#### What It Handles

- **Web interaction** — fill forms, click buttons, navigate multi-step flows, handle login state
- **Diagram rendering** — Mermaid, custom HTML/SVG → high-res PNG export
- **Canvas export** — extract rendered content from Canvas elements (even inside iframes)
- **Screenshot automation** — full page, element-level, or high-DPI (2x) capture

#### Progressive Disclosure

```
SKILL.md (decide which path → skeleton steps)
  ├── references/render-to-image.md    (setContent + CDN rendering patterns)
  ├── references/export-strategies.md  (screenshot / Canvas / download)
  ├── references/iframe-and-canvas.md  (cross-origin iframe, contentFrame)
  ├── references/wait-strategies.md    (condition-based waiting, avoid sleep)
  ├── references/troubleshooting.md    (common errors + fixes)
  ├── templates/skeleton.mjs           (starter script with both paths)
  └── examples/
      ├── diagramgpt.mjs              (full: iframe + follow-up forms + Canvas)
      └── mermaid-render.mjs           (full: CDN Mermaid → batch PNG)
```

#### Design Principles

- **Two paths, one skeleton** — recording is optional, not mandatory
- **Headless by default** — `headless: true` for batch/render tasks, `false` for debugging
- **Reference on demand** — main doc stays under 120 lines; details loaded when needed
- **Real examples** — both examples are production-tested, not toy code

---

## All Skills

| Skill | One-liner | Install |
|-------|-----------|---------|
| **[project-onboarding](skills/project-onboarding/)** | Scan codebase, generate docs, capture domain knowledge | `npx skills add Wubabalala/claude-skills@project-onboarding` |
| **[code-review](skills/code-review/)** | Pragmatic review + machine-readable verdict (`REVIEW_GATE=PASS\|FAIL`) for pre-push hooks | `npx skills add Wubabalala/claude-skills@code-review` |
| **[playwright-web-automation](skills/playwright-web-automation/)** | Browser automation + diagram rendering with Playwright | `npx skills add Wubabalala/claude-skills@playwright-web-automation` |

More skills coming. Each one is built from real production workflows.

## Feedback

⭐ [Star this repo](https://github.com/Wubabalala/claude-skills) if it saved you time · 💬 [Issues & ideas](https://github.com/Wubabalala/claude-skills/issues) welcome

## License

MIT
