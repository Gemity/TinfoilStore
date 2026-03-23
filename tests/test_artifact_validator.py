"""Tests for orchestrator.artifact_validator."""

import json
from pathlib import Path

from orchestrator.artifact_validator import (
    check_required_sections,
    validate_artifact_metadata,
    validate_design,
    validate_implementation_report,
    validate_review_pair,
)
from orchestrator.models import (
    ArtifactMetadata,
    ArtifactType,
    DesignRef,
    ImplementationMode,
    Producer,
    RequirementRef,
    WorkflowState,
)


def _make_state(**overrides) -> WorkflowState:
    defaults = dict(
        run_id="run-20260323-120000-abcdef12",
        phase="designing",
        iteration=1,
        phase_attempt=1,
        requirement=RequirementRef(sha256="abc"),
        design=DesignRef(version=1, sha256="def", status="approved"),
    )
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_metadata(**overrides) -> ArtifactMetadata:
    defaults = dict(
        artifact_type="design",
        artifact_version=1,
        run_id="run-20260323-120000-abcdef12",
        iteration=1,
        phase="designing",
        phase_attempt=1,
        producer="codex",
        created_at="2026-01-01T00:00:00Z",
    )
    defaults.update(overrides)
    return ArtifactMetadata(**defaults)


class TestValidateArtifactMetadata:
    def test_matching_state(self):
        state = _make_state()
        meta = _make_metadata()
        result = validate_artifact_metadata(meta, state, ArtifactType.DESIGN, Producer.CODEX)
        assert result.valid

    def test_run_id_mismatch(self):
        state = _make_state()
        meta = _make_metadata(run_id="run-20260323-999999-ffffffff")
        result = validate_artifact_metadata(meta, state, ArtifactType.DESIGN, Producer.CODEX)
        assert not result.valid
        assert any("run_id" in e for e in result.errors)

    def test_iteration_mismatch(self):
        state = _make_state()
        meta = _make_metadata(iteration=5)
        result = validate_artifact_metadata(meta, state, ArtifactType.DESIGN, Producer.CODEX)
        assert not result.valid

    def test_producer_mismatch(self):
        state = _make_state()
        meta = _make_metadata(producer="claude")
        result = validate_artifact_metadata(meta, state, ArtifactType.DESIGN, Producer.CODEX)
        assert not result.valid


    def test_phase_attempt_mismatch(self):
        """ISS-003: stale artifact from earlier retry should be rejected."""
        state = _make_state(phase_attempt=2)
        meta = _make_metadata(phase_attempt=1)
        result = validate_artifact_metadata(meta, state, ArtifactType.DESIGN, Producer.CODEX)
        assert not result.valid
        assert any("phase_attempt" in e for e in result.errors)


class TestValidateInputFingerprint:
    def test_matching_fingerprint(self):
        from orchestrator.artifact_validator import validate_input_fingerprint
        state = _make_state()
        state.current_inputs.requirement_sha256 = "abc123"
        state.current_inputs.design_sha256 = "def456"
        meta = _make_metadata(extra={
            "input_fingerprint": {
                "requirement_sha256": "abc123",
                "design_sha256": "def456",
            }
        })
        result = validate_input_fingerprint(meta, state)
        assert result.valid

    def test_mismatched_requirement_sha(self):
        """ISS-003: stale artifact with old input set should be rejected."""
        from orchestrator.artifact_validator import validate_input_fingerprint
        state = _make_state()
        state.current_inputs.requirement_sha256 = "new_sha"
        meta = _make_metadata(extra={
            "input_fingerprint": {
                "requirement_sha256": "old_sha",
            }
        })
        result = validate_input_fingerprint(meta, state)
        assert not result.valid
        assert any("requirement_sha256" in e for e in result.errors)

    def test_mismatched_design_sha(self):
        from orchestrator.artifact_validator import validate_input_fingerprint
        state = _make_state()
        state.current_inputs.design_sha256 = "new_design"
        meta = _make_metadata(extra={
            "input_fingerprint": {
                "design_sha256": "old_design",
            }
        })
        result = validate_input_fingerprint(meta, state)
        assert not result.valid
        assert any("design_sha256" in e for e in result.errors)

    def test_no_fingerprint_is_ok(self):
        from orchestrator.artifact_validator import validate_input_fingerprint
        state = _make_state()
        meta = _make_metadata()
        result = validate_input_fingerprint(meta, state)
        assert result.valid


