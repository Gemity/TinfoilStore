"""Minimal CLI entrypoint for the orchestrator.

Supports: status, init, validate, check-transition, advance, accept, run.
Run via: python -m orchestrator <command>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestrator.constants import (
    ARTIFACTS_CURRENT_DIR,
    DESIGN_MD,
    IMPLEMENTATION_REPORT_MD,
    INPUT_DIR,
    REVIEW_JSON,
    REVIEW_MD,
    WORKFLOW_STATE_PATH,
)
from orchestrator.fileutil import atomic_write


def cmd_status(args: argparse.Namespace) -> None:
    """Print current workflow state summary."""
    from orchestrator.state_manager import load_state

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    try:
        state = load_state(state_path)
    except FileNotFoundError:
        print(f"No workflow state found at {state_path}")
        sys.exit(1)
    except ValueError as e:
        print(f"Invalid workflow state: {e}")
        sys.exit(1)

    print(f"Run ID:     {state.run_id}")
    print(f"Status:     {state.status}")
    print(f"Phase:      {state.phase}")
    print(f"Iteration:  {state.iteration}/{state.max_iterations}")
    print(f"Attempt:    {state.phase_attempt}")
    print(f"Design:     v{state.design.version} ({state.design.status})")
    print(f"Last done:  {state.last_completed_phase or 'none'}")

    if state.human_gate.required:
        print(f"HUMAN GATE: {state.human_gate.reason}")

    guard = state.loop_guard
    if guard.consecutive_malformed_artifacts > 0:
        print(f"Malformed:  {guard.consecutive_malformed_artifacts} consecutive")
    if guard.consecutive_no_diff > 0:
        print(f"No-diff:    {guard.consecutive_no_diff} consecutive")


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a new orchestrator run."""
    from orchestrator.state_manager import init_state, save_state
    from orchestrator.audit_logger import log_event

    req_path = Path(args.requirement)
    if not req_path.exists():
        print(f"Requirement file not found: {req_path}")
        sys.exit(1)

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    if state_path.exists() and not args.force:
        print(f"State already exists at {state_path}. Use --force to overwrite.")
        sys.exit(1)

    state = init_state(req_path, max_iterations=args.max_iterations)
    save_state(state, state_path)

    log_event(
        "run_init", state.phase, state.run_id, state.iteration,
        f"New run initialized from {req_path}",
    )

    print(f"Initialized run: {state.run_id}")
    print(f"Phase: {state.phase}")
    print(f"State saved to: {state_path}")


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate current artifacts against workflow state."""
    from orchestrator.state_manager import load_state
    from orchestrator.artifact_validator import (
        validate_design,
        validate_implementation_report,
        validate_review_pair,
    )
    from orchestrator.models import Phase, ImplementationMode

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)
    phase = Phase(state.phase)

    artifacts_dir = ARTIFACTS_CURRENT_DIR
    all_valid = True

    if phase == Phase.DESIGNING:
        result = validate_design(artifacts_dir / DESIGN_MD, state)
        _print_validation("design.md", result)
        all_valid = all_valid and result.valid

    elif phase == Phase.IMPLEMENTING:
        mode = ImplementationMode.IMPLEMENT
        result = validate_implementation_report(
            artifacts_dir / IMPLEMENTATION_REPORT_MD, state, expected_mode=mode,
        )
        _print_validation("implementation_report.md", result)
        all_valid = all_valid and result.valid

    elif phase == Phase.REVIEWING:
        result = validate_review_pair(
            artifacts_dir / REVIEW_MD, artifacts_dir / REVIEW_JSON, state,
        )
        _print_validation("review pair", result)
        all_valid = all_valid and result.valid

    elif phase == Phase.FIXING:
        mode = ImplementationMode.FIX
        result = validate_implementation_report(
            artifacts_dir / IMPLEMENTATION_REPORT_MD, state, expected_mode=mode,
        )
        _print_validation("implementation_report.md (fix)", result)
        all_valid = all_valid and result.valid

    else:
        print(f"No validation defined for phase: {state.phase}")

    sys.exit(0 if all_valid else 1)


def cmd_check_transition(args: argparse.Namespace) -> None:
    """Dry-run: show what the next phase would be."""
    from orchestrator.state_manager import load_state
    from orchestrator.transition_engine import check_loop_guards
    from orchestrator.models import Phase

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)
    artifacts_dir = ARTIFACTS_CURRENT_DIR

    # Check loop guards first
    loop_decision = check_loop_guards(state)
    if loop_decision:
        print(f"LOOP GUARD TRIGGERED: {loop_decision.human_gate_reason}")
        print(f"Would transition to: {loop_decision.next_phase.value}")
        return

    phase, artifact_valid, decision = _evaluate_transition(state, artifacts_dir)

    if decision is None:
        print(f"No transition logic for phase: {state.phase}")
        return

    print(f"Current:    {state.phase} (iter {state.iteration}, attempt {state.phase_attempt})")
    print(f"Artifacts:  {'valid' if artifact_valid else 'INVALID'}")
    print(f"Next phase: {decision.next_phase.value}")
    if decision.increment_iteration:
        print(f"Iteration:  will increment to {state.iteration + 1}")
    if decision.open_human_gate:
        print(f"Human gate: {decision.human_gate_reason}")
    if decision.notes:
        print(f"Notes:      {decision.notes}")


def _evaluate_transition(state, artifacts_dir):
    """Shared helper: validate artifacts and compute transition decision."""
    from orchestrator.artifact_validator import (
        validate_design,
        validate_implementation_report,
        validate_review_pair,
    )
    from orchestrator.artifact_parser import parse_review_json
    from orchestrator.transition_engine import resolve_next_phase
    from orchestrator.models import Phase, ImplementationMode

    phase = Phase(state.phase)
    review = None
    artifact_valid = False
    report_result = "success"

    if phase == Phase.DESIGNING:
        result = validate_design(artifacts_dir / DESIGN_MD, state)
        artifact_valid = result.valid

    elif phase == Phase.IMPLEMENTING:
        result = validate_implementation_report(
            artifacts_dir / IMPLEMENTATION_REPORT_MD, state,
        )
        artifact_valid = result.valid
        if artifact_valid:
            report_result = _extract_report_result(artifacts_dir / IMPLEMENTATION_REPORT_MD)

    elif phase == Phase.REVIEWING:
        result = validate_review_pair(
            artifacts_dir / REVIEW_MD, artifacts_dir / REVIEW_JSON, state,
        )
        artifact_valid = result.valid
        if artifact_valid:
            try:
                review = parse_review_json(artifacts_dir / REVIEW_JSON)
            except Exception:
                artifact_valid = False

    elif phase == Phase.FIXING:
        result = validate_implementation_report(
            artifacts_dir / IMPLEMENTATION_REPORT_MD, state,
            expected_mode=ImplementationMode.FIX,
        )
        artifact_valid = result.valid
        if artifact_valid:
            report_result = _extract_report_result(artifacts_dir / IMPLEMENTATION_REPORT_MD)

    else:
        return phase, artifact_valid, None

    decision = resolve_next_phase(state, artifact_valid, review=review, report_result=report_result)
    return phase, artifact_valid, decision


def cmd_advance(args: argparse.Namespace) -> None:
    """Validate artifacts, compute next phase, and apply the transition to workflow state.

    If human_gates.json marks the transition as 'manual', the workflow pauses
    in NEEDS_HUMAN phase so the operator can review and then run 'accept'.
    """
    from orchestrator.audit_logger import log_event, log_orchestrator
    from orchestrator.human_gate_config import requires_human_approval
    from orchestrator.state_manager import load_state, open_human_gate, save_state
    from orchestrator.transition_engine import apply_transition, check_loop_guards
    from orchestrator.models import Phase

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)
    artifacts_dir = ARTIFACTS_CURRENT_DIR

    phase = Phase(state.phase)
    if phase == Phase.DONE:
        print(f"Run already completed: {state.run_id}")
        return
    if phase == Phase.NEEDS_HUMAN:
        print(f"Workflow is blocked: {state.human_gate.reason}")
        print("Run 'py -m orchestrator accept' to approve, or fix the issue first.")
        sys.exit(1)

    # Check loop guards first
    loop_decision = check_loop_guards(state)
    if loop_decision:
        new_state = apply_transition(state, loop_decision)
        save_state(new_state, state_path)
        log_event(
            "transition", state.phase, state.run_id, state.iteration,
            f"Loop guard triggered -> {loop_decision.next_phase.value}",
            details={"reason": loop_decision.human_gate_reason},
        )
        print(f"LOOP GUARD: {loop_decision.human_gate_reason}")
        print(f"Transitioned to: {loop_decision.next_phase.value}")
        sys.exit(1)

    phase, artifact_valid, decision = _evaluate_transition(state, artifacts_dir)

    if decision is None:
        print(f"No transition logic for phase: {state.phase}")
        sys.exit(1)

    if not artifact_valid:
        print(f"Cannot advance: artifacts are INVALID for phase '{state.phase}'")
        sys.exit(1)

    # Check human gate policy for this transition
    if requires_human_approval(state.phase, decision.next_phase.value):
        # Pause for human review — store pending transition in details
        pending = json.dumps({
            "pending_from": state.phase,
            "pending_to": decision.next_phase.value,
            "increment_iteration": decision.increment_iteration,
            "notes": decision.notes,
        })
        new_state = open_human_gate(
            state,
            reason=f"Awaiting approval: {state.phase} -> {decision.next_phase.value}",
            details=pending,
        )
        save_state(new_state, state_path)

        log_event(
            "human_gate_pending", state.phase, state.run_id, state.iteration,
            f"Human approval required: {state.phase} -> {decision.next_phase.value}",
            details={"from": state.phase, "to": decision.next_phase.value, "policy": "manual"},
        )
        log_orchestrator(
            "INFO", state.run_id, state.phase,
            f"Human gate opened: {state.phase} -> {decision.next_phase.value} (manual policy)",
        )

        print(f"Artifacts:  valid")
        print(f"Transition: {state.phase} -> {decision.next_phase.value}")
        print(f"Status:     WAITING FOR HUMAN APPROVAL")
        print(f"")
        print(f"Review the artifacts, then run:")
        print(f"  py -m orchestrator accept     # approve and continue")
        print(f"  py -m orchestrator status      # check current state")
        return

    # Auto-approve: apply transition directly
    new_state = apply_transition(state, decision)
    save_state(new_state, state_path)

    log_event(
        "transition", state.phase, state.run_id, state.iteration,
        f"Advanced: {state.phase} -> {decision.next_phase.value}",
        details={
            "from_phase": state.phase,
            "to_phase": decision.next_phase.value,
            "increment_iteration": decision.increment_iteration,
            "notes": decision.notes,
            "policy": "auto",
        },
    )
    log_orchestrator(
        "INFO", state.run_id, state.phase,
        f"Transition applied (auto): {state.phase} -> {decision.next_phase.value}",
    )

    print(f"Previous:   {state.phase} (iter {state.iteration}, attempt {state.phase_attempt})")
    print(f"Artifacts:  valid")
    print(f"Transitioned to: {decision.next_phase.value} (auto-approved)")
    if decision.increment_iteration:
        print(f"Iteration:  incremented to {new_state.iteration}")
    if decision.notes:
        print(f"Notes:      {decision.notes}")


def cmd_accept(args: argparse.Namespace) -> None:
    """Accept a pending human gate and apply the stored transition."""
    from orchestrator.audit_logger import log_event, log_orchestrator
    from orchestrator.state_manager import (
        close_human_gate,
        increment_iteration,
        load_state,
        mark_completed,
        record_phase_success,
        save_state,
        set_phase,
    )
    from orchestrator.models import Phase

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)

    if not state.human_gate.required:
        print("No human gate is active. Nothing to accept.")
        return

    # Recover pending transition from human gate details
    pending = None
    if state.human_gate.details:
        try:
            pending = json.loads(state.human_gate.details)
        except (json.JSONDecodeError, TypeError):
            pass

    if not pending or "pending_to" not in pending:
        # Human gate was opened by loop guard or error, not a transition gate.
        # Just close the gate and restore the previous phase.
        new_state = close_human_gate(state)
        # Restore the phase from pending_from if available
        if pending and pending.get("pending_from"):
            new_state.phase = pending["pending_from"]
        save_state(new_state, state_path)
        log_orchestrator("INFO", state.run_id, state.phase, "Human gate closed (no pending transition)")
        print(f"Human gate closed. Phase restored.")
        print(f"Run 'py -m orchestrator status' to check state.")
        return

    from_phase = pending["pending_from"]
    to_phase = pending["pending_to"]
    do_increment = pending.get("increment_iteration", False)
    notes = pending.get("notes", "")

    # Apply the pending transition
    new_state = close_human_gate(state)
    new_state.phase = from_phase  # restore original phase first
    current_phase = Phase(from_phase)
    target_phase = Phase(to_phase)

    # Record current phase as completed
    new_state = record_phase_success(new_state, current_phase)

    if do_increment:
        new_state = increment_iteration(new_state)

    if target_phase == Phase.DONE:
        new_state = mark_completed(new_state)
    else:
        new_state = set_phase(new_state, target_phase)

    save_state(new_state, state_path)

    log_event(
        "transition", from_phase, state.run_id, state.iteration,
        f"Human accepted: {from_phase} -> {to_phase}",
        details={
            "from_phase": from_phase,
            "to_phase": to_phase,
            "increment_iteration": do_increment,
            "notes": notes,
        },
    )
    log_orchestrator(
        "INFO", state.run_id, from_phase,
        f"Human approved transition: {from_phase} -> {to_phase}",
    )

    print(f"Accepted:   {from_phase} -> {to_phase}")
    if do_increment:
        print(f"Iteration:  incremented to {new_state.iteration}")
    if notes:
        print(f"Notes:      {notes}")
    print(f"")
    print(f"Next: py -m orchestrator run")


def cmd_run(args: argparse.Namespace) -> None:
    """Start the current phase by generating its prompt package and invoking the agent."""
    from orchestrator.audit_logger import (
        log_agent_error,
        log_agent_session,
        log_event,
        log_lock_event,
        log_orchestrator,
        log_phase_start,
        log_validation_failure,
    )
    from orchestrator.agent_runner import run_agent
    from orchestrator.lock_manager import acquire_lock, release_lock
    from orchestrator.prompt_builder import build_prompt, get_prompt_output_path
    from orchestrator.state_manager import load_state
    from orchestrator.transition_engine import check_preconditions
    from orchestrator.models import Phase

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)

    phase = Phase(state.phase)
    if phase == Phase.NEEDS_HUMAN:
        reason = state.human_gate.reason or "Human intervention required"
        print(f"Workflow is blocked by a human gate: {reason}")
        sys.exit(1)
    if phase == Phase.DONE:
        print(f"Run already completed: {state.run_id}")
        return

    lock = None
    try:
        lock = acquire_lock(state)
        log_lock_event(state.run_id, state.phase, state.iteration, "acquired")
        log_orchestrator("INFO", state.run_id, state.phase, "Lock acquired")

        preconditions = check_preconditions(state, phase)
        if not preconditions.valid:
            log_validation_failure(state.run_id, state.phase, state.iteration, preconditions.errors)
            log_orchestrator(
                "ERROR", state.run_id, state.phase,
                f"Precondition failed: {'; '.join(preconditions.errors)}",
            )
            print(f"Cannot start phase: {state.phase}")
            for error in preconditions.errors:
                print(f"  - {error}")
            sys.exit(1)

        prompt = build_prompt(state, state.phase)
        prompt_path = get_prompt_output_path(state.phase)
        atomic_write(prompt_path, prompt)

        log_phase_start(state.run_id, state.phase, state.iteration, state.phase_attempt)
        log_orchestrator(
            "INFO", state.run_id, state.phase,
            f"Phase started (attempt {state.phase_attempt}), invoking agent...",
        )

        try:
            agent_result = run_agent(state, state.phase, str(prompt_path))
        except Exception as exc:
            log_event(
                "agent_invocation_failed",
                state.phase,
                state.run_id,
                state.iteration,
                f"Failed to invoke agent for phase {state.phase}",
                details={"error": str(exc)},
            )
            error_log = log_agent_error(
                state.run_id, state.phase, state.phase_attempt,
                exc, prompt_path=str(prompt_path),
            )
            log_orchestrator(
                "ERROR", state.run_id, state.phase,
                f"Agent invocation failed: {exc} (details: {error_log})",
            )
            print(f"Failed to invoke agent: {exc}")
            print(f"Error log:   {error_log}")
            sys.exit(1)

        # Persist full agent output to a dedicated session log
        session_log = log_agent_session(
            state.run_id, state.phase, state.phase_attempt,
            agent_result, str(prompt_path),
        )

        log_event(
            "agent_invocation",
            state.phase,
            state.run_id,
            state.iteration,
            f"Invoked {agent_result['agent']} for phase {state.phase}",
            details={
                "agent": agent_result["agent"],
                "command": agent_result["command"],
                "returncode": agent_result["returncode"],
                "session_log": str(session_log),
            },
        )
        log_orchestrator(
            "INFO" if agent_result["ok"] else "ERROR",
            state.run_id, state.phase,
            f"Agent '{agent_result['agent']}' exited {agent_result['returncode']} "
            f"(log: {session_log})",
        )

        print(f"Run ID:      {state.run_id}")
        print(f"Phase:       {state.phase}")
        print(f"Agent:       {agent_result['agent']}")
        print(f"Prompt file: {prompt_path}")
        print(f"Exit code:   {agent_result['returncode']}")
        if agent_result["ok"]:
            print("Status:      prompt package generated and agent invocation completed")
        else:
            print("Status:      agent invocation failed")
        if phase == Phase.DESIGNING:
            print(f"Expected:    {ARTIFACTS_CURRENT_DIR / DESIGN_MD}")
        elif phase in (Phase.IMPLEMENTING, Phase.FIXING):
            print(f"Expected:    {ARTIFACTS_CURRENT_DIR / IMPLEMENTATION_REPORT_MD}")
        elif phase == Phase.REVIEWING:
            print(f"Expected:    {ARTIFACTS_CURRENT_DIR / REVIEW_MD}")
            print(f"Expected:    {ARTIFACTS_CURRENT_DIR / REVIEW_JSON}")
        print(f"Session log: {session_log}")
        if agent_result["stderr"].strip():
            print(f"Agent stderr: {agent_result['stderr'].strip()}")
        if not agent_result["ok"]:
            sys.exit(agent_result["returncode"] or 1)
    finally:
        if lock is not None:
            release_lock()
            log_lock_event(state.run_id, state.phase, state.iteration, "released")
            log_orchestrator("INFO", state.run_id, state.phase, "Lock released")


def _extract_report_result(report_path: Path) -> str:
    """Extract the 'result' field from an implementation report's frontmatter."""
    from orchestrator.artifact_parser import parse_markdown_frontmatter

    try:
        metadata, _ = parse_markdown_frontmatter(report_path)
        return metadata.extra.get("result", "success")
    except Exception:
        return "success"


