"""Unit tests for check_doc_convention() — audits the doc-convention.md §3 layout."""
import os
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from core.doc_garden_core import check_doc_convention, generate_draft_config, validate_config


def _seed_full_skeleton(root: Path) -> None:
    """Create a complete standard standalone skeleton."""
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (root / "README.md").write_text("# x\n", encoding="utf-8")
    (root / ".claude").mkdir()
    (root / ".claude" / "review-checklist.md").write_text("# x\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "OVERVIEW.md").write_text("# x\n", encoding="utf-8")
    (root / "docs" / "architecture-traps.md").write_text("# x\n", encoding="utf-8")
    (root / "docs" / "TRUTH_SOURCES.md").write_text("# x\n", encoding="utf-8")
    (root / "docs" / "QUICK_REFERENCE.md").write_text("# x\n", encoding="utf-8")
    for sub in ("plans", "ops", "references", "archive"):
        (root / "docs" / sub).mkdir()
    (root / "docs" / "references" / "auth-truth-source.md").write_text("# x\n", encoding="utf-8")


def _seed_simple_skeleton(root: Path) -> None:
    """Create a complete simple skeleton: triplet + docs/OVERVIEW.md."""
    (root / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("# x\n", encoding="utf-8")
    (root / "README.md").write_text("# x\n", encoding="utf-8")
    (root / "docs").mkdir()
    (root / "docs" / "OVERVIEW.md").write_text("# x\n", encoding="utf-8")


class TestStandalone:
    def test_empty_project_missing_root_triplet(self, tmp_path):
        """Empty standalone project reports all three root triplet files as missing."""
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_doc_convention(str(tmp_path), config)
        missing_files = {i.file for i in items if i.category == "missing_doc"}
        assert "CLAUDE.md" in missing_files
        assert "AGENTS.md" in missing_files
        assert "README.md" in missing_files

    def test_full_skeleton_clean(self, tmp_path):
        """A fully populated standalone skeleton produces zero findings."""
        _seed_full_skeleton(tmp_path)
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_doc_convention(str(tmp_path), config)
        assert items == []

    def test_simple_skeleton_clean(self, tmp_path):
        """A fully populated simple skeleton produces zero findings at simple level."""
        _seed_simple_skeleton(tmp_path)
        config = {
            "project_type": "standalone",
            "doc_system_level": "simple",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
        }
        items = check_doc_convention(str(tmp_path), config)
        assert items == []

    def test_simple_missing_overview(self, tmp_path):
        """Simple skeleton requires only docs/OVERVIEW.md beyond root triplet."""
        _seed_simple_skeleton(tmp_path)
        os.remove(tmp_path / "docs" / "OVERVIEW.md")
        config = {
            "project_type": "standalone",
            "doc_system_level": "simple",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
        }
        items = check_doc_convention(str(tmp_path), config)
        files = [i.file for i in items]
        assert files == ["docs/OVERVIEW.md"]

    def test_missing_architecture_traps(self, tmp_path):
        """Standalone skeleton with only architecture-traps.md removed reports exactly that file."""
        _seed_full_skeleton(tmp_path)
        os.remove(tmp_path / "docs" / "architecture-traps.md")
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_doc_convention(str(tmp_path), config)
        files = [i.file for i in items]
        assert files == ["docs/architecture-traps.md"]

    def test_standard_missing_truth_source_index(self, tmp_path):
        """Standard skeleton reports missing truth source index explicitly."""
        _seed_full_skeleton(tmp_path)
        os.remove(tmp_path / "docs" / "TRUTH_SOURCES.md")
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_doc_convention(str(tmp_path), config)
        files = [i.file for i in items]
        assert "docs/TRUTH_SOURCES.md" in files

    def test_standard_missing_review_checklist_is_lifecycle_gap(self, tmp_path):
        """Missing review checklist is a lifecycle readiness gap, not a missing doc."""
        _seed_full_skeleton(tmp_path)
        os.remove(tmp_path / ".claude" / "review-checklist.md")
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        items = check_doc_convention(str(tmp_path), config)
        matches = [i for i in items if i.file == ".claude/review-checklist.md"]
        assert len(matches) == 1
        assert matches[0].category == "lifecycle_readiness"


class TestMicroservice:
    def _seed_root(self, root: Path) -> None:
        _seed_full_skeleton(root)

    def test_submodule_missing_agents_and_docs(self, tmp_path):
        """microservice submodule missing AGENTS.md and docs/ → both reported once each."""
        self._seed_root(tmp_path)
        svc = tmp_path / "svc-a"
        svc.mkdir()
        (svc / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
        (svc / "README.md").write_text("# x\n", encoding="utf-8")
        # AGENTS.md and docs/ are missing

        config = {
            "project_type": "microservice",
            "doc_hierarchy": {
                "layer1": "CLAUDE.md",
                "layer2": ["svc-a/CLAUDE.md"],
            },
        }
        items = check_doc_convention(str(tmp_path), config)
        files = sorted(i.file for i in items)
        assert "svc-a/AGENTS.md" in files
        assert "svc-a/docs/" in files
        # Each reported exactly once (no duplication)
        assert files.count("svc-a/AGENTS.md") == 1
        assert files.count("svc-a/docs/") == 1

    def test_layer2_dedup_same_module(self, tmp_path):
        """layer2 containing both svc/CLAUDE.md and svc/AGENTS.md → same module not reported twice.

        The module svc-b has CLAUDE.md + AGENTS.md but is missing README.md and docs/.
        Even though layer2 references the module via two paths, README.md and docs/ should each appear once.
        """
        self._seed_root(tmp_path)
        svc = tmp_path / "svc-b"
        svc.mkdir()
        (svc / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
        (svc / "AGENTS.md").write_text("# x\n", encoding="utf-8")
        # README.md and docs/ are missing

        config = {
            "project_type": "microservice",
            "doc_hierarchy": {
                "layer1": "CLAUDE.md",
                "layer2": ["svc-b/CLAUDE.md", "svc-b/AGENTS.md"],  # same module referenced twice
            },
        }
        items = check_doc_convention(str(tmp_path), config)
        readme_items = [i for i in items if i.file == "svc-b/README.md"]
        docs_items = [i for i in items if i.file == "svc-b/docs/"]
        assert len(readme_items) == 1, f"README.md should be reported exactly once, got {len(readme_items)}"
        assert len(docs_items) == 1, f"docs/ should be reported exactly once, got {len(docs_items)}"


class TestDocSystemLevelConfig:
    def test_invalid_doc_system_level_reports_schema_error(self):
        config = {
            "project_type": "standalone",
            "doc_system_level": "advanced",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
        }
        errors = validate_config(config)
        assert "doc_system_level must be one of: simple, standard" in errors

    def test_microservice_simple_reports_warning(self):
        config = {
            "project_type": "microservice",
            "doc_system_level": "simple",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
        }
        errors = validate_config(config)
        assert any(e.startswith("WARNING: microservice projects") for e in errors)

    def test_generate_draft_config_preserves_existing_doc_system_level(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# x\n", encoding="utf-8")
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "doc-garden.json").write_text(
            '{"project_type":"standalone","doc_system_level":"simple","doc_hierarchy":{"layer1":"CLAUDE.md"}}',
            encoding="utf-8",
        )
        draft = generate_draft_config(str(tmp_path))
        assert draft["doc_system_level"] == "simple"
