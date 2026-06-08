"""Build the Tinfoil-compatible shop index."""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config
from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from shop_backend.config import VN_TZ, settings
from shop_backend.db.models import ContentObject, Subscription
from shop_backend.services.subscription_service import get_active_subscription
from shop_backend.storage.wasabi import generate_presigned_url

logger = logging.getLogger(__name__)

TITLE_ID_RE = re.compile(r"\[([0-9A-Fa-f]{16})\]")
TITLEDB_PATH = os.path.join(os.path.dirname(__file__), "..", "titledb.json")
TITLEDB_PATH_ALT = "/opt/tinfoilstore/titledb.json"
ASSET_CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "asset_cache"))
ASSET_CACHE_DIR_ALT = "/opt/tinfoilstore/asset_cache"
ICON_MAX_SIZE = (256, 256)
BANNER_MAX_SIZE = (640, 360)
ICON_MAX_BYTES = 80 * 1024
BANNER_MAX_BYTES = 160 * 1024
GAME_EXTENSIONS = (".nsp", ".nsz", ".xci", ".xcz")
VIET_HOA_PREFIX = "TGNN Store [VIệt Hoá]/"

_titledb_cache: dict | None = None


def get_wasabi_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.WASABI_ENDPOINT_URL,
        region_name=settings.WASABI_REGION,
        aws_access_key_id=settings.WASABI_ACCESS_KEY_ID,
        aws_secret_access_key=settings.WASABI_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def _load_titledb() -> dict:
    """Load official titledb and index by title ID."""
    global _titledb_cache
    if _titledb_cache is not None:
        return _titledb_cache

    _titledb_cache = {}
    path = TITLEDB_PATH if os.path.exists(TITLEDB_PATH) else TITLEDB_PATH_ALT
    if not os.path.exists(path):
        logger.warning("titledb.json not found, icons will not be available")
        return _titledb_cache

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        for _nsu_id, entry in raw.items():
            tid = entry.get("id")
            if tid:
                _titledb_cache[tid.upper()] = entry
        logger.info("Loaded titledb: %d entries", len(_titledb_cache))
    except Exception as exc:
        logger.error("Failed to load titledb: %s", exc)

    return _titledb_cache


def get_titledb_entry(title_id: str) -> dict:
    """Return TitleDB metadata for a title ID."""
    return _load_titledb().get(title_id.upper(), {})


def ensure_titledb_asset_cached(title_id: str, field_name: str) -> tuple[str, str]:
    """Download an icon/banner from TitleDB to local disk if needed."""
    entry = get_titledb_entry(title_id)
    asset_url = entry.get(field_name)
    if not asset_url:
        base_tid = _derive_base_title_id(title_id)
        if base_tid and base_tid.upper() != title_id.upper():
            asset_url = get_titledb_entry(base_tid).get(field_name)
    if not asset_url:
        raise FileNotFoundError(f"{field_name} not found for title {title_id}")

    cache_dir = _get_asset_cache_dir()
    suffix = _guess_asset_suffix(asset_url)
    asset_path = cache_dir / field_name / f"{title_id.upper()}{suffix}"
    asset_path.parent.mkdir(parents=True, exist_ok=True)

    if asset_path.exists() and asset_path.stat().st_size > 0:
        _normalize_cached_asset(asset_path, field_name)
        return str(asset_path), _guess_media_type(asset_path.suffix)

    req = Request(asset_url, headers={"User-Agent": "TinfoilStore/1.0"})
    with urlopen(req, timeout=20) as upstream:
        body = upstream.read()
        media_type = upstream.headers.get_content_type() or _guess_media_type(suffix)

    tmp_path = asset_path.with_suffix(f"{asset_path.suffix}.tmp")
    with open(tmp_path, "wb") as f:
        f.write(body)
    os.replace(tmp_path, asset_path)
    _normalize_cached_asset(asset_path, field_name)
    return str(asset_path), media_type


