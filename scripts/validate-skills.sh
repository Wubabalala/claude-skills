#!/usr/bin/env bash
# Skill structure validator for claude-skills repo.
# Usage:
#   bash scripts/validate-skills.sh          # validate skills/
#   bash scripts/validate-skills.sh --test   # validate test-fixtures/ (self-test)

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if [[ "${1:-}" == "--test" ]]; then
    SKILLS_DIR="$SCRIPT_DIR/test-fixtures"
else
    SKILLS_DIR="$REPO_ROOT/skills"
fi

PASS=0
WARN=0
FAIL=0

check_skill() {
    local dir="$1"
    local name
    name="$(basename "$dir")"
    local skill_file="$dir/SKILL.md"
    local errors=()
    local warnings=()

    # --- 1. SKILL.md must exist ---
    if [[ ! -f "$skill_file" ]]; then
        echo "✗ $name: missing SKILL.md"
        ((FAIL++))
        return
    fi

    # --- 2. Frontmatter: must have --- block with name: and description: ---
    local in_frontmatter=false
    local frontmatter_found=false
    local has_name=false
    local has_description=false
    local description_style=""  # "single", "folded", or ""
    local description_value=""
    local reading_folded=false
    local body_started=false
    local body_words=0
    local frontmatter_end_count=0

    while IFS= read -r line || [[ -n "$line" ]]; do
        line="${line%$'\r'}"  # Strip trailing CR for CRLF files
        if [[ "$body_started" == true ]]; then
            # Count body words (after frontmatter)
            local wc
            wc=$(echo "$line" | wc -w | tr -d ' ')
            body_words=$((body_words + wc))
            continue
        fi

        # Frontmatter parsing
        if [[ "$line" == "---" ]]; then
            frontmatter_end_count=$((frontmatter_end_count + 1))
            if [[ $frontmatter_end_count -eq 1 ]]; then
                in_frontmatter=true
                frontmatter_found=true
                continue
            elif [[ $frontmatter_end_count -eq 2 ]]; then
                in_frontmatter=false
                reading_folded=false
                body_started=true
                continue
            fi
        fi

        if [[ "$in_frontmatter" == true ]]; then
            # Check for name:
            if [[ "$line" =~ ^name: ]]; then
                has_name=true
            fi

            # Folded description continuation lines
            if [[ "$reading_folded" == true ]]; then
                if [[ "$line" =~ ^[[:space:]]{2,} ]]; then
                    description_value="$description_value $(echo "$line" | sed 's/^[[:space:]]*//')"
                    continue
                else
                    reading_folded=false
                fi
            fi

            # Check for description:
            if [[ "$line" =~ ^description: ]]; then
                has_description=true
                local after_key
                after_key="$(echo "$line" | sed 's/^description:[[:space:]]*//')"
                if [[ "$after_key" == ">" || "$after_key" == "|" ]]; then
                    description_style="folded"
                    reading_folded=true
                    description_value=""
                elif [[ -n "$after_key" ]]; then
                    description_style="single"
                    description_value="$after_key"
                fi
            fi
        fi
    done < "$skill_file"

    if [[ "$frontmatter_found" == false ]]; then
        errors+=("missing --- frontmatter block")
    fi
    if [[ "$has_name" == false ]]; then
        errors+=("missing name: in frontmatter")
    fi
    if [[ "$has_description" == false ]]; then
        errors+=("missing description: in frontmatter")
    fi

    # --- 3. Description length ≤ 500 chars ---
    if [[ "$has_description" == true ]]; then
        description_value="$(echo "$description_value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        local desc_len=${#description_value}
        if [[ -z "$description_value" && "$description_style" == "" ]]; then
            warnings+=("unable to parse description length")
        elif [[ $desc_len -gt 500 ]]; then
            errors+=("description too long: $desc_len chars (max 500)")
        fi
    fi

    # --- 4/5. Body word count ---
    if [[ $body_words -gt 3000 ]]; then
        errors+=("body $body_words words (error: >3000, target ≤2500)")
    elif [[ $body_words -gt 2500 ]]; then
        warnings+=("body $body_words words (warning: >2500, target ≤2500)")
    fi

    # --- 6. References cross-validation ---
    local ref_dir="$dir/references"
    local ref_info=""
    if [[ -d "$ref_dir" ]]; then
        local ref_files=()
        local orphans=()
        local referenced=0
        local total_refs=0

        for ref in "$ref_dir"/*.md; do
            [[ -f "$ref" ]] || continue
            local ref_name
            ref_name="$(basename "$ref")"
            ref_files+=("$ref_name")
            total_refs=$((total_refs + 1))

            # Check if SKILL.md mentions this filename
            if grep -q "$ref_name" "$skill_file" 2>/dev/null; then
                referenced=$((referenced + 1))
            else
                orphans+=("$ref_name")
            fi
        done

        if [[ $total_refs -gt 0 && $referenced -eq 0 ]]; then
            errors+=("references/ exists but SKILL.md references none of them")
        fi

        # Check for dead links: filenames mentioned in SKILL.md but not in references/
        while IFS= read -r mentioned; do
            local found=false
            for ref_name in "${ref_files[@]}"; do
                if [[ "$ref_name" == "$mentioned" ]]; then
                    found=true
                    break
                fi
            done
            if [[ "$found" == false ]]; then
                errors+=("dead reference: $mentioned mentioned in SKILL.md but not found in references/")
            fi
        done < <(grep -oE 'references/[a-zA-Z0-9_-]+\.md' "$skill_file" 2>/dev/null | sed 's|references/||' | sort -u)

        for orphan in "${orphans[@]}"; do
            warnings+=("orphan reference: $orphan never mentioned in SKILL.md")
        done

        ref_info=", $total_refs references (${#orphans[@]} orphans)"
    fi

    # --- Output ---
    if [[ ${#errors[@]} -gt 0 ]]; then
        echo "✗ $name: ${errors[*]}"
        ((FAIL++))
    elif [[ ${#warnings[@]} -gt 0 ]]; then
        echo "⚠ $name: ${warnings[*]} | ${body_words} words${ref_info}"
        ((WARN++))
    else
        echo "✓ $name: structure OK, frontmatter OK, ${body_words} words${ref_info}"
        ((PASS++))
    fi
}

# --- Main ---
echo "Validating skills in: $SKILLS_DIR"
echo "---"

for skill_dir in "$SKILLS_DIR"/*/; do
    [[ -d "$skill_dir" ]] || continue
    check_skill "$skill_dir"
done

echo "---"
echo "Results: $PASS passed, $WARN warnings, $FAIL errors"

if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