def _print_validation(name: str, result) -> None:
    """Print validation result."""
    status = "PASS" if result.valid else "FAIL"
    print(f"[{status}] {name}")
    for error in result.errors:
        print(f"  - {error}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="orchestrator",
        description="HiveMind AI Orchestrator Runtime",
    )
    parser.add_argument("--state", help="Path to workflow_state.json", default=None)

    subparsers = parser.add_subparsers(dest="command")

    # status
    subparsers.add_parser("status", help="Show current workflow state")

    # init
    init_p = subparsers.add_parser("init", help="Initialize a new run")
    init_p.add_argument(
        "--requirement",
        default=str(INPUT_DIR / "requirement.md"),
        help="Path to requirement.md",
    )
    init_p.add_argument("--max-iterations", type=int, default=6)
    init_p.add_argument("--force", action="store_true", help="Overwrite existing state")

    # validate
    subparsers.add_parser("validate", help="Validate artifacts for current phase")

    # check-transition
    subparsers.add_parser("check-transition", help="Dry-run phase transition check")

    # advance
    subparsers.add_parser("advance", help="Validate artifacts and apply phase transition")

    # accept
    subparsers.add_parser("accept", help="Accept a pending human gate and apply the transition")

    # run
    subparsers.add_parser("run", help="Generate the prompt package for the current phase")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "status": cmd_status,
        "init": cmd_init,
        "validate": cmd_validate,
        "check-transition": cmd_check_transition,
        "advance": cmd_advance,
        "accept": cmd_accept,
        "run": cmd_run,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        cmd_func(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
