#!/bin/bash

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
SOURCE_HOOK="${SCRIPT_DIR}/pre-push"
MARKER='SKILL_CODE_REVIEW_HOOK'

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "[code-review] not inside a git work tree" >&2
    exit 1
fi

HOOK_FILE="$(git rev-parse --git-path hooks/pre-push)"
HOOK_DIR="$(dirname "$HOOK_FILE")"

mkdir -p "$HOOK_DIR"

if [ ! -f "$SOURCE_HOOK" ]; then
    echo "[code-review] source hook not found: $SOURCE_HOOK" >&2
    exit 1
fi

if [ -f "$HOOK_FILE" ]; then
    if grep -q "$MARKER" "$HOOK_FILE" 2>/dev/null; then
        echo "[code-review] existing claude-skills hook found, upgrading" >&2
    else
        BACKUP="${HOOK_FILE}.backup-$(date +%Y%m%d-%H%M%S)"
        mv "$HOOK_FILE" "$BACKUP"
        echo "[code-review] backed up third-party hook to: $BACKUP" >&2
    fi
fi

cp "$SOURCE_HOOK" "$HOOK_FILE"
chmod +x "$HOOK_FILE"

echo "[code-review] installed hook to: $HOOK_FILE"
echo "[code-review] next steps:"
echo "  - test: git push"
echo "  - bypass once: SKIP_REVIEW=1 git push"
echo "  - bypass once: git push --no-verify"
echo "  - strict mode: REVIEW_STRICT=1 git push"
echo "  - uninstall: bash ${SCRIPT_DIR}/uninstall.sh"