def cache_titledb_assets_for_content(db: Session) -> dict[str, int]:
    """Warm the local asset cache for enabled content items."""
    stats = {"titles": 0, "iconUrl": 0, "bannerUrl": 0}
    items = (
        db.query(ContentObject)
        .filter(ContentObject.is_enabled.is_(True))
        .all()
    )
    official_db = _load_titledb()
    icon_name_map = _build_titledb_name_map(official_db, "iconUrl")
    banner_name_map = _build_titledb_name_map(official_db, "bannerUrl")
    content_icon_map = _build_content_name_map(items, official_db, "iconUrl")
    content_banner_map = _build_content_name_map(items, official_db, "bannerUrl")
    seen_title_ids: set[str] = set()

    for item in items:
        title_id = _extract_title_id(item.title)
        if not title_id or title_id in seen_title_ids:
            continue
        seen_title_ids.add(title_id)
        stats["titles"] += 1
        source_ids = {
            "iconUrl": _resolve_asset_source_title_id(
                title_id, item.title, official_db, content_icon_map, icon_name_map, "iconUrl"
            ),
            "bannerUrl": _resolve_asset_source_title_id(
                title_id, item.title, official_db, content_banner_map, banner_name_map, "bannerUrl"
            ),
        }
        for field_name, source_title_id in source_ids.items():
            if not source_title_id:
                continue
            try:
                ensure_titledb_asset_cached(source_title_id, field_name)
            except FileNotFoundError:
                continue
            else:
                stats[field_name] += 1
    return stats


def build_shop_index(db: Session, user_id: uuid.UUID, base_url: str | None = None) -> dict:
    """Return a Tinfoil-format dict for the authenticated user."""
    sub = get_active_subscription(db, user_id)
    if not sub:
        raise PermissionError("No active subscription")

    official_db = _load_titledb()
    items = (
        db.query(ContentObject)
        .filter(ContentObject.is_enabled.is_(True))
        .order_by(ContentObject.title)
        .all()
    )
    icon_name_map = _build_titledb_name_map(official_db, "iconUrl")
    banner_name_map = _build_titledb_name_map(official_db, "bannerUrl")
    content_icon_map = _build_content_name_map(items, official_db, "iconUrl")
    content_banner_map = _build_content_name_map(items, official_db, "bannerUrl")

    files = []
    titledb = {}

    for item in items:
        if base_url:
            quoted_title = quote(item.title, safe="")
            url = f"{base_url}/shop/download/{item.id}/{quoted_title}"
        else:
            url = _resolve_url(item)
        url = f"{url}#{item.title}"
        entry: dict = {"url": url}
        if item.size_bytes is not None:
            entry["size"] = item.size_bytes
        files.append(entry)

        title_id = _extract_title_id(item.title)
        if not title_id:
            continue

        official_entry = official_db.get(title_id, {})
        icon_source_id = _resolve_asset_source_title_id(
            title_id, item.title, official_db, content_icon_map, icon_name_map, "iconUrl"
        )
        banner_source_id = _resolve_asset_source_title_id(
            title_id, item.title, official_db, content_banner_map, banner_name_map, "bannerUrl"
        )
        icon_entry = official_db.get(icon_source_id, {}) if icon_source_id else {}
        banner_entry = official_db.get(banner_source_id, {}) if banner_source_id else {}
        meta_entry = official_entry or icon_entry or banner_entry

        titledb[title_id] = {
            "id": title_id,
            "name": meta_entry.get("name") or _clean_game_name(item.title),
            "size": item.size_bytes or 0,
        }
        if icon_source_id:
            titledb[title_id]["_iconSourceId"] = icon_source_id
        if banner_source_id:
            titledb[title_id]["_bannerSourceId"] = banner_source_id
        publisher = meta_entry.get("publisher")
        if publisher:
            titledb[title_id]["publisher"] = publisher
        description = meta_entry.get("description")
        if description:
            titledb[title_id]["description"] = description

    referrer = f"{base_url}/shop/" if base_url else None
    payload = {
        "files": files,
        "directories": [],
        "titledb": titledb,
        "success": "Welcome to TinfoilStore!",
    }
    if referrer:
        payload["referrer"] = referrer
    return payload


def build_wasabi_tree_index(db: Session, user_id: uuid.UUID, base_url: str, prefix: str = "") -> dict:
    """Return direct Wasabi objects as a Tinfoil browse tree."""
    require_active_subscription(db, user_id)

    client = get_wasabi_client()
    bucket = settings.WASABI_BUCKET
    normalized_prefix = _normalize_s3_prefix(prefix)
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=normalized_prefix, Delimiter="/")

    directories = []
    files = []
    for page in pages:
        for item in page.get("CommonPrefixes", []):
            child_prefix = item.get("Prefix", "")
            name = _display_name_for_prefix(child_prefix)
            public_prefix = _public_prefix_for_storage_prefix(child_prefix)
            url = f"{base_url}/shop/folder/{quote(public_prefix, safe='/')}/"
            directories.append(url)

        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key == normalized_prefix or key.endswith("/"):
                continue
            name = key.rsplit("/", 1)[-1]
            url = f"{base_url}/shop/file/{quote(key, safe='/')}#{name}"
            entry = {"url": url}
            if obj.get("Size") is not None:
                entry["size"] = obj["Size"]
            files.append(entry)

    return {
        "files": sorted(files, key=lambda item: item["url"].lower()),
        "directories": sorted(directories, key=str.lower),
        "titledb": {},
        "success": f"Browsing {normalized_prefix or 'Wasabi root'}",
        "referrer": f"{base_url}/shop/",
    }


