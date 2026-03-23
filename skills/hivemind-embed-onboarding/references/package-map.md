# Package Map

## Runtime Core

- `orchestrator/cli.py`: CLI entrypoints such as `init`, `status`, `validate`, `check-transition`, and `run`
- `orchestrator/models.py`: workflow state, artifact, review, and lock data models
- `orchestrator/state_manager.py`: load/save/init state and pure state mutations
- `orchestrator/transition_engine.py`: phase preconditions, exit rules, and loop guards
- `orchestrator/artifact_parser.py`: frontmatter and JSON parsing
- `orchestrator/artifact_validator.py`: metadata, fingerprint, and section validation
- `orchestrator/lock_manager.py`: exclusive phase lock handling
- `orchestrator/agent_runner.py`: phase-to-agent mapping and local CLI invocation
- `orchestrator/prompt_builder.py`: deterministic prompt package rendering

## Workspace

- `.ai-loop/input/requirement.md`: requirement and success criteria
- `.ai-loop/input/*.md`: generated prompt packages and human queue
- `.ai-loop/state/workflow_state.json`: current phase, iteration, inputs, and human gate
- `.ai-loop/artifacts/current/`: live design, implementation, review, summary, and amendment files
- `.ai-loop/logs/audit.log`: append-only runtime events

## Contract

- `orchestrator_runtime_spec.md`: canonical runtime contract
- `README.md`: repo-level overview and command examples
- `document.md`: operator-oriented workflow guide

## Typical Reading Order

1. `orchestrator_runtime_spec.md`
2. `.ai-loop/state/workflow_state.json`
3. `.ai-loop/input/requirement.md`
4. phase-specific artifacts in `.ai-loop/artifacts/current/`
5. runtime modules only if implementation details matter
