#!/usr/bin/env python3
"""PostToolUse hook: remind to update MEMORY.md after editing memory files.

Triggers on Write/Edit of *.md in memory/ directories.
Exit code 0 always.
"""
import json
import os
import re
import sys

# Dual-path import
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_INSTALLED_CORE = os.path.join(_SCRIPT_DIR, "doc-garden-core")

# This hook doesn't currently import core functions, but the path is set up
# for consistency and future use.

MEMORY_DIR_PATTERN = re.compile(r"[/\\]memory[/\\]([^/\\]+\.md)$")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Write", "Edit"):
        return

    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path:
        return

    match = MEMORY_DIR_PATTERN.search(file_path.replace("\\", "/"))
    if not match:
        return

    filename = match.group(1)
    if filename == "MEMORY.md":
        return

    memory_dir = os.path.dirname(file_path)
    memory_md = os.path.join(memory_dir, "MEMORY.md")

    if not os.path.exists(memory_md):
        return

    try:
        with open(memory_md, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError):
        return

    if filename in content:
        return

    msg = (
        f"[doc-garden] File '{filename}' was edited but is not indexed in MEMORY.md. "
        f"Consider adding an entry to keep the index complete."
    )
    json.dump({"continue": True, "systemMessage": msg}, sys.stdout)


if __name__ == "__main__":
    main()
