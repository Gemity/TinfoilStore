"""Tests for orchestrator.agent_runner."""

from pathlib import Path

import pytest

from orchestrator.agent_runner import get_agent_for_phase, run_agent
from orchestrator.models import RequirementRef, WorkflowState


def _make_state(**overrides) -> WorkflowState:
    defaults = dict(
        run_id="run-20260323-120000-abcdef12",
        phase="designing",
        iteration=1,
        phase_attempt=2,
        requirement=RequirementRef(path=".ai-loop/input/requirement.md", sha256="abc123"),
    )
    defaults.update(overrides)
    return WorkflowState(**defaults)


class TestGetAgentForPhase:
    def test_design_and_review_use_codex(self):
        assert get_agent_for_phase("designing") == "codex"
        assert get_agent_for_phase("reviewing") == "codex"

    def test_implement_and_fix_use_claude(self):
        assert get_agent_for_phase("implementing") == "claude"
        assert get_agent_for_phase("fixing") == "claude"

    def test_done_has_no_agent(self):
        with pytest.raises(ValueError):
            get_agent_for_phase("done")


class TestRunAgent:
    def test_uses_env_command_template(self, tmp_path: Path, monkeypatch):
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("hello agent", encoding="utf-8")
        state = _make_state(phase="designing")

        monkeypatch.setenv(
            "HIVEMIND_CODEX_COMMAND",
            "codex exec --cwd {cwd} --phase {phase} {prompt_path}",
        )
        monkeypatch.setattr("orchestrator.agent_runner._resolve_executable", lambda executable: "C:/tools/codex.exe")

        seen = {}

        def fake_run(command, cwd, input, text, capture_output, check, **kwargs):
            seen["command"] = command
            seen["cwd"] = cwd
            seen["input"] = input

            class Result:
                returncode = 0
                stdout = "ok"
                stderr = ""

            return Result()

        monkeypatch.setattr("orchestrator.agent_runner.subprocess.run", fake_run)

        result = run_agent(state, "designing", str(prompt_path))

        assert result["ok"] is True
        assert result["agent"] == "codex"
        assert seen["input"] == "hello agent"
        assert seen["command"][0] == "C:/tools/codex.exe"
        assert "--phase" in seen["command"]
        assert str(prompt_path) in seen["command"]

    def test_supports_json_array_command(self, tmp_path: Path, monkeypatch):
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("review prompt", encoding="utf-8")
        state = _make_state(phase="reviewing")

        monkeypatch.setenv(
            "HIVEMIND_CODEX_COMMAND",
            '["codex", "exec", "--phase", "{phase}", "{prompt_path}"]',
        )
        monkeypatch.setattr("orchestrator.agent_runner._resolve_executable", lambda executable: "C:/tools/codex.exe")

        def fake_run(command, cwd, input, text, capture_output, check, **kwargs):
            class Result:
                returncode = 0
                stdout = ""
                stderr = ""

            assert command[0] == "C:/tools/codex.exe"
            assert command[3] == "reviewing"
            assert command[4] == str(prompt_path)
            return Result()

        monkeypatch.setattr("orchestrator.agent_runner.subprocess.run", fake_run)

        result = run_agent(state, "reviewing", str(prompt_path))
        assert result["ok"] is True

    def test_missing_command_raises_helpful_error(self, tmp_path: Path, monkeypatch):
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("implement prompt", encoding="utf-8")
        state = _make_state(phase="implementing")

        monkeypatch.delenv("HIVEMIND_CLAUDE_COMMAND", raising=False)
        monkeypatch.setattr("orchestrator.agent_runner._resolve_executable", lambda executable: None)

        with pytest.raises(RuntimeError, match="HIVEMIND_CLAUDE_COMMAND"):
            run_agent(state, "implementing", str(prompt_path))

    def test_wraps_startup_failure_with_actionable_message(self, tmp_path: Path, monkeypatch):
        prompt_path = tmp_path / "prompt.md"
        prompt_path.write_text("design prompt", encoding="utf-8")
        state = _make_state(phase="designing")

        monkeypatch.delenv("HIVEMIND_CODEX_COMMAND", raising=False)
        monkeypatch.setattr("orchestrator.agent_runner._resolve_executable", lambda executable: "C:/tools/codex.exe")

        def fake_run(command, cwd, input, text, capture_output, check, **kwargs):
            raise FileNotFoundError("[WinError 2] The system cannot find the file specified")

        monkeypatch.setattr("orchestrator.agent_runner.subprocess.run", fake_run)

        with pytest.raises(RuntimeError, match="HIVEMIND_CODEX_COMMAND"):
            run_agent(state, "designing", str(prompt_path))
