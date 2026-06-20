"""Tinfoil-compatible shop index endpoint.

Tinfoil on the Switch calls this URL to get the list of downloadable files.
It sends credentials via HTTP Basic Auth (the user configures the shop URL
as  https://username:password@yourserver/shop/  in Tinfoil).

Response format expected by Tinfoil:
{
  "files": [
    {"url": "https://…presigned…", "size": 12345}
  ],
  "directories": [],
  "success": "Welcome message"
}
"""

import hashlib
import hmac
import logging
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request as FastAPIRequest, Response, status
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from shop_backend.api.deps import get_db
from shop_backend.config import settings
from shop_backend.db.models import ContentObject, User
from shop_backend.security.password import verify_password
from shop_backend.services import shop_service

router = APIRouter(tags=["shop"])
logger = logging.getLogger("uvicorn.error")

basic_scheme = HTTPBasic()
SHOP_ACCESS_TOKEN_TTL_SECONDS = 24 * 60 * 60


@router.api_route(
    "/{path:path}",
    methods=["PUT", "DELETE", "PATCH"],
    include_in_schema=False,
)
def shop_block_write(path: str):
    """Block any write operations — shop is read-only."""
    raise HTTPException(status_code=status.HTTP_405_METHOD_NOT_ALLOWED, detail="Read-only shop")


