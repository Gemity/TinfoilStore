"""Minimal CLI entrypoint for the orchestrator.

Supports: status, init, validate, check-transition, run.
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
    from orchestrator.transition_engine import check_loop_guards, resolve_next_phase
    from orchestrator.artifact_validator import (
        validate_design,
        validate_implementation_report,
        validate_review_pair,
    )
    from orchestrator.artifact_parser import parse_review_json
    from orchestrator.models import Phase, ImplementationMode

    state_path = Path(args.state) if args.state else WORKFLOW_STATE_PATH
    state = load_state(state_path)
    phase = Phase(state.phase)
    artifacts_dir = ARTIFACTS_CURRENT_DIR

    # Check loop guards first
    loop_decision = check_loop_guards(state)
    if loop_decision:
        print(f"LOOP GUARD TRIGGERED: {loop_decision.human_gate_reason}")
        print(f"Would transition to: {loop_decision.next_phase.value}")
        return

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
        print(f"No transition logic for phase: {state.phase}")
        return

    decision = resolve_next_phase(state, artifact_valid, review=review, report_result=report_result)

    print(f"Current:    {state.phase} (iter {state.iteration}, attempt {state.phase_attempt})")
    print(f"Artifacts:  {'valid' if artifact_valid else 'INVALID'}")
    print(f"Next phase: {decision.next_phase.value}")
    if decision.increment_iteration:
        print(f"Iteration:  will increment to {state.iteration + 1}")
    if decision.open_human_gate:
        print(f"Human gate: {decision.human_gate_reason}")
    if decision.notes:
        print(f"Notes:      {decision.notes}")


def cmd_run(args: argparse.Namespace) -> None:
    """Start the current phase by generating its prompt package and invoking the agent."""
    from orchestrator.audit_logger import (
        log_event,
        log_lock_event,
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

        preconditions = check_preconditions(state, phase)
        if not preconditions.valid:
            log_validation_failure(state.run_id, state.phase, state.iteration, preconditions.errors)
            print(f"Cannot start phase: {state.phase}")
            for error in preconditions.errors:
                print(f"  - {error}")
            sys.exit(1)

        prompt = build_prompt(state, state.phase)
        prompt_path = get_prompt_output_path(state.phase)
        atomic_write(prompt_path, prompt)

        log_phase_start(state.run_id, state.phase, state.iteration, state.phase_attempt)
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
            print(f"Failed to invoke agent: {exc}")
            sys.exit(1)
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
            },
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
        if agent_result["stderr"].strip():
            print(f"Agent stderr: {agent_result['stderr'].strip()}")
        if not agent_result["ok"]:
            sys.exit(agent_result["returncode"] or 1)
    finally:
        if lock is not None:
            release_lock()
            log_lock_event(state.run_id, state.phase, state.iteration, "released")


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
