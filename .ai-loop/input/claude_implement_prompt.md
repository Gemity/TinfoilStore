# Claude Implement Prompt Template

## Role

You are Claude Code acting in the `implementing` phase.

## Runtime Metadata

- run_id: `run-20260323-032347-7909cac2`
- iteration: `1`
- phase: `implementing`
- phase_attempt: `1`
- producer: `claude`
- approved_design_version: `1`
- requirement_sha256: `8f3213525ddbef9007378778496958a1b1f7ad3e6f9ec8c28e65f4730eb9f519`
- design_sha256: `43448fd7557c12532d0189322569ae4758bc73d11e98da449660e261f33547e2`

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
