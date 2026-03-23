"""Tests for orchestrator.transition_engine."""

from orchestrator.models import (
    CurrentInputs,
    DesignRef,
    LoopGuard,
    Phase,
    RequirementRef,
    ReviewArtifact,
    ReviewIssue,
    ReviewSummary,
    WorkflowState,
    ArtifactMetadata,
)
from orchestrator.transition_engine import (
    TransitionDecision,
    apply_transition,
    check_loop_guards,
    check_preconditions,
    resolve_designing_exit,
    resolve_fixing_exit,
    resolve_implementing_exit,
    resolve_next_phase,
    resolve_reviewing_exit,
)


def _make_state(**overrides) -> WorkflowState:
    defaults = dict(
        run_id="run-20260323-120000-abcdef12",
        phase="designing",
        iteration=1,
        max_iterations=6,
        phase_attempt=1,
        requirement=RequirementRef(sha256="abc"),
        design=DesignRef(version=1, sha256="def", status="approved"),
        current_inputs=CurrentInputs(requirement_sha256="abc", design_sha256="def"),
    )
    defaults.update(overrides)
    return WorkflowState(**defaults)


def _make_review(result: str = "pass", issues=None, design_change_required=False) -> ReviewArtifact:
    return ReviewArtifact(
        metadata=ArtifactMetadata(artifact_type="review"),
        result=result,
        issues=issues or [],
        summary=ReviewSummary(
            total_issues=len(issues or []),
            critical_count=sum(1 for i in (issues or []) if i.severity == "critical"),
            design_change_required=design_change_required,
        ),
    )


class TestCheckPreconditions:
    def test_designing_allowed(self):
        state = _make_state(phase="designing")
        result = check_preconditions(state, Phase.DESIGNING)
        assert result.valid

    def test_implementing_requires_approved_design(self):
        state = _make_state(phase="implementing", design=DesignRef(version=0, status="draft"))
        result = check_preconditions(state, Phase.IMPLEMENTING)
        assert not result.valid

    def test_implementing_with_approved_design(self):
        state = _make_state(phase="implementing")
        result = check_preconditions(state, Phase.IMPLEMENTING)
        assert result.valid

    def test_completed_run_blocked(self):
        state = _make_state(status="completed")
        result = check_preconditions(state, Phase.DESIGNING)
        assert not result.valid


class TestResolveDesigningExit:
    def test_valid_design_goes_to_implementing(self):
        state = _make_state()
        decision = resolve_designing_exit(state, design_valid=True)
        assert decision.next_phase == Phase.IMPLEMENTING

    def test_invalid_design_stays(self):
        state = _make_state()
        decision = resolve_designing_exit(state, design_valid=False)
        assert decision.next_phase == Phase.DESIGNING


class TestResolveImplementingExit:
    def test_valid_report_goes_to_reviewing(self):
        state = _make_state(phase="implementing")
        decision = resolve_implementing_exit(state, report_valid=True)
        assert decision.next_phase == Phase.REVIEWING

    def test_blocked_report_goes_to_human(self):
        state = _make_state(phase="implementing")
        decision = resolve_implementing_exit(state, report_valid=True, report_result="blocked")
        assert decision.next_phase == Phase.NEEDS_HUMAN
        assert decision.open_human_gate

    def test_invalid_report_retries(self):
        state = _make_state(phase="implementing")
        decision = resolve_implementing_exit(state, report_valid=False)
        assert decision.next_phase == Phase.IMPLEMENTING


