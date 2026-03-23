"""Prompt assembly for each phase."""

from __future__ import annotations

from pathlib import Path

from orchestrator.models import Phase, WorkflowState


_ROOT_DIR = Path(__file__).resolve().parent.parent
_TEMPLATE_DIR = _ROOT_DIR / "template" / "prompts"
_INPUT_DIR = _ROOT_DIR / ".ai-loop" / "input"

_PHASE_TEMPLATE_MAP = {
    Phase.DESIGNING: (
        _TEMPLATE_DIR / "codex_design_prompt.template.md",
        _INPUT_DIR / "codex_design_prompt.md",
    ),
    Phase.IMPLEMENTING: (
        _TEMPLATE_DIR / "claude_implement_prompt.template.md",
        _INPUT_DIR / "claude_implement_prompt.md",
    ),
    Phase.REVIEWING: (
        _TEMPLATE_DIR / "codex_review_prompt.template.md",
        _INPUT_DIR / "codex_review_prompt.md",
    ),
    Phase.FIXING: (
        _TEMPLATE_DIR / "claude_fix_prompt.template.md",
        _INPUT_DIR / "claude_fix_prompt.md",
    ),
}


def get_prompt_output_path(phase: str) -> Path:
    """Return the canonical prompt package path for a workflow phase."""
    phase_enum = Phase(phase)
    if phase_enum not in _PHASE_TEMPLATE_MAP:
        raise ValueError(f"No prompt package is defined for phase: {phase}")
    return _PHASE_TEMPLATE_MAP[phase_enum][1]


def build_prompt(state: WorkflowState, phase: str) -> str:
    """Build a deterministic prompt package for the given phase."""
    phase_enum = Phase(phase)
    if phase_enum not in _PHASE_TEMPLATE_MAP:
        raise ValueError(f"No prompt template is defined for phase: {phase}")

    template_path, _ = _PHASE_TEMPLATE_MAP[phase_enum]
    template = template_path.read_text(encoding="utf-8")

    replacements = {
        "{{RUN_ID}}": state.run_id,
        "{{ITERATION}}": str(state.iteration),
        "{{PHASE_ATTEMPT}}": str(state.phase_attempt),
        "{{TARGET_DESIGN_VERSION}}": str(max(1, state.design.version + 1)),
        "{{DESIGN_VERSION}}": str(state.design.version),
        "{{REQUIREMENT_SHA256}}": state.current_inputs.requirement_sha256 or state.requirement.sha256,
        "{{DESIGN_SHA256}}": state.current_inputs.design_sha256 or state.design.sha256 or "unset",
        "{{REVIEW_TARGET_COMMIT}}": state.current_inputs.review_target_commit or state.git.head_commit or "unset",
    }

    prompt = template
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)

    return prompt
