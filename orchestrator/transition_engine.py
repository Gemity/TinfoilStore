"""Phase transition logic: pure functions that determine the next phase.

Maps to design section 'transition_engine' and runtime spec section 9.
All functions are pure - they take state and return decisions without side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from orchestrator.constants import (
    DEFAULT_MALFORMED_ARTIFACT_THRESHOLD,
    DEFAULT_NO_MEANINGFUL_DIFF_THRESHOLD,
    DEFAULT_REPEATED_FINGERPRINT_THRESHOLD,
)
from orchestrator.models import (
    Phase,
    ReviewArtifact,
    ReviewResult,
    RunStatus,
    ValidationResult,
    WorkflowState,
)


@dataclass
class TransitionDecision:
    """Result of a phase transition evaluation."""
    next_phase: Phase
    increment_iteration: bool = False
    open_human_gate: bool = False
    human_gate_reason: Optional[str] = None
    notes: str = ""


# --- Precondition checks ---

def check_preconditions(state: WorkflowState, phase: Phase) -> ValidationResult:
    """Check entry preconditions for a phase."""
    errors = []

    if state.status == RunStatus.COMPLETED.value:
        errors.append("Run is already completed")

    if state.status == RunStatus.FAILED.value:
        errors.append("Run has failed")

    if phase == Phase.DESIGNING:
        # No special preconditions for designing
        pass

    elif phase == Phase.IMPLEMENTING:
        if state.design.status != "approved":
            errors.append("Cannot implement without an approved design")
        if not state.design.sha256:
            errors.append("Design sha256 is missing")

    elif phase == Phase.REVIEWING:
        if state.last_completed_phase not in (Phase.IMPLEMENTING.value, Phase.FIXING.value):
            errors.append(f"Cannot review: last completed phase is '{state.last_completed_phase}'")

    elif phase == Phase.FIXING:
        if state.last_completed_phase != Phase.REVIEWING.value:
            errors.append("Cannot fix: last completed phase is not 'reviewing'")

    elif phase == Phase.NEEDS_HUMAN:
        # Always allowed
        pass

    elif phase == Phase.DONE:
        # Should only be reached via transition
        pass

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# --- Phase exit resolvers ---

def resolve_designing_exit(state: WorkflowState, design_valid: bool) -> TransitionDecision:
    """Determine next phase after designing.

    Spec section 9.1: designing → implementing (if design valid and approved).
    """
    if design_valid:
        return TransitionDecision(
            next_phase=Phase.IMPLEMENTING,
            notes="Design approved, moving to implementation",
        )
    else:
        return TransitionDecision(
            next_phase=Phase.DESIGNING,
            notes="Design not yet valid, retry designing",
        )


def resolve_implementing_exit(
    state: WorkflowState,
    report_valid: bool,
    report_result: str = "success",
) -> TransitionDecision:
    """Determine next phase after implementing.

    Spec section 9.2: implementing → reviewing (if report valid).
    """
    if report_valid and report_result != "blocked":
        return TransitionDecision(
            next_phase=Phase.REVIEWING,
            notes="Implementation report valid, moving to review",
        )
    elif report_result == "blocked":
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason="Implementation blocked",
            notes="Implementation reported blocked state",
        )
    else:
        return TransitionDecision(
            next_phase=Phase.IMPLEMENTING,
            notes="Implementation report invalid, retry",
        )


def resolve_reviewing_exit(state: WorkflowState, review: ReviewArtifact) -> TransitionDecision:
    """Determine next phase after reviewing. Core branching logic.

    Spec section 9.3:
    - result=pass, no blocking amendments → done
    - result=fail, no design change required → fixing
    - result=fail, design change required → designing
    - result=blocked → needs_human
    """
    result = review.result

    if result == ReviewResult.PASS.value:
        # Check for open blocking amendments
        if state.current_inputs.open_amendment_ids:
            return TransitionDecision(
                next_phase=Phase.DESIGNING,
                notes="Review passed but open amendments pending, redesign needed",
            )
        return TransitionDecision(
            next_phase=Phase.DONE,
            notes="Review passed, run complete",
        )

    elif result == ReviewResult.FAIL.value:
        # Check if any critical issue requires design change
        needs_design_change = any(
            issue.requires_design_change
            for issue in review.issues
            if issue.severity == "critical"
        )

        if needs_design_change or review.summary.design_change_required:
            return TransitionDecision(
                next_phase=Phase.DESIGNING,
                increment_iteration=False,
                notes="Review failed with design changes required, same iteration",
            )
        else:
            return TransitionDecision(
                next_phase=Phase.FIXING,
                notes="Review failed, fixing required",
            )

    elif result == ReviewResult.BLOCKED.value:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=review.blocking_reason or "Review reported blocked",
            notes="Review blocked, human intervention needed",
        )

    else:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=f"Unknown review result: {result}",
            notes=f"Unexpected review result '{result}'",
        )


def resolve_fixing_exit(state: WorkflowState, report_valid: bool) -> TransitionDecision:
    """Determine next phase after fixing.

    Spec section 9.4: fixing → reviewing (increment iteration).
    """
    if report_valid:
        return TransitionDecision(
            next_phase=Phase.REVIEWING,
            increment_iteration=True,
            notes="Fix report valid, back to review with new iteration",
        )
    else:
        return TransitionDecision(
            next_phase=Phase.FIXING,
            notes="Fix report invalid, retry fixing",
        )


# --- Loop guard checks ---

def check_loop_guards(
    state: WorkflowState,
    fingerprint_threshold: int = DEFAULT_REPEATED_FINGERPRINT_THRESHOLD,
    malformed_threshold: int = DEFAULT_MALFORMED_ARTIFACT_THRESHOLD,
    no_diff_threshold: int = DEFAULT_NO_MEANINGFUL_DIFF_THRESHOLD,
) -> Optional[TransitionDecision]:
    """Check if any loop guard threshold is breached.

    Returns a needs_human TransitionDecision if breached, None otherwise.
    Spec section 9.5.
    """
    guard = state.loop_guard

    # Max iterations exceeded
    if state.iteration > state.max_iterations:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=f"Max iterations exceeded: {state.iteration}/{state.max_iterations}",
        )

    # Repeated fingerprint threshold
    for fp, count in guard.repeated_fingerprint_counts.items():
        if count >= fingerprint_threshold:
            return TransitionDecision(
                next_phase=Phase.NEEDS_HUMAN,
                open_human_gate=True,
                human_gate_reason=f"Repeated fingerprint detected ({count} times): {fp[:16]}...",
            )

    # Consecutive malformed artifacts
    if guard.consecutive_malformed_artifacts >= malformed_threshold:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=f"Too many consecutive malformed artifacts: {guard.consecutive_malformed_artifacts}",
        )

    # Consecutive no-diff
    if guard.consecutive_no_diff >= no_diff_threshold:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=f"No meaningful diff for {guard.consecutive_no_diff} consecutive attempts",
        )

    return None


# --- Top-level dispatch ---

def resolve_next_phase(
    state: WorkflowState,
    artifact_valid: bool,
    review: Optional[ReviewArtifact] = None,
    report_result: str = "success",
) -> TransitionDecision:
    """Given current phase and validation results, determine the next transition.

    This is the main entry point for transition logic.
    """
    # Check loop guards first
    loop_decision = check_loop_guards(state)
    if loop_decision:
        return loop_decision

    phase = Phase(state.phase)

    if phase == Phase.DESIGNING:
        return resolve_designing_exit(state, artifact_valid)

    elif phase == Phase.IMPLEMENTING:
        return resolve_implementing_exit(state, artifact_valid, report_result)

    elif phase == Phase.REVIEWING:
        if review is None:
            return TransitionDecision(
                next_phase=Phase.REVIEWING,
                notes="No review artifact provided, cannot determine transition",
            )
        return resolve_reviewing_exit(state, review)

    elif phase == Phase.FIXING:
        return resolve_fixing_exit(state, artifact_valid)

    elif phase == Phase.NEEDS_HUMAN:
        # Human must resolve this - no automatic transition
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            notes="Waiting for human decision",
        )

    elif phase == Phase.DONE:
        return TransitionDecision(
            next_phase=Phase.DONE,
            notes="Run already complete",
        )

    else:
        return TransitionDecision(
            next_phase=Phase.NEEDS_HUMAN,
            open_human_gate=True,
            human_gate_reason=f"Unknown phase: {state.phase}",
        )


def apply_transition(state: WorkflowState, decision: TransitionDecision) -> WorkflowState:
    """Apply a TransitionDecision to produce the next WorkflowState.

    This is a pure function - caller is responsible for saving state.
    """
    from orchestrator.state_manager import (
        increment_iteration,
        mark_completed,
        open_human_gate,
        record_phase_success,
        set_phase,
    )

    new_state = state

    # Record current phase as completed (if moving to a different phase)
    current_phase = Phase(state.phase)
    if decision.next_phase != current_phase:
        new_state = record_phase_success(new_state, current_phase)

    # Increment iteration if needed
    if decision.increment_iteration:
        new_state = increment_iteration(new_state)

    # Open human gate if needed
    if decision.open_human_gate:
        reason = decision.human_gate_reason or "Human intervention required (no reason provided)"
        new_state = open_human_gate(new_state, reason)
    elif decision.next_phase == Phase.DONE:
        new_state = mark_completed(new_state)
    else:
        new_state = set_phase(new_state, decision.next_phase)

    return new_state
