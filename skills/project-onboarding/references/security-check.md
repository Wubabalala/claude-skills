# Security Check

**This procedure runs before ANY file is written to disk.**
**It applies to ALL phases — Phase 1 docs AND Phase 2 memory files.**

## Scan Rules

Scan the full content of each file about to be written. Flag any match:

| Type | What to Look For |
|------|-----------------|
| Passwords | plaintext passwords, `password=xxx`, `-p{password}`, `passwd` |
| Tokens / Keys | API keys, `sk-xxx`, `AKIA...`, bearer tokens, secret keys |
| Private keys | `-----BEGIN.*PRIVATE KEY-----` |
| Connection strings | JDBC/Redis/Mongo/AMQP URLs containing credentials |
| IP + credential combos | IP addresses paired with passwords or key file paths |
| Internal hostnames + auth | Intranet URLs with embedded usernames or passwords |

## When Sensitive Content Is Found

**BLOCK the file write.** Present each finding to the user:

```
## Security Check: {n} Sensitive Items Found in {filename}

1. Line {n}:
   Content: "{matched content}"
   Type: {type from table above}
   -> [Redact to placeholder] / [Keep as-is] / [Remove line]

2. Line {n}:
   ...
```

Redaction placeholder format — replace the sensitive value only:
```
ssh -i {SSH_KEY_PATH} {USER}@{SERVER_IP}
password: {DB_PASSWORD}
jdbc:mysql://{DB_HOST}:{DB_PORT}/{DB_NAME}
```

## Security Rules

- **Blocking**: the file is NOT written until EVERY finding is resolved
- **No auto-redact**: user must confirm each item individually
- **Full scope**: every output file is scanned, no exceptions
- **Re-scan after edits**: if user asks to modify generated content, re-scan
