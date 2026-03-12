# Anti-Patterns

| Anti-Pattern | Why It Fails | Correct Approach |
|-------------|-------------|-----------------|
| Guessing business logic from code structure | Plausible-sounding but wrong docs mislead | Only state facts; ask user for "why" in Phase 2 |
| Auto-redacting sensitive info | May break user intent or miss context | Present each finding, user decides |
| Generating docs without reading existing ones | Overwrites team's work | Detect first, let user choose keep/enhance/patch/rebuild |
| Scanning everything at full detail | Wastes tokens on large codebases | Coarse-to-fine: count -> files -> content |
| Forcing all dimensions in Phase 2 | Overwhelms user, low signal-to-noise | Recommend based on evidence, user selects |
| Copying README content into CLAUDE.md | Duplication that drifts apart over time | Reference existing docs, don't duplicate |
| Running build/test to "validate" | Out of scope, may cause side effects | Read-only only. Document commands, don't run them |
| Writing sensitive data to docs | Security risk, especially for public repos | Security scan blocks all writes until resolved |
| Only appending to stale docs | "Found problem but can't fix it" | Offer Patch mode for targeted fixes with user approval |
