"""Shared constants and default paths for the orchestrator runtime."""

from pathlib import Path

# Directory layout
AI_LOOP_DIR = Path(".ai-loop")
STATE_DIR = AI_LOOP_DIR / "state"
ARTIFACTS_CURRENT_DIR = AI_LOOP_DIR / "artifacts" / "current"
ARTIFACTS_HISTORY_DIR = AI_LOOP_DIR / "artifacts" / "history"
LOGS_DIR = AI_LOOP_DIR / "logs"
INPUT_DIR = AI_LOOP_DIR / "input"

# Canonical file paths
WORKFLOW_STATE_PATH = STATE_DIR / "workflow_state.json"
LOCK_PATH = STATE_DIR / "lock.json"
AUDIT_LOG_PATH = LOGS_DIR / "audit.log"
AGENT_LOGS_DIR = LOGS_DIR / "agents"
ORCHESTRATOR_LOG_PATH = LOGS_DIR / "orchestrator.log"
HUMAN_GATES_CONFIG_PATH = AI_LOOP_DIR / "config" / "human_gates.json"

# Artifact file names
DESIGN_MD = "design.md"
DESIGN_AMENDMENTS_MD = "design_amendments.md"
IMPLEMENTATION_REPORT_MD = "implementation_report.md"
REVIEW_MD = "review.md"
REVIEW_JSON = "review.json"
SUMMARY_MD = "summary.md"
TECH_DEBT_MD = "tech_debt.md"

# Runtime spec section 14 defaults
DEFAULT_MAX_ITERATIONS = 6
DEFAULT_MAX_PHASE_ATTEMPTS = 2
DEFAULT_REPEATED_FINGERPRINT_THRESHOLD = 3
DEFAULT_MALFORMED_ARTIFACT_THRESHOLD = 2
DEFAULT_LOCK_TTL_SECONDS = 600
DEFAULT_NO_MEANINGFUL_DIFF_THRESHOLD = 2

# Schema versions
STATE_VERSION = 1
LOCK_VERSION = 1