class TestCheckRequiredSections:
    def test_all_present(self):
        sections = {"Objective": "x", "Scope": "y", "Constraints": "z"}
        result = check_required_sections(sections, ["Objective", "Scope"])
        assert result.valid

    def test_missing_section(self):
        sections = {"Objective": "x"}
        result = check_required_sections(sections, ["Objective", "Scope"])
        assert not result.valid
        assert "Scope" in result.errors[0]


class TestValidateDesign:
    def _write_design(self, tmp_path: Path, **meta_overrides) -> Path:
        meta = {
            "artifact_type": "design",
            "artifact_version": 1,
            "run_id": "run-20260323-120000-abcdef12",
            "iteration": 1,
            "phase": "designing",
            "phase_attempt": 1,
            "producer": "codex",
            "created_at": "2026-01-01T00:00:00Z",
            "design_version": 1,
            "status": "approved",
        }
        meta.update(meta_overrides)
        fm = "\n".join(f"{k}: {v}" for k, v in meta.items())

        content = f"""---
{fm}
---

# Objective
Test

# Scope
Test

# Constraints
Test

# Architecture
Test

# Execution Plan
Test

# Acceptance Criteria
Test

# Non-Goals
Test
"""
        path = tmp_path / "design.md"
        path.write_text(content)
        return path

    def test_valid_design(self, tmp_path: Path):
        path = self._write_design(tmp_path)
        state = _make_state()
        result = validate_design(path, state)
        assert result.valid

    def test_missing_file(self, tmp_path: Path):
        state = _make_state()
        result = validate_design(tmp_path / "missing.md", state)
        assert not result.valid

    def test_missing_section(self, tmp_path: Path):
        path = tmp_path / "design.md"
        path.write_text("""---
artifact_type: design
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: designing
phase_attempt: 1
producer: codex
created_at: 2026-01-01T00:00:00Z
status: approved
---

# Objective
Test
""")
        state = _make_state()
        result = validate_design(path, state)
        assert not result.valid
        assert any("Missing" in e for e in result.errors)

    def test_unapproved_design(self, tmp_path: Path):
        path = self._write_design(tmp_path, status="draft")
        state = _make_state()
        result = validate_design(path, state)
        assert not result.valid


class TestValidateImplementationReport:
    def _write_report(self, tmp_path: Path, mode: str = "implement") -> Path:
        content = f"""---
artifact_type: implementation_report
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: implementing
phase_attempt: 1
producer: claude
created_at: 2026-01-01T00:00:00Z
mode: {mode}
result: success
---

# Summary
Done

# Files Changed
- foo.py

# Tests Run
All pass

# Known Risks
None

# Amendment Requests
None
"""
        path = tmp_path / "implementation_report.md"
        path.write_text(content)
        return path

    def test_valid_report(self, tmp_path: Path):
        path = self._write_report(tmp_path)
        state = _make_state(phase="implementing")
        result = validate_implementation_report(path, state, ImplementationMode.IMPLEMENT)
        assert result.valid

    def test_mode_mismatch(self, tmp_path: Path):
        path = self._write_report(tmp_path, mode="implement")
        state = _make_state(phase="fixing")
        result = validate_implementation_report(path, state, ImplementationMode.FIX)
        assert not result.valid

    def test_missing_result_field(self, tmp_path: Path):
        """Implementation report without 'result' in metadata should fail."""
        content = """---
artifact_type: implementation_report
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: implementing
phase_attempt: 1
producer: claude
created_at: 2026-01-01T00:00:00Z
mode: implement
---

# Summary
Done

# Files Changed
- foo.py

# Tests Run
All pass

# Known Risks
None
"""
        path = tmp_path / "implementation_report.md"
        path.write_text(content)
        state = _make_state(phase="implementing")
        result = validate_implementation_report(path, state, ImplementationMode.IMPLEMENT)
        assert not result.valid
        assert any("result" in e.lower() for e in result.errors)

    def test_invalid_result_field(self, tmp_path: Path):
        """Implementation report with invalid 'result' value should fail."""
        content = """---
artifact_type: implementation_report
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: implementing
phase_attempt: 1
producer: claude
created_at: 2026-01-01T00:00:00Z
mode: implement
result: banana
---

# Summary
Done

# Files Changed
- foo.py

# Tests Run
All pass

# Known Risks
None
"""
        path = tmp_path / "implementation_report.md"
        path.write_text(content)
        state = _make_state(phase="implementing")
        result = validate_implementation_report(path, state, ImplementationMode.IMPLEMENT)
        assert not result.valid
        assert any("banana" in e for e in result.errors)


