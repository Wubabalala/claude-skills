# code-review

Pragmatic code review & pre-push quality gate for Claude Code.

```bash
npx skills add Wubabalala/claude-skills@code-review
```

## What It Does

A structured, risk-based code reviewer that catches real bugs — not style nitpicks.

1. **Auto-detects review scope** — unpushed commits → staged changes → working tree (fallback chain)
2. **Two-layer architecture** — universal checks (Layer 1) + project-specific rules from your docs (Layer 2)
3. **P0-P3 severity grading** — security, logic bugs, robustness, maintainability
4. **Code scoring (1-10)** — quantified quality assessment at report top and bottom
5. **Git blame regression detection** — flags deleted code from security-fix commits
6. **Blast radius analysis** — counts callers of modified functions
7. **Auto-fix for deterministic issues** — .gitignore, unused imports, debug remnants
8. **Mandatory test coverage table** — every new/modified function listed, missing tests escalate risk

## Usage

In Claude Code, type `/code-review` or say "review my code", "ready to push", "check code quality".

### Run Modes (v2.3+)

The skill supports two modes via the `--mode=` argument:

| Mode | When | Behavior |
|------|------|----------|
| `--mode=interactive` (default) | Human-invoked review | Full markdown report, may ask for confirmation, may offer auto-fix |
| `--mode=gate` | Pre-push hook / CI / `claude -p` | Read-only, never blocks waiting for input, never writes files; emits only an optional one-paragraph summary plus a machine-readable sentinel block |

Unknown `--mode=` values fall back to `interactive` (no crash).

### Machine-Readable Sentinel (v2.3)

Every report — in any mode — ends with a sentinel block that hooks and CI can grep without parsing markdown:

```
<!--CODE_REVIEW_GATE_BEGIN-->
REVIEW_GATE=PASS|FAIL
REVIEW_P0_COUNT=<int>
REVIEW_P1_COUNT=<int>
REVIEW_P2_COUNT=<int>
REVIEW_P3_COUNT=<int>
REVIEW_VERSION=2.3
<!--CODE_REVIEW_GATE_END-->
```

Decision rule: `REVIEW_GATE=FAIL` iff `P0_COUNT > 0 OR P1_COUNT > 0`, else `PASS`. The sentinel position is always at the end of the report.

### Human ↔ Machine verdict mapping

| Human verdict | `REVIEW_GATE` | Hook behavior |
|---------------|---------------|----------------|
| `[ READY TO PUSH ]` | `PASS` | proceed |
| `[ NEEDS FIXES ]` | `FAIL` | block |
| `[ REQUIRES DISCUSSION ]` | `PASS` | proceed |

`[ REQUIRES DISCUSSION ]` is a request for architectural conversation, not a must-fix — so the machine verdict still reads `PASS` and the push is not blocked. When `P0_COUNT > 0` or `P1_COUNT > 0`, the human verdict MUST be `[ NEEDS FIXES ]` (DISCUSSION is forbidden in that case) so the human and machine outputs never contradict.

## Roadmap (non-binding, subject to change)

- v2.1 (this release): machine-readable verdict layer (mode + sentinel + log-secrets P0)
- v2.2: pre-push hook, sentinel-driven, read-only, includes install/uninstall scripts
- v2.3 (this release): architecture-traps as authoritative source, checklist as derived artifact, dimensional metadata (severity / scope / frequency)

Versions and scope may evolve based on real-world usage feedback.

## Architecture Traps (v2.3)

Project-specific review memory now flows through `architecture-traps.md`.

- repo-level traps live at `docs/architecture-traps.md`
- module-level traps live at `<module>/docs/architecture-traps.md`
- `.claude/review-checklist.md` is a generated review view, not the source of truth
- automated regression detection only applies to traps that include an explicit `signatures` block

In interactive mode, the skill may suggest new traps when the same high-severity pattern appears in `>=3` distinct files. Confirmed backfill writes to traps only; the checklist is refreshed later through the normal generation flow.

## Key Features

| Feature | Description |
|---------|-------------|
| **Risk-based grading** | Files classified as HIGH/MEDIUM/LOW, review depth scales accordingly |
| **Layer 2 project rules** | Generates `.claude/review-checklist.md` from project docs and `architecture-traps.md` |
| **Cost-benefit rating** | Every issue rated 1-5 on fix cost vs. impact — you decide what to fix |
| **"Do NOT report" list** | 7 rules to prevent false positives (intentional design, framework patterns, etc.) |
| **Large diff handling** | 50+ file changes get risk-tiered: deep analysis for HIGH, surface scan for MEDIUM, skip LOW |
| **Risk escalation** | New functions without tests auto-escalate from MEDIUM to HIGH |
| **Red lines** | Deleted security-fix code, removed auth checks → immediate deep investigation |
| **Traps integration** | Root/module `architecture-traps.md` files act as authoritative project memory for regression detection |
| **Dimensional metadata** | Checklist entries can carry `severity`, `scope`, and `frequency`, with legacy fallback for older projects |

## Output Example

```
## Code Review Report

**Scope**: Lazy cache optimization for video markers
**Commits**: 164e328
**Risk Distribution**: P0: 0 | P1: 0 | P2: 1 | P3: 0
**Code Score**: 8/10 — Clean implementation, one minor .gitignore gap

### Summary
Well-structured caching layer with proper fallback. Minor config hygiene issue.

### P2 Robustness (should fix)
| Location | Issue | Fix Cost | Cost-Benefit |
|----------|-------|----------|--------------|
| .gitignore:43 | Missing storage/markers/ entry | low | 4/5 |

### Test Coverage (mandatory)
| New/Modified Function | Has Tests? | Risk Impact |
|-----------------------|------------|-------------|
| _normalize_fps() | no | escalated MEDIUM→HIGH |
| _marker_cache_key() | no | escalated MEDIUM→HIGH |

### Auto-Fix (deterministic issues)
```diff
# .gitignore
+ storage/markers/
+ storage/queue.db-shm
+ storage/queue.db-wal
```

### Final Verdict
**Code Score: 8/10** — Solid code, minor config gap
**[ READY TO PUSH ]** — 0 P0/P1 issues
```

## What Makes This Different

Compared to other code review skills in the ecosystem:

- **Scoring system** — no other skill quantifies code quality on a 1-10 scale
- **Auto-fix** — no other skill provides directly applicable fixes for deterministic issues
- **Project isolation (Layer 2)** — checklist generated per-project, not global
- **Git blame regression detection** — unique: catches re-introduced bugs from security fixes
- **Blast radius analysis** — unique: counts downstream callers before approving changes
- **Anti-false-positive rules** — 7 explicit "do not report" patterns prevent noise

## Works With

Claude Code, Cursor, Gemini CLI, Codex, Cline, Amp, and more.
