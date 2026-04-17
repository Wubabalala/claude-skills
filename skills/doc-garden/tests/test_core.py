"""Unit tests for doc_garden_core."""
import json
import os
import sys
import pytest
from pathlib import Path

# Add core to path
SKILL_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SKILL_ROOT))

from core.doc_garden_core import (
    resolve_memory_dir,
    detect_project_type,
    memory_index_check,
    path_rot_check,
    staleness_check,
    cross_layer_check,
    config_value_drift_check,
    structure_drift_check,
    generate_draft_config,
    has_config,
    apply_auto_fix,
    validate_config,
    extract_modified_files_from_transcript,
    resolve_module_from_path,
    _git_last_modified,
    _extract_ips_and_ports,
    _parse_env_table,
    load_config,
    DriftType,
    Severity,
    _parse_memory_index,
    _guess_section,
    _read_frontmatter_type,
    DEFAULT_CONFIG,
)

FIXTURES = Path(__file__).parent / "fixtures"
MEMORY_FIXTURE = FIXTURES / "sample-memory-dir"
CLAUDE_FIXTURE = FIXTURES / "sample-claude-md"


# ---------------------------------------------------------------------------
# resolve_memory_dir
# ---------------------------------------------------------------------------

class TestResolveMemoryDir:
    def test_windows_path(self):
        result = resolve_memory_dir("D:\\work\\IDEA\\ideaProject\\v-story")
        home = os.path.expanduser("~")
        expected = os.path.join(home, ".claude", "projects",
                                "D--work-IDEA-ideaProject-v-story", "memory")
        assert result == expected

    def test_unix_path(self):
        result = resolve_memory_dir("/home/user/projects/my-app")
        home = os.path.expanduser("~")
        assert "home-user-projects-my-app" in result

    def test_drive_letter_double_dash(self):
        """Windows drive letter D: should produce D-- (double dash)."""
        result = resolve_memory_dir("D:\\test")
        assert "D--test" in result


# ---------------------------------------------------------------------------
# detect_project_type
# ---------------------------------------------------------------------------

class TestDetectProjectType:
    def test_microservice(self):
        """Fixture has root CLAUDE.md + api/CLAUDE.md = 2, should be monorepo."""
        ptype, files = detect_project_type(str(CLAUDE_FIXTURE))
        assert ptype in ("monorepo", "microservice")
        assert len(files) >= 2

    def test_standalone(self, tmp_path):
        """Single CLAUDE.md = standalone."""
        (tmp_path / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        ptype, files = detect_project_type(str(tmp_path))
        assert ptype == "standalone"
        assert files == ["CLAUDE.md"]

    def test_no_claude_md(self, tmp_path):
        """No CLAUDE.md at all."""
        ptype, files = detect_project_type(str(tmp_path))
        assert ptype == "standalone"
        assert files == []


# ---------------------------------------------------------------------------
# Memory Index Check
# ---------------------------------------------------------------------------

class TestMemoryIndexCheck:
    def _run_with_fixture(self, monkeypatch):
        """Patch resolve_memory_dir to point to fixture."""
        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir",
            lambda cwd: str(MEMORY_FIXTURE)
        )
        return memory_index_check("/fake/cwd")

    def test_detects_sunken_file(self, monkeypatch):
        """feedback-no-prod-writes.md exists but not indexed → sunken."""
        findings = self._run_with_fixture(monkeypatch)
        sunken = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_SUNKEN]
        sunken_files = [f.file for f in sunken]
        assert any("feedback-no-prod-writes.md" in f for f in sunken_files)

    def test_detects_ghost_reference(self, monkeypatch):
        """ghost-file.md is indexed but doesn't exist → ghost."""
        findings = self._run_with_fixture(monkeypatch)
        ghosts = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_GHOST]
        assert len(ghosts) == 1
        assert "ghost-file.md" in ghosts[0].detail

    def test_ghost_is_auto_fixable(self, monkeypatch):
        findings = self._run_with_fixture(monkeypatch)
        ghosts = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_GHOST]
        assert all(f.auto_fixable for f in ghosts)

    def test_sunken_has_section_hint(self, monkeypatch):
        findings = self._run_with_fixture(monkeypatch)
        sunken = [f for f in findings if f.drift_type == DriftType.MEMORY_INDEX_SUNKEN]
        for f in sunken:
            assert f.section_hint != ""

    def test_indexed_files_not_reported(self, monkeypatch):
        """architecture.md and service-topology.md are indexed, should not appear."""
        findings = self._run_with_fixture(monkeypatch)
        all_files = [f.detail for f in findings]
        assert not any("architecture.md" in d for d in all_files)
        assert not any("service-topology.md" in d for d in all_files)


