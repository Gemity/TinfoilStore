# Requirement

Build the first working version of a backend service for a Nintendo Switch Tinfoil shop.

## Context

- Project: Tinfoil shop backend managed through the HiveMind AI orchestration workflow.
- Feature: Core server foundation with user accounts, subscription management, and object storage integration using Wasabi (S3-compatible).
- Goal: Create a maintainable backend that can manage users, validate subscription access, and gate content access based on subscription status.
- Constraints:
  - The project should fit the HiveMind AI workflow where Codex handles design/review and Claude handles implementation/fixes.
  - The backend should be organized so it can later support Tinfoil shop endpoints, admin operations, and storage-backed file delivery.
  - Wasabi integration must use an S3-compatible approach so credentials, bucket, endpoint, and region can be configured from environment variables.
  - Subscription logic must support at least: active, expired, revoked, and manual extension.
  - The system should be designed for future expansion, not only a one-off script.

## Success Criteria

- A concrete backend architecture is defined for the shop service.
- The codebase contains the initial server foundation rather than only orchestrator scaffolding.
- User and subscription data models are defined clearly enough for implementation.
- Access control rules are defined so a user without a valid subscription cannot access protected content.
- Wasabi storage integration requirements are documented clearly enough for implementation.
- The requirement is specific enough that Codex can produce a design artifact and Claude can implement against it without relying on terminal memory.

## Notes For Agents

- This requirement replaces the placeholder template and should be treated as the active project goal.
- Agents should rely on `.ai-loop/state/workflow_state.json` and validated artifacts, not terminal memory.
- If the existing repository currently contains only orchestrator runtime code, the next design should decide how to introduce the actual backend application structure into this repository.
- Prefer small, production-oriented increments: establish the backend skeleton first, then add subscription and storage behavior in follow-up iterations.

