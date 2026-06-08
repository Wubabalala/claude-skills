#!/usr/bin/env python3
"""Evaluate the onboarding -> review -> doc-garden lifecycle.

The harness is intentionally mechanical: it does not use an LLM and does not
judge semantic equivalence. It measures drift density, documentation structure,
truth-source coverage, and review lifecycle readiness.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_GARDEN_ROOT = REPO_ROOT / "skills" / "doc-garden"
sys.path.insert(0, str(DOC_GARDEN_ROOT))

try:
    from core.doc_garden_core import (  # type: ignore
        DriftType,
        collect_doc_files,
        load_config,
        run_audit,
        run_normalize,
    )
except Exception as exc:  # pragma: no cover - exercised by CLI failure path
    print(
        f"Failed to import doc-garden core from {DOC_GARDEN_ROOT}: {exc}",
        file=sys.stderr,
    )
    sys.exit(2)


SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cs",
    ".go",
    ".h",
    ".hpp",
    ".java",
    ".js",
    ".jsx",
    ".kt",
    ".mjs",
    ".py",
    ".rs",
    ".svelte",
    ".ts",
    ".tsx",
    ".vue",
}

IGNORE_DIRS = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "target",
}


def parse_project_arg(raw: str) -> tuple[str, Path]:
    if "=" not in raw:
        raise ValueError(f"--project must be name=path, got: {raw}")
    name, path = raw.split("=", 1)
    name = name.strip()
    if not name:
        raise ValueError(f"--project name is empty: {raw}")
    resolved = Path(path).expanduser().resolve()
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"Project path not found or not a directory: {resolved}")
    return name, resolved


def count_source_files(project: Path) -> int:
    count = 0
    for path in project.rglob("*"):
        if any(part in IGNORE_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in SOURCE_EXTENSIONS:
            count += 1
    return count


def existing_doc_files(project: Path, config: dict[str, Any]) -> list[str]:
    docs = []
    for rel in collect_doc_files(str(project), config):
        if (project / rel).is_file():
            docs.append(rel)
    return docs


def density_score(max_score: float, count: int, denominator: int, severe_at: float) -> float:
    density = count / max(denominator, 1)
    penalty = min(1.0, density / severe_at)
    return round(max_score * (1.0 - penalty), 2)


def redact_text(text: str, drop_credential_lines: bool = True) -> str:
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "<IP>", text)
    text = re.sub(r"[A-Za-z]:[\\/][^\s|`\"',)}\]]+", "<ABS_PATH>", text)
    text = re.sub(r"(?<!\w)/(?:Users|home|var|opt|etc|tmp)/[^\s|`\"',)}\]]+", "<ABS_PATH>", text)
    text = re.sub(
        r"(?i)(key|token|password|secret)(\s*[:=]\s*)([^\s,;|`]+)",
        r"\1\2<REDACTED>",
        text,
    )
    redacted_lines = []
    for line in text.splitlines():
        if drop_credential_lines and re.search(r"(?i)(credential|credentials|secret|token|password).*\.txt", line):
            redacted_lines.append("<REDACTED_CREDENTIAL_LINE>")
        else:
            redacted_lines.append(line)
    return "\n".join(redacted_lines)


def parse_review_checklist(project: Path) -> dict[str, Any]:
    checklist = project / ".claude" / "review-checklist.md"
    result: dict[str, Any] = {
        "exists": checklist.exists(),
        "item_count": 0,
        "source_count": 0,
        "missing_source_count": 0,
        "legacy_without_source_count": 0,
        "warnings": [],
    }
    if not checklist.exists():
        return result

    text = checklist.read_text(encoding="utf-8", errors="ignore")
    items = [line for line in text.splitlines() if line.lstrip().startswith("- [")]
    result["item_count"] = len(items)
    source_re = re.compile(r"source:\s*`?([^()`\n]+?)`?(?:\)|$)", re.IGNORECASE)
    for item in items:
        match = source_re.search(item)
        if not match:
            result["legacy_without_source_count"] += 1
            continue
        source = match.group(1).strip().split("#", 1)[0].strip()
        if not source:
            result["legacy_without_source_count"] += 1
            continue
        result["source_count"] += 1
        if not (project / source).exists():
            result["missing_source_count"] += 1
    if result["legacy_without_source_count"]:
        result["warnings"].append("legacy checklist items without source were skipped for traceability")
    return result


def evaluate_project(name: str, project: Path) -> dict[str, Any]:
    config = load_config(str(project))
    findings = run_audit(str(project), config)
    normalize_items = run_normalize(str(project), config)
    docs = existing_doc_files(project, config)
    source_count = count_source_files(project)
    review = parse_review_checklist(project)

    by_drift: dict[str, int] = {}
    for finding in findings:
        by_drift[finding.drift_type.value] = by_drift.get(finding.drift_type.value, 0) + 1

    normalize_by_category: dict[str, int] = {}
    for item in normalize_items:
        normalize_by_category[item.category] = normalize_by_category.get(item.category, 0) + 1

    scanned_doc_count = len(docs)
    total_findings = len(findings) + len(normalize_items)

    path_rot = by_drift.get(DriftType.PATH_ROT.value, 0)
    fact_conflict = by_drift.get(DriftType.FACT_VALUE_CONFLICT.value, 0)
    staleness = by_drift.get(DriftType.STALENESS.value, 0)
    entity = by_drift.get(DriftType.ENTITY_COVERAGE.value, 0)
    convention = (
        normalize_by_category.get("missing_doc", 0)
        + normalize_by_category.get("missing_section", 0)
        + normalize_by_category.get("missing_frontmatter", 0)
        + normalize_by_category.get("sunken_index", 0)
    )

    drift_score = sum(
        [
            density_score(12, path_rot, scanned_doc_count, 1.0),
            density_score(12, fact_conflict, scanned_doc_count, 0.5),
            density_score(14, convention, scanned_doc_count, 1.0),
            density_score(8, staleness, scanned_doc_count, 0.5),
            density_score(10, entity, max(source_count, 1), 0.05),
            4.0 if total_findings <= max(scanned_doc_count, 1) * 2 else 0.0,
        ]
    )

    level = config.get("doc_system_level", "standard")
    has_truth_index = (project / "docs" / "TRUTH_SOURCES.md").exists()
    has_truth_files = bool(list((project / "docs" / "references").glob("*-truth-source.md")))
    has_refs = (project / "docs" / "references").is_dir()
    has_quick_ref = (project / "docs" / "QUICK_REFERENCE.md").exists()
    has_agents = (project / "AGENTS.md").exists()
    convergence_score = 0.0
    convergence_score += 5 if level in ("simple", "standard") else 0
    convergence_score += 5 if has_truth_index else 0
    convergence_score += 5 if has_truth_files else 0
    convergence_score += 4 if has_refs else 0
    convergence_score += 3 if has_quick_ref else 0
    convergence_score += 3 if has_agents else 0

    review_score = 0.0
    review_score += 4 if review["exists"] else 0
    review_score += 3 if 15 <= review["item_count"] <= 30 else 0
    review_score += 3 if review["source_count"] and review["missing_source_count"] == 0 else 0
    review_score += 2 if review["legacy_without_source_count"] == 0 else 0
    review_score += 2 if ((project / "docs" / "architecture-traps.md").exists() and (has_truth_index or has_truth_files)) else 0
    review_score += 1 if (level == "standard" and review["exists"]) else 0

    score = round(drift_score + convergence_score + review_score, 2)

    return {
        "name": name,
        "path": str(project),
        "project_type": config.get("project_type"),
        "doc_system_level": level,
        "score": score,
        "scores": {
            "drift_resistance": round(drift_score, 2),
            "architecture_convergence": round(convergence_score, 2),
            "review_lifecycle_readiness": round(review_score, 2),
        },
        "counts": {
            "audit_findings": len(findings),
            "normalize_items": len(normalize_items),
            "scanned_doc_count": scanned_doc_count,
            "source_file_count": source_count,
        },
        "density": {
            "findings_per_doc": round(total_findings / max(scanned_doc_count, 1), 4),
            "findings_per_100_source": round(total_findings / max(source_count, 1) * 100, 4),
        },
        "drift_types": by_drift,
        "normalize_categories": normalize_by_category,
        "architecture_signals": {
            "has_truth_sources_index": has_truth_index,
            "has_domain_truth_sources": has_truth_files,
            "has_references_dir": has_refs,
            "has_quick_reference": has_quick_ref,
            "has_agents": has_agents,
        },
        "review_lifecycle": review,
        "efficiency_proxy": {
            "entrypoint_coverage": 1 if has_agents and (project / "docs" / "OVERVIEW.md").exists() else 0,
            "reference_coverage": 1 if has_refs else 0,
            "truth_source_coverage": 1 if has_truth_index and has_truth_files else 0,
            "review_rule_coverage": review["source_count"],
            "task_routing_coverage": 1 if has_agents else 0,
        },
    }


def format_markdown(results: list[dict[str, Any]], public_redact: bool) -> str:
    lines = [
        "# Skill Lifecycle Eval Report",
        "",
        "| Project | Score | Drift | Architecture | Review | Findings/Doc | Findings/100 Source | Level |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in results:
        lines.append(
            "| {name} | {score:.2f} | {drift:.2f} | {arch:.2f} | {review:.2f} | {per_doc:.4f} | {per_src:.4f} | {level} |".format(
                name=item["name"],
                score=item["score"],
                drift=item["scores"]["drift_resistance"],
                arch=item["scores"]["architecture_convergence"],
                review=item["scores"]["review_lifecycle_readiness"],
                per_doc=item["density"]["findings_per_doc"],
                per_src=item["density"]["findings_per_100_source"],
                level=item["doc_system_level"],
            )
        )
    lines.append("")
    lines.append("## Details")
    for item in results:
        lines.extend(
            [
                "",
                f"### {item['name']}",
                "",
                f"- Path: `{item['path']}`",
                f"- Project type: `{item['project_type']}`",
                f"- Doc system level: `{item['doc_system_level']}`",
                f"- Audit findings: {item['counts']['audit_findings']}",
                f"- Normalize items: {item['counts']['normalize_items']}",
                f"- Review checklist exists: {item['review_lifecycle']['exists']}",
                f"- Review checklist items: {item['review_lifecycle']['item_count']}",
                f"- Missing checklist sources: {item['review_lifecycle']['missing_source_count']}",
                f"- Legacy checklist warnings: {item['review_lifecycle']['legacy_without_source_count']}",
            ]
        )
    text = "\n".join(lines) + "\n"
    return redact_text(text) if public_redact else text


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", action="append", required=True, help="Project in name=path form")
    parser.add_argument("--json", required=True, help="Output JSON path")
    parser.add_argument("--md", required=True, help="Output Markdown path")
    parser.add_argument("--public-redact", action="store_true", help="Redact public report fields")
    args = parser.parse_args(argv)

    results = []
    for raw in args.project:
        name, path = parse_project_arg(raw)
        results.append(evaluate_project(name, path))

    payload: dict[str, Any] = {
        "version": 1,
        "scoring": {
            "drift_resistance": 60,
            "architecture_convergence": 25,
            "review_lifecycle_readiness": 15,
        },
        "projects": results,
    }

    json_path = Path(args.json).expanduser().resolve()
    md_path = Path(args.md).expanduser().resolve()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.public_redact:
        json_text = redact_text(json_text, drop_credential_lines=False)
    json_path.write_text(json_text + "\n", encoding="utf-8")
    md_path.write_text(format_markdown(results, args.public_redact), encoding="utf-8")
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