def build_mixed_root_index(db: Session, user_id: uuid.UUID, base_url: str) -> dict:
    """Return installable game files flat plus one Vietnamese patch folder."""
    require_active_subscription(db, user_id)

    client = get_wasabi_client()
    bucket = settings.WASABI_BUCKET
    paginator = client.get_paginator("list_objects_v2")
    files = []
    titledb = {}

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue
            is_game_file = key.lower().endswith(GAME_EXTENSIONS)
            is_viet_hoa_file = key.startswith(VIET_HOA_PREFIX)
            if is_viet_hoa_file or not is_game_file:
                continue

            name = key.rsplit("/", 1)[-1]
            url = f"{base_url}/shop/file/{quote(key, safe='/')}#{name}"
            entry = {"url": url}
            if obj.get("Size") is not None:
                entry["size"] = obj["Size"]
            files.append(entry)

            title_id = _extract_title_id(key.rsplit("/", 1)[-1])
            if is_game_file and title_id:
                titledb[title_id] = {
                    "id": title_id,
                    "name": _clean_game_name(key.rsplit("/", 1)[-1]),
                    "size": obj.get("Size") or 0,
                }

    return {
        "files": sorted(files, key=_shop_entry_display_name),
        "directories": [f"{base_url}/shop/folder/{quote('Việt Hóa', safe='')}/"],
        "titledb": titledb,
        "success": "Welcome to TinfoilStore!",
        "referrer": f"{base_url}/shop/",
    }


def build_mixed_root_html(db: Session, user_id: uuid.UUID, base_url: str) -> str:
    """Return an HTML directory listing for Tinfoil's HTTP parser."""
    require_active_subscription(db, user_id)

    client = get_wasabi_client()
    bucket = settings.WASABI_BUCKET
    paginator = client.get_paginator("list_objects_v2")
    links = [
        _html_link(
            f"{base_url}/shop/html-folder/{quote('Việt Hóa', safe='')}/",
            "Việt Hóa/",
        )
    ]

    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/") or key.startswith(VIET_HOA_PREFIX):
                continue
            if not key.lower().endswith(GAME_EXTENSIONS):
                continue
            name = key.rsplit("/", 1)[-1]
            links.append(_html_link(f"{base_url}/shop/file/{quote(key, safe='/')}", name))

    return _html_listing("TinfoilStore", sorted(links, key=str.lower))


def build_wasabi_tree_html(db: Session, user_id: uuid.UUID, base_url: str, public_prefix: str) -> str:
    """Return an HTML listing for one public folder path."""
    require_active_subscription(db, user_id)

    client = get_wasabi_client()
    bucket = settings.WASABI_BUCKET
    storage_prefix = _storage_prefix_for_public_prefix(public_prefix)
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=storage_prefix, Delimiter="/")
    links = []

    for page in pages:
        for item in page.get("CommonPrefixes", []):
            child_prefix = item.get("Prefix", "")
            child_public_prefix = _public_prefix_for_storage_prefix(child_prefix)
            name = _display_name_for_prefix(child_public_prefix)
            links.append(_html_link(f"{base_url}/shop/html-folder/{quote(child_public_prefix, safe='/')}/", f"{name}/"))

        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key == storage_prefix or key.endswith("/"):
                continue
            name = key.rsplit("/", 1)[-1]
            links.append(_html_link(f"{base_url}/shop/file/{quote(key, safe='/')}", name))

    title = public_prefix.rstrip("/") or "TinfoilStore"
    return _html_listing(title, sorted(links, key=str.lower))


def generate_wasabi_file_url(storage_key: str) -> str:
    return generate_presigned_url(
        storage_key=storage_key,
        bucket_override=None,
        ttl_seconds=settings.WASABI_PRESIGN_TTL_SECONDS,
    )


def require_active_subscription(db: Session, user_id: uuid.UUID) -> None:
    if not get_active_subscription(db, user_id):
        raise PermissionError("No active subscription")


