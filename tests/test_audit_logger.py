"""Tests for orchestrator.audit_logger — agent session and orchestrator logs."""

import json
from pathlib import Path

from orchestrator.audit_logger import (
    log_agent_error,
    log_agent_session,
    log_event,
    log_orchestrator,
)


class TestLogEvent:
    def test_appends_json_line(self, tmp_path: Path):
        log_path = tmp_path / "audit.log"
        log_event("test_event", "designing", "run-1", 1, "hello", log_path=log_path)
        log_event("test_event", "designing", "run-1", 1, "world", log_path=log_path)

        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["event_type"] == "test_event"
        assert entry["message"] == "hello"

    def test_includes_details(self, tmp_path: Path):
        log_path = tmp_path / "audit.log"
        log_event("x", "designing", "run-1", 1, "msg", details={"key": "val"}, log_path=log_path)

        entry = json.loads(log_path.read_text(encoding="utf-8").strip())
        assert entry["details"]["key"] == "val"


class TestLogAgentSession:
    def test_writes_full_session(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("orchestrator.audit_logger.AGENT_LOGS_DIR", tmp_path)

        result = {
            "agent": "codex",
            "command": ["codex", "exec", "-"],
            "returncode": 0,
            "ok": True,
            "stdout": "design output here",
            "stderr": "some warnings",
        }
        log_path = log_agent_session("run-123", "designing", 1, result, "prompt.md")

        assert log_path.exists()
        content = log_path.read_text(encoding="utf-8")
        assert "run-123" in content
        assert "designing" in content
        assert "codex" in content
        assert "design output here" in content
        assert "some warnings" in content
        assert "prompt.md" in content

    def test_handles_empty_output(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("orchestrator.audit_logger.AGENT_LOGS_DIR", tmp_path)

        result = {
            "agent": "claude",
            "command": ["claude", "-p"],
            "returncode": 1,
            "ok": False,
            "stdout": "",
            "stderr": "",
        }
        log_path = log_agent_session("run-456", "implementing", 2, result, "p.md")

        content = log_path.read_text(encoding="utf-8")
        assert "(empty)" in content


class TestLogAgentError:
    def test_writes_exception_and_traceback(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr("orchestrator.audit_logger.AGENT_LOGS_DIR", tmp_path)

        try:
            raise FileNotFoundError("codex not found")
        except FileNotFoundError as exc:
            log_path = log_agent_error(
                "run-err", "designing", 1, exc,
                command=["codex", "exec", "-"],
                prompt_path="prompt.md",
            )

        content = log_path.read_text(encoding="utf-8")
        assert "FileNotFoundError" in content
        assert "codex not found" in content
        assert "TRACEBACK" in content
        assert "run-err" in content


class TestLogOrchestrator:
    def test_appends_structured_line(self, tmp_path: Path):
        log_path = tmp_path / "orchestrator.log"
        log_orchestrator("INFO", "run-1", "designing", "Lock acquired", log_path=log_path)
        log_orchestrator("ERROR", "run-1", "designing", "Something failed", log_path=log_path)

        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert "[INFO]" in lines[0]
        assert "Lock acquired" in lines[0]
        assert "[ERROR]" in lines[1]
        assert "Something failed" in lines[1]
