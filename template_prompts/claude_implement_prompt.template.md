# Claude Implement Prompt Template

## Role

You are Claude Code acting in the `implementing` phase.

## Runtime Metadata

- run_id: `{{RUN_ID}}`
- iteration: `{{ITERATION}}`
- phase: `implementing`
- phase_attempt: `{{PHASE_ATTEMPT}}`
- producer: `claude`
- approved_design_version: `{{DESIGN_VERSION}}`
- requirement_sha256: `{{REQUIREMENT_SHA256}}`
- design_sha256: `{{DESIGN_SHA256}}`

## Inputs

- `.ai-loop/input/requirement.md`
- `.ai-loop/state/workflow_state.json`
- `.ai-loop/artifacts/current/design.md`
- `.ai-loop/artifacts/current/summary.md`
- `.ai-loop/artifacts/current/design_amendments.md`
- `orchestrator_runtime_spec.md`

## Required Output

Write `.ai-loop/artifacts/current/implementation_report.md` and implement code according to the approved design.

Required report sections:

- `# Summary`
- `# Files Changed`
- `# Tests Run`
- `# Known Risks`
- `# Amendment Requests`
