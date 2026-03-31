# Scoring, Escalation & Cost-Benefit

## Code Scoring Criteria

| Score | Meaning | Typical Characteristics |
|-------|---------|------------------------|
| 9-10 | Excellent | No P0-P2, complete test coverage, clean design |
| 7-8 | Good | No P0-P1, few P2/P3, overall robust |
| 5-6 | Acceptable | Has P1 but manageable, insufficient tests, needs fixes before push |
| 3-4 | Poor | Has P0 or multiple P1s, missing tests, needs significant rework |
| 1-2 | Dangerous | Security vulnerabilities, architectural issues, consider rewrite |

> Score appears twice in the report: at the top for quick orientation, at the bottom as part of the final verdict.

## Cost-Benefit Rating

| Rating | Condition | Recommendation |
|--------|-----------|----------------|
| 5/5 | Low cost + High risk | Must fix |
| 4/5 | Low cost + Medium risk | Should fix |
| 3/5 | Medium cost + Medium risk | Consider fixing |
| 2/5 | High cost + Low risk | Case by case |
| 1/5 | High cost + Low benefit | Don't fix |

## Risk Escalation Rules

| Condition | Escalation |
|-----------|------------|
| New function + no tests | MEDIUM → HIGH |
| Validation logic modified + tests not updated | MEDIUM → HIGH |
| Complex logic (>20 lines) + no tests | MEDIUM → HIGH |
| Deleted code from security-fix commit | Current level → P0 |
| Callers >20 + HIGH risk change | Annotate "high blast radius" in report |

## Red Lines (Immediate Deep Investigation)

When any of these patterns appear, regardless of change size, perform deep analysis:

- Code from commits containing "fix", "security", "CVE", "bug" is deleted
- Permission checks removed (auth annotations, interceptor configs)
- Input validation removed with no replacement
- New external calls without error handling
- HIGH risk changes with high impact scope (50+ callers)
