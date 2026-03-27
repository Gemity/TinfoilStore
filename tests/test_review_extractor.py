"""Tests for orchestrator.review_extractor."""

import json
import textwrap
from pathlib import Path

import pytest

from orchestrator.review_extractor import (
    extract_review_artifacts,
    normalize_review_json,
)


SAMPLE_STDOUT = textwrap.dedent("""\
    Some preamble text from Codex about reviewing the code...

    I could not write the artifacts because the workspace is read-only. Exact contents:

    ```md
    ---
    artifact_type: review
    artifact_version: 1
    run_id: run-123
    iteration: 1
    phase: reviewing
    phase_attempt: 1
    producer: codex
    created_at: 2026-03-27T12:00:00+07:00
    ---

    # Verdict

    Result: fail

    # Critical Issues

    ## RV-001
    - severity: critical
    - requires_design_change: false
    - description: Missing dependency.

    # Minor Issues

    None.

    # Amendment Decisions

    No design amendment required.

    # Notes For Next Iteration

    Fix the dependency.
    ```

    ```json
    {
      "artifact_type": "review",
      "artifact_version": 1,
      "run_id": "run-123",
      "iteration": 1,
      "phase": "reviewing",
      "phase_attempt": 1,
      "producer": "codex",
      "created_at": "2026-03-27T12:00:00+07:00",
      "result": "fail",
      "summary": {
        "design_change_required": false,
        "total_issues": 1,
        "critical_count": 1,
        "non_critical_count": 0,
        "notes": "Fix dep"
      },
      "issues": [
        {
          "id": "RV-001",
          "severity": "critical",
          "description": "Missing dependency.",
          "requires_design_change": false
        }
      ],
      "blocking_reason": null,
      "input_fingerprint": {
        "requirement_sha256": "abc123",
        "design_sha256": "def456"
      }
    }
    ```
""")


def test_extract_review_artifacts_from_stdout():
    review_md, review_json = extract_review_artifacts(SAMPLE_STDOUT)

    assert review_md is not None
    assert "artifact_type: review" in review_md
    assert "# Verdict" in review_md
    assert "# Critical Issues" in review_md

    assert review_json is not None
    assert review_json["result"] == "fail"
    assert review_json["summary"]["critical_count"] == 1
    assert len(review_json["issues"]) == 1


def test_extract_returns_none_on_empty():
    md, js = extract_review_artifacts("no code blocks here")
    assert md is None
    assert js is None


def test_extract_ignores_non_review_json():
    stdout = textwrap.dedent("""\
        ```json
        {"some_other": "data"}
        ```
    """)
    _, js = extract_review_artifacts(stdout)
    assert js is None


def test_normalize_adds_metadata_wrapper():
    data = {
        "artifact_type": "review",
        "artifact_version": 1,
        "run_id": "run-1",
        "iteration": 1,
        "phase": "reviewing",
        "phase_attempt": 1,
        "producer": "codex",
        "created_at": "2026-01-01T00:00:00Z",
        "result": "pass",
        "summary": {"total_issues": 0, "critical_count": 0, "non_critical_count": 0},
        "issues": [],
    }
    normalized = normalize_review_json(data)
    assert "metadata" in normalized
    assert normalized["metadata"]["run_id"] == "run-1"


def test_normalize_converts_non_critical_to_major():
    data = {
        "artifact_type": "review",
        "metadata": {"run_id": "x"},
        "result": "fail",
        "summary": {
            "total_issues": 2,
            "critical_count": 1,
            "non_critical_count": 1,
        },
        "issues": [],
    }
    normalized = normalize_review_json(data)
    assert "non_critical_count" not in normalized["summary"]
    assert normalized["summary"]["major_count"] == 1
    assert normalized["summary"]["minor_count"] == 0


def test_normalize_preserves_existing_major_count():
    data = {
        "artifact_type": "review",
        "metadata": {"run_id": "x"},
        "result": "pass",
        "summary": {
            "total_issues": 1,
            "critical_count": 0,
            "major_count": 1,
            "minor_count": 0,
        },
        "issues": [],
    }
    normalized = normalize_review_json(data)
    assert normalized["summary"]["major_count"] == 1
