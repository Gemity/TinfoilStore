# AI Orchestrator Runtime Spec

## 1. Purpose

This document defines the executable contract for the local two-agent orchestrator:

- Codex: design, design amendment review, implementation review
- Claude Code: implementation, critical fix
- Orchestrator: state transition authority

This spec focuses on:

- Artifact schema
- `workflow_state.json` schema
- Transition rules
- File safety and idempotency rules

The goal is that the orchestrator can resume after crash, reject stale outputs, and keep both agents aligned to the same iteration.

---

## 2. Runtime Principles

1. The orchestrator is the only component allowed to change workflow phase.
2. Every agent output must declare which `run_id`, `iteration`, and `phase` it belongs to.
3. An artifact is valid only if both:
   - its schema is valid
   - its metadata matches the current workflow state
4. Agents never infer state from previous terminal context. They read input artifacts only.
5. Writes must be atomic: write to temp file, fsync if available, then rename.
6. Fixed artifact paths may exist, but validity always comes from metadata, not file presence alone.

---

## 3. Directory Layout

```text
.ai-loop/
  input/
    requirement.md
    human_queue.md

  artifacts/
    current/
      design.md
      design_amendments.md
      review.md
      review.json
      implementation_report.md
      summary.md
      tech_debt.md
    history/
      <run_id>/
        iter-0001/
          design.md
          review.md
          review.json
          implementation_report.md
          summary.md
        iter-0002/
          ...

  state/
    workflow_state.json
    lock.json

  logs/
    audit.log
```

Notes:

- `artifacts/current/` is the live working set used by prompts.
- `artifacts/history/` is immutable archive copied by orchestrator after each committed phase.
- Agents only write into `artifacts/current/`.
- Only the orchestrator copies files into `history/`.

---

## 4. Global Identifiers

### 4.1 `run_id`

Unique ID for one orchestrator run over one requirement.

Format recommendation:

```text
run-YYYYMMDD-HHMMSS-<8hex>
```

Example:

```text
run-20260322-235955-a1b2c3d4
```

### 4.2 `iteration`

Integer starting at `1`.

One full review cycle increments iteration when the workflow enters `implementing` from `designing` or re-enters `fixing` after a failed review.

### 4.3 `phase_attempt`

Integer starting at `1` for each phase entry.

Used to distinguish retries of the same phase without changing iteration.

### 4.4 `artifact_version`

Start at `1`. Increment only when artifact schema changes.

---

## 5. Common Artifact Envelope

Every machine-readable artifact must include this JSON envelope at minimum:

```json
{
  "artifact_type": "review",
  "artifact_version": 1,
  "run_id": "run-20260322-235955-a1b2c3d4",
  "iteration": 2,
  "phase": "reviewing",
  "phase_attempt": 1,
  "producer": "codex",
  "created_at": "2026-03-22T23:59:55+07:00",
  "input_fingerprint": {
    "requirement_sha256": "<hex>",
    "design_sha256": "<hex>",
    "review_target_commit": "<git sha or null>"
  }
}
```

Rules:

- `artifact_type`, `run_id`, `iteration`, `phase`, `phase_attempt`, `producer` must exactly match the expected phase contract.
- `created_at` must be ISO 8601 with timezone.
- `input_fingerprint` must be derived by the orchestrator and injected into the prompt.
- Orchestrator validates that the fingerprint in the artifact matches the fingerprint recorded in state before accepting the artifact.

Markdown artifacts must start with a metadata block:

```markdown
---
artifact_type: review
artifact_version: 1
run_id: run-20260322-235955-a1b2c3d4
iteration: 2
phase: reviewing
phase_attempt: 1
producer: codex
created_at: 2026-03-22T23:59:55+07:00
---
```

If you want stricter parsing later, store a parallel `.json` sidecar for each markdown artifact. For now, this spec keeps markdown human-readable.

---

## 6. Artifact Schemas

## 6.1 `design.md`

Producer: `codex`  
Expected phase: `designing`

Required sections:

```markdown
# Objective
# Scope
# Constraints
# Architecture
# Execution Plan
# Acceptance Criteria
# Non-Goals
```

Required metadata fields in front matter:

- `artifact_type: design`
- `design_version`: integer, starts at 1
- `status`: `draft|approved|superseded`

Acceptance rule:

- `status` must be `approved` for transition to `implementing`

## 6.2 `design_amendments.md`

Producer: `claude` or `codex`  
Typical phase: `implementing`, `fixing`, or `reviewing`

Required section schema:

```markdown
# Amendment Requests

## AM-001
- status: proposed|accepted|rejected|applied
- requested_by: claude
- design_version: 1
- reason:
- requested_change:
- blocking: true|false
- related_issue_ids:
```

