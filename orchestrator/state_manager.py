"""Workflow state persistence and mutation helpers.

Maps to design section 'state_manager' and runtime spec sections 7, 12.
All mutation helpers return new WorkflowState instances (immutable pattern).
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from orchestrator.constants import (
    DEFAULT_MAX_ITERATIONS,
    STATE_VERSION,
    WORKFLOW_STATE_PATH,
)
from orchestrator.fileutil import atomic_write, compute_sha256
from orchestrator.models import (
    CurrentInputs,
    DesignRef,
    GitInfo,
    HumanGate,
    LoopGuard,
    Phase,
    RequirementRef,
    RunStatus,
    ValidationResult,
    WorkflowState,
)


# --- Load / Save ---

def load_state(path: Path = WORKFLOW_STATE_PATH) -> WorkflowState:
    """Load and validate workflow_state.json."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    state = WorkflowState.from_dict(data)
    result = validate_state(state)
    if not result.valid:
        raise ValueError(f"Invalid workflow state: {'; '.join(result.errors)}")
    return state


def save_state(state: WorkflowState, path: Path = WORKFLOW_STATE_PATH) -> None:
    """Atomically write state to disk."""
    data = json.dumps(state.to_dict(), indent=2, ensure_ascii=False) + "\n"
    atomic_write(path, data)


# --- Validation ---

def validate_state(state: WorkflowState) -> ValidationResult:
    """Check schema version, required fields, enum values."""
    errors = []

    if state.state_version != STATE_VERSION:
        errors.append(f"Unknown state_version={state.state_version}, expected {STATE_VERSION}")

    if not state.run_id:
        errors.append("run_id is empty")
    elif not re.match(r"^run-\d{8}-\d{6}-[0-9a-f]{8}$", state.run_id):
        errors.append(f"run_id format invalid: {state.run_id}")

    # Validate phase enum
    try:
        Phase(state.phase)
    except ValueError:
        errors.append(f"Unknown phase: {state.phase}")

    # Validate status enum
    try:
        RunStatus(state.status)
    except ValueError:
        errors.append(f"Unknown status: {state.status}")

    if state.iteration < 1:
        errors.append(f"iteration must be >= 1, got {state.iteration}")

    if state.phase_attempt < 1:
        errors.append(f"phase_attempt must be >= 1, got {state.phase_attempt}")

    if state.max_iterations < 1:
        errors.append(f"max_iterations must be >= 1, got {state.max_iterations}")

    if not state.requirement.sha256:
        errors.append("requirement.sha256 is empty")

    return ValidationResult(valid=len(errors) == 0, errors=errors)


# --- Mutation helpers (return new state) ---

def set_phase(state: WorkflowState, phase: Phase, phase_attempt: int = 1) -> WorkflowState:
    """Return new state with updated phase and phase_attempt."""
    new = state.copy()
    new.phase = phase.value
    new.phase_attempt = phase_attempt
    return new


def record_phase_success(state: WorkflowState, phase: Phase) -> WorkflowState:
    """Update last_completed_phase and last_completed_at."""
    new = state.copy()
    new.last_completed_phase = phase.value
    new.last_completed_at = datetime.now(timezone.utc).isoformat()
    return new


def open_human_gate(state: WorkflowState, reason: str, details: Optional[str] = None) -> WorkflowState:
    """Set human_gate.required=True and status=waiting_human."""
    new = state.copy()
    new.status = RunStatus.WAITING_HUMAN.value
    new.phase = Phase.NEEDS_HUMAN.value
    new.human_gate = HumanGate(required=True, reason=reason, details=details)
    return new


def close_human_gate(state: WorkflowState) -> WorkflowState:
    """Clear human gate and restore active status."""
    new = state.copy()
    new.status = RunStatus.ACTIVE.value
    new.human_gate = HumanGate(required=False)
    return new


def increment_iteration(state: WorkflowState) -> WorkflowState:
    """Increment iteration counter and reset phase_attempt."""
    new = state.copy()
    new.iteration += 1
    new.phase_attempt = 1
    return new


def increment_phase_attempt(state: WorkflowState) -> WorkflowState:
    """Increment phase_attempt for retry."""
    new = state.copy()
    new.phase_attempt += 1
    return new


def update_design_ref(state: WorkflowState, version: int, sha256: str, status: str = "approved") -> WorkflowState:
    """Update design reference after a new design is approved."""
    new = state.copy()
    new.design = DesignRef(version=version, sha256=sha256, status=status)
    new.current_inputs.design_sha256 = sha256
    return new


def update_loop_guard(
    state: WorkflowState,
    fingerprint: Optional[str] = None,
    malformed: bool = False,
    no_diff: bool = False,
    reset_malformed: bool = False,
    reset_no_diff: bool = False,
) -> WorkflowState:
    """Update loop guard counters."""
    new = state.copy()
    guard = LoopGuard(
        repeated_fingerprint_counts=dict(state.loop_guard.repeated_fingerprint_counts),
        consecutive_no_diff=state.loop_guard.consecutive_no_diff,
        consecutive_malformed_artifacts=state.loop_guard.consecutive_malformed_artifacts,
    )

    if fingerprint:
        guard.repeated_fingerprint_counts[fingerprint] = (
            guard.repeated_fingerprint_counts.get(fingerprint, 0) + 1
        )

    if malformed:
        guard.consecutive_malformed_artifacts += 1
    if reset_malformed:
        guard.consecutive_malformed_artifacts = 0

    if no_diff:
        guard.consecutive_no_diff += 1
    if reset_no_diff:
        guard.consecutive_no_diff = 0

    new.loop_guard = guard
    return new


def mark_completed(state: WorkflowState) -> WorkflowState:
    """Mark the run as completed."""
    new = state.copy()
    new.status = RunStatus.COMPLETED.value
    new.phase = Phase.DONE.value
    return new


def mark_failed(state: WorkflowState, reason: str) -> WorkflowState:
    """Mark the run as failed."""
    new = state.copy()
    new.status = RunStatus.FAILED.value
    new.human_gate = HumanGate(required=True, reason=reason)
    return new


# --- Run initialization ---

def generate_run_id() -> str:
    """Generate run_id in format: run-YYYYMMDD-HHMMSS-<8hex>."""
    now = datetime.now(timezone.utc)
    hex_part = uuid.uuid4().hex[:8]
    return f"run-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{hex_part}"


def init_state(
    requirement_path: Path,
    max_iterations: int = DEFAULT_MAX_ITERATIONS,
) -> WorkflowState:
    """Create initial WorkflowState for a new run."""
    req_sha = compute_sha256(requirement_path)
    run_id = generate_run_id()

    return WorkflowState(
        state_version=STATE_VERSION,
        run_id=run_id,
        status=RunStatus.ACTIVE.value,
        phase=Phase.DESIGNING.value,
        phase_attempt=1,
        iteration=1,
        max_iterations=max_iterations,
        requirement=RequirementRef(path=str(requirement_path), sha256=req_sha),
        design=DesignRef(version=0, sha256=None, status="draft"),
        current_inputs=CurrentInputs(requirement_sha256=req_sha),
        last_completed_phase=None,
        last_completed_at=None,
        last_artifacts={},
        loop_guard=LoopGuard(),
        human_gate=HumanGate(),
        git=GitInfo(),
        active_lock_owner=None,
    )
