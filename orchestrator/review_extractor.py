"""Extract review artifacts from Codex agent stdout.

Codex runs in read-only sandbox mode and cannot write files directly.
This module parses its stdout to extract the review.md and review.json
content, then writes them to the artifacts directory.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Optional, Tuple


def extract_review_artifacts(stdout: str) -> Tuple[Optional[str], Optional[dict]]:
    """Extract review.md content and review.json dict from Codex stdout.

    Codex outputs the artifacts inside fenced code blocks:
      ```md ... ```   or   ```markdown ... ```   for review.md
      ```json ... ```  for review.json

    Returns (review_md_content, review_json_dict).
    Either may be None if extraction fails.
    """
    review_md = _extract_markdown_block(stdout)
    review_json = _extract_json_block(stdout)
    return review_md, review_json


def _extract_markdown_block(text: str) -> Optional[str]:
    """Extract the first ```md or ```markdown fenced block containing frontmatter."""
    pattern = re.compile(
        r"```(?:md|markdown)\s*\n(---\n.+?\n---\n.+?)```",
        re.DOTALL,
    )
    match = pattern.search(text)
    if match:
        return match.group(1).strip() + "\n"
    return None


def _extract_json_block(text: str) -> Optional[dict]:
    """Extract the first ```json fenced block that parses as a review artifact."""
    pattern = re.compile(r"```json\s*\n(\{.+?\})\s*\n```", re.DOTALL)
    for match in pattern.finditer(text):
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and data.get("artifact_type") == "review":
                return data
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def normalize_review_json(data: dict) -> dict:
    """Normalize Codex output to match the schema expected by the validator.

    Handles known discrepancies:
    - Codex may output 'non_critical_count' instead of 'major_count'/'minor_count'
    - Ensures 'metadata' wrapper exists for ReviewArtifact.from_dict()
    - Ensures summary fields use the correct names
    """
    # Ensure top-level metadata wrapper
    if "metadata" not in data or not isinstance(data.get("metadata"), dict):
        data["metadata"] = {
            "artifact_type": data.get("artifact_type", "review"),
            "artifact_version": data.get("artifact_version", 1),
            "run_id": data.get("run_id", ""),
            "iteration": data.get("iteration", 0),
            "phase": data.get("phase", "reviewing"),
            "phase_attempt": data.get("phase_attempt", 0),
            "producer": data.get("producer", "codex"),
            "created_at": data.get("created_at", ""),
        }

    # Normalize summary: convert non_critical_count → major_count if needed
    summary = data.get("summary", {})
    if "non_critical_count" in summary and "major_count" not in summary:
        summary["major_count"] = summary.pop("non_critical_count")
    if "minor_count" not in summary:
        summary["minor_count"] = 0
    data["summary"] = summary

    # Ensure approved_design_version exists
    if "approved_design_version" not in data:
        data["approved_design_version"] = 0

    return data


def write_review_artifacts(
    review_md: str,
    review_json: dict,
    artifacts_dir: Path,
) -> Tuple[Path, Path]:
    """Write review.md and review.json to the artifacts directory.

    Returns (review_md_path, review_json_path).
    """
    from orchestrator.fileutil import atomic_write

    md_path = artifacts_dir / "review.md"
    json_path = artifacts_dir / "review.json"

    atomic_write(md_path, review_md)
    atomic_write(json_path, json.dumps(review_json, indent=2, ensure_ascii=False) + "\n")

    return md_path, json_path