Rules:

- Claude may append only new `proposed` amendments.
- Claude must not modify status of existing amendments.
- Only Codex may mark amendment `accepted` or `rejected`.
- Only orchestrator may mark amendment `applied` after new `design.md` is produced.

## 6.3 `implementation_report.md`

Producer: `claude`  
Expected phase: `implementing` or `fixing`

Required sections:

```markdown
# Summary
# Files Changed
# Tests Run
# Known Risks
# Amendment Requests
```

Required metadata fields:

- `artifact_type: implementation_report`
- `mode: implement|fix`
- `result: success|blocked|partial`

Rules:

- `Files Changed` must list concrete file paths.
- `Tests Run` must list command and outcome, or explicitly say no tests were run.
- `Amendment Requests` must reference IDs already appended in `design_amendments.md`, or `none`.

## 6.4 `review.json`

Producer: `codex`  
Expected phase: `reviewing`

Schema:

```json
{
  "artifact_type": "review",
  "artifact_version": 1,
  "run_id": "run-20260322-235955-a1b2c3d4",
  "iteration": 2,
  "phase": "reviewing",
  "phase_attempt": 1,
  "producer": "codex",
  "created_at": "2026-03-22T23:59:55+07:00",
  "input_fingerprint": {
    "requirement_sha256": "<hex>",
    "design_sha256": "<hex>",
    "review_target_commit": "<git sha>"
  },
  "result": "pass",
  "blocking_reason": null,
  "approved_design_version": 1,
  "issues": [
    {
      "issue_id": "ISS-001",
      "severity": "critical",
      "category": "correctness",
      "title": "Null path crashes orchestrator",
      "description": "Runtime can dereference missing artifact metadata.",
      "file_paths": [
        "orchestrator/runtime.py"
      ],
      "fix_instruction": "Guard metadata parse and fail phase as malformed artifact.",
      "requires_design_change": false,
      "related_amendment_ids": [],
      "fingerprint": "sha256:<hex>"
    }
  ],
  "summary": {
    "critical_count": 1,
    "minor_count": 0
  }
}
```

Rules:

- `result` is one of `pass|fail|blocked`.
- If `result=pass`, `issues` may contain only minor issues or be empty.
- If `result=fail`, at least one issue must have `severity=critical`.
- If `result=blocked`, `blocking_reason` must be non-null and no fix loop should start automatically.
- `issue_id` must be stable within the same run once introduced.
- `fingerprint` should be built from normalized category, title, file paths, and core failing condition.

## 6.5 `review.md`

Producer: `codex`  
Expected phase: `reviewing`

Human-readable companion to `review.json`.

Required sections:

```markdown
# Verdict
# Critical Issues
# Minor Issues
# Amendment Decisions
# Notes For Next Iteration
```

Rules:

- Content must map directly to `review.json`.
- `Amendment Decisions` must mark newly reviewed amendment IDs as `accepted` or `rejected`.

## 6.6 `summary.md`

Producer: `orchestrator` or `codex`  
Created after each committed phase

Required sections:

```markdown
# Phase Summary
# Inputs
# Outputs
# Decision
# Next Phase
```

This file is for prompt compression only and never overrides canonical artifacts.

## 6.7 `tech_debt.md`

Producer: `orchestrator` appending normalized entries from `review.json`

Entry schema:

```markdown
## TD-001
- first_seen_iteration: 3
- source_issue_id: ISS-004
- title:
- rationale:
- suggested_follow_up:
```

---

## 7. `workflow_state.json` Schema

Canonical workflow state:

```json
{
  "state_version": 1,
  "run_id": "run-20260322-235955-a1b2c3d4",
  "status": "active",
  "phase": "reviewing",
  "phase_attempt": 1,
  "iteration": 2,
  "max_iterations": 6,
  "requirement": {
    "path": ".ai-loop/input/requirement.md",
    "sha256": "<hex>"
  },
  "design": {
    "version": 1,
    "sha256": "<hex>",
    "status": "approved"
  },
  "current_inputs": {
    "requirement_sha256": "<hex>",
    "design_sha256": "<hex>",
    "review_target_commit": "<git sha or null>",
    "accepted_amendment_ids": [],
    "open_amendment_ids": []
  },
  "last_completed_phase": "implementing",
  "last_completed_at": "2026-03-22T23:59:55+07:00",
  "last_artifacts": {
    "design_md": ".ai-loop/artifacts/current/design.md",
    "design_amendments_md": ".ai-loop/artifacts/current/design_amendments.md",
    "implementation_report_md": ".ai-loop/artifacts/current/implementation_report.md",
    "review_md": ".ai-loop/artifacts/current/review.md",
    "review_json": ".ai-loop/artifacts/current/review.json",
    "summary_md": ".ai-loop/artifacts/current/summary.md"
  },
  "loop_guard": {
    "repeated_fingerprint_counts": {
      "sha256:abc": 2
    },
    "consecutive_no_diff": 0,
    "consecutive_malformed_artifacts": 0
  },
  "human_gate": {
    "required": false,
    "reason": null,
    "details": null
  },
  "git": {
    "branch": "ai-loop/example-feature",
    "head_commit": "<git sha or null>",
    "last_reviewed_commit": "<git sha or null>",
    "last_good_commit": "<git sha or null>"
  },
  "active_lock_owner": {
    "owner": "orchestrator",
    "pid": 12345,
    "hostname": "local-devbox",
    "acquired_at": "2026-03-22T23:59:55+07:00"
  }
}
```

