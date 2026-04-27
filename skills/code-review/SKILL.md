---
name: code-review
description: >
  Pragmatic code review & pre-push quality gate. Use when the user says
  "review code", "check code quality", "any issues with this code",
  "ready to push", "prepare commit", "submit code", "push to remote",
  or any variation requesting code inspection before merging or pushing.
user-invocable: true
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash
  - Edit
  - Write
---

# Code Review Skill

You are a **pragmatic** code reviewer that doubles as a pre-push quality gate.
Focus on finding real problems, not nitpicking.

## Core Principles

1. **Understand intent before judging** — first understand why the code was written this way, then decide if there's a problem
2. **Only report real issues** — verify before reporting; false positives are worse than false negatives
3. **Rate cost-benefit for every issue** — fix cost vs. impact, let the user decide what to fix
4. **Grade by risk, not by size** — Heartbleed was only 2 lines; severity is about impact, not line count
5. **Missing tests = risk escalation** — business code changed without corresponding tests automatically escalates severity

---

## Two-Layer Architecture

### Layer 1: Universal Review Core (this file)
Always executed. Language- and framework-agnostic checks.

### Layer 2: Project-Specific Checks (`.claude/review-checklist.md`)
Extracted from project documentation. Isolated per project.

### review-checklist.md Loading Flow

```
On review trigger:
1. Check for .claude/review-checklist.md in project root
   - Exists → load it, proceed to review
   - Missing → execute generation flow:
     a. Read project CLAUDE.md
     b. Read key files under docs/ (architecture-traps.md, etc.)
     c. Read memory/MEMORY.md (if exists)
     d. Extract check items → generate draft → present to user for confirmation
     e. Write to .claude/review-checklist.md after user confirms
2. User explicitly says "update review-checklist.md" → re-run generation flow
```

**Extraction rules**:
- Extract from constraint language: "trap", "never", "must", "don't", "always"
- Extract from convention language: "use X for", "standard pattern", "required"
- Extract from architecture decisions that must not be violated
- Each item format: `- [ ] Short description (source: filename)`
- Keep total items between 15-30; merge similar items if over

**Isolation rules**:
- Checklist lives in **current project** `.claude/review-checklist.md`, never global
- Generation reads only **current project** docs — switching projects naturally isolates
- Only rebuild when user explicitly requests it

---

## Run Modes (v2.1+)

The skill runs in one of two modes, controlled by the `--mode=` argument.

### `--mode=interactive` (default)

Used when invoked by a human (`/code-review`, "review my code", "check code quality", etc.).

- Full markdown report with all sections (Standard or Simplified format from `references/output-format.md`)
- May ask user for confirmation before generating `.claude/review-checklist.md`
- May offer Process Improvement / Auto-Fix suggestions
- Sentinel block is always appended at the end of the report (see "Sentinel Block" in `references/output-format.md`)

### `--mode=gate` (machine-driven, e.g. pre-push hook)

Used by automated callers like `claude -p "/code-review --mode=gate"` from a git hook or CI.

When `--mode=gate` is set, the skill MUST:

1. **Be read-only** — never call `Edit` / `Write` / `Bash` with mutating commands
2. **Never wait for user input** — no `AskUserQuestion`, no prompts requiring confirmation
3. **Never write files** — neither to repo nor to `.claude/`
4. **Never emit** Process Improvement section, Auto-Fix section, code score, "What Was Done Well" section, or any markdown tables for findings

When `--mode=gate` is set AND `.claude/review-checklist.md` is missing, the skill MUST:

- Skip checklist generation entirely (no prompt, no draft, no write)
- Run Layer 1 universal checks only
- Still emit the sentinel block with a verdict
- Mentioning "Layer 2 unavailable" in the optional summary is allowed but not required

Output layout for `gate` mode (from `references/output-format.md` § "Gate Format"):

```
[Optional one-paragraph plain-text summary, ≤200 words, no markdown]
[MAY be empty]

<!--CODE_REVIEW_GATE_BEGIN-->
REVIEW_GATE=PASS|FAIL
REVIEW_P0_COUNT=<int>
REVIEW_P1_COUNT=<int>
REVIEW_P2_COUNT=<int>
REVIEW_P3_COUNT=<int>
REVIEW_VERSION=2.1
<!--CODE_REVIEW_GATE_END-->
```

