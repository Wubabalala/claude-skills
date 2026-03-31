# Universal Review Checklist (Layer 1)

Language- and framework-agnostic checks, applied to every review.

## P0 Security Issues [must fix]

- Hardcoded passwords, API keys, tokens
- SQL injection (unparameterized queries)
- XSS (unescaped user input)
- Unsafe eval/exec
- Permission checks removed or relaxed

## P0 Transaction Safety [must fix]

Check whenever code touches money/state across tables:

- Catching `DataIntegrityViolationException` inside `@Transactional` — transaction is already marked rollback-only before the catch runs; the catch cannot save it
- Two tables must be atomic but use different transaction propagation (one REQUIRES_NEW, one outer) — partial commit / orphan state risk
- Optimistic lock retry loop inside a `@Transactional(REQUIRES_NEW)` method — transaction is poisoned after first failure, retries are useless
- For every method involving money: are caller and callee in the same transaction? If they commit independently, what happens when one succeeds and the other rolls back?

## P1 Logic Bugs [must fix]

- Errors that will cause crashes
- Logic that will produce incorrect data
- Resource leaks (unclosed connections, uncleared state)
- Race conditions
- Return value disconnected from computed result (e.g., builds a list then returns empty/different object)
- Request attribute name mismatch between interceptor and controller (e.g., interceptor sets "adminId" but controller reads "userId")

## P1 API Input Validation [must fix]

- Request body fields accessed without null check — `body.get("x").toString()` NPEs when key is absent
- Numeric fields parsed without try-catch — `new BigDecimal(input)` throws NumberFormatException on invalid input
- Missing business validation before passing to service layer (empty strings, negative amounts, zero values)

## P2 Robustness [should fix]

- Missing necessary try-catch
- Empty catch blocks
- Unhandled edge cases (null, empty arrays)
- N+1 queries (especially: loading all rows then paginating in memory instead of DB-level pagination)
- Repeated computation/requests inside loops
- Obvious memory leaks
- ORM/JPA pitfalls: `@Version` field missing `@Builder.Default` when using Lombok `@Builder`; entity returned directly as JSON with lazy-loaded fields; `findAll()` on unbounded tables for aggregation instead of `@Query` with SUM/COUNT

## P3 Maintainability [optional fix]

- Functions longer than 100 lines
- Nesting deeper than 4 levels
- Significant code duplication (>20 similar lines)
- Magic numbers
- console.log / print debug remnants
- Commented-out code blocks
- TODO/FIXME