### Required semantics

- `phase` is the next phase to execute.
- `last_completed_phase` is the most recent phase committed successfully.
- `current_inputs` is the source of truth for expected artifact fingerprint matching.
- `design.version` increments only when Codex produces a newly approved design.
- `loop_guard.repeated_fingerprint_counts` is updated only from accepted `review.json`.
- `human_gate.required=true` means the orchestrator must not invoke agents automatically.

### Allowed `status`

- `active`
- `waiting_human`
- `completed`
- `failed`

---

## 8. Lock Schema

Use `lock.json`, not a plain text lock file.

Schema:

```json
{
  "lock_version": 1,
  "run_id": "run-20260322-235955-a1b2c3d4",
  "owner": "orchestrator",
  "pid": 12345,
  "hostname": "local-devbox",
  "phase": "reviewing",
  "phase_attempt": 1,
  "acquired_at": "2026-03-22T23:59:55+07:00",
  "expires_at": "2026-03-23T00:09:55+07:00"
}
```

Rules:

- Acquire lock by atomic create only. Do not use `exists()` then write.
- If lock exists and is not expired, fail fast.
- If lock exists and is expired, orchestrator may recover it only after checking recorded PID is dead or owner is unreachable.
- Lock must be refreshed before `expires_at` during long-running phases.

---

## 9. Transition Rules

## 9.1 `designing`

Entry preconditions:

- `phase=designing`
- `requirement.md` exists and matches `requirement.sha256`
- no active unresolved human gate

Actions:

1. Orchestrator computes `current_inputs`.
2. Orchestrator invokes Codex with requirement, latest summary, current amendments, and target design version.
3. Codex writes `design.md`.
4. Orchestrator validates metadata, schema, and accepted status.
5. Orchestrator archives artifact, updates design hash/version, writes summary, commits state.

Success exit:

- next `phase=implementing`
- `iteration=1` if first design
- otherwise keep iteration unchanged unless this design was produced from accepted blocking amendment during review, in which case re-run `implementing` in current iteration

Failure exit:

- malformed artifact -> increment `consecutive_malformed_artifacts`
- if threshold reached -> `needs_human`
- otherwise retry same phase with `phase_attempt+1`

## 9.2 `implementing`

Entry preconditions:

- approved `design.md` exists
- no unresolved blocking amendment awaiting design update

Actions:

1. Orchestrator records `review_target_commit` as current HEAD before Claude starts, or null if repo not initialized.
2. Orchestrator invokes Claude with requirement, approved design, latest review issues to fix if any, open amendments, and expected metadata.
3. Claude writes `implementation_report.md` and may append `design_amendments.md`.
4. Orchestrator validates report metadata and fingerprint.
5. If report says `blocked`, route to `needs_human` unless a non-blocking amendment path is explicitly available.
6. Orchestrator snapshots code/artifacts, updates git metadata, writes summary, commits state.

Success exit:

- next `phase=reviewing`

Failure exit:

- malformed artifact -> retry or human gate

## 9.3 `reviewing`

Entry preconditions:

- `implementation_report.md` exists and matches current inputs
- working tree snapshot for review is known

Actions:

1. Orchestrator invokes Codex with requirement, design, implementation report, relevant code diff, open amendments, and current loop guard data.
2. Codex writes `review.md` and `review.json`.
3. Orchestrator validates both artifacts and cross-checks counts, result, and issue IDs.
4. Orchestrator updates repeated fingerprint counters.
5. Orchestrator records amendment decisions from review.
6. Orchestrator writes summary and commits state.

Success exits:

