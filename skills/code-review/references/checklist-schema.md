# Checklist Schema

## v2.3 Schema (preferred for new entries)

```markdown
- [ ] Short description (source: filename)
  severity: P0|P1|P2|P3
  scope: universal|project|module
  frequency: 1x|2x+|chronic
```

This format is preferred for newly generated checklist entries and for refreshed Layer 2 review views.

## v2.1 Schema (legacy, still supported)

```markdown
- [ ] Short description (source: filename)
```

Legacy items remain valid. The skill must apply fallback defaults when it encounters them.

## Legacy Fallback Defaults

When the skill encounters a v2.1-format item:

- `frequency: 1x`
- `scope: project`
- `severity: P2` by default

Lightweight uplift is allowed only for clearly imperative wording:

- if the rule contains `must`
- or `禁止`
- or `never`
- or `MUST`

then uplift `severity` to `P1`.

Do **not** auto-upgrade legacy items to `P0` without explicit author intent.

## Sort Order on Load

Checklist items should be surfaced in this order:

1. `frequency`: `chronic > 2x+ > 1x`
2. `severity` within the same frequency: `P0 > P1 > P2 > P3`
3. `scope` within the same severity: `universal > project > module`

This puts high-recurrence systemic issues at the top of the mental checklist before lower-signal local rules.
