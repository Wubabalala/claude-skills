#!/bin/bash

MARKER='SKILL_CODE_REVIEW_HOOK'

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[code-review] not inside a git work tree" >&2
    exit 1
fi

HOOK_FILE="$(git rev-parse --git-path hooks/pre-push)"

if [ ! -f "$HOOK_FILE" ]; then
    echo "[code-review] no pre-push hook installed at: $HOOK_FILE" >&2
    exit 0
fi

if ! grep -q "$MARKER" "$HOOK_FILE" 2>/dev/null; then
    echo "[code-review] existing pre-push hook is not managed by claude-skills; refusing to modify" >&2
    exit 1
fi

rm -f "$HOOK_FILE"

latest_backup=$(ls -1t "${HOOK_FILE}".backup-* 2>/dev/null | head -1)
if [ -n "$latest_backup" ]; then
    mv "$latest_backup" "$HOOK_FILE"
    echo "[code-review] restored backup: $latest_backup -> $HOOK_FILE"
else
    echo "[code-review] removed managed hook; no backup found to restore"
fi
