# Codex Review Prompt Template

## Role

You are Codex acting in the `reviewing` phase.

## Runtime Metadata

- run_id: `run-20260323-032347-7909cac2`
- iteration: `1`
- phase: `reviewing`
- phase_attempt: `1`
- producer: `codex`
- requirement_sha256: `8f3213525ddbef9007378778496958a1b1f7ad3e6f9ec8c28e65f4730eb9f519`
- design_sha256: `43448fd7557c12532d0189322569ae4758bc73d11e98da449660e261f33547e2`
- review_target_commit: `unset`

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
run_id: run-20260323-032347-7909cac2
iteration: 1
phase: reviewing
phase_attempt: 1
producer: codex
created_at: <ISO 8601 with timezone, e.g. 2026-03-26T12:00:00+00:00>
input_fingerprint:
  requirement_sha256: 8f3213525ddbef9007378778496958a1b1f7ad3e6f9ec8c28e65f4730eb9f519
  design_sha256: 43448fd7557c12532d0189322569ae4758bc73d11e98da449660e261f33547e2
---
```

### `.ai-loop/artifacts/current/review.json`

Must follow this JSON schema:

```json
{
  "artifact_type": "review",
  "artifact_version": 1,
  "run_id": "run-20260323-032347-7909cac2",
  "iteration": 1,
  "phase": "reviewing",
  "phase_attempt": 1,
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
    "requirement_sha256": "8f3213525ddbef9007378778496958a1b1f7ad3e6f9ec8c28e65f4730eb9f519",
    "design_sha256": "43448fd7557c12532d0189322569ae4758bc73d11e98da449660e261f33547e2"
  }
}
```

**Field rules:**
- `result` must be exactly one of: `pass`, `fail`, or `blocked`
- `run_id`, `iteration`, `phase_attempt` must match the values above --copy them exactly
- Each issue in `issues` must have: `id`, `severity` (`critical`|`non_critical`), `description`, `requires_design_change` (boolean)