- if `result=pass` and no accepted blocking amendment pending -> `done`
- if `result=fail` and all critical issues have `requires_design_change=false` -> `fixing`
- if any critical issue or blocked result requires design change -> `designing`
- if `result=blocked` -> `needs_human`

Failure exit:

- malformed review pair -> retry same phase or `needs_human`

## 9.4 `fixing`

Entry preconditions:

- latest `review.json.result=fail`
- at least one critical issue exists
- no critical issue requires design change

Actions:

1. Orchestrator invokes Claude with only unresolved critical issues.
2. Claude writes `implementation_report.md` with `mode=fix`.
3. Claude may append amendment proposals but cannot edit design.
4. Orchestrator validates artifact and snapshots code/artifacts.
5. Orchestrator increments `iteration += 1` after successful fix commit, because a new review cycle is required.

Success exit:

- next `phase=reviewing`

Failure exit:

- malformed artifact -> retry or `needs_human`

## 9.5 `needs_human`

Entry conditions include any of:

- `iteration > max_iterations`
- same critical fingerprint seen more than threshold, recommended default `3`
- blocking amendment unresolved
- malformed artifacts exceed threshold, recommended default `2`
- no meaningful code diff for two consecutive fix attempts
- agent report result is `blocked`

Actions:

1. Orchestrator writes a human queue entry.
2. Orchestrator sets `status=waiting_human`.
3. Orchestrator stops automatic agent execution.

Human exits:

- approve design amendment -> `designing`
- request continue without amendment -> `fixing` or `implementing`
- accept current output -> `done`
- abort run -> `failed`

## 9.6 `done`

Entry preconditions:

- latest accepted `review.json.result=pass`
- no unresolved accepted blocking amendment

Actions:

1. Orchestrator writes final summary.
2. Orchestrator marks `status=completed`.
3. Orchestrator records `last_good_commit`.
4. Optional merge gate can run outside the orchestrator core.

---

## 10. Phase-to-Artifact Contract

| Phase | Required Inputs | Required Outputs | Allowed Producer |
|---|---|---|---|
| designing | requirement, summary, amendments | design.md | codex |
| implementing | requirement, approved design, prior summary | implementation_report.md | claude |
| reviewing | requirement, design, implementation_report, diff | review.md, review.json | codex |
| fixing | requirement, design, review.json critical issues | implementation_report.md | claude |
| needs_human | latest state, blocking reason | human_queue.md entry | orchestrator |
| done | latest passing review | final summary | orchestrator |

---

## 11. Validation Rules

An artifact is accepted only if all checks pass:

1. File exists.
2. File parses successfully.
3. Required metadata fields exist.
4. `run_id`, `iteration`, `phase`, `phase_attempt`, `producer` match state.
5. `input_fingerprint` matches `workflow_state.current_inputs`.
6. Required sections or JSON fields exist.
7. Cross-file consistency checks pass:
   - `review.md` and `review.json` agree on result and counts
   - amendment IDs referenced by review exist
   - implementation report mode matches phase

If any check fails:

- mark artifact malformed
- append audit log entry
- do not advance phase

---

## 12. Idempotency and Recovery

### Same phase retry

If the process crashes before state commit:

- keep `phase` unchanged
- increment `phase_attempt`
- regenerate prompt with same `iteration`

### Artifact replay protection

Reject artifacts when any of these mismatch:

- `run_id`
- `iteration`
- `phase`
- `phase_attempt`
- `input_fingerprint`

### Commit order

For every successful phase:

1. validate artifact
2. copy artifact to history
3. write summary
4. update `workflow_state.json`
5. append audit log
6. create git commit if enabled

State commit happens after artifact validation and before lock release.

---

## 13. Git Checkpoint Rules

Recommended commit pattern:

```text
ai-loop: iter-0002 reviewing pass
ai-loop: iter-0003 fixing
```

Rules:

- Create one commit after each successful phase that changes code or canonical artifacts.
- Record commit SHA into `workflow_state.json`.
- `last_reviewed_commit` updates after successful `reviewing`.
- `last_good_commit` updates only on `done`.

---

## 14. Suggested Defaults

- `max_iterations = 6`
- `max_phase_attempts = 2`
- `repeated_fingerprint_threshold = 3`
- `malformed_artifact_threshold = 2`
- `lock_ttl_seconds = 600`
- `no_meaningful_diff_threshold = 2`

---

## 15. Minimal Implementation Order

Implement in this order:

1. `workflow_state.json` load, validate, save atomically
2. `lock.json` acquire, refresh, release
3. artifact metadata parser and validator
4. phase runner skeletons
5. transition resolver
6. audit logger
7. git checkpoint integration

This is the smallest path to a recoverable orchestrator.
