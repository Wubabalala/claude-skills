"""Unit tests for hook scripts."""
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch
from io import StringIO

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT))

FIXTURES = Path(__file__).parent / "fixtures"
PAYLOADS = FIXTURES / "sample-payloads"
MEMORY_FIXTURE = FIXTURES / "sample-memory-dir"


# ---------------------------------------------------------------------------
# Stop hook: transcript parsing
# ---------------------------------------------------------------------------

class TestStopTranscriptParsing:
    """These now test core functions (moved from hook to core in #2 refactor)."""

    def test_extracts_write_edit_only(self):
        from core.doc_garden_core import extract_modified_files_from_transcript
        transcript = str(PAYLOADS / "transcript.jsonl")
        result = extract_modified_files_from_transcript(transcript)
        paths = {os.path.basename(p) for p in result}
        assert "handler.java" in paths
        assert "new_file.py" in paths
        assert "main.py" not in paths

    def test_ignores_non_tool_use(self):
        from core.doc_garden_core import extract_modified_files_from_transcript
        transcript = str(PAYLOADS / "transcript.jsonl")
        result = extract_modified_files_from_transcript(transcript)
        assert len(result) == 2

    def test_handles_missing_transcript(self):
        from core.doc_garden_core import extract_modified_files_from_transcript
        result = extract_modified_files_from_transcript("/nonexistent/transcript.jsonl")
        assert result == set()

    def test_handles_malformed_jsonl(self, tmp_path):
        from core.doc_garden_core import extract_modified_files_from_transcript
        transcript = tmp_path / "bad.jsonl"
        transcript.write_text("not json\n{}\n{\"message\": null}\n", encoding="utf-8")
        result = extract_modified_files_from_transcript(str(transcript))
        assert result == set()


class TestStopModuleResolution:
    def test_resolves_module(self):
        from core.doc_garden_core import resolve_module_from_path
        assert resolve_module_from_path("D:/work/project/api-module/src/Main.java", "D:/work/project") == "api-module"

    def test_root_file_no_module(self):
        from core.doc_garden_core import resolve_module_from_path
        assert resolve_module_from_path("D:/work/project/README.md", "D:/work/project") == ""

    def test_windows_backslash(self):
        from core.doc_garden_core import resolve_module_from_path
        assert resolve_module_from_path("D:\\work\\project\\web\\src\\index.ts", "D:\\work\\project") == "web"


# ---------------------------------------------------------------------------
# PostToolUse hook: memory index check
# ---------------------------------------------------------------------------

class TestPostEditMemoryIndex:
    def test_detects_unindexed_file(self):
        """Editing a memory file not in MEMORY.md → should output message."""
        from hooks.post_edit_memory_index import main, MEMORY_DIR_PATTERN

        # feedback-no-prod-writes.md is NOT indexed in our fixture MEMORY.md
        file_path = str(MEMORY_FIXTURE / "feedback-no-prod-writes.md").replace("\\", "/")

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path},
        }

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        output = stdout.getvalue()
        if output:
            result = json.loads(output)
            assert result["continue"] is True
            assert "not indexed" in result["systemMessage"]

    def test_ignores_indexed_file(self):
        """Editing a file that IS indexed → no output."""
        from hooks.post_edit_memory_index import main

        file_path = str(MEMORY_FIXTURE / "architecture.md").replace("\\", "/")

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path},
        }

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_ignores_memory_md_itself(self):
        """Editing MEMORY.md itself → no output."""
        from hooks.post_edit_memory_index import main

        file_path = str(MEMORY_FIXTURE / "MEMORY.md").replace("\\", "/")

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": file_path},
        }

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_ignores_non_memory_files(self):
        """Editing a file NOT in a memory/ dir → no output."""
        from hooks.post_edit_memory_index import main

        payload = {
            "tool_name": "Edit",
            "tool_input": {"file_path": "/some/other/file.md"},
        }

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""

    def test_ignores_read_tool(self):
        """Read tool → no output regardless of path."""
        from hooks.post_edit_memory_index import main

        file_path = str(MEMORY_FIXTURE / "feedback-no-prod-writes.md").replace("\\", "/")

        payload = {
            "tool_name": "Read",
            "tool_input": {"file_path": file_path},
        }

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""


# ---------------------------------------------------------------------------
# SessionStart hook: basic smoke test
# ---------------------------------------------------------------------------

class TestSessionStartCheck:
    def test_outputs_warning_for_sunken(self, monkeypatch):
        """Should output systemMessage when sunken files exist."""
        from hooks.session_start_check import main

        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir",
            lambda cwd: str(MEMORY_FIXTURE)
        )

        payload = {"cwd": "/fake/project", "hook_event_name": "SessionStart"}

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        output = stdout.getvalue()
        assert output  # should have output
        result = json.loads(output)
        assert result["continue"] is True
        assert "doc-garden" in result["systemMessage"]
        assert "not indexed" in result["systemMessage"]

    def test_silent_when_clean(self, monkeypatch, tmp_path):
        """No output when all files are indexed."""
        from hooks.session_start_check import main
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("# Index\n- [test](test.md)", encoding="utf-8")
        (mem_dir / "test.md").write_text("---\nname: test\n---\ncontent", encoding="utf-8")

        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir",
            lambda cwd: str(mem_dir)
        )

        payload = {"cwd": str(tmp_path), "hook_event_name": "SessionStart"}

        stdin = StringIO(json.dumps(payload))
        stdout = StringIO()
        with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
            main()

        assert stdout.getvalue() == ""