def _basic_auth_user(
    credentials: HTTPBasicCredentials = Depends(basic_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Authenticate via HTTP Basic Auth and return the User row."""
    user = (
        db.query(User)
        .filter(User.username == credentials.username, User.is_active.is_(True))
        .first()
    )
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return user


def _access_query(user: User) -> str:
    return f"?access_token={_make_access_token(user)}"


def _make_access_token(user: User) -> str:
    expires_at = int(time.time()) + SHOP_ACCESS_TOKEN_TTL_SECONDS
    payload = f"{user.id}:{expires_at}"
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}:{signature}"


def _token_auth_user(access_token: str, db: Session) -> User:
    try:
        user_id, expires_at_text, signature = access_token.rsplit(":", 2)
        expires_at = int(expires_at_text)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    payload = f"{user_id}:{expires_at}"
    expected = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected) or expires_at < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")

    try:
        parsed_user_id = uuid.UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    user = db.query(User).filter(User.id == parsed_user_id, User.is_active.is_(True)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token")
    return user


@router.get("")
@router.get("/")
def shop_index(
    request: FastAPIRequest,
    user: User = Depends(_basic_auth_user),
    db: Session = Depends(get_db),
):
    """Return a Tinfoil-compatible shop index."""
    base_url = str(request.base_url).rstrip("/")
    try:
        payload = shop_service.build_shop_index(
            db,
            user.id,
            base_url=base_url,
            access_query=_access_query(user),
        )
        _rewrite_titledb_assets(payload, request)
        return payload
    except PermissionError:
        return shop_service.build_expired_response(db, user.id)


@router.get("/browse")
def shop_browse(
    request: FastAPIRequest,
    prefix: str = "",
    user: User = Depends(_basic_auth_user),
    db: Session = Depends(get_db),
):
    """Return one Wasabi prefix as a Tinfoil-compatible folder."""
    base_url = str(request.base_url).rstrip("/")
    try:
        return shop_service.build_wasabi_tree_index(
            db,
            user.id,
            base_url=base_url,
            prefix=prefix,
            access_query=_access_query(user),
        )
    except PermissionError:
        return shop_service.build_expired_response(db, user.id)


@router.get("/folder/{prefix:path}")
def shop_folder(
    request: FastAPIRequest,
    prefix: str,
    access_token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Return one Wasabi prefix using path-style folder URLs for Tinfoil."""
    user = _token_auth_user(access_token, db)
    base_url = str(request.base_url).rstrip("/")
    storage_prefix = shop_service._storage_prefix_for_public_prefix(prefix)
    try:
        return shop_service.build_wasabi_tree_index(
            db,
            user.id,
            base_url=base_url,
            prefix=storage_prefix,
            access_query=f"?access_token={access_token}",
        )
    except PermissionError:
        return shop_service.build_expired_response(db, user.id)


@router.get("/html-folder/{prefix:path}")
def shop_html_folder(
    request: FastAPIRequest,
    prefix: str,
    access_token: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """Return one Wasabi prefix as an HTML directory listing."""
    user = _token_auth_user(access_token, db)
    base_url = str(request.base_url).rstrip("/")
    try:
        return HTMLResponse(
            shop_service.build_wasabi_tree_html(
                db,
                user.id,
                base_url=base_url,
                public_prefix=prefix,
                access_query=f"?access_token={access_token}",
            )
        )
    except PermissionError:
        return shop_service.build_expired_response(db, user.id)


@router.get("/assets/icon/{title_id}")
def shop_icon_asset(title_id: str) -> Response:
    """Serve locally cached icon assets."""
    return _serve_titledb_asset(title_id, "iconUrl")


@router.get("/assets/banner/{title_id}")
def shop_banner_asset(title_id: str) -> Response:
    """Serve locally cached banner assets."""
    return _serve_titledb_asset(title_id, "bannerUrl")


@router.get("/download/{content_id}/{filename:path}")
def shop_download(
    content_id: str,
    filename: str,
    access_token: str = Query(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect authenticated clients to a fresh Wasabi URL with a stable filename path."""
    user = _token_auth_user(access_token, db)
    try:
        shop_service.build_shop_index(db, user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active subscription")

    try:
        parsed_content_id = uuid.UUID(content_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid content id") from exc

    obj = db.query(ContentObject).filter(ContentObject.id == parsed_content_id).first()
    if not obj or not obj.is_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Content not found")
    return RedirectResponse(url=shop_service._resolve_url(obj), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@router.get("/file/{storage_key:path}")
def shop_file(
    storage_key: str,
    access_token: str = Query(default=""),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    """Redirect authenticated clients to a fresh Wasabi URL for any object key."""
    user = _token_auth_user(access_token, db)
    try:
        shop_service.require_active_subscription(db, user.id)
    except PermissionError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active subscription")
    return RedirectResponse(url=shop_service.generate_wasabi_file_url(storage_key), status_code=status.HTTP_307_TEMPORARY_REDIRECT)


def _rewrite_titledb_assets(payload: dict, request: FastAPIRequest) -> None:
    base_url = str(request.base_url).rstrip("/")
    for title_id, entry in payload.get("titledb", {}).items():
        icon_source_id = entry.pop("_iconSourceId", None)
        banner_source_id = entry.pop("_bannerSourceId", None)
        if icon_source_id:
            entry["iconUrl"] = f"{base_url}/shop/assets/icon/{icon_source_id}"
        elif "iconUrl" in entry:
            entry.pop("iconUrl", None)
        if banner_source_id:
            entry["bannerUrl"] = f"{base_url}/shop/assets/banner/{banner_source_id}"
        elif "bannerUrl" in entry:
            entry.pop("bannerUrl", None)


def _serve_titledb_asset(title_id: str, field_name: str) -> Response:
    title_id = title_id.upper()
    if len(title_id) != 16 or any(ch not in "0123456789ABCDEF" for ch in title_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid title id")

    try:
        asset_path, media_type = shop_service.ensure_titledb_asset_cached(title_id, field_name)
    except FileNotFoundError as exc:
        logger.info(
            "shop asset miss field=%s title_id=%s path=%s",
            field_name,
            title_id,
            f"/shop/assets/{'icon' if field_name == 'iconUrl' else 'banner'}/{title_id}",
        )
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found") from exc
    except Exception as exc:
        logger.exception("shop asset error field=%s title_id=%s", field_name, title_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to cache upstream asset",
        ) from exc

    try:
        size_bytes = Path(asset_path).stat().st_size
    except Exception:
        size_bytes = None
    logger.info(
        "shop asset served field=%s title_id=%s size_bytes=%s media_type=%s path=%s",
        field_name,
        title_id,
        size_bytes,
        media_type,
        asset_path,
    )

    return FileResponse(
        asset_path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
