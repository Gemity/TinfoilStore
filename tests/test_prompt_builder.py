"""Tests for orchestrator.prompt_builder."""

from pathlib import Path

from orchestrator.prompt_builder import build_prompt, get_prompt_output_path
from orchestrator.models import (
    CurrentInputs,
    DesignRef,
    GitInfo,
    RequirementRef,
    WorkflowState,
)


def _make_state(**overrides) -> WorkflowState:
    defaults = dict(
        run_id="run-20260323-120000-abcdef12",
        phase="designing",
        iteration=2,
        phase_attempt=3,
        requirement=RequirementRef(path=".ai-loop/input/requirement.md", sha256="req-sha"),
        design=DesignRef(version=1, sha256="design-sha", status="approved"),
        current_inputs=CurrentInputs(
            requirement_sha256="req-sha",
            design_sha256="design-sha",
            review_target_commit="abc123def",
        ),
        git=GitInfo(head_commit="head-commit"),
    )
    defaults.update(overrides)
    return WorkflowState(**defaults)


class TestBuildPrompt:
    def test_design_prompt_injects_runtime_values(self):
        state = _make_state(phase="designing")
        prompt = build_prompt(state, "designing")
        assert "run-20260323-120000-abcdef12" in prompt
        assert "`2`" in prompt
        assert "`3`" in prompt
        assert "`2`" in prompt  # target design version = current version + 1
        assert "req-sha" in prompt

    def test_review_prompt_uses_commit_and_design_sha(self):
        state = _make_state(phase="reviewing")
        prompt = build_prompt(state, "reviewing")
        assert "design-sha" in prompt
        assert "abc123def" in prompt

    def test_fix_prompt_output_path(self):
        output = get_prompt_output_path("fixing")
        assert output == Path(".ai-loop/input/claude_fix_prompt.md").resolve()

    def test_unknown_phase_raises(self):
        state = _make_state()
        try:
            build_prompt(state, "needs_human")
        except ValueError as exc:
            assert "No prompt template" in str(exc)
        else:
            raise AssertionError("Expected ValueError for unsupported phase")
