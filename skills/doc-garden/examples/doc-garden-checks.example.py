"""
Example custom checks for doc-garden.

Copy this file to `<your-project>/.claude/doc-garden-checks.py` and adapt
the check functions to your project's domain-specific drift patterns.

=============================================================================
CONTRACT
=============================================================================

1. Expose a top-level function `run_custom_checks(cwd, config) -> list[Finding]`.
   The doc-garden audit runner loads this file, calls this function, and
   concatenates its return value into the global findings list.

2. IMPORT STRICTLY FROM `core.doc_garden_core` (the line below, verbatim).
   The runner uses `isinstance(item, Finding)` to validate return values.
   Python's isinstance is module-identity-sensitive: if your check imports
   Finding via a sys.path hack (`import doc_garden_core as dg; dg.Finding`)
   it becomes a DIFFERENT class object and the runner will reject every
   finding you produce, converting each into a CUSTOM_CHECK_ERROR.

   The runner adds the skill's parent directory to sys.path via
   `spec_from_file_location`, so the `from core.doc_garden_core import ...`
   form resolves the same module identity the runner itself uses.

3. Failure isolation: if this file raises on import, crashes during the
   check, returns a non-list, or returns list items that aren't Finding
   instances, the runner catches everything and emits CUSTOM_CHECK_ERROR
   findings. The rest of the audit completes normally. You do not need
   defensive try/except inside check functions — but if you want to
   distinguish "check ran, found nothing" from "check crashed", return
   an empty list on handled failures.

=============================================================================
WHAT BELONGS HERE
=============================================================================

Use custom checks for DOMAIN-SPECIFIC CONTENT DRIFT that the built-in
audit cannot detect:

  ✓ "Memory X claims Daily Schedule is 135 min, but CLAUDE.md v4 says 165-195"
  ✓ "Module A's Python version declaration differs from root AGENTS.md"
  ✓ "project_plan.md says Primary target is X, but root doc says Y"

Do NOT put these here:

  ✗ Path existence checks — use the built-in PATH_ROT + path_resolvers
  ✗ Memory index completeness — use the built-in MEMORY_INDEX_{SUNKEN,GHOST}
  ✗ Broad "is this file stale" rules — use staleness_check
  ✗ Anything that could reasonably live in skill-level config

The skill's generic checks are the foundation; custom checks are the
project-shaped tail.
"""

from core.doc_garden_core import Finding, DriftType, Severity


def run_custom_checks(cwd: str, config: dict) -> list:
    """Dispatch to each domain-specific check and aggregate findings.

    Keep this function boring: it's a router. Put real logic in per-check
    functions below so each is individually testable.
    """
    findings = []
    findings += check_example_cross_file_consistency(cwd, config)
    return findings


# ---------------------------------------------------------------------------
# Example check: demonstrate the Finding construction pattern
# ---------------------------------------------------------------------------

def check_example_cross_file_consistency(cwd: str, config: dict) -> list:
    """Template for a CONTENT_DRIFT check.

    Pattern:
      1. Read two or more files that SHOULD agree on some fact
      2. Extract the claim from each (regex, markdown parser, whatever)
      3. If they disagree, emit a Finding with drift_type=CONTENT_DRIFT

    The example below is a no-op — replace the body with your actual
    extraction + comparison.
    """
    import os
    findings = []

    # --- Step 1: define which files to compare ---
    # claude_md = os.path.join(cwd, "CLAUDE.md")
    # memory_file = os.path.join(resolve_memory_dir(cwd), "project_plan.md")

    # --- Step 2: extract claims (replace with real parsing) ---
    # claude_claim = _extract_field(claude_md, "Primary target")
    # memory_claim = _extract_field(memory_file, "Primary target")

    # --- Step 3: compare and emit ---
    # if claude_claim and memory_claim and claude_claim != memory_claim:
    #     findings.append(Finding(
    #         drift_type=DriftType.CONTENT_DRIFT,
    #         severity=Severity.WARNING,
    #         file="memory/project_plan.md",       # where the fix should land
    #         detail=(f"'Primary target' differs: CLAUDE.md says {claude_claim!r}, "
    #                 f"memory/project_plan.md says {memory_claim!r}"),
    #         fix_suggestion="Refresh project_plan.md to match CLAUDE.md, which is the canonical source",
    #     ))

    return findings


# ---------------------------------------------------------------------------
# Notes for agents writing new checks
# ---------------------------------------------------------------------------
# Finding fields (from core.doc_garden_core):
#
#   drift_type      : DriftType enum  (use CONTENT_DRIFT for cross-file semantic mismatch)
#   severity        : Severity enum   (WARNING for drift, INFO for soft hints, CRITICAL rare)
#   file            : str             (path to the file the human should open to fix)
#   detail          : str             (one-line description of what's wrong)
#   fix_suggestion  : str             (optional; one-line instruction for the fix)
#   auto_fixable    : bool            (default False; custom checks rarely set True)
#   section_hint    : str             (default ""; reserved for memory index normalizer)
#
# Severity choice:
#   CRITICAL : config schema is broken, file is unparseable, invariant violated
#   WARNING  : drift the user should resolve in next doc-audit cycle
#   INFO     : informational signal, user may choose to ignore
#
# Keep `detail` under 200 chars so it renders well in the report table.
