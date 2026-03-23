"""Artifact archival and summary generation. Stub for first implementation pass."""

from orchestrator.models import WorkflowState


def archive_artifacts(state: WorkflowState) -> None:
    """Copy accepted artifacts from current/ to history/<run_id>/iter-xxxx/.

    Not yet implemented.
    """
    raise NotImplementedError("history_manager.archive_artifacts is not yet implemented")


def update_summary(state: WorkflowState) -> None:
    """Generate or update summary.md after a phase completes.

    Not yet implemented.
    """
    raise NotImplementedError("history_manager.update_summary is not yet implemented")
