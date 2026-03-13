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

## Key Features

| Feature | Description |
|---------|-------------|
| **Risk-based grading** | Files classified as HIGH/MEDIUM/LOW, review depth scales accordingly |
| **Layer 2 project rules** | Auto-generates `.claude/review-checklist.md` from your CLAUDE.md and docs |
| **Cost-benefit rating** | Every issue rated 1-5 on fix cost vs. impact — you decide what to fix |
| **"Do NOT report" list** | 7 rules to prevent false positives (intentional design, framework patterns, etc.) |
| **Large diff handling** | 50+ file changes get risk-tiered: deep analysis for HIGH, surface scan for MEDIUM, skip LOW |
| **Risk escalation** | New functions without tests auto-escalate from MEDIUM to HIGH |
| **Red lines** | Deleted security-fix code, removed auth checks → immediate deep investigation |

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