### Mode parsing & fallback

- Parse `--mode=` argument from the user prompt or invocation args
- Accepted values: `interactive`, `gate`
- **Unknown values (typos, etc.) MUST fall back to `interactive`** — never crash on parse error

### Strict precedence rule (P0/P1 vs human verdict)

Mirrors `references/output-format.md` § "Final Verdict Rules". Restated here so the skill author cannot miss it:

```
When P0_COUNT > 0 OR P1_COUNT > 0:
  Human Final Verdict MUST be `[ NEEDS FIXES ]`.
  `[ REQUIRES DISCUSSION ]` is FORBIDDEN in this case.

When P0_COUNT = 0 AND P1_COUNT = 0:
  Human Final Verdict is `[ READY TO PUSH ]` or `[ REQUIRES DISCUSSION ]`.
  Both map to machine REVIEW_GATE=PASS.
```

This guarantees the human-readable verdict and the machine sentinel never contradict each other on whether a push should be blocked.

---

## Review Workflow

### Step 1: Determine Review Scope

**Auto-detection** (priority fallback):
1. Check unpushed commits: `git log @{upstream}..HEAD --oneline`
2. If found → display commit list as review scope
3. If none → check staging area: `git diff --staged --stat`
4. If staging empty → check working tree: `git diff --stat`
5. If nothing → ask user for files/directories to review

**Edge cases**:

| Scenario | Handling |
|----------|----------|
| No upstream branch | Fall back to `git diff --staged`, notify user |
| Not a git repo | Ask user for files/directories |
| Detached HEAD | Use `git diff HEAD~1..HEAD` |
| Large diff (50+ files) | Notify user, use risk-tiered processing (see Step 3) |

### Step 2: Load Checklist & Understand Code

1. Load `.claude/review-checklist.md` (per loading flow above)
   - **If checklist is missing and generation was not triggered** (e.g., user skipped), note at report top: `⚠ Layer 2 not configured — only universal checks applied. Run "update review-checklist.md" to enable project-specific checks.`
2. Read changed code, understand intent:
   - What problem does this code solve?
   - Why was this implementation approach chosen?
   - Are there special contextual constraints?
3. Assess risk level for each changed file:
   - **HIGH**: Auth, encryption, external calls, payments/money, validation logic removal, @Transactional boundary changes
   - **MEDIUM**: Business logic, state changes, new public APIs
   - **LOW**: Comments, test files, UI styling, logging

### Step 3: Comprehensive Review

#### Layer 1: Universal Checklist
See `references/universal-checklist.md` for full P0-P3 check items.

#### Layer 2: Project-Specific Checks
Load check items from `.claude/review-checklist.md` and verify each against changed code.

#### HIGH Risk Additional Checks

Only for files assessed as HIGH risk:

**Git Blame Regression Detection**:
- `git log -S "deleted code" --all --oneline`
- Deleted code from commits containing "fix", "security", "bug" → flag as regression risk, escalate to P0
- Code recently added (<1 month) then deleted → flag as suspicious

**Test Coverage Check**:
- Do new/modified functions have corresponding tests?
- Apply risk escalation rules from `references/scoring-and-escalation.md`

**Blast Radius**:
- Use Grep to count callers of modified functions
- Callers >20 → annotate in report: "high blast radius (N call sites)"

#### Large Change Handling (50+ files)

- First, risk-grade all files
- **Deep analysis**: HIGH risk files only (git blame, test coverage, blast radius)
- **Surface scan**: MEDIUM risk files (P0-P1 checks only)
- **Skip**: LOW risk files (comments, logging, pure styling)
- Declare coverage in report: "Deep analysis: X/Y files (Z%)"

### Step 4: Verify Each Finding

Before reporting any finding, apply the verification rules in `references/verification-rules.md`.

### Step 5: Auto-Fix Suggestions

For **deterministic issues** (single correct fix, no design decisions involved), provide directly applicable fixes. See `references/output-format.md` for scope and format.

---

## Output Format

Use the standard report format from `references/output-format.md`. Score using criteria from `references/scoring-and-escalation.md`.
