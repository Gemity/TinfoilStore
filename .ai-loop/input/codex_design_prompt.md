# Codex Design Prompt Template

## Role

You are Codex acting in the `designing` phase.

## Runtime Metadata

- run_id: `run-20260323-032347-7909cac2`
- iteration: `1`
- phase: `designing`
- phase_attempt: `1`
- producer: `codex`
- artifact_version: `1`
- target_design_version: `1`
- requirement_sha256: `8f3213525ddbef9007378778496958a1b1f7ad3e6f9ec8c28e65f4730eb9f519`

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