class TestValidateReviewPair:
    def _write_review_pair(self, tmp_path: Path, result: str = "pass") -> tuple:
        md_content = """---
artifact_type: review
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: reviewing
phase_attempt: 1
producer: codex
created_at: 2026-01-01T00:00:00Z
---

# Verdict
Pass

# Critical Issues
None

# Minor Issues
None

# Amendment Decisions
None

# Notes For Next Iteration
None
"""
        json_data = {
            "metadata": {
                "artifact_type": "review",
                "artifact_version": 1,
                "run_id": "run-20260323-120000-abcdef12",
                "iteration": 1,
                "phase": "reviewing",
                "phase_attempt": 1,
                "producer": "codex",
                "created_at": "2026-01-01T00:00:00Z",
            },
            "result": result,
            "blocking_reason": None,
            "approved_design_version": 1,
            "issues": [],
            "summary": {
                "total_issues": 0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "design_change_required": False,
            },
        }
        md_path = tmp_path / "review.md"
        md_path.write_text(md_content)
        json_path = tmp_path / "review.json"
        json_path.write_text(json.dumps(json_data))
        return md_path, json_path

    def test_valid_pair(self, tmp_path: Path):
        md_path, json_path = self._write_review_pair(tmp_path)
        state = _make_state(phase="reviewing")
        result = validate_review_pair(md_path, json_path, state)
        assert result.valid

    def test_missing_review_md(self, tmp_path: Path):
        _, json_path = self._write_review_pair(tmp_path)
        state = _make_state(phase="reviewing")
        result = validate_review_pair(tmp_path / "missing.md", json_path, state)
        assert not result.valid

    def test_critical_count_mismatch(self, tmp_path: Path):
        md_path, json_path = self._write_review_pair(tmp_path)
        # Tamper with the JSON to have mismatched counts
        data = json.loads(json_path.read_text())
        data["summary"]["critical_count"] = 5  # but no critical issues
        json_path.write_text(json.dumps(data))

        state = _make_state(phase="reviewing")
        result = validate_review_pair(md_path, json_path, state)
        assert not result.valid
        assert any("critical_count" in e for e in result.errors)

    def test_stale_review_json_fingerprint_rejected(self, tmp_path: Path):
        """ISS-006: review.json with stale input_fingerprint should be rejected."""
        md_path, json_path = self._write_review_pair(tmp_path)
        # Inject a stale fingerprint into the review.json metadata
        data = json.loads(json_path.read_text())
        data["metadata"]["input_fingerprint"] = {
            "requirement_sha256": "stale_sha",
        }
        json_path.write_text(json.dumps(data))

        state = _make_state(phase="reviewing")
        state.current_inputs.requirement_sha256 = "current_sha"
        result = validate_review_pair(md_path, json_path, state)
        assert not result.valid
        assert any("requirement_sha256" in e for e in result.errors)


class TestMissingAmendmentRequests:
    def test_implementation_report_missing_amendment_requests(self, tmp_path: Path):
        """ISS-007: implementation report without Amendment Requests should fail."""
        content = """---
artifact_type: implementation_report
artifact_version: 1
run_id: run-20260323-120000-abcdef12
iteration: 1
phase: implementing
phase_attempt: 1
producer: claude
created_at: 2026-01-01T00:00:00Z
mode: implement
result: success
---

# Summary
Done

# Files Changed
- foo.py

# Tests Run
All pass

# Known Risks
None
"""
        path = tmp_path / "implementation_report.md"
        path.write_text(content)
        state = _make_state(phase="implementing")
        result = validate_implementation_report(path, state, ImplementationMode.IMPLEMENT)
        assert not result.valid
        assert any("Amendment Requests" in e for e in result.errors)
