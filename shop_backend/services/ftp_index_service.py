import os
import subprocess
from pathlib import Path


FTP_ROOT = Path(os.getenv("TINFOIL_FTP_ROOT", "/srv/tinfoil-unified"))
WASABI_MOUNT_SERVICE = os.getenv("TINFOIL_WASABI_MOUNT_SERVICE", "tinfoil-wasabi-mount")
FTP_INDEX_SERVICE = os.getenv("TINFOIL_FTP_INDEX_SERVICE", "tinfoil-ftp-unified-root")
GAME_EXTENSIONS = {".nsp", ".nsz", ".xci", ".xcz"}


class FtpIndexError(RuntimeError):
    pass


def list_ftp_content(max_items: int = 500) -> dict:
    max_items = max(1, min(max_items, 5000))
    root_exists = FTP_ROOT.exists()
    files = []
    directories = []
    errors = []

    if root_exists:
        for entry in sorted(FTP_ROOT.iterdir(), key=lambda item: item.name.lower()):
            try:
                is_directory = entry.is_dir()
                is_file = entry.is_file()
            except OSError as exc:
                errors.append({"name": entry.name, "error": str(exc)})
                continue

            item = {
                "name": entry.name,
                "path": f"/{entry.name}",
                "type": "directory" if is_directory else "file",
            }
            if is_file:
                try:
                    item["size_bytes"] = entry.stat().st_size
                except OSError as exc:
                    item["size_bytes"] = None
                    item["error"] = str(exc)
                item["is_game_file"] = entry.suffix.lower() in GAME_EXTENSIONS
                files.append(item)
            elif is_directory:
                directories.append(item)

            if len(files) + len(directories) >= max_items:
                break

    return {
        "root": str(FTP_ROOT),
        "root_exists": root_exists,
        "files": files,
        "directories": directories,
        "total_returned": len(files) + len(directories),
        "game_files_returned": sum(1 for item in files if item.get("is_game_file")),
        "viet_hoa_present": (FTP_ROOT / "viet-hoa").exists(),
        "errors": errors,
    }


def refresh_ftp_index(rebuild_wasabi_mount: bool = False) -> dict:
    """Refresh the FTP root.

    Restarting `tinfoil-wasabi-mount` drops rclone's 30m dir-cache and briefly
    interrupts every bind-mounted file under it while the mount comes back
    up, so it's disruptive to do on every sync. New files added to Wasabi are
    already picked up by `tinfoil-ftp-unified-root` alone, without touching
    the cache. Only pass rebuild_wasabi_mount=True after a rename/move on
    Wasabi, where the stale dir-cache would otherwise hide the new path for
    up to 30 minutes.
    """
    if rebuild_wasabi_mount:
        _restart_service(WASABI_MOUNT_SERVICE)
    _restart_service(FTP_INDEX_SERVICE)
    content = list_ftp_content(max_items=5000)
    return {
        "message": "FTP index refreshed.",
        "services": {
            WASABI_MOUNT_SERVICE: _service_state(WASABI_MOUNT_SERVICE),
            FTP_INDEX_SERVICE: _service_state(FTP_INDEX_SERVICE),
        },
        "content": {
            "root": content["root"],
            "root_exists": content["root_exists"],
            "total_count": content["total_returned"],
            "total_game_files": content["game_files_returned"],
            "viet_hoa_present": content["viet_hoa_present"],
        },
    }


# Each restart gets this long before we give up; keeps total request time under
# nginx's proxy_read_timeout (300s) instead of hanging until nginx returns 504.
SERVICE_RESTART_TIMEOUT_SECONDS = 120


def _restart_service(name: str) -> None:
    _run(["systemctl", "restart", name], timeout=SERVICE_RESTART_TIMEOUT_SECONDS)


def _service_state(name: str) -> str:
    result = subprocess.run(["systemctl", "is-active", name], text=True, capture_output=True, check=False)
    return (result.stdout or result.stderr or "unknown").strip()


def _run(args: list[str], timeout: float | None = None) -> None:
    try:
        subprocess.run(args, text=True, capture_output=True, check=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise FtpIndexError(f"Command not available: {args[0]}") from exc
    except subprocess.TimeoutExpired as exc:
        raise FtpIndexError(f"Command timed out after {timeout}s: {' '.join(args)}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise FtpIndexError(detail) from exc
