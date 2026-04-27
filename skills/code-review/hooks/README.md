# code-review pre-push hook (v2.2)

This directory contains an optional Git `pre-push` hook for the `code-review` skill.

It consumes the v2.1+ machine-readable sentinel:

```text
REVIEW_GATE=PASS|FAIL
REVIEW_VERSION=2.3
```

The hook is **fail-open by default**:

- `claude` CLI missing -> warn, allow push
- timeout -> warn, allow push
- sentinel missing or unsupported version -> warn, allow push
- only `REVIEW_GATE=FAIL` blocks push

Set `REVIEW_STRICT=1` to make all of the above failure paths block instead.

## Files

- `pre-push` - the hook itself; single source of runtime logic
- `install.sh` - install/upgrade from Git Bash or Linux/macOS shell
- `install.ps1` - native PowerShell installer
- `uninstall.sh` - remove managed hook and restore latest backup

## Installation

### Bash / Git Bash / Linux / macOS

From the target Git repository:

```bash
bash ~/.claude/skills/code-review/hooks/install.sh
```

The installer resolves the hook path via:

```bash
git rev-parse --git-path hooks/pre-push
```

This supports:

- standard `.git/hooks/`
- `core.hooksPath`
- Git worktrees

### PowerShell (Windows)

From the target Git repository:

```powershell
pwsh ~/.claude/skills/code-review/hooks/install.ps1
```

`install.ps1` is a native PowerShell implementation for file management. The installed hook is still the same Bash `pre-push` file.

## Upgrade behavior

When `install.sh` or `install.ps1` finds an existing `pre-push` hook:

- if it contains `SKILL_CODE_REVIEW_HOOK`, it is treated as a managed claude-skills hook and upgraded in place
- otherwise it is backed up to `pre-push.backup-YYYYMMDD-HHMMSS` before installation

## Uninstall

From the target Git repository:

```bash
bash ~/.claude/skills/code-review/hooks/uninstall.sh
```

Uninstall rules:

- only removes a hook that contains the managed marker
- restores the newest `pre-push.backup-*` file in the same hook path, if present
- if no backup exists, it simply removes the managed hook
- if the current hook is not managed by claude-skills, uninstall refuses to modify it

## Bypass

Bypass once with the dedicated environment variable:

```bash
SKIP_REVIEW=1 git push
```

Or bypass all Git hooks using Git's built-in mechanism:

```bash
git push --no-verify
```

## Timeout behavior

The hook looks for timeout support in this order:

1. `timeout`
2. `gtimeout`
3. no timeout command available

Default timeout is 120 seconds:

```bash
REVIEW_TIMEOUT=120 git push
```

If neither `timeout` nor `gtimeout` exists, the hook runs without a timeout and prints a warning.

## Strict mode

Default behavior is fail-open. To make environment and parsing failures block the push:

```bash
REVIEW_STRICT=1 git push
```

In strict mode, the following conditions block:

- `claude` CLI missing
- timeout
- `claude` exits non-zero
- sentinel block missing
- `REVIEW_GATE` field missing
- unsupported `REVIEW_VERSION`

## Version compatibility

This hook accepts sentinel versions:

- `2.1`
- `2.2`
- `2.3`

Other versions are treated as unsupported and trigger warn-and-skip by default, or block under `REVIEW_STRICT=1`.

## Limitations

- Running `claude -p` on every push costs time and tokens
- Large diffs may still be slow; the hook does not add a file-count threshold
- The quality gate is only as strict as the installed `code-review` skill and sentinel contract
- `install.ps1` installs the Bash hook, so Windows users still need Git for Windows or another environment that can execute Bash hooks
- Scripts in this directory should use **LF** line endings; CRLF may break `#!/bin/bash` execution in Git Bash
