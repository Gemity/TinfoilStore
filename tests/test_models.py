"""Tests for orchestrator.models - round-trip serialization and enum handling."""

from orchestrator.models import (
    ArtifactMetadata,
    CurrentInputs,
    DesignRef,
    GitInfo,
    HumanGate,
    LockOwner,
    LockRecord,
    LoopGuard,
    Phase,
    RequirementRef,
    ReviewArtifact,
    ReviewIssue,
    ReviewSummary,
    RunStatus,
    ValidationResult,
    WorkflowState,
)


def _make_state(**overrides) -> WorkflowState:
    defaults = dict(
        state_version=1,
        run_id="run-20260323-000003-be751c2f",
        status="active",
        phase="designing",
        phase_attempt=1,
        iteration=1,
        max_iterations=6,
        requirement=RequirementRef(path=".ai-loop/input/requirement.md", sha256="abc123"),
        design=DesignRef(version=0, sha256=None, status="draft"),
        current_inputs=CurrentInputs(requirement_sha256="abc123"),
        last_completed_phase=None,
        last_completed_at=None,
        last_artifacts={},
        loop_guard=LoopGuard(),
        human_gate=HumanGate(),
        git=GitInfo(),
        active_lock_owner=None,
    )
    defaults.update(overrides)
    return WorkflowState(**defaults)


class TestWorkflowStateRoundTrip:
    def test_basic_round_trip(self):
        state = _make_state()
        d = state.to_dict()
        restored = WorkflowState.from_dict(d)
        assert restored.run_id == state.run_id
        assert restored.phase == state.phase
        assert restored.iteration == state.iteration

    def test_round_trip_with_lock_owner(self):
        owner = LockOwner(owner="orchestrator", pid=1234, hostname="myhost", acquired_at="2026-01-01T00:00:00Z")
        state = _make_state(active_lock_owner=owner)
        d = state.to_dict()
        restored = WorkflowState.from_dict(d)
        assert restored.active_lock_owner is not None
        assert restored.active_lock_owner.pid == 1234
        assert restored.active_lock_owner.hostname == "myhost"

    def test_round_trip_with_null_lock_owner(self):
        state = _make_state(active_lock_owner=None)
        d = state.to_dict()
        assert d["active_lock_owner"] is None
        restored = WorkflowState.from_dict(d)
        assert restored.active_lock_owner is None

    def test_nested_objects_preserved(self):
        state = _make_state(
            loop_guard=LoopGuard(
                repeated_fingerprint_counts={"fp1": 2},
                consecutive_no_diff=1,
                consecutive_malformed_artifacts=0,
            ),
            human_gate=HumanGate(required=True, reason="test"),
        )
        d = state.to_dict()
        restored = WorkflowState.from_dict(d)
        assert restored.loop_guard.repeated_fingerprint_counts == {"fp1": 2}
        assert restored.loop_guard.consecutive_no_diff == 1
        assert restored.human_gate.required is True
        assert restored.human_gate.reason == "test"

    def test_copy_is_independent(self):
        state = _make_state()
        copy = state.copy()
        copy.phase = "implementing"
        assert state.phase == "designing"


class TestLockRecordRoundTrip:
    def test_basic_round_trip(self):
        lock = LockRecord(
            lock_version=1, run_id="run-123", owner="orch",
            pid=42, hostname="h", phase="designing", phase_attempt=1,
            acquired_at="2026-01-01T00:00:00Z", expires_at="2026-01-01T00:10:00Z",
        )
        d = lock.to_dict()
        restored = LockRecord.from_dict(d)
        assert restored.run_id == "run-123"
        assert restored.pid == 42

    def test_null_fields(self):
        lock = LockRecord()
        d = lock.to_dict()
        restored = LockRecord.from_dict(d)
        assert restored.run_id is None
        assert restored.pid is None


class TestEnumSerialization:
    def test_phase_values_are_strings(self):
        assert Phase.DESIGNING.value == "designing"
        assert Phase.DONE.value == "done"

    def test_run_status_values(self):
        assert RunStatus.ACTIVE.value == "active"
        assert RunStatus.WAITING_HUMAN.value == "waiting_human"

    def test_phase_from_string(self):
        assert Phase("designing") == Phase.DESIGNING
        assert Phase("implementing") == Phase.IMPLEMENTING


class TestArtifactMetadata:
    def test_extra_fields_preserved(self):
        d = {
            "artifact_type": "design",
            "artifact_version": 1,
            "run_id": "run-123",
            "iteration": 1,
            "phase": "designing",
            "phase_attempt": 1,
            "producer": "codex",
            "created_at": "2026-01-01T00:00:00Z",
            "design_version": 1,
            "status": "approved",
        }
        meta = ArtifactMetadata.from_dict(d)
        assert meta.extra["design_version"] == 1
        assert meta.extra["status"] == "approved"

    def test_to_dict_merges_extra(self):
        meta = ArtifactMetadata(
            artifact_type="design", run_id="run-123",
            extra={"custom_field": "value"},
        )
        d = meta.to_dict()
        assert d["custom_field"] == "value"


class TestValidationResult:
    def test_merge_both_valid(self):
        a = ValidationResult(valid=True)
        b = ValidationResult(valid=True)
        merged = a.merge(b)
        assert merged.valid is True
        assert merged.errors == []

    def test_merge_one_invalid(self):
        a = ValidationResult(valid=True)
        b = ValidationResult(valid=False, errors=["err1"])
        merged = a.merge(b)
        assert merged.valid is False
        assert merged.errors == ["err1"]

    def test_merge_both_invalid(self):
        a = ValidationResult(valid=False, errors=["e1"])
        b = ValidationResult(valid=False, errors=["e2"])
        merged = a.merge(b)
        assert merged.valid is False
        assert set(merged.errors) == {"e1", "e2"}


class TestReviewArtifact:
    def test_round_trip(self):
        review = ReviewArtifact(
            metadata=ArtifactMetadata(artifact_type="review", run_id="run-1"),
            result="fail",
            issues=[
                ReviewIssue(issue_id="i1", severity="critical", fingerprint="fp1"),
            ],
            summary=ReviewSummary(total_issues=1, critical_count=1),
        )
        d = review.to_dict()
        restored = ReviewArtifact.from_dict(d)
        assert restored.result == "fail"
        assert len(restored.issues) == 1
        assert restored.issues[0].severity == "critical"
        assert restored.summary.critical_count == 1
