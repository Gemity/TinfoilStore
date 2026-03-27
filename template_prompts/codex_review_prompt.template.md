# Codex Review Prompt Template

## Role

You are Codex acting in the `reviewing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `reviewing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `codex`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`
- design_sha256: `{{DESIGN_SHA256}}`
- review_target_commit: `{{REVIEW_TARGET_COMMIT}}`

## Inputs

- `.ai-loop/input/requirement.md`
- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/design.md`
- `.ai-loop/artifacts/current/implementation_report.md`
- `.ai-loop/artifacts/current/design_amendments.md`
- relevant code diff

## Required Output

Write both review artifacts:

### `.ai-loop/artifacts/current/review.md`

Must start with this exact YAML frontmatter format:

```yaml
---
artifact_type: review
artifact_version: 1
run_id: {{RUN_ID}}
iteration: {{ITERATION}}
phase: reviewing
phase_attempt: {{PHASE_ATTEMPT}}
producer: codex
created_at: <ISO 8601 with timezone, e.g. 2026-03-26T12:00:00+00:00>
input_fingerprint:
  requirement_sha256: {{REQUIREMENT_SHA256}}
  design_sha256: {{DESIGN_SHA256}}
---
```

### `.ai-loop/artifacts/current/review.json`

Must follow this JSON schema:

```json
{
  "artifact_type": "review",
  "artifact_version": 1,
  "run_id": "{{RUN_ID}}",
  "iteration": {{ITERATION}},
  "phase": "reviewing",
  "phase_attempt": {{PHASE_ATTEMPT}},
  "producer": "codex",
  "created_at": "<ISO 8601 with timezone>",
  "result": "pass|fail|blocked",
  "summary": {
    "design_change_required": false,
    "total_issues": 0,
    "critical_count": 0,
    "non_critical_count": 0,
    "notes": ""
  },
  "issues": [],
  "blocking_reason": null,
  "input_fingerprint": {
    "requirement_sha256": "{{REQUIREMENT_SHA256}}",
    "design_sha256": "{{DESIGN_SHA256}}"
  }
}
```

**Field rules:**
- `result` must be exactly one of: `pass`, `fail`, or `blocked`
- `run_id`, `iteration`, `phase_attempt` must match the values above --copy them exactly
- Each issue in `issues` must have: `id`, `severity` (`critical`|`non_critical`), `description`, `requires_design_change` (boolean)