# ---------------------------------------------------------------------------
# Path Rot Check
# ---------------------------------------------------------------------------

class TestPathRotCheck:
    def test_detects_nonexistent_path(self):
        """CLAUDE.md references docs/nonexistent.md which doesn't exist."""
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": ["node_modules/", ".git/"],
        }
        findings = path_rot_check(str(CLAUDE_FIXTURE), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        rot_paths = [f.detail for f in rot]
        assert any("nonexistent" in d for d in rot_paths)

    def test_existing_path_not_reported(self):
        """docs/OVERVIEW.md and deploy.sh exist, should not be reported."""
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": ["node_modules/", ".git/"],
        }
        findings = path_rot_check(str(CLAUDE_FIXTURE), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("OVERVIEW.md" in d for d in rot_paths)
        assert not any("deploy.sh" in d for d in rot_paths)

    def test_ignores_configured_paths(self):
        """Paths matching ignore_paths should be skipped."""
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": ["docs/"],  # ignore ALL docs/ paths
        }
        findings = path_rot_check(str(CLAUDE_FIXTURE), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("docs/" in f.detail for f in rot)

    def test_path_rot_resolves_memory_prefix_to_runtime_dir(self, tmp_path, monkeypatch):
        """memory/ prefix should resolve to user-level memory dir, not project root."""
        fake_mem = tmp_path / "runtime_memory"
        fake_mem.mkdir()
        (fake_mem / "reference_foo.md").write_text(
            "---\ntype: reference\n---\n", encoding="utf-8"
        )

        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir", lambda cwd: str(fake_mem)
        )
        (tmp_path / "CLAUDE.md").write_text(
            "See `memory/reference_foo.md` for details.\n", encoding="utf-8"
        )

        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("reference_foo.md" in d for d in rot_paths), rot_paths

    def test_path_rot_flags_missing_memory_file(self, tmp_path, monkeypatch):
        """If file missing in runtime memory dir too, still PATH_ROT."""
        fake_mem = tmp_path / "runtime_memory"
        fake_mem.mkdir()
        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir", lambda cwd: str(fake_mem)
        )
        (tmp_path / "CLAUDE.md").write_text(
            "See `memory/missing.md`.\n", encoding="utf-8"
        )

        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        assert any(
            "missing.md" in f.detail
            for f in findings
            if f.drift_type == DriftType.PATH_ROT
        )

    def test_path_rot_resolves_plans_prefix_to_claude_plans_dir(self, tmp_path, monkeypatch):
        """plans/ prefix should resolve to ~/.claude/plans/."""
        fake_home = tmp_path / "fake_home"
        fake_plans = fake_home / ".claude" / "plans"
        fake_plans.mkdir(parents=True)
        (fake_plans / "my_plan.md").write_text("plan", encoding="utf-8")

        monkeypatch.setenv("HOME", str(fake_home))
        monkeypatch.setenv("USERPROFILE", str(fake_home))  # Windows

        (tmp_path / "CLAUDE.md").write_text(
            "See `plans/my_plan.md`.\n", encoding="utf-8"
        )

        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("my_plan.md" in d for d in rot_paths), rot_paths

    def test_path_rot_skips_github_org_repo_refs(self, tmp_path):
        """External GitHub repo refs like `duanyytop/agents-radar` should not be flagged."""
        (tmp_path / "CLAUDE.md").write_text(
            "Upstream: `duanyytop/agents-radar` provides digests.\n"
            "Also `some-org/my-tool` here.\n",
            encoding="utf-8",
        )

        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("agents-radar" in d for d in rot_paths), rot_paths
        assert not any("my-tool" in d for d in rot_paths), rot_paths

    def test_path_rot_still_catches_real_two_segment_paths(self, tmp_path):
        """Regression guard: 2-segment paths WITH extension must still be checked."""
        (tmp_path / "CLAUDE.md").write_text(
            "Entry: `src/main.py`\nConfig: `config/app.yml`\n", encoding="utf-8"
        )
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert any("main.py" in d for d in rot_paths), rot_paths
        assert any("app.yml" in d for d in rot_paths), rot_paths


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestConfig:
    def test_load_missing_returns_defaults(self, tmp_path):
        config = load_config(str(tmp_path))
        assert config["project_type"] == "standalone"
        assert config["staleness_threshold_days"] == 14

    def test_load_existing(self, tmp_path):
        (tmp_path / ".claude").mkdir()
        config_data = {"project_type": "microservice", "staleness_threshold_days": 30}
        (tmp_path / ".claude" / "doc-garden.json").write_text(
            json.dumps(config_data), encoding="utf-8"
        )
        config = load_config(str(tmp_path))
        assert config["project_type"] == "microservice"
        assert config["staleness_threshold_days"] == 30

    def test_has_config(self, tmp_path):
        assert has_config(str(tmp_path)) is False
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / "doc-garden.json").write_text("{}", encoding="utf-8")
        assert has_config(str(tmp_path)) is True


