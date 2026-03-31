# Verification Rules

## Verify Each Finding Before Reporting

Before reporting, confirm:
- Is this really a bug, or did I misunderstand?
- Is there a legitimate design reason?
- Does the fix benefit outweigh the cost?
- Does the project's global error handler already cover this scenario?

## Mandatory Verification for Interface/Protocol/API Findings

Skip any of these → finding is unverified → do NOT include in report:

| Check | How | Anti-pattern |
|-------|-----|-------------|
| Producer-consumer dual verification | Before claiming "field may be missing", read the producer-side code to confirm whether it guarantees the field | Only looked at frontend `x \|\| []` and filed P1, never checked if server always returns x |
| Dependency chain evidence | Before claiming "missing X causes Y to break", grep to confirm Y actually reads X | Claimed "missing roundTurnOrder causes problems" but the consuming function never uses that field |
| Complete pattern coverage | After finding one instance of a pattern issue, search for ALL similar occurrences — report all or none | Only reported availableActions risk in split_action, missed that action_execute has the same dependency |

## What NOT to Report

These are **not problems** — do not report them:

1. **Intentional design** — e.g., IIFE used for a specific purpose
2. **Standard framework usage** — e.g., Axios async interceptors
3. **Has a safety net** — e.g., global error handler exists, local catch not needed
4. **Pure style preference** — naming conventions, blank lines, comment density
5. **Over-defensive coding** — theoretically possible but practically impossible scenarios
6. **Pure refactor with no behavior change** — unless it breaks an invariant (verify first)
7. **Simplified patterns in test files** — tests are allowed to be looser than production code

## Review Discipline (Do Not Skip)

| Common Excuse | Why It's Wrong | Correct Approach |
|---------------|----------------|------------------|
| "Small change, quick look" | Heartbleed was 2 lines | Grade by risk, not size |
| "I know this codebase" | Familiarity creates blind spots | Still check git blame |
| "Missing tests isn't my problem" | Missing tests = risk escalation | Note in report, escalate severity |
| "Just a refactor" | Refactors can break invariants | Treat as HIGH until confirmed safe |
