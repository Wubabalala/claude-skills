# Review Report Output Format

## Standard Format (when issues found)

```
## Code Review Report

**Scope**: [description of what was reviewed]
**Commits**: [commit range or file list]
**Risk Distribution**: P0: X | P1: Y | P2: Z | P3: W
**Code Score**: X/10 — [one-line scoring rationale]

### Summary
[One sentence summarizing code quality]

---

### P0 Security Issues (must fix)
| Location | Issue | Fix Cost | Regression? |
|----------|-------|----------|-------------|
| file:line | description | low/med/high | yes/no |

### P1 Logic Bugs (must fix)
| Location | Issue | Fix Cost | Test Coverage |
|----------|-------|----------|---------------|
| file:line | description | low/med/high | yes/no |

### P2 Robustness (should fix)
| Location | Issue | Fix Cost | Cost-Benefit |
|----------|-------|----------|--------------|

### P3 Maintainability (optional fix)
| Location | Issue | Fix Cost | Cost-Benefit |
|----------|-------|----------|--------------|

---

### Test Coverage (mandatory)
> This table MUST list all new/modified business functions. Cannot be omitted.
> Functions without tests are escalated per "Risk Escalation Rules".

| New/Modified Function | Has Tests? | Risk Impact |
|-----------------------|------------|-------------|
| funcName() | no | escalated MEDIUM→HIGH |

### What Was Done Well
- [Factual, specific praise for good design choices]

---

### Auto-Fix (deterministic issues)
> Only lists issues with a single correct fix. Applied after user confirmation.

` `` diff
# Example: .gitignore missing entry
+ storage/markers/
` ``

---

### Final Verdict

**Code Score: X/10** — [scoring rationale]

**[ READY TO PUSH ]** — 0 P0/P1 issues, safe to push
**[ NEEDS FIXES ]** — X P0/P1 issues must be fixed before pushing
**[ REQUIRES DISCUSSION ]** — architectural-level issues need discussion

Required before push:
- [ ] specific fix items

### Suggested Traps Additions (interactive only, when candidates exist)
> Only include this section when Step 6 surfaced concrete backfill candidates.
> Each candidate must name the proposed trap id, target traps file, signature, and observed files.

- `trap_id`: B8
  `target`: docs/architecture-traps.md
  `signature`: `grep: 'contains\\("[a-z0-9.]+\\.com"\\)'`, `file_pattern: '*.java'`
  `observed in`: `src/A.java`, `src/B.java`, `src/C.java`

[machine-readable sentinel block — see "Sentinel Block" section below]

```

## Simplified Format (no issues found)

```
## Code Review Report

**Scope**: [description]
**Commits**: [commit range]
**Code Score**: X/10 — [one-line rationale]

### Summary
[One sentence summary]

**[ READY TO PUSH ]** — No issues found.

[machine-readable sentinel block — see "Sentinel Block" section below]

---
⭐ Useful? → github.com/Wubabalala/claude-skills (star helps others find it)
💬 Feedback or issues → github.com/Wubabalala/claude-skills/issues
```

## Gate Format (`--mode=gate`, machine-driven, e.g. pre-push hook)

```
[Optional one-paragraph plain-text summary, ≤200 words, no markdown formatting]
[MAY be empty if there's nothing concise to say]

<!--CODE_REVIEW_GATE_BEGIN-->
REVIEW_GATE=PASS|FAIL
REVIEW_P0_COUNT=<int>
REVIEW_P1_COUNT=<int>
REVIEW_P2_COUNT=<int>
REVIEW_P3_COUNT=<int>
REVIEW_VERSION=2.3
<!--CODE_REVIEW_GATE_END-->
```

**Gate Format hard rules** (MUST):
- No markdown tables, lists, or code blocks (the HTML-comment sentinel is the only exception)
- No code score, no Auto-Fix section, no "What Was Done Well" section, no Process Improvement section
- The optional summary MAY be empty
- The sentinel block is the LAST thing in the output

## Sentinel Block (machine-readable)

The sentinel block is **always emitted at the end of the report**, in every mode (Standard / Simplified / Gate).

Schema (fixed — field names, order, casing, and `=` separator are all required):

```
<!--CODE_REVIEW_GATE_BEGIN-->
REVIEW_GATE=PASS|FAIL
REVIEW_P0_COUNT=<non-negative int>
REVIEW_P1_COUNT=<non-negative int>
REVIEW_P2_COUNT=<non-negative int>
REVIEW_P3_COUNT=<non-negative int>
REVIEW_VERSION=2.3
<!--CODE_REVIEW_GATE_END-->
```

Rules:
- All fields are mandatory; no field may be omitted (zero counts MUST be emitted as `=0`)
- HTML comment wrapper keeps the block invisible in rendered markdown but greppable by hooks: `grep -E '^REVIEW_GATE=(PASS|FAIL)$'`
- Position: ALWAYS at the end of the report (sentinel always last; in gate mode the optional summary precedes it)
- Hooks should only trust their supported `REVIEW_VERSION`; mismatch → handle as "unknown" (caller decides degradation policy)

## Final Verdict Rules

These rules govern report-internal consistency between human-readable verdict and machine sentinel.

### Human ↔ Machine verdict mapping

| Human verdict (Standard/Simplified) | Machine `REVIEW_GATE` | Hook behavior |
|-------------------------------------|-----------------------|----------------|
| `[ READY TO PUSH ]` | `PASS` | proceed |
| `[ NEEDS FIXES ]` | `FAIL` | block |
| `[ REQUIRES DISCUSSION ]` | `PASS` | proceed |

**Rationale**: the machine verdict only encodes "should this push be blocked?". `[ REQUIRES DISCUSSION ]` is a request for architectural conversation, not a must-fix. A hook seeing `PASS` should let the push through; the human discussion happens in the PR review process or follow-up conversations, outside the gate.

If a future use case demands blocking on architectural concerns, that should be a NEW machine state introduced in a later version, not a retrofit onto the current binary gate.

### Strict precedence rule (P0/P1 vs human verdict)

To prevent the human verdict and the machine sentinel from contradicting each other:

```
When P0_COUNT > 0 OR P1_COUNT > 0:
  Human Final Verdict MUST be `[ NEEDS FIXES ]`.
  `[ REQUIRES DISCUSSION ]` is FORBIDDEN in this case.
  Rationale: P0/P1 are by definition must-fix; "discussion" cannot supersede them.

When P0_COUNT = 0 AND P1_COUNT = 0:
  Human Final Verdict is one of:
    - `[ READY TO PUSH ]` — no architectural concerns
    - `[ REQUIRES DISCUSSION ]` — architectural concerns worth discussing,
      but nothing must-fix
  Both map to machine `REVIEW_GATE=PASS`.
```

This guarantees:
- Human reader and machine hook always see the same blocking decision
- `[ NEEDS FIXES ]` ↔ `FAIL` is a 1:1 mapping
- `PASS` covers two human states (READY / DISCUSSION), differentiated only by the human-readable verdict text, not by hook behavior

## Auto-Fix Scope

Only these types qualify for auto-fix (single correct fix, no design decisions):

- `.gitignore` missing entries
- Import sorting / unused imports
- Obvious typos
- Missing trailing newline
- Debug remnants (console.log / print)

Never put uncertain issues in auto-fix. User confirms before applying.
