# Embedded Workspace Checklist

Use this checklist when HiveMind has been copied into another project or feature workspace.

1. Verify the embedded package includes:
   - `orchestrator/`
   - `tests/`
   - `skills/`
   - `orchestrator_runtime_spec.md`
   - `.ai-loop/`
2. Read `.ai-loop/input/requirement.md`.
3. Read `.ai-loop/state/workflow_state.json`.
4. Confirm the current phase and owning agent:
   - `designing` and `reviewing` are owned by Codex
   - `implementing` and `fixing` are owned by Claude
5. Read the current phase's required artifacts from `.ai-loop/artifacts/current/`.
6. If execution should start now, run `py -m orchestrator run` or `bash run`.
7. If the task is analysis only, summarize the recovered phase state before suggesting changes.
