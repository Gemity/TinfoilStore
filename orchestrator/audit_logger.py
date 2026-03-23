"""Structured append-only audit logger.

Maps to design section 'audit_logger'. Writes JSON-line events to audit.log.
Also provides detailed agent session logging and orchestrator runtime logging.
"""

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from orchestrator.constants import AGENT_LOGS_DIR, AUDIT_LOG_PATH, ORCHESTRATOR_LOG_PATH
from orchestrator.fileutil import ensure_directory


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_event(
    event_type: str,
    phase: str,
    run_id: str,
    iteration: int,
    message: str,
    details: Optional[dict] = None,
    log_path: Path = AUDIT_LOG_PATH,
) -> None:
    """Append a single JSON-line event to audit.log."""
    ensure_directory(log_path.parent)
    entry = {
        "timestamp": _now_iso(),
        "event_type": event_type,
        "run_id": run_id,
        "phase": phase,
        "iteration": iteration,
        "message": message,
    }
    if details:
        entry["details"] = details
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


# ---------------------------------------------------------------------------
# Agent session log: full stdout/stderr per invocation
# ---------------------------------------------------------------------------

def _agent_log_path(run_id: str, phase: str, phase_attempt: int) -> Path:
    """Return the path for a per-invocation agent log file."""
    safe_run = run_id.replace(":", "-")
    return AGENT_LOGS_DIR / f"{safe_run}_{phase}_attempt{phase_attempt}.log"


def log_agent_session(
    run_id: str,
    phase: str,
    phase_attempt: int,
    agent_result: dict,
    prompt_path: str,
) -> Path:
    """Write a detailed agent session log capturing the full invocation.

    Returns the path of the written log file.
    """
    log_path = _agent_log_path(run_id, phase, phase_attempt)
    ensure_directory(log_path.parent)

    lines = [
        f"=== Agent Session Log ===",
        f"Timestamp : {_now_iso()}",
        f"Run ID    : {run_id}",
        f"Phase     : {phase}",
        f"Attempt   : {phase_attempt}",
        f"Agent     : {agent_result.get('agent', 'unknown')}",
        f"Command   : {agent_result.get('command', [])}",
        f"Prompt    : {prompt_path}",
        f"Exit code : {agent_result.get('returncode', 'N/A')}",
        f"Success   : {agent_result.get('ok', False)}",
        "",
        "--- STDOUT ---",
        agent_result.get("stdout", "") or "(empty)",
        "",
        "--- STDERR ---",
        agent_result.get("stderr", "") or "(empty)",
        "",
    ]

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return log_path


def log_agent_error(
    run_id: str,
    phase: str,
    phase_attempt: int,
    exc: Exception,
    command: Optional[list] = None,
    prompt_path: Optional[str] = None,
) -> Path:
    """Write a detailed log when agent invocation fails before producing output."""
    log_path = _agent_log_path(run_id, phase, phase_attempt)
    ensure_directory(log_path.parent)

    lines = [
        f"=== Agent Error Log ===",
        f"Timestamp : {_now_iso()}",
        f"Run ID    : {run_id}",
        f"Phase     : {phase}",
        f"Attempt   : {phase_attempt}",
        f"Command   : {command or 'N/A'}",
        f"Prompt    : {prompt_path or 'N/A'}",
        "",
        "--- EXCEPTION ---",
        f"{type(exc).__name__}: {exc}",
        "",
        "--- TRACEBACK ---",
        traceback.format_exc(),
    ]

    with open(log_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return log_path


# ---------------------------------------------------------------------------
# Orchestrator runtime log: append-only text log for CLI-level events
# ---------------------------------------------------------------------------

def log_orchestrator(
    level: str,
    run_id: str,
    phase: str,
    message: str,
    log_path: Path = ORCHESTRATOR_LOG_PATH,
) -> None:
    """Append a timestamped line to the orchestrator runtime log."""
    ensure_directory(log_path.parent)
    ts = _now_iso()
    line = f"[{ts}] [{level.upper()}] [{run_id}] [{phase}] {message}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(line)


def log_phase_start(run_id: str, phase: str, iteration: int, phase_attempt: int, **kwargs) -> None:
    log_event(
        "phase_start", phase, run_id, iteration,
        f"Starting phase={phase} attempt={phase_attempt}",
        details={"phase_attempt": phase_attempt},
        **kwargs,
    )


def log_phase_end(run_id: str, phase: str, iteration: int, success: bool, message: str, **kwargs) -> None:
    log_event(
        "phase_end", phase, run_id, iteration,
        message,
        details={"success": success},
        **kwargs,
    )


def log_validation_failure(run_id: str, phase: str, iteration: int, errors: List[str], **kwargs) -> None:
    log_event(
        "validation_failure", phase, run_id, iteration,
        f"Validation failed with {len(errors)} error(s)",
        details={"errors": errors},
        **kwargs,
    )


def log_human_gate(run_id: str, phase: str, iteration: int, reason: str, **kwargs) -> None:
    log_event(
        "human_gate", phase, run_id, iteration,
        f"Human gate opened: {reason}",
        details={"reason": reason},
        **kwargs,
    )


def log_lock_event(run_id: str, phase: str, iteration: int, action: str, **kwargs) -> None:
    log_event(
        "lock", phase, run_id, iteration,
        f"Lock action: {action}",
        details={"action": action},
        **kwargs,
    )
