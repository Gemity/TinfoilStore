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

Update:

- `.ai-loop/artifacts/current/review.md`
- `.ai-loop/artifacts/current/review.json`
