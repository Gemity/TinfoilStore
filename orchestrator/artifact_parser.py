"""Artifact parsing: extract metadata and sections from markdown/JSON artifacts.

Maps to design section 'artifact_models' parsing and runtime spec sections 5-6.
Parser extracts structure only - validation is the validator's job.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Tuple

from orchestrator.models import ArtifactMetadata, ReviewArtifact


def parse_yaml_frontmatter(text: str) -> dict:
    """Parse YAML-like front matter from text between --- delimiters.

    Implements a minimal key-value parser for flat scalar values.
    Does not require pyyaml - handles the simple metadata format used by artifacts.
    """
    lines = text.split("\n")

    # Find opening ---
    start = -1
    for i, line in enumerate(lines):
        if line.strip() == "---":
            start = i
            break

    if start == -1:
        return {}

    # Find closing ---
    end = -1
    for i in range(start + 1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break

    if end == -1:
        return {}

    # Parse key: value pairs
    result = {}
    for line in lines[start + 1 : end]:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*:\s*(.*)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            result[key] = _coerce_value(value)

    return result


def _coerce_value(value: str):
    """Coerce a YAML scalar string to the appropriate Python type."""
    if value == "" or value.lower() == "null" or value == "~":
        return None
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    # Try integer
    try:
        return int(value)
    except ValueError:
        pass
    # Try float
    try:
        return float(value)
    except ValueError:
        pass
    # Strip quotes if present
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def parse_markdown_frontmatter(path: Path) -> Tuple[ArtifactMetadata, str]:
    """Parse YAML front matter from a markdown artifact file.

    Returns (metadata, body) where body is everything after the closing ---.
    """
    text = Path(path).read_text(encoding="utf-8")
    fm = parse_yaml_frontmatter(text)

    if not fm:
        return ArtifactMetadata(), text

    metadata = ArtifactMetadata.from_dict(fm)

    # Extract body (everything after second ---)
    lines = text.split("\n")
    dash_count = 0
    body_start = 0
    for i, line in enumerate(lines):
        if line.strip() == "---":
            dash_count += 1
            if dash_count == 2:
                body_start = i + 1
                break

    body = "\n".join(lines[body_start:])
    return metadata, body


def extract_markdown_sections(body: str) -> Dict[str, str]:
    """Extract H1 (# ) section headings and their content from markdown body.

    Returns a dict mapping heading text (without #) to section content.
    """
    sections: Dict[str, str] = {}
    current_heading = None
    current_lines = []

    for line in body.split("\n"):
        h1_match = re.match(r"^#\s+(.+)$", line)
        if h1_match:
            # Save previous section
            if current_heading is not None:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = h1_match.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    if current_heading is not None:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def parse_json_artifact(path: Path) -> dict:
    """Parse a JSON artifact file and return raw dict."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_review_json(path: Path) -> ReviewArtifact:
    """Parse review.json into structured ReviewArtifact."""
    data = parse_json_artifact(path)
    return ReviewArtifact.from_dict(data)
