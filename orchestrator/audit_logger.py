"""Structured append-only audit logger.

Maps to design section 'audit_logger'. Writes JSON-line events to audit.log.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from orchestrator.constants import AUDIT_LOG_PATH
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
