"""Core data models for the orchestrator runtime.

Maps to runtime spec sections 4-8 and design section 'artifact_models'.
All models use stdlib dataclasses - no external dependencies.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


# --- Enums ---

class Phase(str, Enum):
    DESIGNING = "designing"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    FIXING = "fixing"
    NEEDS_HUMAN = "needs_human"
    DONE = "done"


class RunStatus(str, Enum):
    ACTIVE = "active"
    WAITING_HUMAN = "waiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactType(str, Enum):
    DESIGN = "design"
    DESIGN_AMENDMENTS = "design_amendments"
    IMPLEMENTATION_REPORT = "implementation_report"
    REVIEW = "review"
    SUMMARY = "summary"
    TECH_DEBT = "tech_debt"


class Producer(str, Enum):
    CODEX = "codex"
    CLAUDE = "claude"
    ORCHESTRATOR = "orchestrator"


class ReviewResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    BLOCKED = "blocked"


class ImplementationMode(str, Enum):
    IMPLEMENT = "implement"
    FIX = "fix"


class ImplementationResult(str, Enum):
    SUCCESS = "success"
    BLOCKED = "blocked"
    PARTIAL = "partial"


class DesignStatus(str, Enum):
    DRAFT = "draft"
    APPROVED = "approved"
    SUPERSEDED = "superseded"


# --- Nested state dataclasses ---

@dataclass
class RequirementRef:
    path: str = ""
    sha256: str = ""

    def to_dict(self) -> dict:
        return {"path": self.path, "sha256": self.sha256}

    @classmethod
    def from_dict(cls, d: dict) -> RequirementRef:
        return cls(path=d.get("path", ""), sha256=d.get("sha256", ""))


@dataclass
class DesignRef:
    version: int = 0
    sha256: Optional[str] = None
    status: str = "draft"

    def to_dict(self) -> dict:
        return {"version": self.version, "sha256": self.sha256, "status": self.status}

    @classmethod
    def from_dict(cls, d: dict) -> DesignRef:
        return cls(
            version=d.get("version", 0),
            sha256=d.get("sha256"),
            status=d.get("status", "draft"),
        )


@dataclass
class CurrentInputs:
    requirement_sha256: str = ""
    design_sha256: Optional[str] = None
    review_target_commit: Optional[str] = None
    accepted_amendment_ids: List[str] = field(default_factory=list)
    open_amendment_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "requirement_sha256": self.requirement_sha256,
            "design_sha256": self.design_sha256,
            "review_target_commit": self.review_target_commit,
            "accepted_amendment_ids": list(self.accepted_amendment_ids),
            "open_amendment_ids": list(self.open_amendment_ids),
        }

    @classmethod
    def from_dict(cls, d: dict) -> CurrentInputs:
        return cls(
            requirement_sha256=d.get("requirement_sha256", ""),
            design_sha256=d.get("design_sha256"),
            review_target_commit=d.get("review_target_commit"),
            accepted_amendment_ids=list(d.get("accepted_amendment_ids", [])),
            open_amendment_ids=list(d.get("open_amendment_ids", [])),
        )


@dataclass
class LoopGuard:
    repeated_fingerprint_counts: Dict[str, int] = field(default_factory=dict)
    consecutive_no_diff: int = 0
    consecutive_malformed_artifacts: int = 0

    def to_dict(self) -> dict:
        return {
            "repeated_fingerprint_counts": dict(self.repeated_fingerprint_counts),
            "consecutive_no_diff": self.consecutive_no_diff,
            "consecutive_malformed_artifacts": self.consecutive_malformed_artifacts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LoopGuard:
        return cls(
            repeated_fingerprint_counts=dict(d.get("repeated_fingerprint_counts", {})),
            consecutive_no_diff=d.get("consecutive_no_diff", 0),
            consecutive_malformed_artifacts=d.get("consecutive_malformed_artifacts", 0),
        )


@dataclass
class HumanGate:
    required: bool = False
    reason: Optional[str] = None
    details: Optional[str] = None

    def to_dict(self) -> dict:
        return {"required": self.required, "reason": self.reason, "details": self.details}

    @classmethod
    def from_dict(cls, d: dict) -> HumanGate:
        return cls(
            required=d.get("required", False),
            reason=d.get("reason"),
            details=d.get("details"),
        )


@dataclass
class GitInfo:
    branch: Optional[str] = None
    head_commit: Optional[str] = None
    last_reviewed_commit: Optional[str] = None
    last_good_commit: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "branch": self.branch,
            "head_commit": self.head_commit,
            "last_reviewed_commit": self.last_reviewed_commit,
            "last_good_commit": self.last_good_commit,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GitInfo:
        return cls(
            branch=d.get("branch"),
            head_commit=d.get("head_commit"),
            last_reviewed_commit=d.get("last_reviewed_commit"),
            last_good_commit=d.get("last_good_commit"),
        )


@dataclass
class LockOwner:
    owner: str = ""
    pid: int = 0
    hostname: str = ""
    acquired_at: str = ""

    def to_dict(self) -> dict:
        return {
            "owner": self.owner,
            "pid": self.pid,
            "hostname": self.hostname,
            "acquired_at": self.acquired_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LockOwner:
        return cls(
            owner=d.get("owner", ""),
            pid=d.get("pid", 0),
            hostname=d.get("hostname", ""),
            acquired_at=d.get("acquired_at", ""),
        )


# --- Top-level state model ---

@dataclass
class WorkflowState:
    state_version: int = 1
    run_id: str = ""
    status: str = "active"
    phase: str = "designing"
    phase_attempt: int = 1
    iteration: int = 1
    max_iterations: int = 6
    requirement: RequirementRef = field(default_factory=RequirementRef)
    design: DesignRef = field(default_factory=DesignRef)
    current_inputs: CurrentInputs = field(default_factory=CurrentInputs)
    last_completed_phase: Optional[str] = None
    last_completed_at: Optional[str] = None
    last_artifacts: Dict[str, str] = field(default_factory=dict)
    loop_guard: LoopGuard = field(default_factory=LoopGuard)
    human_gate: HumanGate = field(default_factory=HumanGate)
    git: GitInfo = field(default_factory=GitInfo)
    active_lock_owner: Optional[LockOwner] = None

    def to_dict(self) -> dict:
        return {
            "state_version": self.state_version,
            "run_id": self.run_id,
            "status": self.status,
            "phase": self.phase,
            "phase_attempt": self.phase_attempt,
            "iteration": self.iteration,
            "max_iterations": self.max_iterations,
            "requirement": self.requirement.to_dict(),
            "design": self.design.to_dict(),
            "current_inputs": self.current_inputs.to_dict(),
            "last_completed_phase": self.last_completed_phase,
            "last_completed_at": self.last_completed_at,
            "last_artifacts": dict(self.last_artifacts),
            "loop_guard": self.loop_guard.to_dict(),
            "human_gate": self.human_gate.to_dict(),
            "git": self.git.to_dict(),
            "active_lock_owner": self.active_lock_owner.to_dict() if self.active_lock_owner else None,
        }

    @classmethod
    def from_dict(cls, d: dict) -> WorkflowState:
        lock_owner_data = d.get("active_lock_owner")
        return cls(
            state_version=d.get("state_version", 1),
            run_id=d.get("run_id", ""),
            status=d.get("status", "active"),
            phase=d.get("phase", "designing"),
            phase_attempt=d.get("phase_attempt", 1),
            iteration=d.get("iteration", 1),
            max_iterations=d.get("max_iterations", 6),
            requirement=RequirementRef.from_dict(d.get("requirement", {})),
            design=DesignRef.from_dict(d.get("design", {})),
            current_inputs=CurrentInputs.from_dict(d.get("current_inputs", {})),
            last_completed_phase=d.get("last_completed_phase"),
            last_completed_at=d.get("last_completed_at"),
            last_artifacts=dict(d.get("last_artifacts", {})),
            loop_guard=LoopGuard.from_dict(d.get("loop_guard", {})),
            human_gate=HumanGate.from_dict(d.get("human_gate", {})),
            git=GitInfo.from_dict(d.get("git", {})),
            active_lock_owner=LockOwner.from_dict(lock_owner_data) if lock_owner_data else None,
        )

    def copy(self) -> WorkflowState:
        """Return a deep copy of this state."""
        return WorkflowState.from_dict(copy.deepcopy(self.to_dict()))


# --- Lock record ---

@dataclass
class LockRecord:
    lock_version: int = 1
    run_id: Optional[str] = None
    owner: Optional[str] = None
    pid: Optional[int] = None
    hostname: Optional[str] = None
    phase: Optional[str] = None
    phase_attempt: Optional[int] = None
    acquired_at: Optional[str] = None
    expires_at: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "lock_version": self.lock_version,
            "run_id": self.run_id,
            "owner": self.owner,
            "pid": self.pid,
            "hostname": self.hostname,
            "phase": self.phase,
            "phase_attempt": self.phase_attempt,
            "acquired_at": self.acquired_at,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LockRecord:
        return cls(
            lock_version=d.get("lock_version", 1),
            run_id=d.get("run_id"),
            owner=d.get("owner"),
            pid=d.get("pid"),
            hostname=d.get("hostname"),
            phase=d.get("phase"),
            phase_attempt=d.get("phase_attempt"),
            acquired_at=d.get("acquired_at"),
            expires_at=d.get("expires_at"),
        )


# --- Artifact metadata ---

@dataclass
class ArtifactMetadata:
    artifact_type: str = ""
    artifact_version: int = 1
    run_id: str = ""
    iteration: int = 1
    phase: str = ""
    phase_attempt: int = 1
    producer: str = ""
    created_at: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = {
            "artifact_type": self.artifact_type,
            "artifact_version": self.artifact_version,
            "run_id": self.run_id,
            "iteration": self.iteration,
            "phase": self.phase,
            "phase_attempt": self.phase_attempt,
            "producer": self.producer,
            "created_at": self.created_at,
        }
        d.update(self.extra)
        return d

    @classmethod
    def from_dict(cls, d: dict) -> ArtifactMetadata:
        known_keys = {
            "artifact_type", "artifact_version", "run_id", "iteration",
            "phase", "phase_attempt", "producer", "created_at",
        }
        extra = {k: v for k, v in d.items() if k not in known_keys}
        return cls(
            artifact_type=d.get("artifact_type", ""),
            artifact_version=d.get("artifact_version", 1),
            run_id=d.get("run_id", ""),
            iteration=d.get("iteration", 1),
            phase=d.get("phase", ""),
            phase_attempt=d.get("phase_attempt", 1),
            producer=d.get("producer", ""),
            created_at=d.get("created_at", ""),
            extra=extra,
        )


# --- Review structures ---

@dataclass
class ReviewIssue:
    issue_id: str = ""
    severity: str = ""
    category: str = ""
    title: str = ""
    description: str = ""
    file_paths: List[str] = field(default_factory=list)
    fix_instruction: str = ""
    requires_design_change: bool = False
    related_amendment_ids: List[str] = field(default_factory=list)
    fingerprint: str = ""

    def to_dict(self) -> dict:
        return {
            "issue_id": self.issue_id,
            "severity": self.severity,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "file_paths": list(self.file_paths),
            "fix_instruction": self.fix_instruction,
            "requires_design_change": self.requires_design_change,
            "related_amendment_ids": list(self.related_amendment_ids),
            "fingerprint": self.fingerprint,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReviewIssue:
        return cls(
            issue_id=d.get("issue_id", ""),
            severity=d.get("severity", ""),
            category=d.get("category", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            file_paths=list(d.get("file_paths", [])),
            fix_instruction=d.get("fix_instruction", ""),
            requires_design_change=d.get("requires_design_change", False),
            related_amendment_ids=list(d.get("related_amendment_ids", [])),
            fingerprint=d.get("fingerprint", ""),
        )


@dataclass
class ReviewSummary:
    total_issues: int = 0
    critical_count: int = 0
    major_count: int = 0
    minor_count: int = 0
    design_change_required: bool = False

    def to_dict(self) -> dict:
        return {
            "total_issues": self.total_issues,
            "critical_count": self.critical_count,
            "major_count": self.major_count,
            "minor_count": self.minor_count,
            "design_change_required": self.design_change_required,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReviewSummary:
        return cls(
            total_issues=d.get("total_issues", 0),
            critical_count=d.get("critical_count", 0),
            major_count=d.get("major_count", 0),
            minor_count=d.get("minor_count", 0),
            design_change_required=d.get("design_change_required", False),
        )


@dataclass
class ReviewArtifact:
    metadata: ArtifactMetadata = field(default_factory=ArtifactMetadata)
    result: str = ""
    blocking_reason: Optional[str] = None
    approved_design_version: int = 0
    issues: List[ReviewIssue] = field(default_factory=list)
    summary: ReviewSummary = field(default_factory=ReviewSummary)

    def to_dict(self) -> dict:
        return {
            "metadata": self.metadata.to_dict(),
            "result": self.result,
            "blocking_reason": self.blocking_reason,
            "approved_design_version": self.approved_design_version,
            "issues": [i.to_dict() for i in self.issues],
            "summary": self.summary.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> ReviewArtifact:
        # Support both nested {"metadata": {...}} and top-level metadata fields.
        # The spec defines metadata at the top level; legacy format nests it.
        if "metadata" in d and isinstance(d["metadata"], dict):
            metadata = ArtifactMetadata.from_dict(d["metadata"])
        else:
            metadata = ArtifactMetadata.from_dict(d)
        return cls(
            metadata=metadata,
            result=d.get("result", ""),
            blocking_reason=d.get("blocking_reason"),
            approved_design_version=d.get("approved_design_version", 0),
            issues=[ReviewIssue.from_dict(i) for i in d.get("issues", [])],
            summary=ReviewSummary.from_dict(d.get("summary", {})),
        )


# --- Validation result ---

@dataclass
class ValidationResult:
    valid: bool = True
    errors: List[str] = field(default_factory=list)

    def merge(self, other: ValidationResult) -> ValidationResult:
        """Merge another result into this one."""
        return ValidationResult(
            valid=self.valid and other.valid,
            errors=self.errors + other.errors,
        )