def build_icon_debug_info(db: Session, title_id: str) -> dict:
    """Return detailed icon mapping/debug information for a title ID."""
    title_id = title_id.upper()
    official_db = _load_titledb()
    items = (
        db.query(ContentObject)
        .filter(ContentObject.is_enabled.is_(True))
        .order_by(ContentObject.title)
        .all()
    )
    icon_name_map = _build_titledb_name_map(official_db, "iconUrl")
    banner_name_map = _build_titledb_name_map(official_db, "bannerUrl")
    content_icon_map = _build_content_name_map(items, official_db, "iconUrl")
    content_banner_map = _build_content_name_map(items, official_db, "bannerUrl")

    matched_item = None
    for item in items:
        if _extract_title_id(item.title) == title_id:
            matched_item = item
            break

    item_title = matched_item.title if matched_item else None
    icon_source_id = (
        _resolve_asset_source_title_id(
            title_id,
            item_title or title_id,
            official_db,
            content_icon_map,
            icon_name_map,
            "iconUrl",
        )
        if item_title
        else _resolve_direct_or_base_asset_title_id(title_id, official_db, "iconUrl")
    )
    banner_source_id = (
        _resolve_asset_source_title_id(
            title_id,
            item_title or title_id,
            official_db,
            content_banner_map,
            banner_name_map,
            "bannerUrl",
        )
        if item_title
        else _resolve_direct_or_base_asset_title_id(title_id, official_db, "bannerUrl")
    )

    icon_path = None
    icon_exists = False
    icon_size = None
    if icon_source_id:
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            candidate = _get_asset_cache_dir() / "iconUrl" / f"{icon_source_id}{suffix}"
            if candidate.exists():
                icon_path = str(candidate)
                icon_exists = True
                icon_size = candidate.stat().st_size
                break

    return {
        "requested_title_id": title_id,
        "matched_item_title": item_title,
        "clean_name": _clean_game_name(item_title) if item_title else None,
        "direct_titledb_entry": bool(official_db.get(title_id)),
        "base_title_id": _derive_base_title_id(title_id),
        "icon_source_id": icon_source_id,
        "banner_source_id": banner_source_id,
        "icon_source_name": official_db.get(icon_source_id, {}).get("name") if icon_source_id else None,
        "banner_source_name": official_db.get(banner_source_id, {}).get("name") if banner_source_id else None,
        "icon_exists_on_disk": icon_exists,
        "icon_cache_path": icon_path,
        "icon_cache_size": icon_size,
        "direct_icon_url_in_titledb": official_db.get(title_id, {}).get("iconUrl"),
        "base_icon_url_in_titledb": official_db.get(_derive_base_title_id(title_id) or "", {}).get("iconUrl"),
    }


def _resolve_url(obj: ContentObject) -> str:
    """Return a presigned or direct URL for a content object."""
    if obj.is_protected:
        return generate_presigned_url(
            storage_key=obj.storage_key,
            bucket_override=obj.bucket_override,
            ttl_seconds=settings.WASABI_PRESIGN_TTL_SECONDS,
        )
    bucket = obj.bucket_override or settings.WASABI_BUCKET
    return f"{settings.WASABI_ENDPOINT_URL}/{bucket}/{obj.storage_key}"


def _normalize_s3_prefix(prefix: str) -> str:
    prefix = (prefix or "").lstrip("/")
    if prefix and not prefix.endswith("/"):
        prefix = f"{prefix}/"
    return prefix


def _display_name_for_prefix(prefix: str) -> str:
    return prefix.rstrip("/").rsplit("/", 1)[-1]


def _shop_entry_display_name(entry: dict) -> str:
    return entry["url"].split("#", 1)[-1].lower()


def _html_link(url: str, label: str) -> str:
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a><br>'


def _html_listing(title: str, links: list[str]) -> str:
    return (
        "<!doctype html><html><head>"
        f"<title>{escape(title)}</title>"
        "</head><body>"
        f"<h1>{escape(title)}</h1>"
        + "\n".join(links)
        + "</body></html>"
    )


def _storage_prefix_for_public_prefix(prefix: str) -> str:
    prefix = _normalize_s3_prefix(prefix)
    if prefix == "Việt Hóa/":
        return VIET_HOA_PREFIX
    if prefix.startswith("Việt Hóa/"):
        return f"{VIET_HOA_PREFIX}{prefix[len('Việt Hóa/'):]}"
    return prefix


def _public_prefix_for_storage_prefix(prefix: str) -> str:
    prefix = _normalize_s3_prefix(prefix)
    if prefix == VIET_HOA_PREFIX:
        return "Việt Hóa"
    if prefix.startswith(VIET_HOA_PREFIX):
        return f"Việt Hóa/{prefix[len(VIET_HOA_PREFIX):].rstrip('/')}"
    return prefix.rstrip("/")


def _extract_title_id(filename: str) -> str | None:
    """Extract 16-char hex title ID from filename."""
    match = TITLE_ID_RE.search(filename)
    return match.group(1).upper() if match else None


