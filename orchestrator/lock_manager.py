"""Lock management for exclusive phase execution.

Maps to design section 'lock_manager' and runtime spec section 8.
Uses OS-level atomic file creation to prevent TOCTOU races.
"""

from __future__ import annotations

import json
import os
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from orchestrator.constants import DEFAULT_LOCK_TTL_SECONDS, LOCK_PATH, LOCK_VERSION
from orchestrator.fileutil import atomic_write
from orchestrator.models import LockRecord, WorkflowState


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s)


def acquire_lock(
    state: WorkflowState,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    path: Path = LOCK_PATH,
) -> LockRecord:
    """Atomically create lock.json using O_CREAT|O_EXCL to prevent races.

    If a stale lock exists (expired + owner dead), it is recovered first
    in a separate step, then exclusive creation is re-attempted.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    now = _now_utc()
    lock = LockRecord(
        lock_version=LOCK_VERSION,
        run_id=state.run_id,
        owner="orchestrator",
        pid=os.getpid(),
        hostname=socket.gethostname(),
        phase=state.phase,
        phase_attempt=state.phase_attempt,
        acquired_at=now.isoformat(),
        expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
    )
    data = json.dumps(lock.to_dict(), indent=2, ensure_ascii=False) + "\n"

    try:
        _exclusive_create(path, data)
        return lock
    except FileExistsError:
        pass

    # A placeholder/null lock file from a bootstrapped workspace is inactive.
    # Remove it so the first real acquire can proceed.
    if _recover_inactive_lock(path):
        try:
            _exclusive_create(path, data)
            return lock
        except FileExistsError:
            pass

    # File exists - check if it is stale and can be recovered.
    existing = read_lock(path)
    if existing and not is_lock_expired(existing):
        raise RuntimeError(
            f"Lock already held by owner={existing.owner} pid={existing.pid} "
            f"until {existing.expires_at}"
        )

    # Attempt stale-lock recovery, then retry exclusive create
    recover_stale_lock(path)

    try:
        _exclusive_create(path, data)
        return lock
    except FileExistsError:
        # Another process won the race during recovery
        raise RuntimeError("Lock contention: another process acquired the lock during recovery")


def _exclusive_create(path: Path, data: str, encoding: str = "utf-8") -> None:
    """Create a file exclusively (O_CREAT|O_EXCL). Raises FileExistsError if it exists."""
    fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        try:
            os.unlink(str(path))
        except OSError:
            pass
        raise


def release_lock(path: Path = LOCK_PATH) -> None:
    """Remove lock.json."""
    path = Path(path)
    try:
        os.remove(path)
    except FileNotFoundError:
        pass


def _recover_inactive_lock(path: Path) -> bool:
    """Remove a lock file that exists on disk but does not represent an active lock."""
    path = Path(path)
    if not path.exists():
        return False
    if read_lock(path) is not None:
        return False
    release_lock(path)
    return True


def refresh_lock(
    lock: LockRecord,
    ttl_seconds: int = DEFAULT_LOCK_TTL_SECONDS,
    path: Path = LOCK_PATH,
) -> LockRecord:
    """Update expires_at in lock file."""
    now = _now_utc()
    new_lock = LockRecord(
        lock_version=lock.lock_version,
        run_id=lock.run_id,
        owner=lock.owner,
        pid=lock.pid,
        hostname=lock.hostname,
        phase=lock.phase,
        phase_attempt=lock.phase_attempt,
        acquired_at=lock.acquired_at,
        expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
    )
    data = json.dumps(new_lock.to_dict(), indent=2, ensure_ascii=False) + "\n"
    atomic_write(path, data)
    return new_lock


def read_lock(path: Path = LOCK_PATH) -> Optional[LockRecord]:
    """Read current lock. Returns None if file doesn't exist or is empty/null."""
    path = Path(path)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # An empty/null lock means no active lock
        if not data or not data.get("run_id"):
            return None
        return LockRecord.from_dict(data)
    except (json.JSONDecodeError, KeyError):
        return None


def is_lock_expired(lock: LockRecord) -> bool:
    """Check if lock has passed expires_at."""
    if not lock.expires_at:
        return True
    try:
        expires = _parse_iso(lock.expires_at)
        return _now_utc() > expires
    except ValueError:
        return True


def is_lock_owner_alive(lock: LockRecord) -> bool:
    """Check if the PID in the lock is still running (best-effort).

    Also checks hostname match - if different host, assume alive (can't check).
    """
    if not lock.pid:
        return False

    # If different hostname, we can't check - assume alive for safety
    if lock.hostname and lock.hostname != socket.gethostname():
        return True

    try:
        os.kill(lock.pid, 0)
        return True
    except OSError:
        return False


def recover_stale_lock(path: Path = LOCK_PATH) -> bool:
    """If lock is expired and owner is dead, remove it. Returns True if recovered."""
    lock = read_lock(path)
    if lock is None:
        return False

    if is_lock_expired(lock) and not is_lock_owner_alive(lock):
        release_lock(path)
        return True

    return False
