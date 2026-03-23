"""Tests for orchestrator.state_manager."""

import json
import re
from pathlib import Path

import pytest

from orchestrator.models import (
    HumanGate,
    Phase,
    RequirementRef,
    RunStatus,
    WorkflowState,
)
from orchestrator.state_manager import (
    generate_run_id,
    increment_iteration,
    increment_phase_attempt,
    init_state,
    load_state,
    mark_completed,
    open_human_gate,
    record_phase_success,
    save_state,
    set_phase,
    validate_state,
)


def _make_valid_state() -> WorkflowState:
    return WorkflowState(
        state_version=1,
        run_id="run-20260323-120000-abcdef12",
        status="active",
        phase="designing",
        phase_attempt=1,
        iteration=1,
        max_iterations=6,
        requirement=RequirementRef(path="req.md", sha256="abc123"),
    )


class TestLoadSave:
    def test_round_trip(self, tmp_path: Path):
        state = _make_valid_state()
        path = tmp_path / "state.json"
        save_state(state, path)
        loaded = load_state(path)
        assert loaded.run_id == state.run_id
        assert loaded.phase == state.phase

    def test_load_rejects_bad_version(self, tmp_path: Path):
        state = _make_valid_state()
        state.state_version = 99
        path = tmp_path / "state.json"
        data = json.dumps(state.to_dict(), indent=2)
        path.write_text(data)
        with pytest.raises(ValueError, match="state_version"):
            load_state(path)

    def test_load_file_not_found(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_state(tmp_path / "missing.json")


class TestValidateState:
    def test_valid_state(self):
        state = _make_valid_state()
        result = validate_state(state)
        assert result.valid

    def test_empty_run_id(self):
        state = _make_valid_state()
        state.run_id = ""
        result = validate_state(state)
        assert not result.valid
        assert any("run_id" in e for e in result.errors)

    def test_bad_run_id_format(self):
        state = _make_valid_state()
        state.run_id = "bad-format"
        result = validate_state(state)
        assert not result.valid

    def test_unknown_phase(self):
        state = _make_valid_state()
        state.phase = "flying"
        result = validate_state(state)
        assert not result.valid

    def test_iteration_zero(self):
        state = _make_valid_state()
        state.iteration = 0
        result = validate_state(state)
        assert not result.valid


class TestMutationHelpers:
    def test_set_phase(self):
        state = _make_valid_state()
        new = set_phase(state, Phase.IMPLEMENTING)
        assert new.phase == "implementing"
        assert new.phase_attempt == 1
        assert state.phase == "designing"  # original unchanged

    def test_record_phase_success(self):
        state = _make_valid_state()
        new = record_phase_success(state, Phase.DESIGNING)
        assert new.last_completed_phase == "designing"
        assert new.last_completed_at is not None

    def test_open_human_gate(self):
        state = _make_valid_state()
        new = open_human_gate(state, "test reason", "details")
        assert new.human_gate.required is True
        assert new.human_gate.reason == "test reason"
        assert new.status == "waiting_human"
        assert new.phase == "needs_human"

    def test_increment_iteration(self):
        state = _make_valid_state()
        state.phase_attempt = 3
        new = increment_iteration(state)
        assert new.iteration == 2
        assert new.phase_attempt == 1  # reset

    def test_increment_phase_attempt(self):
        state = _make_valid_state()
        new = increment_phase_attempt(state)
        assert new.phase_attempt == 2

    def test_mark_completed(self):
        state = _make_valid_state()
        new = mark_completed(state)
        assert new.status == "completed"
        assert new.phase == "done"


class TestGenerateRunId:
    def test_format(self):
        rid = generate_run_id()
        assert re.match(r"^run-\d{8}-\d{6}-[0-9a-f]{8}$", rid)

    def test_unique(self):
        ids = {generate_run_id() for _ in range(10)}
        assert len(ids) == 10


class TestInitState:
    def test_creates_valid_state(self, tmp_path: Path):
        req = tmp_path / "requirement.md"
        req.write_text("# Test Requirement")
        state = init_state(req)
        result = validate_state(state)
        assert result.valid
        assert state.phase == "designing"
        assert state.iteration == 1
        assert state.requirement.sha256 != ""
