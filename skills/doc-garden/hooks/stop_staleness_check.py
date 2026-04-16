#!/usr/bin/env python3
"""Stop hook: check if code was modified but CLAUDE.md wasn't updated.

Parses session transcript to find Write/Edit file paths, then checks
if corresponding module CLAUDE.md was also modified.

Never blocks — only outputs systemMessage suggestion.
Exit code 0 always.
"""
import json
import os
import sys

# Dual-path import: in-repo vs installed
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_SKILL_ROOT = os.path.dirname(_SCRIPT_DIR)
_INSTALLED_CORE = os.path.join(_SCRIPT_DIR, "doc-garden-core")

if os.path.isdir(_INSTALLED_CORE):
    sys.path.insert(0, _INSTALLED_CORE)
    from doc_garden_core import extract_modified_files_from_transcript, resolve_module_from_path
else:
    sys.path.insert(0, _SKILL_ROOT)
    from core.doc_garden_core import extract_modified_files_from_transcript, resolve_module_from_path


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    cwd = payload.get("cwd", "")
    transcript_path = payload.get("transcript_path", "")

    if not cwd or not transcript_path:
        return

    modified = extract_modified_files_from_transcript(transcript_path)
    if not modified:
        return

    code_files = [f for f in modified if not f.endswith(".md")]
    if not code_files:
        return

    modules_touched = set()
    for f in code_files:
        mod = resolve_module_from_path(f, cwd)
        if mod:
            modules_touched.add(mod)

    if not modules_touched:
        return

    md_modified = {f for f in modified if f.endswith(".md")}
    stale_modules = []

    for mod in sorted(modules_touched):
        claude_md = os.path.join(cwd, mod, "CLAUDE.md")
        if not os.path.exists(claude_md):
            continue
        claude_md_norm = os.path.normpath(claude_md)
        was_updated = any(os.path.normpath(m) == claude_md_norm for m in md_modified)
        if not was_updated:
            stale_modules.append(mod)

    if stale_modules:
        mods = ", ".join(stale_modules[:3])
        suffix = f" (+{len(stale_modules)-3} more)" if len(stale_modules) > 3 else ""
        msg = (
            f"[doc-garden] Code was modified in {mods}{suffix} "
            f"but their CLAUDE.md was not updated this session. "
            f"Consider running /doc-audit normalize."
        )
        json.dump({"continue": True, "systemMessage": msg}, sys.stdout)


if __name__ == "__main__":
    main()