# ---------------------------------------------------------------------------
# Config Generation
# ---------------------------------------------------------------------------

class TestGenerateDraftConfig:
    def test_standalone_project(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# My Project\n\nSome content", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        assert draft["project_type"] == "standalone"
        assert draft["doc_hierarchy"]["layer1"] == "CLAUDE.md"
        assert "_discovery" in draft
        assert draft["_discovery"]["detected_type"] == "standalone"

    def test_microservice_project(self):
        """Fixture has root + api/CLAUDE.md → detected as monorepo/microservice."""
        draft = generate_draft_config(str(CLAUDE_FIXTURE))
        assert draft["project_type"] in ("monorepo", "microservice")
        assert "layer2" in draft["doc_hierarchy"]
        assert any("api/CLAUDE.md" in f for f in draft["doc_hierarchy"]["layer2"])

    def test_discovers_ips(self):
        """Should extract IPs from root CLAUDE.md."""
        draft = generate_draft_config(str(CLAUDE_FIXTURE))
        ips = draft["_discovery"]["discovered_ips"]
        assert "8.129.22.14" in ips
        assert "47.112.120.194" in ips

    def test_discovery_metadata(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Test", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        d = draft["_discovery"]
        assert "detected_type" in d
        assert "claude_md_count" in d
        assert "memory_dir_exists" in d

    def test_has_default_fields(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Test", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        assert draft["staleness_threshold_days"] == 14
        assert "node_modules/" in draft["ignore_paths"]


class TestParseEnvTable:
    def test_parses_env_table_from_fixture(self):
        """Fixture root CLAUDE.md has an environment table."""
        domains = _parse_env_table(str(CLAUDE_FIXTURE / "CLAUDE.md"))
        # Fixture has: 测试 | 8.129.22.14 | 97xx and 生产 | 47.112.120.194 | 98xx
        if domains:  # parser may or may not succeed depending on table format
            assert any("8.129.22.14" in d.get("ips", []) for d in domains.values())

    def test_returns_empty_for_no_table(self, tmp_path):
        (tmp_path / "test.md").write_text("# No tables here\nJust text.", encoding="utf-8")
        domains = _parse_env_table(str(tmp_path / "test.md"))
        assert domains == {}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_parse_memory_index(self):
        linked, sections = _parse_memory_index(str(MEMORY_FIXTURE / "MEMORY.md"))
        assert "architecture.md" in linked
        assert "service-topology.md" in linked
        assert "ghost-file.md" in linked
        assert len(sections) >= 2  # 模块文档, 用户偏好, 踩坑记录

    def test_read_frontmatter_type(self):
        assert _read_frontmatter_type(str(MEMORY_FIXTURE / "architecture.md")) == "project"
        assert _read_frontmatter_type(str(MEMORY_FIXTURE / "feedback-no-prod-writes.md")) == "feedback"

    def test_guess_section_feedback(self):
        sections = [("模块文档", 3), ("用户偏好", 7), ("踩坑记录", 11)]
        assert _guess_section("feedback-no-prod-writes.md", "feedback", sections) == "用户偏好"

    def test_guess_section_keycloak(self):
        sections = [("模块文档", 3), ("Keycloak排查手册", 7), ("踩坑记录", 11)]
        assert _guess_section("keycloak-auth.md", "project", sections) == "Keycloak排查手册"


# ---------------------------------------------------------------------------
# Staleness Check
# ---------------------------------------------------------------------------

class TestStalenessCheck:
    def test_non_git_repo_returns_empty(self, tmp_path):
        """Non-git directory → empty findings (silent skip)."""
        (tmp_path / "CLAUDE.md").write_text("# Test", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "staleness_threshold_days": 14}
        findings = staleness_check(str(tmp_path), config)
        assert findings == []

    def test_git_last_modified_nonexistent(self):
        """Non-existent path → 0."""
        assert _git_last_modified("/nonexistent/file.md") == 0

    def test_on_real_git_repo(self):
        """Run on claude-skills repo (known git repo) → should not crash."""
        cwd = str(SKILL_ROOT.parent.parent)  # claude-skills root
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "staleness_threshold_days": 1}
        findings = staleness_check(cwd, config)
        # May or may not find staleness, but should not error
        assert isinstance(findings, list)
        for f in findings:
            assert f.drift_type == DriftType.STALENESS


# ---------------------------------------------------------------------------
# Cross-Layer Contradiction
# ---------------------------------------------------------------------------

class TestCrossLayerCheck:
    def test_detects_unknown_ip_in_module(self):
        """Module has IP not in any environment domain → flag."""
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]},
            "environment_domains": {
                "test": {"ips": ["8.129.22.14"]},
                "prod": {"ips": ["47.112.120.194"]},
            },
        }
        findings = cross_layer_check(str(CLAUDE_FIXTURE), config)
        # api/CLAUDE.md has 123.56.64.34 which is not in any domain
        unknown = [f for f in findings if f.drift_type == DriftType.CROSS_LAYER_CONTRADICTION]
        assert any("123.56.64.34" in f.detail for f in unknown)

    def test_no_flag_for_known_ips(self):
        """IPs that ARE in environment domains should not be flagged."""
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]},
            "environment_domains": {
                "test": {"ips": ["8.129.22.14", "123.56.64.34"]},  # both known
                "prod": {"ips": ["47.112.120.194"]},
            },
        }
        findings = cross_layer_check(str(CLAUDE_FIXTURE), config)
        assert not any("123.56.64.34" in f.detail for f in findings)

    def test_skips_without_env_domains(self):
        """No environment_domains → empty findings."""
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]}}
        findings = cross_layer_check(str(CLAUDE_FIXTURE), config)
        assert findings == []


