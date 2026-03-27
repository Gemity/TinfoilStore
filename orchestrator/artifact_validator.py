"""Artifact validation: check metadata, required sections, cross-consistency.

Maps to design section 'artifact_validator' and runtime spec section 11.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

from orchestrator.models import (
    ArtifactMetadata,
    ArtifactType,
    ImplementationMode,
    ImplementationResult,
    Phase,
    Producer,
    ReviewArtifact,
    ValidationResult,
)
from orchestrator.artifact_parser import (
    extract_markdown_sections,
    parse_markdown_frontmatter,
    parse_review_json,
)
from orchestrator.models import WorkflowState


# --- Required sections per artifact type (from spec sections 6.1-6.5) ---

DESIGN_REQUIRED_SECTIONS = [
    "Objective", "Scope", "Constraints", "Architecture",
    "Execution Plan", "Acceptance Criteria", "Non-Goals",
]

IMPLEMENTATION_REPORT_REQUIRED_SECTIONS = [
    "Summary", "Files Changed", "Tests Run", "Known Risks", "Amendment Requests",
]

REVIEW_MD_REQUIRED_SECTIONS = [
    "Verdict", "Critical Issues", "Minor Issues",
    "Amendment Decisions", "Notes For Next Iteration",
]


# --- Metadata validation ---

def validate_artifact_metadata(
    metadata: ArtifactMetadata,
    state: WorkflowState,
    expected_type: ArtifactType,
    expected_producer: Producer,
) -> ValidationResult:
    """Check run_id, iteration, phase, phase_attempt, producer match current state."""
    errors = []

    if metadata.run_id != state.run_id:
        errors.append(f"run_id mismatch: artifact={metadata.run_id}, state={state.run_id}")

    if metadata.iteration != state.iteration:
        errors.append(f"iteration mismatch: artifact={metadata.iteration}, state={state.iteration}")

    if metadata.phase != state.phase:
        errors.append(f"phase mismatch: artifact={metadata.phase}, state={state.phase}")

    if metadata.phase_attempt != state.phase_attempt:
        errors.append(f"phase_attempt mismatch: artifact={metadata.phase_attempt}, state={state.phase_attempt}")

    if metadata.artifact_type != expected_type.value:
        errors.append(f"artifact_type mismatch: artifact={metadata.artifact_type}, expected={expected_type.value}")

    if metadata.producer != expected_producer.value:
        errors.append(f"producer mismatch: artifact={metadata.producer}, expected={expected_producer.value}")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# --- Input fingerprint validation ---

def validate_input_fingerprint(
    metadata: ArtifactMetadata,
    state: WorkflowState,
) -> ValidationResult:
    """Check that artifact input_fingerprint matches current_inputs in state."""
    fp = metadata.extra.get("input_fingerprint")
    if fp is None or not isinstance(fp, dict):
        # input_fingerprint is optional in some artifacts; skip if absent
        return ValidationResult(valid=True)

    errors = []
    ci = state.current_inputs

    fp_req = fp.get("requirement_sha256")
    if fp_req and ci.requirement_sha256 and fp_req != ci.requirement_sha256:
        errors.append(
            f"input_fingerprint.requirement_sha256 mismatch: "
            f"artifact={fp_req}, state={ci.requirement_sha256}"
        )

    fp_design = fp.get("design_sha256")
    if fp_design and ci.design_sha256 and fp_design != ci.design_sha256:
        errors.append(
            f"input_fingerprint.design_sha256 mismatch: "
            f"artifact={fp_design}, state={ci.design_sha256}"
        )

    fp_commit = fp.get("review_target_commit")
    if fp_commit and ci.review_target_commit and fp_commit != ci.review_target_commit:
        errors.append(
            f"input_fingerprint.review_target_commit mismatch: "
            f"artifact={fp_commit}, state={ci.review_target_commit}"
        )

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# --- Section validation ---

_SECTION_ALIASES: Dict[str, List[str]] = {
    "Minor Issues": ["Non-Critical Issues"],
}


def check_required_sections(sections: Dict[str, str], required: List[str]) -> ValidationResult:
    """Check that all required section headings exist.

    Supports aliases for sections that LLM agents may name differently.
    """
    missing = []
    for req in required:
        if req in sections:
            continue
        aliases = _SECTION_ALIASES.get(req, [])
        if not any(alias in sections for alias in aliases):
            missing.append(req)
    if missing:
        return ValidationResult(
            valid=False,
            errors=[f"Missing required section(s): {', '.join(missing)}"],
        )
    return ValidationResult(valid=True)


# --- Full artifact validators ---

def validate_design(path: Path, state: WorkflowState) -> ValidationResult:
    """Full validation of design.md: exists, parses, metadata matches, required sections."""
    path = Path(path)
    result = ValidationResult(valid=True)

    if not path.exists():
        return ValidationResult(valid=False, errors=[f"Design artifact not found: {path}"])

    try:
        metadata, body = parse_markdown_frontmatter(path)
    except Exception as e:
        return ValidationResult(valid=False, errors=[f"Failed to parse design: {e}"])

    # Metadata validation
    meta_result = validate_artifact_metadata(
        metadata, state, ArtifactType.DESIGN, Producer.CODEX,
    )
    result = result.merge(meta_result)

    # Input fingerprint
    result = result.merge(validate_input_fingerprint(metadata, state))

    # Check design status
    if metadata.extra.get("status") != "approved":
        result = result.merge(ValidationResult(
            valid=False,
            errors=[f"Design status is '{metadata.extra.get('status')}', expected 'approved'"],
        ))

    # Required sections
    sections = extract_markdown_sections(body)
    result = result.merge(check_required_sections(sections, DESIGN_REQUIRED_SECTIONS))

    return result


def validate_implementation_report(
    path: Path,
    state: WorkflowState,
    expected_mode: Optional[ImplementationMode] = None,
) -> ValidationResult:
    """Full validation of implementation_report.md."""
    path = Path(path)
    result = ValidationResult(valid=True)

    if not path.exists():
        return ValidationResult(valid=False, errors=[f"Implementation report not found: {path}"])

    try:
        metadata, body = parse_markdown_frontmatter(path)
    except Exception as e:
        return ValidationResult(valid=False, errors=[f"Failed to parse implementation report: {e}"])

    # Determine expected producer based on phase
    meta_result = validate_artifact_metadata(
        metadata, state, ArtifactType.IMPLEMENTATION_REPORT, Producer.CLAUDE,
    )
    result = result.merge(meta_result)

    # Input fingerprint
    result = result.merge(validate_input_fingerprint(metadata, state))

    # Check mode if specified
    if expected_mode and metadata.extra.get("mode") != expected_mode.value:
        result = result.merge(ValidationResult(
            valid=False,
            errors=[f"mode mismatch: artifact={metadata.extra.get('mode')}, expected={expected_mode.value}"],
        ))

    # Validate result field
    valid_results = {r.value for r in ImplementationResult}
    report_result = metadata.extra.get("result")
    if report_result is None:
        result = result.merge(ValidationResult(
            valid=False,
            errors=["Missing required 'result' field in implementation report metadata"],
        ))
    elif report_result not in valid_results:
        result = result.merge(ValidationResult(
            valid=False,
            errors=[f"Invalid result value '{report_result}', expected one of: {', '.join(sorted(valid_results))}"],
        ))

    # Required sections
    sections = extract_markdown_sections(body)
    result = result.merge(check_required_sections(sections, IMPLEMENTATION_REPORT_REQUIRED_SECTIONS))

    return result


def validate_review_pair(
    review_md_path: Path,
    review_json_path: Path,
    state: WorkflowState,
) -> ValidationResult:
    """Validate both review artifacts and cross-check consistency."""
    result = ValidationResult(valid=True)

    # --- review.md ---
    review_md_path = Path(review_md_path)
    if not review_md_path.exists():
        result = result.merge(ValidationResult(valid=False, errors=[f"review.md not found: {review_md_path}"]))
    else:
        try:
            md_metadata, md_body = parse_markdown_frontmatter(review_md_path)
            md_meta_result = validate_artifact_metadata(
                md_metadata, state, ArtifactType.REVIEW, Producer.CODEX,
            )
            result = result.merge(md_meta_result)
            result = result.merge(validate_input_fingerprint(md_metadata, state))

            sections = extract_markdown_sections(md_body)
            result = result.merge(check_required_sections(sections, REVIEW_MD_REQUIRED_SECTIONS))
        except Exception as e:
            result = result.merge(ValidationResult(valid=False, errors=[f"Failed to parse review.md: {e}"]))

    # --- review.json ---
    review_json_path = Path(review_json_path)
    if not review_json_path.exists():
        result = result.merge(ValidationResult(valid=False, errors=[f"review.json not found: {review_json_path}"]))
    else:
        try:
            review = parse_review_json(review_json_path)

            json_meta_result = validate_artifact_metadata(
                review.metadata, state, ArtifactType.REVIEW, Producer.CODEX,
            )
            result = result.merge(json_meta_result)
            result = result.merge(validate_input_fingerprint(review.metadata, state))

            # Cross-check: critical count in summary matches actual critical issues
            actual_critical = sum(1 for i in review.issues if i.severity == "critical")
            if review.summary.critical_count != actual_critical:
                result = result.merge(ValidationResult(
                    valid=False,
                    errors=[
                        f"review.json critical_count mismatch: "
                        f"summary says {review.summary.critical_count}, "
                        f"actual critical issues = {actual_critical}"
                    ],
                ))

            # Cross-check: total issues count
            if review.summary.total_issues != len(review.issues):
                result = result.merge(ValidationResult(
                    valid=False,
                    errors=[
                        f"review.json total_issues mismatch: "
                        f"summary says {review.summary.total_issues}, "
                        f"actual = {len(review.issues)}"
                    ],
                ))

        except Exception as e:
            result = result.merge(ValidationResult(valid=False, errors=[f"Failed to parse review.json: {e}"]))

    return result
