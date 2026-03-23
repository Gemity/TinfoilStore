"""Tests for orchestrator.artifact_parser."""

import json
from pathlib import Path

from orchestrator.artifact_parser import (
    extract_markdown_sections,
    parse_json_artifact,
    parse_markdown_frontmatter,
    parse_review_json,
    parse_yaml_frontmatter,
)


class TestParseYamlFrontmatter:
    def test_basic_parsing(self):
        text = """---
artifact_type: design
artifact_version: 1
run_id: run-123
iteration: 1
phase: designing
---

# Body here
"""
        result = parse_yaml_frontmatter(text)
        assert result["artifact_type"] == "design"
        assert result["artifact_version"] == 1
        assert result["run_id"] == "run-123"
        assert result["iteration"] == 1

    def test_boolean_and_null(self):
        text = """---
flag_true: true
flag_false: false
empty: null
---
"""
        result = parse_yaml_frontmatter(text)
        assert result["flag_true"] is True
        assert result["flag_false"] is False
        assert result["empty"] is None

    def test_no_frontmatter(self):
        text = "# Just a heading\nSome content"
        result = parse_yaml_frontmatter(text)
        assert result == {}

    def test_quoted_string(self):
        text = '---\nname: "hello world"\n---\n'
        result = parse_yaml_frontmatter(text)
        assert result["name"] == "hello world"


class TestParseMarkdownFrontmatter:
    def test_extracts_metadata_and_body(self, tmp_path: Path):
        content = """---
artifact_type: design
artifact_version: 1
run_id: run-20260323-000003-be751c2f
iteration: 1
phase: designing
phase_attempt: 1
producer: codex
created_at: 2026-03-23T00:07:21+07:00
---

# Objective

Design an orchestrator.
"""
        path = tmp_path / "design.md"
        path.write_text(content)

        metadata, body = parse_markdown_frontmatter(path)
        assert metadata.artifact_type == "design"
        assert metadata.run_id == "run-20260323-000003-be751c2f"
        assert metadata.producer == "codex"
        assert "# Objective" in body


class TestExtractMarkdownSections:
    def test_extracts_h1_sections(self):
        body = """
# Objective

Design an orchestrator.

# Scope

Everything in scope.

# Constraints

Local only.
"""
        sections = extract_markdown_sections(body)
        assert "Objective" in sections
        assert "Scope" in sections
        assert "Constraints" in sections
        assert "orchestrator" in sections["Objective"]

    def test_empty_body(self):
        sections = extract_markdown_sections("")
        assert sections == {}


class TestParseReviewJson:
    def test_parses_valid_review(self, tmp_path: Path):
        review_data = {
            "metadata": {
                "artifact_type": "review",
                "artifact_version": 1,
                "run_id": "run-123",
                "iteration": 1,
                "phase": "reviewing",
                "phase_attempt": 1,
                "producer": "codex",
                "created_at": "2026-01-01T00:00:00Z",
            },
            "result": "fail",
            "blocking_reason": None,
            "approved_design_version": 1,
            "issues": [
                {
                    "issue_id": "i1",
                    "severity": "critical",
                    "category": "correctness",
                    "title": "Bug",
                    "description": "A bug",
                    "file_paths": ["foo.py"],
                    "fix_instruction": "Fix it",
                    "requires_design_change": False,
                    "related_amendment_ids": [],
                    "fingerprint": "fp1",
                },
            ],
            "summary": {
                "total_issues": 1,
                "critical_count": 1,
                "major_count": 0,
                "minor_count": 0,
                "design_change_required": False,
            },
        }
        path = tmp_path / "review.json"
        path.write_text(json.dumps(review_data))

        review = parse_review_json(path)
        assert review.result == "fail"
        assert len(review.issues) == 1
        assert review.issues[0].severity == "critical"
        assert review.summary.critical_count == 1

    def test_parses_top_level_metadata_review(self, tmp_path: Path):
        """ISS-002: spec defines metadata at top level, not nested."""
        review_data = {
            "artifact_type": "review",
            "artifact_version": 1,
            "run_id": "run-top-level",
            "iteration": 1,
            "phase": "reviewing",
            "phase_attempt": 1,
            "producer": "codex",
            "created_at": "2026-01-01T00:00:00Z",
            "result": "pass",
            "blocking_reason": None,
            "approved_design_version": 1,
            "issues": [],
            "summary": {
                "total_issues": 0,
                "critical_count": 0,
                "major_count": 0,
                "minor_count": 0,
                "design_change_required": False,
            },
        }
        path = tmp_path / "review.json"
        path.write_text(json.dumps(review_data))

        review = parse_review_json(path)
        assert review.result == "pass"
        assert review.metadata.run_id == "run-top-level"
        assert review.metadata.producer == "codex"
