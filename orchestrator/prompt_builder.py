"""Prompt assembly for each phase.

Builds self-contained prompts by resolving templates, substituting
placeholders, and inlining the content of all input artifacts so that
stateless agents (Claude -p, Codex exec) have full context in a single
prompt text.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from orchestrator.models import Phase, WorkflowState


_ROOT_DIR = Path(__file__).resolve().parent.parent
_TEMPLATE_DIRS = (
    _ROOT_DIR / "template" / "prompts",
    _ROOT_DIR / "template_prompts",
)
_INPUT_DIR = _ROOT_DIR / ".ai-loop" / "input"
_ARTIFACTS_DIR = _ROOT_DIR / ".ai-loop" / "artifacts" / "current"

_PHASE_TEMPLATE_MAP = {
    Phase.DESIGNING: (
        "codex_design_prompt.template.md",
        _INPUT_DIR / "codex_design_prompt.md",
    ),
    Phase.IMPLEMENTING: (
        "claude_implement_prompt.template.md",
        _INPUT_DIR / "claude_implement_prompt.md",
    ),
    Phase.REVIEWING: (
        "codex_review_prompt.template.md",
        _INPUT_DIR / "codex_review_prompt.md",
    ),
    Phase.FIXING: (
        "claude_fix_prompt.template.md",
        _INPUT_DIR / "claude_fix_prompt.md",
    ),
}

# Files to inline per phase. Paths are relative to _ROOT_DIR.
# Each entry is (label, relative_path).
_PHASE_INLINE_FILES: dict[Phase, List[Tuple[str, str]]] = {
    Phase.DESIGNING: [
        ("requirement.md", ".ai-loop/input/requirement.md"),
        ("summary.md", ".ai-loop/artifacts/current/summary.md"),
        ("design_amendments.md", ".ai-loop/artifacts/current/design_amendments.md"),
    ],
    Phase.IMPLEMENTING: [
        ("requirement.md", ".ai-loop/input/requirement.md"),
        ("design.md", ".ai-loop/artifacts/current/design.md"),
        ("design_amendments.md", ".ai-loop/artifacts/current/design_amendments.md"),
    ],
    Phase.REVIEWING: [
        ("requirement.md", ".ai-loop/input/requirement.md"),
        ("design.md", ".ai-loop/artifacts/current/design.md"),
        ("implementation_report.md", ".ai-loop/artifacts/current/implementation_report.md"),
        ("design_amendments.md", ".ai-loop/artifacts/current/design_amendments.md"),
    ],
    Phase.FIXING: [
        ("design.md", ".ai-loop/artifacts/current/design.md"),
        ("review.md", ".ai-loop/artifacts/current/review.md"),
        ("review.json", ".ai-loop/artifacts/current/review.json"),
        ("implementation_report.md", ".ai-loop/artifacts/current/implementation_report.md"),
    ],
}


def _resolve_template_path(template_name: str) -> Path:
    """Resolve a prompt template from supported embedded workspace locations."""
    for template_dir in _TEMPLATE_DIRS:
        candidate = template_dir / template_name
        if candidate.exists():
            return candidate
    searched = ", ".join(str(template_dir / template_name) for template_dir in _TEMPLATE_DIRS)
    raise FileNotFoundError(f"Prompt template not found. Searched: {searched}")


def _read_file_safe(path: Path) -> str | None:
    """Read a file, returning None if it doesn't exist or is empty."""
    try:
        content = path.read_text(encoding="utf-8").strip()
        return content if content else None
    except (FileNotFoundError, OSError):
        return None


def _build_inline_section(phase: Phase) -> str:
    """Build the inline context section for a phase by reading input files."""
    entries = _PHASE_INLINE_FILES.get(phase, [])
    if not entries:
        return ""

    parts = ["\n\n---\n\n## Inline Context\n"]
    parts.append("The following artifact contents are provided inline so you have full context.\n")

    for label, rel_path in entries:
        full_path = _ROOT_DIR / rel_path
        content = _read_file_safe(full_path)
        if content is None:
            parts.append(f"\n### {label}\n\n*(file not found or empty: `{rel_path}`)*\n")
        else:
            parts.append(f"\n### {label}\n\n```\n{content}\n```\n")

    return "\n".join(parts)


def get_prompt_output_path(phase: str) -> Path:
    """Return the canonical prompt package path for a workflow phase."""
    phase_enum = Phase(phase)
    if phase_enum not in _PHASE_TEMPLATE_MAP:
        raise ValueError(f"No prompt package is defined for phase: {phase}")
    return _PHASE_TEMPLATE_MAP[phase_enum][1]


def build_prompt(state: WorkflowState, phase: str) -> str:
    """Build a self-contained prompt package for the given phase.

    Resolves the template, substitutes placeholders, and appends inline
    content of all input artifacts so stateless agents have full context.
    """
    phase_enum = Phase(phase)
    if phase_enum not in _PHASE_TEMPLATE_MAP:
        raise ValueError(f"No prompt template is defined for phase: {phase}")

    template_name, _ = _PHASE_TEMPLATE_MAP[phase_enum]
    template_path = _resolve_template_path(template_name)
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

    # Append inline context
    prompt += _build_inline_section(phase_enum)

    return prompt
