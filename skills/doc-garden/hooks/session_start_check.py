#!/usr/bin/env python3
"""SessionStart hook: quick memory index completeness check.

Runs on every session start. Outputs systemMessage if issues found.
Performance budget: <2s.

Hook output: JSON to stdout
  {"continue": true, "systemMessage": "..."}

Exit codes:
  0 = success (stdout shown)
  non-zero = error (ignored, session continues)
"""
import json
import os
import sys

# Resolve core import: works both in-repo and after installation to ~/.claude/hooks/
# In-repo: script is at skills/doc-garden/hooks/ → parent.parent = skills/doc-garden/
# Installed: script is at ~/.claude/hooks/ with core at ~/.claude/hooks/doc-garden-core/
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_SCRIPT_DIR)  # in-repo
_INSTALLED_CORE = os.path.join(_SCRIPT_DIR, "doc-garden-core")  # installed

if os.path.isdir(os.path.join(_INSTALLED_CORE)):
    sys.path.insert(0, _INSTALLED_CORE)
    from doc_garden_core import resolve_memory_dir, memory_index_check, DriftType
else:
    sys.path.insert(0, _SKILL_ROOT)
    from core.doc_garden_core import resolve_memory_dir, memory_index_check, DriftType


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return  # can't parse, silent exit

    cwd = payload.get("cwd", "")
    if not cwd:
        return

    # Quick memory index check
    findings = memory_index_check(cwd)
    if not findings:
        return  # clean, no output needed

    sunken = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_SUNKEN]
    ghost = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_GHOST]

    parts = []
    if sunken:
        files = ", ".join(f.file.split("/")[-1] for f in sunken[:3])
        suffix = f" (+{len(sunken)-3} more)" if len(sunken) > 3 else ""
        parts.append(f"{len(sunken)} memory file(s) not indexed in MEMORY.md: {files}{suffix}")
    if ghost:
        parts.append(f"{len(ghost)} ghost reference(s) in MEMORY.md (file missing)")

    if parts:
        msg = "[doc-garden] " + "; ".join(parts) + ". Run /doc-audit to see details."
        output = {"continue": True, "systemMessage": msg}
        json.dump(output, sys.stdout)


if __name__ == "__main__":
    main()
