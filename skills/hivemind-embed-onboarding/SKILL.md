---
name: hivemind-embed-onboarding
description: Reconstruct the embedded HiveMind orchestrator package inside a new project or feature workspace. Use when Codex or another agent is working in a repo that contains `orchestrator/`, `.ai-loop/`, `orchestrator_runtime_spec.md`, `template_prompts/` or `template/prompts/`, and needs to re-learn the local workflow before designing, implementing, reviewing, or fixing.
---

# HiveMind Embed Onboarding

Rebuild working context from the embedded package before acting.

## Quick Start

1. Confirm the workspace contains the HiveMind package markers:
   - `orchestrator/`
   - `.ai-loop/`
   - `orchestrator_runtime_spec.md`
2. Read only the minimum files needed to recover the workflow:
   - `README.md` if present
   - `orchestrator_runtime_spec.md`
   - `.ai-loop/state/workflow_state.json`
   - `.ai-loop/input/requirement.md`
3. Read the phase-specific artifacts that match the current state:
   - `designing`: `.ai-loop/artifacts/current/design.md`, `.ai-loop/artifacts/current/design_amendments.md`, `.ai-loop/artifacts/current/summary.md`
   - `implementing`: `.ai-loop/artifacts/current/design.md`, `.ai-loop/artifacts/current/design_amendments.md`, `.ai-loop/artifacts/current/summary.md`
   - `reviewing`: `.ai-loop/artifacts/current/design.md`, `.ai-loop/artifacts/current/implementation_report.md`, `.ai-loop/artifacts/current/review.json` if it exists
   - `fixing`: `.ai-loop/artifacts/current/review.json`, `.ai-loop/artifacts/current/review.md`, `.ai-loop/artifacts/current/design.md`
4. Inspect `orchestrator/cli.py`, `orchestrator/prompt_builder.py`, and `orchestrator/transition_engine.py` if the task depends on runtime behavior.
5. Summarize the recovered state before making changes:
   - current phase
   - current iteration and phase attempt
   - expected artifact outputs for the phase
   - whether a human gate is open
   - which agent owns the current phase

## Operating Rules

- Treat `workflow_state.json` as the source of truth for the next phase to execute.
- Treat artifacts as valid only when their metadata matches the current workflow state.
- Do not infer phase from stale files alone; prefer state, then validate supporting artifacts.
- Do not edit the approved design directly from implementation or fixing work.
- Use `py -m orchestrator run` or `bash run` to start a phase when the workspace includes the runnable package.

## File Map

Read [references/package-map.md](references/package-map.md) when you need a compact map of the package structure and which files matter for each question.

Read [references/embedded-workspace-checklist.md](references/embedded-workspace-checklist.md) when you need the exact onboarding checklist for a newly embedded project or feature workspace.

## Output Pattern

After reloading the package, report the workspace in a short operational summary:

- what HiveMind components are present
- what the current phase is
- what files the assigned agent is expected to read and write next
- any obvious state/artifact mismatch that should be resolved before execution
