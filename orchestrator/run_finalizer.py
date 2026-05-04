"""Post-agent finalization steps for the summarizing phase.

After Claude writes summary.md and updates CLAUDE.md, the orchestrator
runs these steps automatically:
  1. Archive artifacts to history/{run_id}/
  2. Git tag the current commit
  3. Write run metrics
"""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from orchestrator.constants import (
    ARTIFACTS_CURRENT_DIR,
    ARTIFACTS_HISTORY_DIR,
    LOGS_DIR,
    WORKFLOW_STATE_PATH,
)
from orchestrator.models import WorkflowState


_ROOT_DIR = Path(__file__).resolve().parent.parent
_METRICS_PATH = LOGS_DIR / "run_metrics.jsonl"


def archive_artifacts(state: WorkflowState) -> Optional[Path]:
    """Copy artifacts/current/ to artifacts/history/{run_id}/.

    Returns the archive path, or None if nothing to archive.
    """
    src = _ROOT_DIR / ARTIFACTS_CURRENT_DIR
    if not src.exists() or not any(src.iterdir()):
        return None

    dest = _ROOT_DIR / ARTIFACTS_HISTORY_DIR / state.run_id
    dest.mkdir(parents=True, exist_ok=True)

    for item in src.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)

    # Also copy workflow state snapshot
    state_src = _ROOT_DIR / WORKFLOW_STATE_PATH
    if state_src.exists():
        shutil.copy2(state_src, dest / "workflow_state.json")

    return dest


def git_tag_run(state: WorkflowState) -> Optional[str]:
    """Create a lightweight git tag for the completed run.

    Tag format: orchestrator/{run_id}
    Returns the tag name, or None if git is not available or tagging fails.
    """
    tag_name = f"orchestrator/{state.run_id}"

    try:
        # Check if we're in a git repo
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=str(_ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            return None

        # Check if tag already exists
        result = subprocess.run(
            ["git", "tag", "-l", tag_name],
            cwd=str(_ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.stdout.strip():
            return None  # Tag already exists

        # Create tag
        result = subprocess.run(
            ["git", "tag", tag_name, "-m",
             f"Orchestrator run completed: {state.run_id} "
             f"(iteration {state.iteration})"],
            cwd=str(_ROOT_DIR),
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return tag_name
    except FileNotFoundError:
        pass  # git not installed

    return None


def write_run_metrics(state: WorkflowState, started_at: Optional[str] = None) -> Path:
    """Append a single JSONL line with run metrics.

    Metrics include: run_id, iterations used, final phase, duration, timestamp.
    """
    metrics_path = _ROOT_DIR / _METRICS_PATH
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc).isoformat()

    record = {
        "run_id": state.run_id,
        "completed_at": now,
        "iteration": state.iteration,
        "max_iterations": state.max_iterations,
        "last_completed_phase": state.last_completed_phase,
        "status": state.status,
        "design_version": state.design.version,
    }

    with open(metrics_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return metrics_path


def run_post_summary_steps(state: WorkflowState) -> dict:
    """Execute all post-summary finalization steps.

    Returns a dict summarizing what was done.
    """
    results = {}

    # 1. Archive artifacts
    archive_path = archive_artifacts(state)
    results["archived"] = str(archive_path) if archive_path else None

    # 2. Git tag
    tag = git_tag_run(state)
    results["git_tag"] = tag

    # 3. Metrics
    metrics_path = write_run_metrics(state)
    results["metrics"] = str(metrics_path)

    return results
