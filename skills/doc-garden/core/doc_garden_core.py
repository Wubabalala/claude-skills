"""doc-garden core: shared detection engine for documentation drift auditing.

All detection logic lives here. SKILL.md and hooks are thin consumers.
"""
import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(str, Enum):
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class DriftType(str, Enum):
    MEMORY_INDEX_SUNKEN = "MEMORY_INDEX_SUNKEN"    # file exists but not indexed
    MEMORY_INDEX_GHOST = "MEMORY_INDEX_GHOST"       # indexed but file missing
    PATH_ROT = "PATH_ROT"                           # path in doc doesn't exist
    CONFIG_VALUE_DRIFT = "CONFIG_VALUE_DRIFT"        # doc value != code value
    CROSS_LAYER_CONTRADICTION = "CROSS_LAYER_CONTRADICTION"
    STRUCTURE_DRIFT = "STRUCTURE_DRIFT"
    STALENESS = "STALENESS"


@dataclass
class Finding:
    drift_type: DriftType
    severity: Severity
    file: str               # which doc file has the issue
    detail: str             # human-readable description
    fix_suggestion: str = ""
    auto_fixable: bool = False
    section_hint: str = ""  # for memory index: which section to insert into


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = {
    "project_type": "standalone",
    "doc_hierarchy": {"layer1": "CLAUDE.md"},
    "staleness_threshold_days": 14,
    "ignore_paths": ["node_modules/", ".git/", "dist/", ".venv/", "__pycache__/"],
}