class TestResolveReviewingExit:
    def test_pass_goes_to_done(self):
        state = _make_state(phase="reviewing")
        review = _make_review(result="pass")
        decision = resolve_reviewing_exit(state, review)
        assert decision.next_phase == Phase.DONE

    def test_pass_with_open_amendments_goes_to_designing(self):
        state = _make_state(
            phase="reviewing",
            current_inputs=CurrentInputs(
                requirement_sha256="abc",
                design_sha256="def",
                open_amendment_ids=["amend-1"],
            ),
        )
        review = _make_review(result="pass")
        decision = resolve_reviewing_exit(state, review)
        assert decision.next_phase == Phase.DESIGNING

    def test_fail_no_design_change_goes_to_fixing(self):
        state = _make_state(phase="reviewing")
        issues = [ReviewIssue(issue_id="i1", severity="critical", requires_design_change=False)]
        review = _make_review(result="fail", issues=issues)
        decision = resolve_reviewing_exit(state, review)
        assert decision.next_phase == Phase.FIXING

    def test_fail_with_design_change_goes_to_designing(self):
        state = _make_state(phase="reviewing")
        issues = [ReviewIssue(issue_id="i1", severity="critical", requires_design_change=True)]
        review = _make_review(result="fail", issues=issues)
        decision = resolve_reviewing_exit(state, review)
        assert decision.next_phase == Phase.DESIGNING
        assert not decision.increment_iteration  # ISS-005: redesign stays same iteration

    def test_blocked_goes_to_human(self):
        state = _make_state(phase="reviewing")
        review = _make_review(result="blocked")
        review.blocking_reason = "Cannot determine"
        decision = resolve_reviewing_exit(state, review)
        assert decision.next_phase == Phase.NEEDS_HUMAN
        assert decision.open_human_gate


class TestResolveFixingExit:
    def test_valid_fix_goes_to_reviewing(self):
        state = _make_state(phase="fixing")
        decision = resolve_fixing_exit(state, report_valid=True)
        assert decision.next_phase == Phase.REVIEWING
        assert decision.increment_iteration

    def test_invalid_fix_retries(self):
        state = _make_state(phase="fixing")
        decision = resolve_fixing_exit(state, report_valid=False)
        assert decision.next_phase == Phase.FIXING


class TestCheckLoopGuards:
    def test_no_breach(self):
        state = _make_state()
        assert check_loop_guards(state) is None

    def test_max_iterations_exceeded(self):
        state = _make_state(iteration=7, max_iterations=6)
        decision = check_loop_guards(state)
        assert decision is not None
        assert decision.next_phase == Phase.NEEDS_HUMAN

    def test_repeated_fingerprint(self):
        state = _make_state(
            loop_guard=LoopGuard(repeated_fingerprint_counts={"fp1": 3}),
        )
        decision = check_loop_guards(state)
        assert decision is not None
        assert decision.open_human_gate

    def test_consecutive_malformed(self):
        state = _make_state(
            loop_guard=LoopGuard(consecutive_malformed_artifacts=2),
        )
        decision = check_loop_guards(state)
        assert decision is not None

    def test_consecutive_no_diff(self):
        state = _make_state(
            loop_guard=LoopGuard(consecutive_no_diff=2),
        )
        decision = check_loop_guards(state)
        assert decision is not None


class TestApplyTransition:
    def test_move_to_implementing(self):
        state = _make_state(phase="designing")
        decision = TransitionDecision(next_phase=Phase.IMPLEMENTING)
        new_state = apply_transition(state, decision)
        assert new_state.phase == "implementing"
        assert new_state.last_completed_phase == "designing"

    def test_move_to_done(self):
        state = _make_state(phase="reviewing")
        decision = TransitionDecision(next_phase=Phase.DONE)
        new_state = apply_transition(state, decision)
        assert new_state.phase == "done"
        assert new_state.status == "completed"

    def test_increment_iteration(self):
        state = _make_state(phase="fixing", iteration=1)
        decision = TransitionDecision(next_phase=Phase.REVIEWING, increment_iteration=True)
        new_state = apply_transition(state, decision)
        assert new_state.iteration == 2

    def test_open_human_gate(self):
        state = _make_state(phase="reviewing")
        decision = TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason="blocked",
        )
        new_state = apply_transition(state, decision)
        assert new_state.phase == "needs_human"
        assert new_state.human_gate.required is True
        assert new_state.status == "waiting_human"

    def test_open_human_gate_without_reason(self):
        """open_human_gate=True with reason=None should still trigger gate."""
        state = _make_state(phase="implementing")
        decision = TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=None,
        )
        new_state = apply_transition(state, decision)
        assert new_state.phase == "needs_human"
        assert new_state.human_gate.required is True
        assert new_state.status == "waiting_human"
        assert new_state.human_gate.reason is not None
