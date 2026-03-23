"""Tests for orchestrator.human_gate_config."""

import json
from pathlib import Path

from orchestrator.human_gate_config import get_gate_policy, requires_human_approval


class TestGetGatePolicy:
    def test_reads_manual_from_config(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({
            "transitions": {
                "designing -> implementing": "manual",
            }
        }))
        assert get_gate_policy("designing", "implementing", path=config_path) == "manual"

    def test_reads_auto_from_config(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({
            "transitions": {
                "implementing -> reviewing": "auto",
            }
        }))
        assert get_gate_policy("implementing", "reviewing", path=config_path) == "auto"

    def test_falls_back_to_defaults_on_missing_key(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({"transitions": {}}))
        # Built-in default for designing -> implementing is "manual"
        assert get_gate_policy("designing", "implementing", path=config_path) == "manual"

    def test_falls_back_to_auto_for_unknown_transition(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({"transitions": {}}))
        assert get_gate_policy("unknown", "phase", path=config_path) == "auto"

    def test_falls_back_on_missing_file(self, tmp_path: Path):
        config_path = tmp_path / "nonexistent.json"
        # Uses built-in defaults
        assert get_gate_policy("designing", "implementing", path=config_path) == "manual"
        assert get_gate_policy("implementing", "reviewing", path=config_path) == "auto"

    def test_ignores_invalid_policy_value(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({
            "transitions": {
                "designing -> implementing": "invalid_value",
            }
        }))
        # Falls back to built-in default
        assert get_gate_policy("designing", "implementing", path=config_path) == "manual"


class TestRequiresHumanApproval:
    def test_manual_requires_approval(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({
            "transitions": {"designing -> implementing": "manual"}
        }))
        assert requires_human_approval("designing", "implementing", path=config_path) is True

    def test_auto_does_not_require_approval(self, tmp_path: Path):
        config_path = tmp_path / "gates.json"
        config_path.write_text(json.dumps({
            "transitions": {"implementing -> reviewing": "auto"}
        }))
        assert requires_human_approval("implementing", "reviewing", path=config_path) is False