def load_config(cwd: str) -> dict:
    """Load .claude/doc-garden.json from project root, or return defaults."""
    config_path = os.path.join(cwd, ".claude", "doc-garden.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    return dict(DEFAULT_CONFIG)


def save_config(cwd: str, config: dict):
    """Save config to .claude/doc-garden.json.

    Top-level keys starting with `_` (e.g. `_discovery`) are agent-facing
    metadata and are stripped before persistence. The caller's dict is not
    mutated. Note: nested `_`-prefix keys (e.g. `_unorganized` inside
    `environment_domains`) are NOT stripped — if they reach save time it
    means the interactive env-domain grouping step was skipped, and the
    dirty data is preserved to surface the oversight.
    """
    persisted = {k: v for k, v in config.items() if not k.startswith("_")}
    config_dir = os.path.join(cwd, ".claude")
    os.makedirs(config_dir, exist_ok=True)
    config_path = os.path.join(config_dir, "doc-garden.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(persisted, f, ensure_ascii=False, indent=2)


def has_config(cwd: str) -> bool:
    """Check if .claude/doc-garden.json exists."""
    return os.path.exists(os.path.join(cwd, ".claude", "doc-garden.json"))


def generate_draft_config(cwd: str) -> dict:
    """Scan project structure and generate a draft config for user confirmation.

    This is a HEURISTIC — the output must be reviewed by the user before saving.

    Steps:
    1. Detect project type + find all CLAUDE.md files
    2. Extract all IPs from root CLAUDE.md (for environment domain discovery)
    3. Attempt to group IPs by parsing markdown tables with environment headers
    4. If table parsing fails, list discovered IPs for user to organize
    5. Set sensible defaults for threshold and ignore paths

    Returns a dict with the draft config + a '_discovery' key containing
    metadata for the agent to present to the user.
    """
    project_type, claude_mds = detect_project_type(cwd)

    # Build layer2 from discovered CLAUDE.md files (exclude root)
    layer2 = [f for f in claude_mds if f != "CLAUDE.md"]

    # Extract IPs from root CLAUDE.md for environment domain discovery
    root_path = os.path.join(cwd, "CLAUDE.md")
    discovered_ips = set()
    env_domains = {}

    if os.path.exists(root_path):
        root_ips, _ = _extract_ips_and_ports(root_path)
        discovered_ips = root_ips - {"127.0.0.1", "0.0.0.0"}

        # Attempt table parsing: look for rows with environment keywords + IPs
        env_domains = _parse_env_table(root_path)

    # If table parsing found nothing but we have IPs, leave for user to organize
    if not env_domains and discovered_ips:
        env_domains = {
            "_unorganized": {
                "ips": sorted(discovered_ips),
                "_note": "IPs discovered in root CLAUDE.md. Please organize into environment domains (e.g., test/prod/local)."
            }
        }

    config = {
        "project_type": project_type,
        "doc_hierarchy": {
            "layer1": "CLAUDE.md",
        },
        "staleness_threshold_days": 14,
        "ignore_paths": ["node_modules/", ".git/", "dist/", ".venv/", "__pycache__/", "target/"],
    }

    if layer2:
        config["doc_hierarchy"]["layer2"] = layer2

    if env_domains:
        config["environment_domains"] = env_domains

    # Discovery metadata for agent to present
    config["_discovery"] = {
        "detected_type": project_type,
        "claude_md_count": len(claude_mds),
        "claude_md_files": claude_mds,
        "discovered_ips": sorted(discovered_ips) if discovered_ips else [],
        "env_table_parsed": "_unorganized" not in env_domains if env_domains else False,
        "memory_dir_exists": os.path.isdir(resolve_memory_dir(cwd)),
    }

    return config


# Environment table patterns for auto-parsing
_ENV_KEYWORDS = {"测试", "生产", "本地", "开发", "test", "prod", "production", "local", "dev", "staging"}
_TABLE_ROW = re.compile(r"\|\s*([^|]+?)\s*\|")


def _parse_env_table(filepath: str) -> dict:
    """Attempt to parse environment tables from a CLAUDE.md file.

    Handles multiple tables (e.g., server info table + Nacos table).
    Merges data by environment name across tables (same env gets IPs from
    one table, namespace from another).

    Returns dict of {env_name: {"ips": [...], "ports_prefix": "...", "namespace": "..."}}
    or empty dict if parsing fails.
    """
    domains = {}
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except (OSError, UnicodeDecodeError):
        return domains

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "|" in line and any(kw in line.lower() for kw in ["ip", "端口", "port", "环境", "命名空间", "namespace"]):
            if i + 1 < len(lines) and "---" in lines[i + 1]:
                j = i + 2
                while j < len(lines) and "|" in lines[j] and "---" not in lines[j]:
                    cells = [c.strip() for c in lines[j].split("|") if c.strip()]
                    if len(cells) >= 2:
                        env_name = None
                        ip_val = None
                        port_prefix = None
                        namespace_val = None

                        for cell in cells:
                            cell_clean = cell.strip('`').strip()
                            cell_lower = cell_clean.lower()
                            if cell_lower in _ENV_KEYWORDS or any(kw in cell_lower for kw in _ENV_KEYWORDS):
                                env_name = cell_clean
                            ip_match = _IP_PATTERN.search(cell)
                            if ip_match:
                                ip_val = ip_match.group(1)
                            port_match = re.search(r"(\d{2})xx", cell)
                            if port_match:
                                port_prefix = port_match.group(1)
                            # Namespace: only match if cell doesn't contain IP (avoid confusion)
                            if not ip_match:
                                ns_match = re.search(r"(vs-[\w-]+)", cell)
                                if ns_match:
                                    namespace_val = ns_match.group(1)

                        if env_name:
                            # MERGE into existing domain (don't overwrite)
                            if env_name not in domains:
                                domains[env_name] = {}
                            d = domains[env_name]
                            if ip_val:
                                d.setdefault("ips", [])
                                if ip_val not in d["ips"]:
                                    d["ips"].append(ip_val)
                            if port_prefix:
                                d["ports_prefix"] = port_prefix
                            if namespace_val:
                                d["namespace"] = namespace_val

                    j += 1
                i = j
                continue
        i += 1

    return domains


# ---------------------------------------------------------------------------
# Memory directory resolution (matches memory_health_check.sh:23-25 exactly)
# ---------------------------------------------------------------------------

def resolve_memory_dir(cwd: str) -> str:
    """Derive memory directory from cwd, using the same algorithm as
    memory_health_check.sh — replace : / \\ with -."""
    project_name = cwd.replace(":", "-").replace("/", "-").replace("\\", "-")
    home = os.path.expanduser("~")
    return os.path.join(home, ".claude", "projects", project_name, "memory")


# ---------------------------------------------------------------------------
# Project type detection (heuristic + user confirmation)
# ---------------------------------------------------------------------------

IGNORE_DIRS = {"node_modules", ".git", "dist", ".venv", "__pycache__", ".next", "target"}


def detect_project_type(cwd: str) -> tuple:
    """Heuristic project type detection.
    Returns (type_guess: str, claude_md_files: list[str]).
    The result is a SUGGESTION — must be confirmed by user before use.
    """
    claude_mds = []
    cwd_path = Path(cwd)
    # Scan max depth 2 for CLAUDE.md
    for depth in range(3):
        if depth == 0:
            candidates = [cwd_path / "CLAUDE.md"]
        else:
            candidates = list(cwd_path.glob("/".join(["*"] * depth) + "/CLAUDE.md"))
        for p in candidates:
            if p.exists() and not any(skip in str(p) for skip in IGNORE_DIRS):
                rel = str(p.relative_to(cwd_path)).replace("\\", "/")
                claude_mds.append(rel)

    if len(claude_mds) > 2:
        return "microservice", claude_mds
    elif len(claude_mds) == 2:
        return "monorepo", claude_mds
    else:
        return "standalone", claude_mds


# ---------------------------------------------------------------------------
# Memory Index Check
# ---------------------------------------------------------------------------

_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\(([^)]+\.md)\)")


def _parse_memory_index(memory_md_path: str) -> tuple:
    """Parse MEMORY.md, extract linked filenames and section structure.
    Returns (linked_files: set[str], sections: list[tuple[str, int]])
    where sections = [(section_title, line_number), ...]
    """
    linked_files = set()
    sections = []

    with open(memory_md_path, encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            # Section headers
            if line.startswith("## "):
                sections.append((line.strip().lstrip("# ").strip(), i))
            # Markdown links: [text](file.md)
            for match in _LINK_PATTERN.finditer(line):
                filename = match.group(2)
                # Normalize: strip ./ prefix
                if filename.startswith("./"):
                    filename = filename[2:]
                linked_files.add(filename)

    return linked_files, sections


def _guess_section(filename: str, frontmatter_type: str, sections: list) -> str:
    """Guess which MEMORY.md section a file belongs to based on naming/type."""
    prefix_map = {
        "feedback": "用户偏好",
        "keycloak": "Keycloak",
        "syncdata": "syncdata",
        "auth": "认证",
        "nacos": "Nacos",
        "prod": "部署",
        "deployment": "部署",
        "client": "客户端",
        "build": "构建",
        "env": "环境",
        "local": "环境",
        "service": "服务",
        "business": "业务",
        "editor": "生产问题",
        "ai-detection": "生产问题",
    }

    stem = Path(filename).stem.lower()
    section_names = [s[0] for s in sections]

    # Try prefix matching
    for prefix, keyword in prefix_map.items():
        if stem.startswith(prefix):
            # Find section containing keyword
            for name in section_names:
                if keyword in name:
                    return name
            break

    # Try frontmatter type
    type_section_map = {
        "feedback": "用户偏好",
        "user": "用户偏好",
        "project": "记忆文件",
        "reference": "记忆文件",
    }
    if frontmatter_type in type_section_map:
        keyword = type_section_map[frontmatter_type]
        for name in section_names:
            if keyword in name:
                return name

    # Default: last section or "记忆文件"
    for name in section_names:
        if "记忆" in name or "memory" in name.lower():
            return name
    return section_names[-1] if section_names else "记忆文件"


def _read_frontmatter_type(filepath: str) -> str:
    """Read the type field from YAML frontmatter."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read(2000)  # frontmatter is at top
    except (OSError, UnicodeDecodeError):
        return ""
    if not content.startswith("---"):
        return ""
    end = content.find("---", 3)
    if end == -1:
        return ""
    frontmatter = content[3:end]
    for line in frontmatter.split("\n"):
        if line.strip().startswith("type:"):
            return line.split(":", 1)[1].strip().strip("'\"")
    return ""


def memory_index_check(cwd: str) -> list:
    """Check MEMORY.md index completeness.
    Returns list of Finding objects.
    """
    findings = []
    memory_dir = resolve_memory_dir(cwd)

    if not os.path.isdir(memory_dir):
        return findings

    memory_md = os.path.join(memory_dir, "MEMORY.md")
    if not os.path.exists(memory_md):
        return findings

    # Get actual .md files (excluding MEMORY.md itself)
    actual_files = set()
    for f in os.listdir(memory_dir):
        if f.endswith(".md") and f != "MEMORY.md":
            actual_files.add(f)

    # Parse index
    linked_files, sections = _parse_memory_index(memory_md)

    # Sunken: exists on disk but not in index
    for f in sorted(actual_files - linked_files):
        fm_type = _read_frontmatter_type(os.path.join(memory_dir, f))
        section = _guess_section(f, fm_type, sections)
        findings.append(Finding(
            drift_type=DriftType.MEMORY_INDEX_SUNKEN,
            severity=Severity.WARNING,
            file=f"memory/{f}",
            detail=f"File exists but not indexed in MEMORY.md",
            fix_suggestion=f"Add to MEMORY.md section '{section}'",
            auto_fixable=False,  # semi-auto: needs user to confirm position
            section_hint=section,
        ))

    # Ghost: in index but not on disk
    for f in sorted(linked_files - actual_files):
        # Skip non-memory references (e.g., CLAUDE.md, docs/OVERVIEW.md)
        if "/" in f or not f.endswith(".md"):
            continue
        findings.append(Finding(
            drift_type=DriftType.MEMORY_INDEX_GHOST,
            severity=Severity.WARNING,
            file=f"MEMORY.md",
            detail=f"References '{f}' but file does not exist in memory directory",
            fix_suggestion=f"Remove ghost reference to '{f}' from MEMORY.md",
            auto_fixable=True,
        ))

    return findings


# ---------------------------------------------------------------------------
# Path Rot Check
# ---------------------------------------------------------------------------

_PATH_IN_BACKTICKS = re.compile(
    r"`((?:[\w./-]+/[\w./-]+|[\w.-]+\.(?:md|py|sh|js|ts|json|yml|yaml|sql|java|xml|toml|cfg)))`"
)
_PATH_IN_LINKS = re.compile(r"\[([^\]]*)\]\(([^)#]+)\)")

# Patterns that look like paths but aren't local repo files.
# Each rule documents a real doc authoring pattern that would otherwise
# false-positive as a local file reference.
_NOT_A_LOCAL_PATH = re.compile(r"""
    # Unix server absolute paths — appear in deployment/ops docs describing
    # server filesystems, not files tracked in this repo.
    # Examples: `/opt/app/bootstrap.yml`, `/var/log/nginx.log`, `/etc/hosts`.
    ^/(?:opt|etc|usr|var|apps?|home|tmp|mnt|proc|sys|dev)/ |

    # Legacy JBoss/WebSphere/containerized deployment layouts referenced
    # in runbooks. Shape: `/<appname>/{server,web,docker}_modules/...`.
    ^/\w+/server_modules/ |
    ^/\w+/web_modules/ |
    ^/\w+/docker_modules/ |

    # Markdown / prose placeholder ellipsis for truncated paths.
    # Example: `.../config/app.yml` in a narrative like "see .../app.yml".
    ^\.\.\./ |

    # Windows absolute paths. Authors use these when referencing local tools
    # or external machines, not repo-relative files.
    # Example: `C:/Users/hyc/.claude/plans/foo.md`.
    ^[A-Z]:/ |

    # Glob / wildcard patterns — intent is "files matching this shape",
    # not a specific file. Example: `src/**/*.py`, `tests/**/test_*.py`.
    /\*\*/ |

    # Git branch names that look path-like due to slashes. `devlop/` matches
    # the misspelled-but-real convention used in some projects; `origin/` is
    # a remote ref; bare `main`/`master` are default branch names.
    ^devlop/ |
    ^origin/ |
    ^main$ | ^master$ |

    # Boilerplate / template project references (not a file in this repo).
    # Example: "forked from `starter-kit-java`".
    ^starter-kit |

    # IANA timezone identifiers. Shape `Continent/City` collides with 2-segment
    # paths. Example: `Asia/Shanghai`, `America/New_York`, `Europe/London`.
    ^Asia/ | ^America/ | ^Europe/ |

    # SSH / scp target notation `user@host[:path]`. Appears in deployment
    # command examples. Example: `deploy@prod-01`.
    ^\w+@\w+
""", re.VERBOSE)


_GITHUB_ORG_REPO = re.compile(r"^[\w.-]+/[\w.-]+$")


def _is_local_repo_path(path_str: str) -> bool:
    """Filter out paths that are clearly not local repository file references."""
    if _NOT_A_LOCAL_PATH.search(path_str):
        return False
    # Must contain a dot (file extension) or end with / (directory)
    # Bare names like "deploy.sh" are ok, but "service/impl/" needs /
    # Skip if it's just a bare word without extension or slash
    has_extension = '.' in path_str.split('/')[-1]
    has_slash = '/' in path_str
    if not has_extension and not has_slash:
        return False
    # GitHub org/repo pattern: single slash, no extension in last segment.
    # e.g. "duanyytop/agents-radar" — but NOT "src/main.py" (last segment has extension)
    if has_slash and not has_extension and _GITHUB_ORG_REPO.match(path_str):
        return False
    return True


def _extract_paths_from_doc(filepath: str) -> list:
    """Extract file/dir paths mentioned in a markdown doc.
    Only extracts paths that look like local repository file references.
    Skips content inside fenced code blocks (``` ... ```).
    Returns list of (path_str, line_number).
    """
    paths = []
    in_code_block = False
    try:
        with open(filepath, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                # Track fenced code blocks
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    continue

                # Paths in backticks (inline code, not fenced blocks)
                for m in _PATH_IN_BACKTICKS.finditer(line):
                    candidate = m.group(1)
                    if candidate and not candidate.startswith("http") and _is_local_repo_path(candidate):
                        paths.append((candidate, i))
                # Paths in markdown links (not URLs)
                for m in _PATH_IN_LINKS.finditer(line):
                    href = m.group(2)
                    if href and not href.startswith("http") and not href.startswith("#") and _is_local_repo_path(href):
                        paths.append((href, i))
    except (OSError, UnicodeDecodeError):
        pass
    return paths


def path_rot_check(cwd: str, config: dict) -> list:
    """Check if file paths referenced in CLAUDE.md files actually exist.
    Only checks paths that look like local repo references (not server paths,
    branch names, timezone strings, etc.).
    Returns list of Finding objects.
    """
    findings = []
    ignore = config.get("ignore_paths", DEFAULT_CONFIG["ignore_paths"])

    # Collect all CLAUDE.md files to scan
    doc_files = []
    hierarchy = config.get("doc_hierarchy", {})
    layer1 = hierarchy.get("layer1")
    if layer1:
        doc_files.append(layer1)
    for f in hierarchy.get("layer2", []):
        doc_files.append(f)
    for f in hierarchy.get("docs", []):
        doc_files.append(f)

    for doc_rel in doc_files:
        doc_abs = os.path.join(cwd, doc_rel)
        if not os.path.exists(doc_abs):
            continue

        # For module CLAUDE.md, also resolve relative to module root
        doc_dir = os.path.dirname(doc_abs)
        module_root = doc_dir  # e.g., auto-submit-api/

        for path_str, line_no in _extract_paths_from_doc(doc_abs):
            # Skip ignored paths
            if any(ig in path_str for ig in ignore):
                continue

            # Try resolving relative to: doc location, module root, project root
            candidates = [
                os.path.join(doc_dir, path_str),
                os.path.join(cwd, path_str),
            ]
            # For module docs: also try relative to module root
            if doc_dir != cwd:
                candidates.append(os.path.join(module_root, path_str))

            # Claude Code runtime-resolved prefixes: memory/ lives in user-level
            # project memory dir, plans/ lives in ~/.claude/plans/
            if path_str.startswith("memory/"):
                candidates.append(
                    os.path.join(resolve_memory_dir(cwd), path_str[len("memory/"):])
                )
            if path_str.startswith("plans/"):
                candidates.append(
                    os.path.expanduser(f"~/.claude/plans/{path_str[len('plans/'):]}")
                )

            # For nested module paths (e.g., dw-modules-vstory/src/...):
            # try glob search within module root
            if doc_dir != cwd and "/" in path_str:
                leaf = path_str.split("/")[-1]
                for root_dir, dirs, files in os.walk(module_root):
                    # Limit depth to avoid deep scanning
                    depth = root_dir.replace(module_root, "").count(os.sep)
                    if depth > 4:
                        dirs.clear()
                        continue
                    if leaf in files or leaf in dirs:
                        candidates.append(os.path.join(root_dir, leaf))

            exists = any(os.path.exists(c) for c in candidates)

            if not exists:
                findings.append(Finding(
                    drift_type=DriftType.PATH_ROT,
                    severity=Severity.WARNING,
                    file=f"{doc_rel}:{line_no}",
                    detail=f"Referenced path `{path_str}` does not exist",
                    fix_suggestion="Remove reference or update to correct path",
                    auto_fixable=False,
                ))

    return findings


# ---------------------------------------------------------------------------
# Staleness Check (git timestamp)
# ---------------------------------------------------------------------------

def _git_last_modified(path: str) -> int:
    """Get last commit timestamp for a path via git log.
    Returns epoch seconds, or 0 if git not available or path not tracked.
    """
    import subprocess
    try:
        cwd = os.path.dirname(path) or "."
        if not os.path.isdir(cwd):
            return 0
        result = subprocess.run(
            ["git", "log", "-1", "--format=%at", "--", path],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError, OSError):
        pass
    return 0


def staleness_check(cwd: str, config: dict) -> list:
    """Check if CLAUDE.md files are stale relative to the code they document.

    For each CLAUDE.md, compares its last git commit time against the most recent
    commit in the directory it documents. If code is newer by more than
    staleness_threshold_days, reports as stale.

    Requires git. Silently skips if not a git repo.
    """
    import subprocess
    findings = []
    threshold_days = config.get("staleness_threshold_days", 14)
    threshold_secs = threshold_days * 86400
    hierarchy = config.get("doc_hierarchy", {})

    # Check if cwd is a git repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        if result.returncode != 0:
            return findings  # not a git repo
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return findings

    # Collect (doc_path, code_dir) pairs
    pairs = []

    # Root CLAUDE.md → entire project (but compare against top-level code changes only)
    root_doc = hierarchy.get("layer1", "CLAUDE.md")
    root_doc_abs = os.path.join(cwd, root_doc)
    if os.path.exists(root_doc_abs):
        pairs.append((root_doc, cwd))

    # Module CLAUDE.md → module directory
    for mod_doc in hierarchy.get("layer2", []):
        mod_doc_abs = os.path.join(cwd, mod_doc)
        if os.path.exists(mod_doc_abs):
            mod_dir = os.path.dirname(mod_doc_abs)
            pairs.append((mod_doc, mod_dir))

    for doc_rel, code_dir in pairs:
        doc_abs = os.path.join(cwd, doc_rel)
        doc_time = _git_last_modified(doc_abs)
        if doc_time == 0:
            continue  # not tracked by git

        # Most recent commit in code_dir. CLAUDE.md is included in `.` on
        # purpose: if CLAUDE.md is the newest file, `code_time == doc_time`
        # and `gap = 0` (no report, correct). If code is actually newer,
        # max() collapses to the real code commit and gap reflects real drift.
        # Excluding CLAUDE.md would be defensive but behaviourally equivalent.
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%at", "--", "."],
                capture_output=True, text=True, timeout=5, cwd=code_dir,
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            code_time = int(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
            continue

        gap = code_time - doc_time
        if gap > threshold_secs:
            gap_days = gap // 86400
            findings.append(Finding(
                drift_type=DriftType.STALENESS,
                severity=Severity.INFO if gap_days < threshold_days * 2 else Severity.WARNING,
                file=doc_rel,
                detail=f"CLAUDE.md is {gap_days} days behind code (threshold: {threshold_days}d)",
                fix_suggestion="Review and update CLAUDE.md to reflect recent code changes",
                auto_fixable=False,
            ))

    return findings


# ---------------------------------------------------------------------------
# Cross-Layer Contradiction + Config Value Drift
# ---------------------------------------------------------------------------

_IP_PATTERN = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
_PORT_PATTERN = re.compile(r"\b(9[0-9]{3})\b")  # 4-digit ports starting with 9 (common for services)


def _extract_ips_and_ports(filepath: str) -> tuple:
    """Extract all IPs and 4-digit ports from a doc file.
    Returns (ips: set[str], ports: set[str]).
    """
    ips = set()
    ports = set()
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                for m in _IP_PATTERN.finditer(line):
                    ip = m.group(1)
                    # Filter out version-like patterns (e.g., 3.6.5, 1.0.0)
                    parts = ip.split(".")
                    if all(0 <= int(p) <= 255 for p in parts) and int(parts[0]) > 0:
                        ips.add(ip)
                for m in _PORT_PATTERN.finditer(line):
                    ports.add(m.group(1))
    except (OSError, UnicodeDecodeError):
        pass
    return ips, ports


def cross_layer_check(cwd: str, config: dict) -> list:
    """Check for contradictions between root and module CLAUDE.md files.

    Uses environment_domains from config to determine which IPs/ports belong
    to which environment. Only flags contradictions WITHIN the same domain
    (e.g., two different "test" IPs). Cross-domain differences are expected.

    Also flags IPs in module docs that don't belong to ANY known domain.
    """
    findings = []
    hierarchy = config.get("doc_hierarchy", {})
    env_domains = config.get("environment_domains", {})

    if not env_domains:
        return findings  # can't check without domain definitions

    root_doc = hierarchy.get("layer1", "CLAUDE.md")
    root_abs = os.path.join(cwd, root_doc)
    if not os.path.exists(root_abs):
        return findings

    # Collect all known IPs across all domains
    known_ips = set()
    for domain_info in env_domains.values():
        known_ips.update(domain_info.get("ips", []))

    # Extract IPs from root doc (for reference)
    root_ips, root_ports = _extract_ips_and_ports(root_abs)

    # Check each module doc
    for mod_doc in hierarchy.get("layer2", []):
        mod_abs = os.path.join(cwd, mod_doc)
        if not os.path.exists(mod_abs):
            continue

        mod_ips, mod_ports = _extract_ips_and_ports(mod_abs)

        # Find IPs in module that are NOT in any known domain
        unknown_ips = mod_ips - known_ips - {"127.0.0.1", "0.0.0.0", "localhost"}
        # Also exclude IPs that are in the root doc (they might be documented consistently)
        truly_unknown = unknown_ips - root_ips

        for ip in sorted(truly_unknown):
            verify_steps = [
                f"1. Check actual running config: ssh to server, cat bootstrap.yml or .env for this module",
                f"2. If IP is current → add to doc-garden.json environment_domains",
                f"3. If IP is stale → update {mod_doc} to use the correct IP from root CLAUDE.md",
            ]
            findings.append(Finding(
                drift_type=DriftType.CROSS_LAYER_CONTRADICTION,
                severity=Severity.WARNING,
                file=mod_doc,
                detail=f"IP `{ip}` not in any configured environment domain and not in root CLAUDE.md",
                fix_suggestion=" → ".join(verify_steps),
                auto_fixable=False,
            ))

        # Port comparison: find ports in module not in root
        # Only compare 4-digit service ports (9xxx range)
        known_ports = set()
        for domain_info in env_domains.values():
            prefix = domain_info.get("ports_prefix", "")
            if prefix:
                # Generate expected ports from prefix (e.g., "97" → 9701-9709)
                for suffix in range(10):
                    known_ports.add(f"{prefix}0{suffix}")
        unknown_ports = mod_ports - root_ports - known_ports
        if unknown_ports:
            for port in sorted(unknown_ports):
                findings.append(Finding(
                    drift_type=DriftType.CROSS_LAYER_CONTRADICTION,
                    severity=Severity.INFO,
                    file=mod_doc,
                    detail=f"Port `{port}` in module doc but not in root CLAUDE.md or known port ranges",
                    fix_suggestion="Verify this port is current. If valid, add to root CLAUDE.md port table",
                    auto_fixable=False,
                ))

    return findings


def config_value_drift_check(cwd: str, config: dict) -> list:
    """Check if IPs/ports in CLAUDE.md match actual config files.

    Searches for known environment domain IPs in config files
    (bootstrap.yml, .env, docker-compose.yml, application.yml).
    Flags if a doc claims an IP but the config file uses a different one.
    """
    findings = []
    env_domains = config.get("environment_domains", {})
    if not env_domains:
        return findings

    # Find config files in the project
    config_patterns = [
        "**/bootstrap.yml", "**/application.yml", "**/docker-compose.yml",
        "**/.env", "**/.env.local", "**/.env.production",
    ]
    ignore = config.get("ignore_paths", DEFAULT_CONFIG["ignore_paths"])

    config_files = []
    cwd_path = Path(cwd)
    for pattern in config_patterns:
        for f in cwd_path.glob(pattern):
            f_str = str(f)
            if not any(ig in f_str for ig in ignore):
                config_files.append(f)

    if not config_files:
        return findings

    # Collect all known domain IPs
    all_known_ips = set()
    for domain_info in env_domains.values():
        all_known_ips.update(domain_info.get("ips", []))

    # Scan config files for IPs
    for cf in config_files:
        try:
            content = cf.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue

        file_ips = set(_IP_PATTERN.findall(content))
        # Find IPs in config files that are NOT in any known domain
        unknown_in_config = file_ips - all_known_ips - {"127.0.0.1", "0.0.0.0"}
        # Only flag if the config file also contains a known domain IP (so it's env-relevant)
        has_known = bool(file_ips & all_known_ips)

        if has_known and unknown_in_config:
            rel_path = str(cf.relative_to(cwd_path)).replace("\\", "/")
            for ip in sorted(unknown_in_config):
                findings.append(Finding(
                    drift_type=DriftType.CONFIG_VALUE_DRIFT,
                    severity=Severity.INFO,
                    file=rel_path,
                    detail=f"Config contains IP `{ip}` not in any environment domain",
                    fix_suggestion=f"1. Verify if `{ip}` is actively used (check running service) → 2. If valid, add to environment_domains → 3. If stale, update config file",
                    auto_fixable=False,
                ))

    return findings


# ---------------------------------------------------------------------------
# Structure Drift (filesystem is truth source)
# ---------------------------------------------------------------------------

def structure_drift_check(cwd: str, config: dict) -> list:
    """Check if CLAUDE.md's module list matches actual directories.

    Truth source: filesystem. CLAUDE.md is the claim.
    - Module in CLAUDE.md but directory doesn't exist → GHOST MODULE
    - Directory exists with code but no entry in CLAUDE.md module table → UNDOCUMENTED MODULE

    Only runs for microservice/monorepo projects with layer2 defined.
    """
    findings = []
    hierarchy = config.get("doc_hierarchy", {})
    layer2 = hierarchy.get("layer2")

    if layer2 is None:
        return findings  # standalone (key not in config), skip

    # Documented modules: extract directory names from layer2 paths
    # e.g., "auto-submit-api/CLAUDE.md" → "auto-submit-api"
    documented_modules = set()
    for doc_path in layer2:
        parts = doc_path.replace("\\", "/").split("/")
        if len(parts) >= 2:
            documented_modules.add(parts[0])

    # Actual directories in project root (potential modules)
    ignore = set(config.get("ignore_paths", DEFAULT_CONFIG["ignore_paths"]))
    ignore_dirs = {"node_modules", ".git", "dist", ".venv", "__pycache__", ".next",
                   "target", ".claude", ".github", ".idea", "docs", "scripts"}

    actual_dirs = set()
    try:
        for entry in os.scandir(cwd):
            if not entry.is_dir():
                continue
            name = entry.name
            if name.startswith(".") and name not in documented_modules:
                continue
            if name in ignore_dirs:
                continue
            # Heuristic: is this a "code module"? Must contain source files
            has_code = False
            try:
                for sub in os.scandir(entry.path):
                    if sub.name in ("src", "lib", "app", "pages", "components",
                                    "main.py", "index.ts", "index.js", "pom.xml",
                                    "package.json", "pyproject.toml", "Cargo.toml",
                                    "CLAUDE.md", "build.gradle"):
                        has_code = True
                        break
            except OSError:
                pass
            if has_code:
                actual_dirs.add(name)
    except OSError:
        return findings

    # Ghost modules: documented but directory doesn't exist
    for mod in sorted(documented_modules - actual_dirs):
        # Check if dir exists at all (it might exist but not be detected as "code module")
        mod_path = os.path.join(cwd, mod)
        if not os.path.isdir(mod_path):
            findings.append(Finding(
                drift_type=DriftType.STRUCTURE_DRIFT,
                severity=Severity.WARNING,
                file=f"{mod}/CLAUDE.md",
                detail=f"Module '{mod}' documented in config but directory does not exist",
                fix_suggestion=f"1. Verify: was '{mod}' renamed or removed? → 2. Update doc-garden.json layer2 list",
                auto_fixable=False,
            ))

    # Undocumented modules: exist but not in docs
    for mod in sorted(actual_dirs - documented_modules):
        findings.append(Finding(
            drift_type=DriftType.STRUCTURE_DRIFT,
            severity=Severity.INFO,
            file="CLAUDE.md (root)",
            detail=f"Directory '{mod}/' contains code but is not in documented module list",
            fix_suggestion=f"1. Check if '{mod}' is a real module → 2. If yes, add {mod}/CLAUDE.md to layer2 and create module CLAUDE.md",
            auto_fixable=False,
        ))

    return findings


# ---------------------------------------------------------------------------
# Run full audit
# ---------------------------------------------------------------------------

def run_audit(cwd: str, config: dict = None) -> list:
    """Run all applicable audit checks based on config.
    Returns list of Finding objects.
    """
    if config is None:
        config = load_config(cwd)

    findings = []

    # Memory index: always run
    findings += memory_index_check(cwd)

    # Path rot: always run
    findings += path_rot_check(cwd, config)

    # Cross-layer contradiction: only if layer2 + environment_domains defined
    if config.get("doc_hierarchy", {}).get("layer2") and config.get("environment_domains"):
        findings += cross_layer_check(cwd, config)

    # Config value drift: only if environment_domains defined
    if config.get("environment_domains"):
        findings += config_value_drift_check(cwd, config)

    # Structure drift: only if layer2 defined
    if config.get("doc_hierarchy", {}).get("layer2"):
        findings += structure_drift_check(cwd, config)

    # Staleness: always run
    findings += staleness_check(cwd, config)

    return findings


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------

def format_report(findings: list, project_name: str = "") -> str:
    """Format findings into a markdown report table."""
    if not findings:
        return f"## Documentation Audit Report\n\n**Project**: {project_name}\n\n No drift detected."

    by_type = {}
    for f in findings:
        by_type.setdefault(f.drift_type.value, []).append(f)

    lines = [
        f"## Documentation Audit Report\n",
        f"**Project**: {project_name}",
        f"**Drift found**: {len(findings)} issues\n",
    ]

    for dtype, items in by_type.items():
        lines.append(f"### {dtype} ({len(items)})\n")
        lines.append("| Severity | File | Issue | Fix |")
        lines.append("|----------|------|-------|-----|")
        for f in items:
            auto = " [auto-fixable]" if f.auto_fixable else ""
            lines.append(f"| {f.severity.value} | `{f.file}` | {f.detail} | {f.fix_suggestion}{auto} |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Normalize: skeleton definitions + checks
# ---------------------------------------------------------------------------

# Bilingual keyword aliases for section matching
# Each "required" entry can match any of its aliases
SECTION_ALIASES = {
    "技术栈": ["技术栈", "tech stack", "technology", "development environment", "开发环境"],
    "常用命令": ["常用命令", "commands", "common commands", "essential commands", "build and development", "running", "快速开始"],
    "架构概览": ["架构概览", "架构", "architecture", "overview", "project overview", "system architecture"],
    "注意事项": ["注意事项", "notes", "caveats", "traps", "踩坑", "gotchas"],
    "模块速查": ["模块速查", "module", "modules"],
    "分支策略": ["分支策略", "branch", "git"],
    "部署流程": ["部署流程", "deploy", "deployment", "发布"],
    "环境信息": ["环境信息", "environment", "server", "环境"],
    "踩坑记录": ["踩坑记录", "踩坑", "traps", "known issues", "troubleshooting"],
}

# Required/recommended sections per project type
SKELETONS = {
    "microservice": {
        "root": {
            "required": ["模块速查", "分支策略", "部署流程", "环境信息"],
            "recommended": ["踩坑记录"],
        },
        "module": {
            "required": ["技术栈", "常用命令"],
            "recommended": ["架构概览", "注意事项"],
        },
    },
    "monorepo": {
        "root": {
            "required": ["模块速查", "常用命令"],
            "recommended": ["分支策略", "部署流程"],
        },
        "module": {
            "required": ["技术栈", "常用命令"],
            "recommended": [],
        },
    },
    "standalone": {
        "root": {
            "required": ["技术栈", "常用命令"],
            "recommended": ["架构概览"],
        },
    },
}


def _extract_sections(filepath: str) -> list:
    """Extract ## section titles from a markdown file.
    Returns list of section title strings (without ## prefix).
    """
    sections = []
    try:
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                if line.startswith("## "):
                    title = line.strip().lstrip("# ").strip()
                    sections.append(title)
    except (OSError, UnicodeDecodeError):
        pass
    return sections


def _has_frontmatter(filepath: str) -> bool:
    """Check if a markdown file has YAML frontmatter (starts with ---)."""
    try:
        with open(filepath, encoding="utf-8") as f:
            first_line = f.readline().strip()
            return first_line == "---"
    except (OSError, UnicodeDecodeError):
        return False


def _section_contains_keyword(section_title: str, keyword: str) -> bool:
    """Fuzzy check if a section title matches a keyword or any of its aliases.
    Case-insensitive, partial match against all bilingual aliases."""
    title_lower = section_title.lower()
    # Check against all aliases for this keyword
    aliases = SECTION_ALIASES.get(keyword, [keyword])
    return any(alias.lower() in title_lower for alias in aliases)


@dataclass
class NormalizeItem:
    category: str          # 'missing_section' | 'missing_frontmatter' | 'sunken_index' | 'missing_doc'
    file: str              # which file
    detail: str            # what's wrong
    suggestion: str        # what to do
    auto_level: str        # 'auto' | 'semi-auto' | 'suggest'


def check_skeleton(cwd: str, config: dict) -> list:
    """Check if CLAUDE.md files have required sections per project type.
    Returns list of NormalizeItem.
    """
    items = []
    project_type = config.get("project_type", "standalone")
    skeleton = SKELETONS.get(project_type, SKELETONS["standalone"])
    hierarchy = config.get("doc_hierarchy", {})

    # Check root CLAUDE.md
    root_doc = hierarchy.get("layer1", "CLAUDE.md")
    root_path = os.path.join(cwd, root_doc)
    if os.path.exists(root_path):
        existing = _extract_sections(root_path)
        root_skel = skeleton.get("root", {})
        for section in root_skel.get("required", []):
            if not any(_section_contains_keyword(s, section) for s in existing):
                items.append(NormalizeItem(
                    category="missing_section",
                    file=root_doc,
                    detail=f"Missing required section: {section}",
                    suggestion=f"Add '## {section}' section",
                    auto_level="suggest",
                ))
    else:
        items.append(NormalizeItem(
            category="missing_doc",
            file=root_doc,
            detail="Root CLAUDE.md does not exist",
            suggestion="Generate skeleton CLAUDE.md with required sections",
            auto_level="suggest",
        ))

    # Check module CLAUDE.md files (microservice/monorepo only)
    module_skel = skeleton.get("module")
    if module_skel:
        for mod_doc in hierarchy.get("layer2", []):
            mod_path = os.path.join(cwd, mod_doc)
            if os.path.exists(mod_path):
                existing = _extract_sections(mod_path)
                for section in module_skel.get("required", []):
                    if not any(_section_contains_keyword(s, section) for s in existing):
                        items.append(NormalizeItem(
                            category="missing_section",
                            file=mod_doc,
                            detail=f"Missing required section: {section}",
                            suggestion=f"Add '## {section}' section",
                            auto_level="suggest",
                        ))
            else:
                items.append(NormalizeItem(
                    category="missing_doc",
                    file=mod_doc,
                    detail=f"Module CLAUDE.md does not exist",
                    suggestion="Generate skeleton with tech stack + commands",
                    auto_level="suggest",
                ))

    return items


def check_frontmatter(cwd: str) -> list:
    """Check if all memory files have YAML frontmatter.
    Returns list of NormalizeItem.
    """
    items = []
    memory_dir = resolve_memory_dir(cwd)
    if not os.path.isdir(memory_dir):
        return items

    for f in sorted(os.listdir(memory_dir)):
        if not f.endswith(".md") or f == "MEMORY.md":
            continue
        filepath = os.path.join(memory_dir, f)
        if not _has_frontmatter(filepath):
            items.append(NormalizeItem(
                category="missing_frontmatter",
                file=f"memory/{f}",
                detail="Missing YAML frontmatter (---)",
                suggestion="Add frontmatter with name, description, type fields",
                auto_level="semi-auto",
            ))

    return items


# English equivalents for skeleton section titles
_SECTION_EN = {
    "技术栈": "Tech Stack",
    "常用命令": "Common Commands",
    "架构概览": "Architecture Overview",
    "注意事项": "Notes & Caveats",
    "模块速查": "Module Quick Reference",
    "分支策略": "Branch Strategy",
    "部署流程": "Deployment",
    "环境信息": "Environment Info",
    "踩坑记录": "Known Issues",
}


def generate_root_skeleton(project_type: str, lang: str = "auto") -> str:
    """Generate a CLAUDE.md skeleton template.
    lang: 'zh' for Chinese, 'en' for English, 'auto' for bilingual (zh primary, en comment).
    """
    skeleton = SKELETONS.get(project_type, SKELETONS["standalone"])
    root = skeleton.get("root", {})
    lines = ["# Project Name\n"]

    for section in root.get("required", []):
        en = _SECTION_EN.get(section, section)
        if lang == "en":
            lines.append(f"## {en}\n")
        elif lang == "auto":
            lines.append(f"## {section}\n")
            lines.append(f"<!-- {en} — TODO: Fill in -->\n")
        else:
            lines.append(f"## {section}\n")
            lines.append(f"<!-- TODO: Fill in {section} -->\n")

    for section in root.get("recommended", []):
        en = _SECTION_EN.get(section, section)
        if lang == "en":
            lines.append(f"## {en}\n")
        elif lang == "auto":
            lines.append(f"## {section}\n")
            lines.append(f"<!-- {en} — Optional -->\n")
        else:
            lines.append(f"## {section}\n")
            lines.append(f"<!-- Optional: {section} -->\n")

    return "\n".join(lines)


def generate_module_skeleton(module_name: str, project_type: str, lang: str = "auto") -> str:
    """Generate a module CLAUDE.md skeleton."""
    skeleton = SKELETONS.get(project_type, SKELETONS["standalone"])
    module = skeleton.get("module", skeleton.get("root", {}))
    lines = [f"# {module_name}\n"]

    for section in module.get("required", []):
        en = _SECTION_EN.get(section, section)
        if lang == "en":
            lines.append(f"## {en}\n")
        elif lang == "auto":
            lines.append(f"## {section}\n")
            lines.append(f"<!-- {en} — TODO: Fill in -->\n")
        else:
            lines.append(f"## {section}\n")
            lines.append(f"<!-- TODO: Fill in {section} -->\n")

    for section in module.get("recommended", []):
        en = _SECTION_EN.get(section, section)
        if lang == "en":
            lines.append(f"## {en}\n")
        elif lang == "auto":
            lines.append(f"## {section}\n")
            lines.append(f"<!-- {en} — Optional -->\n")
        else:
            lines.append(f"## {section}\n")
            lines.append(f"<!-- Optional: {section} -->\n")

    return "\n".join(lines)


def run_normalize(cwd: str, config: dict = None) -> list:
    """Run all normalize checks. Returns list of NormalizeItem."""
    if config is None:
        config = load_config(cwd)

    items = []
    items += check_skeleton(cwd, config)
    items += check_frontmatter(cwd)

    # Also include sunken memory files as normalize items
    for finding in memory_index_check(cwd):
        if finding.drift_type == DriftType.MEMORY_INDEX_SUNKEN:
            items.append(NormalizeItem(
                category="sunken_index",
                file=finding.file,
                detail=finding.detail,
                suggestion=finding.fix_suggestion,
                auto_level="semi-auto",
            ))

    return items


def format_normalize_report(items: list, project_name: str = "") -> str:
    """Format normalize items into a readable report."""
    if not items:
        return f"## Normalize Report\n\n**Project**: {project_name}\n\nAll documentation follows target skeleton. No normalization needed."

    by_cat = {}
    for item in items:
        by_cat.setdefault(item.category, []).append(item)

    lines = [
        f"## Normalize Report\n",
        f"**Project**: {project_name}",
        f"**Issues**: {len(items)}\n",
    ]

    cat_labels = {
        "missing_doc": "Missing Documentation Files",
        "missing_section": "Missing Required Sections",
        "missing_frontmatter": "Missing Frontmatter",
        "sunken_index": "Unindexed Memory Files",
    }

    for cat, cat_items in by_cat.items():
        label = cat_labels.get(cat, cat)
        lines.append(f"### {label} ({len(cat_items)})\n")
        lines.append("| File | Issue | Suggestion | Level |")
        lines.append("|------|-------|------------|-------|")
        for item in cat_items:
            lines.append(f"| `{item.file}` | {item.detail} | {item.suggestion} | {item.auto_level} |")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fix mode: apply auto-fixable changes
# ---------------------------------------------------------------------------

def apply_auto_fix(cwd: str, findings: list) -> list:
    """Apply auto-fixable changes. Currently supports:
    - GHOST refs: remove lines from MEMORY.md that reference non-existent files

    Returns list of actions taken (strings).
    """
    actions = []
    memory_dir = resolve_memory_dir(cwd)
    memory_md = os.path.join(memory_dir, "MEMORY.md")

    # Collect ghost filenames to remove
    ghost_files = set()
    for f in findings:
        if f.drift_type == DriftType.MEMORY_INDEX_GHOST and f.auto_fixable:
            match = re.search(r"'([^']+\.md)'", f.detail)
            if match:
                ghost_files.add(match.group(1))

    if ghost_files and os.path.exists(memory_md):
        with open(memory_md, encoding="utf-8") as fh:
            original_lines = fh.readlines()

        new_lines = []
        removed = []
        for line in original_lines:
            skip = False
            for ghost in ghost_files:
                if ghost in line and _LINK_PATTERN.search(line):
                    skip = True
                    removed.append(ghost)
                    break
            if not skip:
                new_lines.append(line)

        if removed:
            with open(memory_md, "w", encoding="utf-8") as fh:
                fh.writelines(new_lines)
            for r in removed:
                actions.append(f"Removed ghost reference '{r}' from MEMORY.md")

    return actions


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def validate_config(config: dict) -> list:
    """Validate a config dict. Returns list of error strings. Empty = valid."""
    errors = []

    internal_keys = [k for k in config if k.startswith("_")]
    if internal_keys:
        errors.append(f"Internal keys should be removed before saving: {internal_keys}")

    if "project_type" not in config:
        errors.append("Missing required field: project_type")
    if "doc_hierarchy" not in config:
        errors.append("Missing required field: doc_hierarchy")
    elif "layer1" not in config.get("doc_hierarchy", {}):
        errors.append("Missing required field: doc_hierarchy.layer1")

    env = config.get("environment_domains", {})
    if "_unorganized" in env:
        errors.append("environment_domains still has '_unorganized' — IPs need to be organized into named domains")

    return errors


# ---------------------------------------------------------------------------
# Transcript parsing (shared by Stop hook)
# ---------------------------------------------------------------------------

def extract_modified_files_from_transcript(transcript_path: str) -> set:
    """Extract file paths modified by Write/Edit in a session transcript.

    Transcript is JSONL, each line: {message: {role, content: [{type, name, input}]}}
    Only extracts Write/Edit tool_use entries, NOT Read.
    """
    modified = set()
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                message = entry.get("message")
                if not isinstance(message, dict):
                    continue
                if message.get("role") != "assistant":
                    continue
                for item in message.get("content", []):
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") != "tool_use":
                        continue
                    if item.get("name") not in ("Write", "Edit"):
                        continue
                    fp = (item.get("input") or {}).get("file_path", "")
                    if fp:
                        modified.add(fp)
    except (OSError, IOError):
        pass
    return modified


def resolve_module_from_path(file_path: str, cwd: str) -> str:
    """Given a file path and project root, return the module directory name.
    e.g., 'D:/work/project/api-module/src/Main.java' → 'api-module'
    Returns '' if file is in project root.
    """
    try:
        rel = os.path.relpath(file_path, cwd).replace("\\", "/")
    except ValueError:
        return ""
    parts = rel.split("/")
    return parts[0] if len(parts) > 1 else ""