def _clean_game_name(filename: str) -> str:
    """Remove brackets, version, region, and extension from filename."""
    name = re.sub(r"\.(nsp|nsz|xci|xcz)$", "", filename, flags=re.IGNORECASE)
    name = re.sub(r"\s*\[[^\]]*\]", "", name)
    return name.strip()


def _normalize_lookup_name(name: str) -> str:
    name = _clean_game_name(name).lower()
    name = re.sub(r"[^a-z0-9]+", " ", name)
    return " ".join(name.split())


def _derive_base_title_id(title_id: str) -> str | None:
    if len(title_id) != 16:
        return None
    return title_id[:13] + "000"


def _build_titledb_name_map(official_db: dict, field_name: str) -> dict[str, str]:
    name_map: dict[str, str] = {}
    for title_id, entry in official_db.items():
        if entry.get(field_name) and entry.get("name"):
            name_map.setdefault(_normalize_lookup_name(entry["name"]), title_id)
    return name_map


def _build_content_name_map(items: list[ContentObject], official_db: dict, field_name: str) -> dict[str, str]:
    name_map: dict[str, str] = {}
    seen: set[str] = set()
    for item in items:
        title_id = _extract_title_id(item.title)
        if not title_id or title_id in seen:
            continue
        seen.add(title_id)
        source_title_id = _resolve_direct_or_base_asset_title_id(title_id, official_db, field_name)
        if source_title_id:
            name_map.setdefault(_normalize_lookup_name(item.title), source_title_id)
    return name_map


def _resolve_asset_source_title_id(
    title_id: str,
    item_title: str,
    official_db: dict,
    content_name_map: dict[str, str],
    titledb_name_map: dict[str, str],
    field_name: str,
) -> str | None:
    direct_source = _resolve_direct_or_base_asset_title_id(title_id, official_db, field_name)
    if direct_source:
        return direct_source
    normalized_name = _normalize_lookup_name(item_title)
    return content_name_map.get(normalized_name) or titledb_name_map.get(normalized_name)


def _resolve_direct_or_base_asset_title_id(title_id: str, official_db: dict, field_name: str) -> str | None:
    if official_db.get(title_id, {}).get(field_name):
        return title_id
    base_title_id = _derive_base_title_id(title_id)
    if base_title_id and base_title_id != title_id and official_db.get(base_title_id, {}).get(field_name):
        return base_title_id
    return None


def _get_asset_cache_dir() -> Path:
    path = Path(ASSET_CACHE_DIR if os.path.isdir(ASSET_CACHE_DIR) else ASSET_CACHE_DIR_ALT)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _guess_asset_suffix(asset_url: str) -> str:
    lower_url = asset_url.lower()
    for suffix in (".jpg", ".jpeg", ".png", ".webp"):
        if lower_url.endswith(suffix):
            return suffix
    return ".jpg"


def _guess_media_type(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".png":
        return "image/png"
    if suffix == ".webp":
        return "image/webp"
    return "application/octet-stream"


def _normalize_cached_asset(asset_path: Path, field_name: str) -> None:
    max_size = ICON_MAX_SIZE if field_name == "iconUrl" else BANNER_MAX_SIZE
    max_bytes = ICON_MAX_BYTES if field_name == "iconUrl" else BANNER_MAX_BYTES
    if asset_path.stat().st_size <= max_bytes and asset_path.suffix.lower() in (".jpg", ".jpeg"):
        return

    tmp_path = asset_path.with_suffix(f"{asset_path.suffix}.tmp")
    try:
        with Image.open(asset_path) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            img.save(tmp_path, format="JPEG", quality=82, optimize=True)
        os.replace(tmp_path, asset_path)
    except Exception as exc:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        logger.warning("Failed to normalize cached %s asset %s: %s", field_name, asset_path, exc)


def build_expired_response(db: Session, user_id: uuid.UUID) -> dict:
    """Return a Tinfoil error response when subscription is expired."""
    last_sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id)
        .order_by(Subscription.ends_at.desc())
        .first()
    )

    if last_sub:
        ended = last_sub.ends_at
        if ended.tzinfo is None:
            ended = ended.replace(tzinfo=timezone.utc)
        ended_vn = ended.astimezone(VN_TZ).strftime("%d/%m/%Y %H:%M")
        msg = (
            f"Subscription da het han vao {ended_vn}.\n"
            f"Vui long lien he admin de gia han."
        )
    else:
        msg = "Ban chua co subscription.\nVui long lien he admin de dang ky."

    return {
        "files": [],
        "directories": [],
        "error": msg,
    }
