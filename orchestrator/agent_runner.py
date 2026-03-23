"""Worker invocation adapter for local Codex and Claude CLIs."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from pathlib import Path

from orchestrator.models import Phase, WorkflowState


_ROOT_DIR = Path(__file__).resolve().parent.parent

_PHASE_TO_AGENT = {
    Phase.DESIGNING: "codex",
    Phase.REVIEWING: "codex",
    Phase.IMPLEMENTING: "claude",
    Phase.FIXING: "claude",
}

_ENV_VAR_BY_AGENT = {
    "codex": "HIVEMIND_CODEX_COMMAND",
    "claude": "HIVEMIND_CLAUDE_COMMAND",
}

_DEFAULT_COMMANDS = {
    "codex": ["codex", "exec", "-"],
    "claude": ["claude", "-p"],
}


def get_agent_for_phase(phase: str) -> str:
    """Return the agent responsible for a workflow phase."""
    phase_enum = Phase(phase)
    if phase_enum not in _PHASE_TO_AGENT:
        raise ValueError(f"No agent is configured for phase: {phase}")
    return _PHASE_TO_AGENT[phase_enum]


def run_agent(state: WorkflowState, phase: str, prompt_path: str) -> dict:
    """Invoke the worker responsible for the given phase."""
    agent = get_agent_for_phase(phase)
    prompt_file = Path(prompt_path)
    prompt_text = prompt_file.read_text(encoding="utf-8")
    command = _resolve_command(agent, state, phase, prompt_file)

    completed = subprocess.run(
        command,
        cwd=str(_ROOT_DIR),
        input=prompt_text,
        text=True,
        capture_output=True,
        check=False,
    )

    return {
        "ok": completed.returncode == 0,
        "agent": agent,
        "command": command,
        "prompt_path": str(prompt_file),
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
    }


def _resolve_command(agent: str, state: WorkflowState, phase: str, prompt_path: Path) -> list[str]:
    env_name = _ENV_VAR_BY_AGENT[agent]
    configured = os.environ.get(env_name)
    if configured:
        parts = _parse_command(configured)
    else:
        parts = list(_DEFAULT_COMMANDS[agent])

    rendered = [
        part.format(
            prompt_path=str(prompt_path),
            cwd=str(_ROOT_DIR),
            phase=phase,
            run_id=state.run_id,
            iteration=state.iteration,
            phase_attempt=state.phase_attempt,
            agent=agent,
        )
        for part in parts
    ]

    executable = rendered[0]
    if not _command_exists(executable):
        raise RuntimeError(
            f"Agent command not found for '{agent}': {executable}. "
            f"Set {_ENV_VAR_BY_AGENT[agent]} to the correct CLI invocation."
        )

    return rendered


def _parse_command(value: str) -> list[str]:
    value = value.strip()
    if not value:
        raise ValueError("Agent command cannot be empty")

    if value.startswith("["):
        parsed = json.loads(value)
        if not isinstance(parsed, list) or not parsed or not all(isinstance(x, str) for x in parsed):
            raise ValueError("Agent command JSON must be a non-empty string array")
        return parsed

    return shlex.split(value, posix=(os.name != "nt"))


def _command_exists(executable: str) -> bool:
    if os.path.isabs(executable):
        return Path(executable).exists()
    if any(sep in executable for sep in ("/", "\\")):
        return Path(executable).exists()
    return shutil.which(executable) is not None
