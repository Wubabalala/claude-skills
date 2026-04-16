"""Unit tests for normalize functionality."""
import json
import os
import sys
import pytest
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from core.doc_garden_core import (
    check_skeleton,
    check_frontmatter,
    run_normalize,
    generate_root_skeleton,
    generate_module_skeleton,
    _extract_sections,
    _has_frontmatter,
    format_normalize_report,
)

FIXTURES = Path(__file__).parent / "fixtures"
MEMORY_FIXTURE = FIXTURES / "sample-memory-dir"
CLAUDE_FIXTURE = FIXTURES / "sample-claude-md"


# ---------------------------------------------------------------------------
# Skeleton checks
# ---------------------------------------------------------------------------

class TestCheckSkeleton:
    def test_microservice_root_has_sections(self):
        """sample-claude-md root CLAUDE.md has 模块速查 and 环境信息."""
        config = {
            "project_type": "microservice",
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]},
        }
        items = check_skeleton(str(CLAUDE_FIXTURE), config)
        missing = [i.detail for i in items if i.category == "missing_section" and i.file == "CLAUDE.md"]
        # Root has 模块速查 and 环境信息, but may lack 分支策略 and 部署流程
        assert not any("模块速查" in d for d in missing), "模块速查 exists, should not be flagged"

    def test_microservice_root_missing_sections(self):
        """Fixture root CLAUDE.md lacks 分支策略 and 部署流程."""
        config = {
            "project_type": "microservice",
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": []},
        }
        items = check_skeleton(str(CLAUDE_FIXTURE), config)
        missing = [i.detail for i in items if i.category == "missing_section"]
        assert any("分支策略" in d for d in missing)
        assert any("部署流程" in d for d in missing)

    def test_standalone_minimal(self, tmp_path):
        """Standalone: only 技术栈 and 常用命令 required."""
        (tmp_path / "CLAUDE.md").write_text("# Project\n\n## 技术栈\nPython\n\n## 常用命令\npip install\n", encoding="utf-8")
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_skeleton(str(tmp_path), config)
        missing = [i for i in items if i.category == "missing_section"]
        assert len(missing) == 0

    def test_missing_root_doc(self, tmp_path):
        """If CLAUDE.md doesn't exist, report as missing_doc."""
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_skeleton(str(tmp_path), config)
        assert any(i.category == "missing_doc" for i in items)

    def test_missing_module_doc(self, tmp_path):
        """If module CLAUDE.md doesn't exist, report as missing_doc."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        config = {
            "project_type": "microservice",
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]},
        }
        items = check_skeleton(str(tmp_path), config)
        assert any(i.category == "missing_doc" and "api/CLAUDE.md" in i.file for i in items)


# ---------------------------------------------------------------------------
# Frontmatter checks
# ---------------------------------------------------------------------------

class TestCheckFrontmatter:
    def test_detects_missing_frontmatter(self, monkeypatch, tmp_path):
        """File without --- frontmatter is flagged."""
        mem_dir = tmp_path / "memory"
        mem_dir.mkdir()
        (mem_dir / "MEMORY.md").write_text("# Index\n- [test](test.md)", encoding="utf-8")
        (mem_dir / "test.md").write_text("# No frontmatter\nContent here.", encoding="utf-8")
        monkeypatch.setattr("core.doc_garden_core.resolve_memory_dir", lambda cwd: str(mem_dir))
        items = check_frontmatter(str(tmp_path))
        assert len(items) == 1
        assert items[0].category == "missing_frontmatter"

    def test_passes_with_frontmatter(self, monkeypatch):
        """Files in fixture all have frontmatter (except MEMORY.md which is skipped)."""
        monkeypatch.setattr("core.doc_garden_core.resolve_memory_dir", lambda cwd: str(MEMORY_FIXTURE))
        items = check_frontmatter("/fake")
        # architecture.md, service-topology.md, feedback-no-prod-writes.md all have frontmatter
        assert len(items) == 0

    def test_has_frontmatter_helper(self):
        assert _has_frontmatter(str(MEMORY_FIXTURE / "architecture.md")) is True
        assert _has_frontmatter(str(MEMORY_FIXTURE / "MEMORY.md")) is False  # starts with #


# ---------------------------------------------------------------------------
# Skeleton generation
# ---------------------------------------------------------------------------

class TestGenerateSkeleton:
    def test_microservice_root(self):
        skel = generate_root_skeleton("microservice")
        assert "## 模块速查" in skel
        assert "## 分支策略" in skel
        assert "## 部署流程" in skel
        assert "## 环境信息" in skel
        assert "## 踩坑记录" in skel

    def test_standalone_root(self):
        skel = generate_root_skeleton("standalone")
        assert "## 技术栈" in skel
        assert "## 常用命令" in skel
        # Should NOT have microservice sections
        assert "## 分支策略" not in skel

    def test_module_skeleton(self):
        skel = generate_module_skeleton("api-service", "microservice")
        assert "# api-service" in skel
        assert "## 技术栈" in skel
        assert "## 常用命令" in skel

    def test_idempotent_section_check(self, tmp_path):
        """If sections already exist, skeleton check should not flag them."""
        (tmp_path / "CLAUDE.md").write_text(
            "# Project\n\n## 技术栈\nJava\n\n## 常用命令\nmvn\n", encoding="utf-8"
        )
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items1 = check_skeleton(str(tmp_path), config)
        items2 = check_skeleton(str(tmp_path), config)
        assert items1 == items2  # same result = idempotent


# ---------------------------------------------------------------------------
# Integration: run_normalize
# ---------------------------------------------------------------------------

class TestRunNormalize:
    def test_includes_sunken(self, monkeypatch):
        """run_normalize should include sunken memory files from memory_index_check."""
        monkeypatch.setattr("core.doc_garden_core.resolve_memory_dir", lambda cwd: str(MEMORY_FIXTURE))
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = run_normalize(str(CLAUDE_FIXTURE), config)
        sunken = [i for i in items if i.category == "sunken_index"]
        assert len(sunken) == 1  # feedback-no-prod-writes.md

    def test_report_format(self, monkeypatch):
        monkeypatch.setattr("core.doc_garden_core.resolve_memory_dir", lambda cwd: str(MEMORY_FIXTURE))
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = run_normalize(str(CLAUDE_FIXTURE), config)
        report = format_normalize_report(items, "test-project")
        assert "## Normalize Report" in report
        assert "test-project" in report


# ---------------------------------------------------------------------------
# Helper: _extract_sections
# ---------------------------------------------------------------------------

class TestExtractSections:
    def test_root_fixture(self):
        sections = _extract_sections(str(CLAUDE_FIXTURE / "CLAUDE.md"))
        titles = [s for s in sections]
        assert "模块速查" in titles
        assert "环境信息" in titles
        assert "文档引用" in titles

    def test_empty_file(self, tmp_path):
        (tmp_path / "empty.md").write_text("", encoding="utf-8")
        assert _extract_sections(str(tmp_path / "empty.md")) == []
