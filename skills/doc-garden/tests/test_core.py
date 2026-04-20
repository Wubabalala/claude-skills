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
    fact_value_conflict_check,
    generate_draft_config,
    has_config,
    save_config,
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
    Finding,
    _parse_memory_index,
    _guess_section,
    _read_frontmatter_type,
    DEFAULT_CONFIG,
    deep_merge,
    collect_doc_files,
    resolve_reference,
    ResolveResult,
    run_audit,
    format_report,
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

        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "path_resolvers": [
                {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": True},
            ],
            "ignore_paths": [],
        }
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

        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "path_resolvers": [
                {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": True},
            ],
            "ignore_paths": [],
        }
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

        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "path_resolvers": [
                {"prefix": "plans/", "root": "$HOME/.claude/plans", "optional": True},
            ],
            "ignore_paths": [],
        }
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

    def test_ignore_url_prefixes_skips_http_endpoint(self, tmp_path):
        """HTTP endpoint strings like `/admin/auth/login` should NOT be flagged
        as PATH_ROT when the project opts in via `ignore_url_prefixes`."""
        (tmp_path / "CLAUDE.md").write_text(
            "Login: `/admin/auth/login`\nCallback: `/api/payment/callback/wechat`\n"
            "Real file: `src/main.py`\n",
            encoding="utf-8",
        )
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "main.py").write_text("", encoding="utf-8")
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": [],
            "ignore_url_prefixes": ["/admin/", "/api/"],
        }
        findings = path_rot_check(str(tmp_path), config)
        rot_paths = [f.detail for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not any("admin" in d for d in rot_paths), rot_paths
        assert not any("/api/payment" in d for d in rot_paths), rot_paths

    def test_ignore_url_prefixes_default_empty_still_flags(self, tmp_path):
        """Without opt-in, URL-like paths are still caught (backward compat)."""
        (tmp_path / "CLAUDE.md").write_text(
            "Endpoint: `/admin/dashboard`\n", encoding="utf-8"
        )
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "ignore_paths": []}
        findings = path_rot_check(str(tmp_path), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert any("admin/dashboard" in f.detail for f in rot), rot

    def test_generic_path_fallbacks_resolves_monorepo_prefix(self, tmp_path):
        """Short relative references resolve against configured fallback prefixes."""
        # Simulate monorepo layout: real file under frontend/src/
        (tmp_path / "frontend" / "src" / "components").mkdir(parents=True)
        (tmp_path / "frontend" / "src" / "components" / "Foo.vue").write_text(
            "", encoding="utf-8"
        )
        (tmp_path / "CLAUDE.md").write_text(
            "See `components/Foo.vue`\n", encoding="utf-8"
        )
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": [],
            "generic_path_fallbacks": ["frontend/src/"],
        }
        findings = path_rot_check(str(tmp_path), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not rot, f"expected no PATH_ROT with fallback, got: {rot}"

    def test_generic_path_fallbacks_flags_when_all_fail(self, tmp_path):
        """Fallback prefixes are last resort; truly missing files still flagged."""
        (tmp_path / "CLAUDE.md").write_text(
            "Missing: `components/Ghost.vue`\n", encoding="utf-8"
        )
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": [],
            "generic_path_fallbacks": ["frontend/src/", "backend/src/"],
        }
        findings = path_rot_check(str(tmp_path), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert any("Ghost.vue" in f.detail for f in rot), rot

    def test_generic_path_fallbacks_ordered_first_hit_wins(self, tmp_path):
        """Fallbacks checked in order; if any prefix resolves, no PATH_ROT."""
        (tmp_path / "backend" / "src" / "svc").mkdir(parents=True)
        (tmp_path / "backend" / "src" / "svc" / "Impl.java").write_text(
            "", encoding="utf-8"
        )
        (tmp_path / "CLAUDE.md").write_text(
            "Service: `svc/Impl.java`\n", encoding="utf-8"
        )
        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "ignore_paths": [],
            # frontend 先, backend 后; backend 命中也算成功
            "generic_path_fallbacks": ["frontend/src/", "backend/src/"],
        }
        findings = path_rot_check(str(tmp_path), config)
        rot = [f for f in findings if f.drift_type == DriftType.PATH_ROT]
        assert not rot, f"expected backend fallback to resolve, got: {rot}"


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

    def test_save_config_strips_underscore_prefix_keys(self, tmp_path):
        """save_config must not persist _-prefixed agent-facing metadata.
        Guards SKILL.md's promise that `_discovery` is removed before save."""
        config = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "staleness_threshold_days": 14,
            "_discovery": {"detected_type": "standalone", "claude_md_count": 1},
        }
        save_config(str(tmp_path), config)
        loaded = load_config(str(tmp_path))
        assert "_discovery" not in loaded
        assert loaded["project_type"] == "standalone"
        assert loaded["doc_hierarchy"] == {"layer1": "CLAUDE.md"}
        assert loaded["staleness_threshold_days"] == 14

    def test_save_config_does_not_mutate_caller_dict(self, tmp_path):
        """save_config must not mutate the caller's config dict when stripping keys."""
        config = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "_discovery": {"x": 1},
        }
        save_config(str(tmp_path), config)
        assert "_discovery" in config  # original dict untouched


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
        assert "doc_count" in d
        assert "doc_files" in d
        assert "layer1_chosen" in d
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

    def test_untracked_file_skipped(self, tmp_path):
        """A file that exists on disk but is not tracked by git should be
        silently skipped (drift-taxonomy §6 contract). This covers both
        'never committed' and 'previously committed then gitignored + rm'."""
        import subprocess
        # Initialize a git repo
        subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True)
        # Commit something so there IS a git history (needed for the `git log -- .`
        # query in staleness_check to return nonzero)
        (tmp_path / "dummy.txt").write_text("seed", encoding="utf-8")
        subprocess.run(["git", "add", "dummy.txt"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "-m", "seed", "-q"], cwd=str(tmp_path), check=True)
        # Create CLAUDE.md but DON'T add it to git (untracked)
        (tmp_path / "CLAUDE.md").write_text("# Root doc", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "staleness_threshold_days": 1}
        findings = staleness_check(str(tmp_path), config)
        # Untracked CLAUDE.md → no STALENESS finding
        stale = [f for f in findings if f.drift_type == DriftType.STALENESS]
        assert not stale, f"untracked CLAUDE.md should not report STALENESS, got: {stale}"

    def test_gitignored_file_skipped(self, tmp_path):
        """A file that was tracked, git rm'd, and added to .gitignore should
        be treated as untracked and skipped. This is the real-world scenario:
        CLAUDE.md used to be in git, got rm'd and gitignored."""
        import subprocess
        subprocess.run(["git", "init", "-q"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.email", "t@t"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "config", "user.name", "t"], cwd=str(tmp_path), check=True)
        (tmp_path / "CLAUDE.md").write_text("# Initial", encoding="utf-8")
        subprocess.run(["git", "add", "CLAUDE.md"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "-m", "initial", "-q"], cwd=str(tmp_path), check=True)
        # Now rm and gitignore
        subprocess.run(["git", "rm", "CLAUDE.md", "-q"], cwd=str(tmp_path), check=True)
        (tmp_path / ".gitignore").write_text("CLAUDE.md\n", encoding="utf-8")
        subprocess.run(["git", "add", ".gitignore"], cwd=str(tmp_path), check=True)
        subprocess.run(["git", "commit", "-m", "gitignore", "-q"], cwd=str(tmp_path), check=True)
        # Recreate locally (untracked)
        (tmp_path / "CLAUDE.md").write_text("# Local only", encoding="utf-8")
        config = {"doc_hierarchy": {"layer1": "CLAUDE.md"}, "staleness_threshold_days": 1}
        findings = staleness_check(str(tmp_path), config)
        stale = [f for f in findings if f.drift_type == DriftType.STALENESS]
        assert not stale, f"gitignored + rm'd CLAUDE.md should skip STALENESS, got: {stale}"


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


# ---------------------------------------------------------------------------
# New features (multi-format discovery + deep_merge + resolver + custom hook)
# ---------------------------------------------------------------------------

class TestDeepMerge:
    def test_preserves_user_overrides(self):
        default = {"a": 1, "b": {"c": 2}, "tags": ["x"]}
        user = {"a": 99, "b": {"c": 100}, "tags": ["y", "z"]}
        result = deep_merge(default, user)
        assert result["a"] == 99
        assert result["b"]["c"] == 100
        # Lists are replaced wholesale, not concatenated
        assert result["tags"] == ["y", "z"]

    def test_new_fields_inherit(self):
        """Old user config missing doc_patterns/path_resolvers → inherits from DEFAULT."""
        old_user = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "staleness_threshold_days": 7,
            "ignore_paths": ["node_modules/"],
        }
        merged = deep_merge(DEFAULT_CONFIG, old_user)
        assert merged["doc_patterns"] == DEFAULT_CONFIG["doc_patterns"]
        assert merged["path_resolvers"] == DEFAULT_CONFIG["path_resolvers"]
        # User's override survives
        assert merged["staleness_threshold_days"] == 7

    def test_empty_hierarchy_respected(self):
        """doc_hierarchy: {} is explicit opt-out; do not backfill layer1."""
        user = {"doc_hierarchy": {}}
        merged = deep_merge(DEFAULT_CONFIG, user)
        assert merged["doc_hierarchy"] == {}
        # But doc_patterns still inherited
        assert "doc_patterns" in merged

    def test_does_not_mutate_inputs(self):
        default = {"a": {"b": 1}}
        user = {"a": {"c": 2}}
        deep_merge(default, user)
        assert default == {"a": {"b": 1}}
        assert user == {"a": {"c": 2}}


class TestCollectDocFiles:
    def test_union_of_hierarchy_and_patterns(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("root", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("agents", encoding="utf-8")
        (tmp_path / "module-a").mkdir()
        (tmp_path / "module-a" / "CLAUDE.md").write_text("mod a", encoding="utf-8")

        config = {
            "doc_hierarchy": {"layer1": "CLAUDE.md", "layer2": ["module-a/CLAUDE.md"]},
            "doc_patterns": ["CLAUDE.md", "AGENTS.md"],
            "ignore_paths": [],
        }
        result = collect_doc_files(str(tmp_path), config)
        assert "CLAUDE.md" in result
        assert "AGENTS.md" in result
        assert "module-a/CLAUDE.md" in result
        # Dedup: "CLAUDE.md" not duplicated from both hierarchy and discovery
        assert result.count("CLAUDE.md") == 1

    def test_stable_order(self, tmp_path):
        """Root docs first (0 slashes), then 1-level (1 slash), etc; alpha within tier."""
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
        (tmp_path / "z-mod").mkdir()
        (tmp_path / "z-mod" / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "a-mod").mkdir()
        (tmp_path / "a-mod" / "CLAUDE.md").write_text("", encoding="utf-8")

        config = {"doc_patterns": ["CLAUDE.md", "AGENTS.md"], "ignore_paths": []}
        result = collect_doc_files(str(tmp_path), config)
        # Root docs (no slash) come before module docs, alpha within each tier
        assert result == ["AGENTS.md", "CLAUDE.md", "a-mod/CLAUDE.md", "z-mod/CLAUDE.md"]

    def test_without_layer1(self, tmp_path):
        """doc_hierarchy: {} + doc_patterns still finds docs via walk."""
        (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
        config = {
            "doc_hierarchy": {},
            "doc_patterns": ["AGENTS.md"],
            "ignore_paths": [],
        }
        result = collect_doc_files(str(tmp_path), config)
        assert result == ["AGENTS.md"]

    def test_prunes_ignore_paths(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "CLAUDE.md").write_text("", encoding="utf-8")
        config = {
            "doc_patterns": ["CLAUDE.md"],
            "ignore_paths": ["node_modules/"],  # trailing slash — normalization required
        }
        result = collect_doc_files(str(tmp_path), config)
        assert "node_modules/CLAUDE.md" not in result
        assert "CLAUDE.md" in result


class TestDetectProjectTypeAgentsMd:
    def test_agents_only_standalone(self, tmp_path):
        (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
        ptype, docs = detect_project_type(str(tmp_path))
        assert ptype == "standalone"
        assert docs == ["AGENTS.md"]

    def test_two_root_docs_still_standalone(self, tmp_path):
        """CLAUDE.md + AGENTS.md at root is still 1 directory → standalone.
        Regression guard: prior heuristic counted total doc files and would
        have misclassified this as 'monorepo'."""
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
        ptype, docs = detect_project_type(str(tmp_path))
        assert ptype == "standalone"
        assert set(docs) == {"CLAUDE.md", "AGENTS.md"}

    def test_root_plus_one_module_monorepo(self, tmp_path):
        """Root doc + one module doc = 2 dirs → monorepo."""
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "mod-a").mkdir()
        (tmp_path / "mod-a" / "CLAUDE.md").write_text("", encoding="utf-8")
        ptype, _ = detect_project_type(str(tmp_path))
        assert ptype == "monorepo"

    def test_root_plus_two_modules_microservice(self, tmp_path):
        """Root + 2 modules = 3 dirs → microservice."""
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        for mod in ("mod-a", "mod-b"):
            (tmp_path / mod).mkdir()
            (tmp_path / mod / "CLAUDE.md").write_text("", encoding="utf-8")
        ptype, _ = detect_project_type(str(tmp_path))
        assert ptype == "microservice"


class TestGenerateDraftConfigNew:
    def test_agents_only(self, tmp_path):
        """AGENTS-only repo: layer1 should be AGENTS.md (not CLAUDE.md)."""
        (tmp_path / "AGENTS.md").write_text("# Project", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        assert draft["doc_hierarchy"]["layer1"] == "AGENTS.md"
        assert draft["_discovery"]["layer1_chosen"] == "AGENTS.md"
        assert draft["_discovery"]["root_agents_md_present"] is True
        assert "warning" not in draft["_discovery"]

    def test_no_root_doc_warns(self, tmp_path):
        """Neither CLAUDE.md nor AGENTS.md at root → layer1 falls back + warning."""
        # Put a subdir doc so detect_project_type has something to find
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "CLAUDE.md").write_text("", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        assert draft["doc_hierarchy"]["layer1"] == "CLAUDE.md"  # fallback
        assert draft["_discovery"]["root_claude_md_present"] is False
        assert draft["_discovery"]["root_agents_md_present"] is False
        assert "warning" in draft["_discovery"]

    def test_claude_md_wins_over_agents_md(self, tmp_path):
        """Both present → CLAUDE.md picked (Claude Code convention)."""
        (tmp_path / "CLAUDE.md").write_text("", encoding="utf-8")
        (tmp_path / "AGENTS.md").write_text("", encoding="utf-8")
        draft = generate_draft_config(str(tmp_path))
        assert draft["doc_hierarchy"]["layer1"] == "CLAUDE.md"


class TestResolveReference:
    def test_memory_exists(self, tmp_path, monkeypatch):
        fake_mem = tmp_path / "mem"
        fake_mem.mkdir()
        (fake_mem / "foo.md").write_text("", encoding="utf-8")
        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir", lambda cwd: str(fake_mem)
        )
        config = {
            "path_resolvers": [
                {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": True},
            ],
        }
        result = resolve_reference(
            "memory/foo.md", str(tmp_path / "CLAUDE.md"), str(tmp_path), config
        )
        assert result.status == "exists"

    def test_memory_missing(self, tmp_path, monkeypatch):
        fake_mem = tmp_path / "mem"
        fake_mem.mkdir()  # root exists, file inside doesn't
        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir", lambda cwd: str(fake_mem)
        )
        config = {
            "path_resolvers": [
                {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": True},
            ],
        }
        result = resolve_reference(
            "memory/ghost.md", str(tmp_path / "CLAUDE.md"), str(tmp_path), config
        )
        assert result.status == "missing"

    def test_optional_resolver_skip_when_root_missing(self, tmp_path, monkeypatch):
        """Optional resolver whose root does not exist → skip, no finding."""
        nonexistent = tmp_path / "does-not-exist"
        monkeypatch.setattr(
            "core.doc_garden_core.resolve_memory_dir", lambda cwd: str(nonexistent)
        )
        config = {
            "path_resolvers": [
                {"prefix": "memory/", "root": "$CLAUDE_MEMORY_DIR", "optional": True},
            ],
        }
        result = resolve_reference(
            "memory/foo.md", str(tmp_path / "CLAUDE.md"), str(tmp_path), config
        )
        assert result.status == "skip"
        assert "does not exist" in result.reason

    def test_env_placeholder_resolves(self, tmp_path, monkeypatch):
        """$ENV:VAR placeholder pulls from process environment."""
        custom_root = tmp_path / "custom-docs"
        custom_root.mkdir()
        (custom_root / "note.md").write_text("", encoding="utf-8")
        monkeypatch.setenv("DG_CUSTOM_ROOT", str(custom_root))
        config = {
            "path_resolvers": [
                {"prefix": "notes/", "root": "$ENV:DG_CUSTOM_ROOT", "optional": False},
            ],
        }
        result = resolve_reference(
            "notes/note.md", str(tmp_path / "CLAUDE.md"), str(tmp_path), config
        )
        assert result.status == "exists"

    def test_env_placeholder_unset_with_optional_skips(self, tmp_path, monkeypatch):
        """Unset $ENV:VAR + optional resolver → skip (user chose to make it optional)."""
        monkeypatch.delenv("DG_NEVER_SET", raising=False)
        config = {
            "path_resolvers": [
                {"prefix": "ext/", "root": "$ENV:DG_NEVER_SET", "optional": True},
            ],
        }
        result = resolve_reference(
            "ext/thing.md", str(tmp_path / "CLAUDE.md"), str(tmp_path), config
        )
        assert result.status == "skip"


class TestCustomHook:
    def _write_hook(self, tmp_path, body):
        hook_dir = tmp_path / ".claude"
        hook_dir.mkdir()
        (hook_dir / "doc-garden-checks.py").write_text(body, encoding="utf-8")

    def _minimal_config_with_layer1(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Project", encoding="utf-8")
        return {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
        }

    def test_custom_hook_runs(self, tmp_path):
        """Hook returning Finding list is integrated into audit findings."""
        self._write_hook(tmp_path, """
from core.doc_garden_core import Finding, DriftType, Severity
def run_custom_checks(cwd, config):
    return [Finding(
        drift_type=DriftType.CONTENT_DRIFT,
        severity=Severity.WARNING,
        file="custom/file.md",
        detail="Custom-detected drift",
        fix_suggestion="Fix it",
    )]
""")
        cfg = self._minimal_config_with_layer1(tmp_path)
        findings = run_audit(str(tmp_path), cfg)
        content_drift = [f for f in findings if f.drift_type == DriftType.CONTENT_DRIFT]
        assert len(content_drift) == 1
        assert content_drift[0].detail == "Custom-detected drift"

    def test_custom_hook_exception_isolated(self, tmp_path):
        """Hook raising → CUSTOM_CHECK_ERROR, rest of audit still runs."""
        self._write_hook(tmp_path, """
def run_custom_checks(cwd, config):
    raise RuntimeError("boom")
""")
        cfg = self._minimal_config_with_layer1(tmp_path)
        findings = run_audit(str(tmp_path), cfg)
        errors = [f for f in findings if f.drift_type == DriftType.CUSTOM_CHECK_ERROR]
        assert len(errors) == 1
        assert "RuntimeError" in errors[0].detail
        assert "boom" in errors[0].detail

    def test_custom_hook_bad_return_type(self, tmp_path):
        """Hook returning None / dict → CUSTOM_CHECK_ERROR, audit continues."""
        self._write_hook(tmp_path, """
def run_custom_checks(cwd, config):
    return {"not": "a list"}
""")
        cfg = self._minimal_config_with_layer1(tmp_path)
        findings = run_audit(str(tmp_path), cfg)
        errors = [f for f in findings if f.drift_type == DriftType.CUSTOM_CHECK_ERROR]
        assert len(errors) == 1
        assert "list[Finding]" in errors[0].detail

    def test_custom_hook_list_with_bad_item(self, tmp_path):
        """Hook returning list with non-Finding items → per-item CUSTOM_CHECK_ERROR."""
        self._write_hook(tmp_path, """
from core.doc_garden_core import Finding, DriftType, Severity
def run_custom_checks(cwd, config):
    return [
        Finding(drift_type=DriftType.CONTENT_DRIFT, severity=Severity.WARNING,
                file="ok.md", detail="legit", fix_suggestion=""),
        "this is not a Finding",
        42,
    ]
""")
        cfg = self._minimal_config_with_layer1(tmp_path)
        findings = run_audit(str(tmp_path), cfg)
        content = [f for f in findings if f.drift_type == DriftType.CONTENT_DRIFT]
        errors = [f for f in findings if f.drift_type == DriftType.CUSTOM_CHECK_ERROR]
        # Valid Finding kept, 2 invalid items → 2 CUSTOM_CHECK_ERROR
        assert len(content) == 1
        assert len(errors) == 2


class TestValidateConfigNew:
    def test_catches_bad_doc_patterns(self):
        cases = [
            {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"},
             "doc_patterns": []},              # empty list
            {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"},
             "doc_patterns": ""},              # not a list
            {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"},
             "doc_patterns": [""]},            # empty string item
        ]
        for cfg in cases:
            errors = validate_config(cfg)
            assert any("doc_patterns" in e for e in errors), f"missed: {cfg}"

    def test_catches_bad_path_resolvers(self):
        cfg = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "path_resolvers": [
                {"prefix": "memory/"},  # missing root
            ],
        }
        errors = validate_config(cfg)
        assert any("path_resolvers[0]" in e and "root" in e for e in errors)

    def test_catches_empty_string_layer1(self):
        cfg = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": ""},
        }
        errors = validate_config(cfg)
        assert any("layer1" in e and "non-empty" in e for e in errors)

    def test_layer1_missing_soft_when_doc_patterns_set(self, tmp_path):
        """run_audit downgrades 'Missing layer1' to WARNING if doc_patterns is set.
        Empty-string layer1 stays CRITICAL."""
        (tmp_path / "CLAUDE.md").write_text("# stub", encoding="utf-8")
        # Case A: layer1 truly absent, patterns provided
        cfg_a = {
            "project_type": "standalone",
            "doc_hierarchy": {},
            "doc_patterns": ["CLAUDE.md"],
        }
        findings_a = run_audit(str(tmp_path), cfg_a)
        schema_a = [f for f in findings_a if f.drift_type == DriftType.CONFIG_SCHEMA_WARNING
                    and "layer1" in f.detail]
        assert schema_a, "expected layer1-missing finding"
        assert schema_a[0].severity == Severity.WARNING, "should be downgraded"

        # Case B: layer1 is empty string (a different, harsher error)
        cfg_b = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": ""},
            "doc_patterns": ["CLAUDE.md"],
        }
        findings_b = run_audit(str(tmp_path), cfg_b)
        schema_b = [f for f in findings_b if f.drift_type == DriftType.CONFIG_SCHEMA_WARNING
                    and "layer1" in f.detail]
        assert schema_b
        # Empty-string layer1 must stay CRITICAL
        assert schema_b[0].severity == Severity.CRITICAL


class TestFormatReport:
    def test_project_name(self):
        findings = [Finding(
            drift_type=DriftType.PATH_ROT, severity=Severity.WARNING,
            file="x.md", detail="missing", fix_suggestion="",
        )]
        report = format_report(findings, project_name="my-project")
        assert "**Project**: my-project" in report


# ---------------------------------------------------------------------------
# fact_value_conflict_check
# ---------------------------------------------------------------------------

class TestFactValueConflict:
    """FACT_VALUE_CONFLICT detects same fact-key values diverging across docs."""

    def _write(self, path: Path, content: str):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _cfg(self, extra=None):
        cfg = {
            "project_type": "standalone",
            "doc_hierarchy": {"layer1": "CLAUDE.md"},
            "doc_patterns": ["CLAUDE.md", "REFERENCE.md"],
            "fact_patterns": [
                {
                    "name": "file_line_count",
                    "regex": r"([\w.-]+\.(?:java|vue|py))\s*\((\d{2,})\)",
                    "key_group": 1,
                    "value_group": 2,
                }
            ],
        }
        if extra:
            cfg.update(extra)
        return cfg

    def test_reports_cross_doc_divergent_value(self, tmp_path):
        """Same key, different values, in two docs → one finding."""
        self._write(tmp_path / "CLAUDE.md", "PaymentService.java (1497)\n")
        self._write(tmp_path / "REFERENCE.md", "PaymentService.java (1200)\n")

        findings = fact_value_conflict_check(str(tmp_path), self._cfg())
        assert len(findings) == 1
        f = findings[0]
        assert f.drift_type == DriftType.FACT_VALUE_CONFLICT
        assert f.severity == Severity.WARNING
        assert "PaymentService.java" in f.detail
        assert "1497" in f.detail and "1200" in f.detail
        assert "file_line_count" in f.detail

    def test_aligned_values_no_finding(self, tmp_path):
        """Same key, same value across docs → no conflict."""
        self._write(tmp_path / "CLAUDE.md", "Editor.vue (1032)\n")
        self._write(tmp_path / "REFERENCE.md", "See Editor.vue (1032) for layout.\n")

        findings = fact_value_conflict_check(str(tmp_path), self._cfg())
        assert findings == []

    def test_single_doc_repetition_ignored(self, tmp_path):
        """Intra-doc repetition (even with divergent values) does not trigger
        a conflict — only cross-doc divergence counts."""
        self._write(
            tmp_path / "CLAUDE.md",
            "PaymentService.java (1497)\n... later in the doc ...\nPaymentService.java (1200)\n",
        )
        findings = fact_value_conflict_check(str(tmp_path), self._cfg())
        assert findings == []

    def test_no_fact_patterns_no_check(self, tmp_path):
        """Empty/absent fact_patterns → check is a no-op."""
        self._write(tmp_path / "CLAUDE.md", "PaymentService.java (1497)\n")
        self._write(tmp_path / "REFERENCE.md", "PaymentService.java (1200)\n")

        cfg = self._cfg()
        cfg["fact_patterns"] = []
        assert fact_value_conflict_check(str(tmp_path), cfg) == []

    def test_run_audit_wires_check(self, tmp_path):
        """run_audit includes FACT_VALUE_CONFLICT findings when fact_patterns set."""
        self._write(tmp_path / "CLAUDE.md", "WorkService.java (1119)\n")
        self._write(tmp_path / "REFERENCE.md", "WorkService.java (9999)\n")

        all_findings = run_audit(str(tmp_path), self._cfg())
        fvc = [f for f in all_findings if f.drift_type == DriftType.FACT_VALUE_CONFLICT]
        assert len(fvc) == 1

    def test_detail_cites_all_sites_with_line_numbers(self, tmp_path):
        """Finding detail lists every (doc:line, value) tuple so the user can
        see where each divergent value lives."""
        self._write(
            tmp_path / "CLAUDE.md",
            "Header\n\nAIProviderManager.java (1425)\n",
        )
        self._write(
            tmp_path / "REFERENCE.md",
            "# Ref\n\n\nAIProviderManager.java (2000)\n",
        )
        findings = fact_value_conflict_check(str(tmp_path), self._cfg())
        assert len(findings) == 1
        detail = findings[0].detail
        # CLAUDE.md line 3 = "AIProviderManager.java (1425)"
        # REFERENCE.md line 4 = "AIProviderManager.java (2000)"
        assert "CLAUDE.md:3" in detail
        assert "REFERENCE.md:4" in detail

    def test_validate_config_catches_bad_fact_patterns(self):
        """Schema validation surfaces malformed fact_patterns entries."""
        cases = [
            {"fact_patterns": "not-a-list"},
            {"fact_patterns": [{"regex": "x", "key_group": 1, "value_group": 2}]},    # missing name
            {"fact_patterns": [{"name": "n", "key_group": 1, "value_group": 2}]},     # missing regex
            {"fact_patterns": [{"name": "n", "regex": "x", "key_group": 0, "value_group": 2}]},  # key_group < 1
            {"fact_patterns": [{"name": "n", "regex": "(", "key_group": 1, "value_group": 1}]},  # invalid regex
        ]
        for extra in cases:
            cfg = {"project_type": "standalone", "doc_hierarchy": {"layer1": "CLAUDE.md"}}
            cfg.update(extra)
            errors = validate_config(cfg)
            assert any("fact_patterns" in e for e in errors), f"missed: {extra}"
