# Codex Design Prompt Template

## Role

You are Codex acting in the `designing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `designing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `codex`
- artifact_version: `1`
- target_design_version: `{{TARGET_DESIGN_VERSION}}`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`

## Inputs

- `.ai-loop/input/requirement.md`
- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/summary.md`
- `.ai-loop/artifacts/current/design_amendments.md`
- `orchestrator_runtime_spec.md`

## Required Output

Write `.ai-loop/artifacts/current/design.md` with approved design metadata and these sections:

- `# Objective`
- `# Scope`
- `# Constraints`
- `# Architecture`
- `# Execution Plan`
- `# Acceptance Criteria`
- `# Non-Goals`
