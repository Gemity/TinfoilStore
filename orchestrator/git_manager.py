"""Git checkpoint management. Stub for first implementation pass."""

from orchestrator.models import WorkflowState


def create_checkpoint(state: WorkflowState, message: str) -> None:
    """Create a git checkpoint commit after a successful phase.

    Not yet implemented. Will degrade gracefully when git is unavailable.
    """
    raise NotImplementedError("git_manager.create_checkpoint is not yet implemented")


def get_current_branch() -> str | None:
    """Return current git branch name, or None if not in a git repo."""
    raise NotImplementedError("git_manager.get_current_branch is not yet implemented")


def get_head_commit() -> str | None:
    """Return current HEAD commit hash, or None if not in a git repo."""
    raise NotImplementedError("git_manager.get_head_commit is not yet implemented")
