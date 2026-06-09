import re
import shutil
import subprocess

try:
    import grp
    import pwd
except ImportError:
    grp = None
    pwd = None


FTP_GROUP = "tinfoilftp"
FTP_ROOT = "/srv/tinfoil-unified"
FTP_SHELL = "/usr/sbin/nologin"
USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")
RESERVED_USERNAMES = {"root", "admin", "daemon", "bin", "sys", "sync", "games", "man"}


class FtpUserError(ValueError):
    pass


def list_ftp_users() -> list[dict]:
    _ensure_linux_user_modules()
    group = _get_group()
    members = set(group.gr_mem)
    users = []
    for entry in pwd.getpwall():
        in_primary_group = entry.pw_gid == group.gr_gid
        in_supplementary_group = entry.pw_name in members
        if in_primary_group or in_supplementary_group:
            users.append(_response(entry))
    return sorted(users, key=lambda item: item["username"])


def create_ftp_user(username: str, password: str, is_active: bool = True) -> dict:
    username = _validate_username(username)
    _validate_password(password)
    _ensure_root()
    _ensure_group()

    if _user_exists(username):
        raise FtpUserError("FTP user already exists")

    shell = _preferred_shell()
    _run(["useradd", "-M", "-d", FTP_ROOT, "-s", shell, "-g", FTP_GROUP, username])
    _set_password(username, password)
    if not is_active:
        _run(["passwd", "-l", username])
    return get_ftp_user(username)


def get_ftp_user(username: str) -> dict:
    _ensure_linux_user_modules()
    username = _validate_username(username)
    try:
        return _response(pwd.getpwnam(username))
    except KeyError as exc:
        raise LookupError("FTP user not found") from exc


def update_ftp_user(username: str, password: str | None = None, is_active: bool | None = None) -> dict:
    username = _validate_username(username)
    _ensure_group_member(username)
    if password is not None:
        _validate_password(password)
        _set_password(username, password)
    if is_active is not None:
        _run(["passwd", "-u" if is_active else "-l", username])
    return get_ftp_user(username)


def delete_ftp_user(username: str) -> None:
    username = _validate_username(username)
    _ensure_group_member(username)
    _run(["userdel", username])


def ensure_group_and_members(usernames: list[str] | None = None) -> dict:
    _ensure_root()
    _ensure_group()
    changed = []
    for username in usernames or []:
        if _user_exists(username):
            _run(["usermod", "-a", "-G", FTP_GROUP, username])
            changed.append(username)
    return {"group": FTP_GROUP, "members_added": changed}


def _validate_username(username: str) -> str:
    username = username.strip()
    if not USERNAME_RE.match(username):
        raise FtpUserError("Invalid FTP username")
    if username in RESERVED_USERNAMES:
        raise FtpUserError("Reserved FTP username")
    return username


def _validate_password(password: str) -> None:
    if len(password) < 6:
        raise FtpUserError("FTP password must be at least 6 characters")


def _ensure_root() -> None:
    _ensure_linux_user_modules()
    if not shutil.which("useradd"):
        raise FtpUserError("Linux user management tools are not available")


def _ensure_linux_user_modules() -> None:
    if grp is None or pwd is None:
        raise FtpUserError("Linux user management modules are not available")


def _ensure_group() -> None:
    try:
        grp.getgrnam(FTP_GROUP)
    except KeyError:
        _run(["groupadd", "--system", FTP_GROUP])


def _get_group():
    _ensure_group()
    return grp.getgrnam(FTP_GROUP)


def _user_exists(username: str) -> bool:
    try:
        pwd.getpwnam(username)
        return True
    except KeyError:
        return False


def _ensure_group_member(username: str) -> None:
    _ensure_linux_user_modules()
    try:
        entry = pwd.getpwnam(username)
    except KeyError as exc:
        raise LookupError("FTP user not found") from exc
    group = _get_group()
    if entry.pw_gid != group.gr_gid and username not in group.gr_mem:
        raise LookupError("User exists but is not managed as a Tinfoil FTP user")


def _preferred_shell() -> str:
    if shutil.which("nologin"):
        return shutil.which("nologin") or FTP_SHELL
    return "/bin/bash"


def _set_password(username: str, password: str) -> None:
    _run(["chpasswd"], input_text=f"{username}:{password}\n")


def _is_locked(username: str) -> bool:
    result = subprocess.run(["passwd", "-S", username], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        return False
    parts = result.stdout.split()
    return len(parts) > 1 and parts[1] in {"L", "LK"}


def _response(entry) -> dict:
    return {
        "username": entry.pw_name,
        "is_active": not _is_locked(entry.pw_name),
        "home": entry.pw_dir,
        "shell": entry.pw_shell,
        "group": FTP_GROUP,
    }


def _run(args: list[str], input_text: str | None = None) -> None:
    try:
        subprocess.run(args, input=input_text, text=True, capture_output=True, check=True)
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or str(exc)).strip()
        raise FtpUserError(detail) from exc
