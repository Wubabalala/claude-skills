#!/usr/bin/env bash
# Project-side doc-garden audit entry (git hook friendly).
#
# Copy to your project as `scripts/doc-audit.sh`, then wire into git hooks
# via `scripts/install-hooks.sh` (companion example).
#
# Usage:
#   bash scripts/doc-audit.sh           # run audit on the repo
#
# Environment:
#   DOC_GARDEN_PATH — path to doc-garden skill's directory, i.e. the folder
#                     containing `core/doc_garden_core.py`. Default tries
#                     a few common locations; override when different:
#                       export DOC_GARDEN_PATH=/path/to/claude-skills/skills/doc-garden
#
# Exit codes:
#   0 — clean (no drift)
#   1 — drift found (blocks git commit when called from pre-commit)
#   2 — environment error: doc-garden not found, Python missing, etc.
#       (does NOT block commit — intended for "setup not ready" cases)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

# Locate doc-garden skill. Try $DOC_GARDEN_PATH, then a few conventional
# places. Tune this list for your environment.
CANDIDATES=(
    "${DOC_GARDEN_PATH:-}"
    "$HOME/.claude/skills/doc-garden"
    "$HOME/claude-skills/skills/doc-garden"
    "/d/work/IDEA/claude-skills/skills/doc-garden"
    "/c/work/claude-skills/skills/doc-garden"
)
DOC_GARDEN_PATH=""
for p in "${CANDIDATES[@]}"; do
    if [[ -n "$p" && -f "$p/core/doc_garden_core.py" ]]; then
        DOC_GARDEN_PATH="$p"
        break
    fi
done
if [[ -z "$DOC_GARDEN_PATH" ]]; then
    echo "⚠️  doc-garden skill not found. Searched:" >&2
    for p in "${CANDIDATES[@]}"; do [[ -n "$p" ]] && echo "    $p" >&2; done
    echo "    Set DOC_GARDEN_PATH env var or edit this script." >&2
    echo "    Skipping drift check (commit NOT blocked)." >&2
    exit 2
fi

# Find Python (on Windows, `python3` can be an MS Store stub — probe with `pass`)
PY=""
for cand in python python3; do
    if command -v "$cand" >/dev/null 2>&1 && "$cand" -c "pass" 2>/dev/null; then
        PY="$cand"
        break
    fi
done
if [[ -z "$PY" ]]; then
    echo "⚠️  Python not found — skipping drift check (commit NOT blocked)" >&2
    exit 2
fi

PROJECT_NAME="$(basename "$REPO_ROOT")"
echo "===== doc-garden drift check: $PROJECT_NAME ====="

export PYTHONPATH="$DOC_GARDEN_PATH"
OUTPUT=$("$PY" -c "
from core.doc_garden_core import run_audit, load_config, format_report
import sys
cfg = load_config('.')
findings = run_audit('.', cfg)
if not findings:
    print('PASS:0')
else:
    print(f'FAIL:{len(findings)}')
    print(format_report(findings, project_name=sys.argv[1] if len(sys.argv) > 1 else ''))
" "$PROJECT_NAME" 2>&1) || {
    echo "❌ doc-garden execution failed:" >&2
    echo "$OUTPUT" >&2
    exit 2
}

STATUS_LINE=$(echo "$OUTPUT" | head -1)
REST=$(echo "$OUTPUT" | tail -n +2)

case "$STATUS_LINE" in
    PASS:0)
        echo "✅ No drift"
        exit 0
        ;;
    FAIL:*)
        COUNT="${STATUS_LINE#FAIL:}"
        echo "❌ $COUNT drift finding(s)"
        echo ""
        echo "$REST"
        echo ""
        echo "💡 Fix options:"
        echo "   - Real typo / stale path → update the doc"
        echo "   - Known non-existent (API endpoint / example / tutorial placeholder)"
        echo "     → add to .claude/doc-garden.json ignore_url_prefixes / ignore_path_patterns"
        echo "   - Cross-layer contradiction → reconcile root vs module docs"
        echo ""
        echo "   Bypass (not recommended): git commit --no-verify"
        exit 1
        ;;
    *)
        echo "❌ Unexpected output: $STATUS_LINE" >&2
        echo "$OUTPUT" >&2
        exit 2
        ;;
esac