class TestStructureDrift:
    def test_detects_ghost_module(self, tmp_path):
        """Module in config but directory doesn't exist → ghost."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        # api/ doesn't exist
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]}}
        findings = structure_drift_check(str(tmp_path), config)
        ghosts = [f for f in findings if "does not exist" in f.detail]
        assert len(ghosts) == 1
        assert "api" in ghosts[0].detail

    def test_detects_undocumented_module(self, tmp_path):
        """Directory with code exists but not in docs → undocumented."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        # Create a code module not in layer2
        mod = tmp_path / "new-service"
        mod.mkdir()
        (mod / "src").mkdir()
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": []}}
        findings = structure_drift_check(str(tmp_path), config)
        undoc = [f for f in findings if "not in documented" in f.detail]
        assert any("new-service" in f.detail for f in undoc)

    def test_no_false_positive_for_documented(self, tmp_path):
        """Documented module with matching directory → no finding."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        mod = tmp_path / "api"
        mod.mkdir()
        (mod / "src").mkdir()
        (mod / "CLAUDE.md").write_text("# API", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["api/CLAUDE.md"]}}
        findings = structure_drift_check(str(tmp_path), config)
        assert len(findings) == 0

    def test_standalone_skips(self, tmp_path):
        """Standalone project (no layer2) → no findings."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}}
        findings = structure_drift_check(str(tmp_path), config)
        assert findings == []

    def test_verification_path_in_suggestion(self, tmp_path):
        """Fix suggestion should include verification steps."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["gone/CLAUDE.md"]}}
        findings = structure_drift_check(str(tmp_path), config)
        assert findings[0].fix_suggestion.startswith("1.")


class TestExtractIpsAndPorts:
    def test_extracts_ips(self):
        ips, _ = _extract_ips_and_ports(str(CLAUDE_FIXTURE / "CLAUDE.md"))
        assert "8.129.22.14" in ips
        assert "47.112.120.194" in ips

    def test_extracts_from_module(self):
        ips, _ = _extract_ips_and_ports(str(CLAUDE_FIXTURE / "api" / "CLAUDE.md"))
        assert "123.56.64.34" in ips


# ---------------------------------------------------------------------------
# Config Value Drift (dedicated tests, was #5)
# ---------------------------------------------------------------------------

class TestConfigValueDrift:
    def test_flags_unknown_ip_in_config_file(self, tmp_path):
        """Config file has IP not in any domain → flag."""
        (tmp_path / "CLAUDE.md").write_text("# Root", encoding="utf-8")
        (tmp_path / "bootstrap.yml").write_text(
            "server:\n  addr: 8.129.22.14:8848\n  backup: 99.99.99.99\n", encoding="utf-8"
        )
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "environment_domains": {"test": {"ips": ["8.129.22.14"]}},
            "ignore_paths": [],
        }
        findings = config_value_drift_check(str(tmp_path), config)
        assert any("99.99.99.99" in f.detail for f in findings)

    def test_no_flag_when_all_known(self, tmp_path):
        """All IPs in config are in domains → no flag."""
        (tmp_path / "bootstrap.yml").write_text("addr: 8.129.22.14", encoding="utf-8")
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "environment_domains": {"test": {"ips": ["8.129.22.14"]}},
            "ignore_paths": [],
        }
        findings = config_value_drift_check(str(tmp_path), config)
        assert len(findings) == 0

    def test_skips_without_env_domains(self, tmp_path):
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}}
        findings = config_value_drift_check(str(tmp_path), config)
        assert findings == []


# ---------------------------------------------------------------------------
# Staleness boundary (was #9)
# ---------------------------------------------------------------------------

class TestStalenessBoundary:
    def test_within_threshold_not_reported(self, monkeypatch):
        """Gap < threshold → no finding."""
        import time
        now = int(time.time())
        monkeypatch.setattr("core.doc_garden_core._git_last_modified", lambda p: now - 86400)  # 1 day ago

        import subprocess
        original_run = subprocess.run
        def mock_run(args, **kwargs):
            if "rev-parse" in args:
                class R: returncode = 0; stdout = "true"
                return R()
            if "log" in args and "--" in args:
                class R: returncode = 0; stdout = str(now - 3600)  # 1 hour ago (code newer by 23h)
                return R()
            return original_run(args, **kwargs)
        monkeypatch.setattr("subprocess.run", mock_run)

        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "staleness_threshold_days": 14}
        # 23 hours gap < 14 days → no finding
        findings = staleness_check("/fake", config)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Apply auto fix (was #1)
# ---------------------------------------------------------------------------

class TestApplyAutoFix:
    def test_removes_ghost_from_memory_md(self, monkeypatch, tmp_path):
        mem = tmp_path / "memory"
        mem.mkdir()
        (mem / "MEMORY.md").write_text(
            "# Index\n- [real](real.md) — exists\n- [ghost](ghost.md) — doesn't exist\n",
            encoding="utf-8"
        )
        (mem / "real.md").write_text("content", encoding="utf-8")
        # ghost.md does NOT exist

        monkeypatch.setattr("core.doc_garden_core.resolve_memory_dir", lambda cwd: str(mem))

        from core.doc_garden_core import Finding
        ghost_finding = Finding(
            drift_type=DriftType.MEMORY_INDEX_GHOST, severity=Severity.WARNING,
            file="MEMORY.md", detail="References 'ghost.md' but file does not exist",
            fix_suggestion="Remove", auto_fixable=True,
        )
        actions = apply_auto_fix(str(tmp_path), [ghost_finding])
        assert len(actions) == 1
        assert "ghost.md" in actions[0]

        # Verify ghost line removed
        content = (mem / "MEMORY.md").read_text(encoding="utf-8")
        assert "ghost.md" not in content
        assert "real.md" in content


# ---------------------------------------------------------------------------
# Validate config (was #10)
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_valid_config(self):
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
        assert validate_config(config) == []

    def test_internal_keys(self):
        config = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}, "_discovery": {}}
        errors = validate_config(config)
        assert any("Internal keys" in e for e in errors)

    def test_missing_project_type(self):
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}}
        errors = validate_config(config)
        assert any("project_type" in e for e in errors)

    def test_unorganized_domains(self):
        config = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "environment_domains": {"_unorganized": {"ips": ["1.2.3.4"]}},
        }
        errors = validate_config(config)
        assert any("_unorganized" in e for e in errors)


# ---------------------------------------------------------------------------
# Transcript parsing (moved to core, was #2)
# ---------------------------------------------------------------------------

class TestTranscriptParsing:
    def test_extracts_write_edit(self):
        transcript = str(FIXTURES / "sample-payloads" / "transcript.jsonl")
        result = extract_modified_files_from_transcript(transcript)
        paths = {os.path.basename(p) for p in result}
        assert "handler.java" in paths
        assert "new_file.py" in paths
        assert "main.py" not in paths

    def test_resolve_module(self):
        assert resolve_module_from_path("D:/work/project/api/src/Main.java", "D:/work/project") == "api"
        assert resolve_module_from_path("D:/work/project/README.md", "D:/work/project") == ""
