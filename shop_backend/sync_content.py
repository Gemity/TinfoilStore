"""Scan Wasabi bucket and sync all game files to the database.

Usage:
    python -m shop_backend.sync_content

What it does:
    1. Lists ALL files in your Wasabi bucket
    2. Filters for game files (.nsp, .nsz, .xci, .xcz)
    3. Adds new files to DB (skips files already in DB)
    4. Optionally removes DB entries for deleted files

The file name on Wasabi becomes the title in the shop.
Example: "Super Mario Odyssey [0100000000010000][v0].nsp"
         → title: "Super Mario Odyssey [0100000000010000][v0].nsp"
"""

import argparse
import sys

import boto3
from botocore.config import Config

from shop_backend.config import settings
from shop_backend.db.session import SessionLocal
from shop_backend.db.models import ContentObject


GAME_EXTENSIONS = (".nsp", ".nsz", ".xci", ".xcz")


def get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.WASABI_ENDPOINT_URL,
        region_name=settings.WASABI_REGION,
        aws_access_key_id=settings.WASABI_ACCESS_KEY_ID,
        aws_secret_access_key=settings.WASABI_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
    )


def list_bucket_files(client, bucket: str, prefix: str = "") -> list[dict]:
    """List all objects in the bucket, handling pagination."""
    files = []
    paginator = client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.lower().endswith(GAME_EXTENSIONS):
                files.append({
                    "storage_key": key,
                    "size_bytes": obj["Size"],
                    "title": key.rsplit("/", 1)[-1],  # filename only
                })
    return files


def sync(prefix: str = "", cleanup: bool = False) -> dict:
    """Sync Wasabi bucket to DB. Returns summary dict."""
    client = get_s3_client()
    bucket = settings.WASABI_BUCKET
    db = SessionLocal()

    try:
        return _sync_with_db(db, client, bucket, prefix, cleanup)
    finally:
        db.close()


def sync_with_session(db, prefix: str = "", cleanup: bool = False) -> dict:
    """Sync using an existing DB session (for API endpoint)."""
    client = get_s3_client()
    bucket = settings.WASABI_BUCKET
    return _sync_with_db(db, client, bucket, prefix, cleanup)


def _sync_with_db(db, client, bucket: str, prefix: str, cleanup: bool) -> dict:
    """Core sync logic. Returns summary dict."""
    added_list = []
    removed_list = []

    # 1. Scan Wasabi
    print(f"Scanning bucket '{bucket}'...")
    if prefix:
        print(f"  Prefix filter: {prefix}")
    remote_files = list_bucket_files(client, bucket, prefix)
    print(f"  Found {len(remote_files)} game files on Wasabi\n")

    if not remote_files:
        print("No game files found. Supported extensions:", ", ".join(GAME_EXTENSIONS))
        total = db.query(ContentObject).count()
        return {"added": [], "removed": [], "total": total, "scanned": 0}

    # 2. Get existing entries from DB
    existing_keys = {
        row.storage_key
        for row in db.query(ContentObject.storage_key).all()
    }
    print(f"  Existing in DB: {len(existing_keys)} entries\n")

    # 3. Add new files
    for f in remote_files:
        if f["storage_key"] not in existing_keys:
            obj = ContentObject(
                title=f["title"],
                storage_key=f["storage_key"],
                size_bytes=f["size_bytes"],
                is_protected=True,
                is_enabled=True,
            )
            db.add(obj)
            added_list.append(f["title"])
            print(f"  + {f['title']}  ({_human_size(f['size_bytes'])})")

    if added_list:
        db.commit()
        print(f"\nAdded {len(added_list)} new games to DB")
    else:
        print("No new games to add (all already in DB)")

    # 4. Optional: remove DB entries for files no longer on Wasabi
    if cleanup:
        remote_keys = {f["storage_key"] for f in remote_files}
        stale = db.query(ContentObject).filter(
            ContentObject.storage_key.notin_(remote_keys)
        ).all()
        for obj in stale:
            removed_list.append(obj.title)
            print(f"  - {obj.title}  (removed from DB)")
            db.delete(obj)
        if removed_list:
            db.commit()
            print(f"\nRemoved {len(removed_list)} stale entries from DB")

    # 5. Summary
    total = db.query(ContentObject).count()
    print(f"\nTotal games in DB: {total}")

    return {
        "added": added_list,
        "removed": removed_list,
        "total": total,
        "scanned": len(remote_files),
    }


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human readable string."""
    if size_bytes is None:
        return "unknown"
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description="Sync Wasabi bucket to DB")
    parser.add_argument("--prefix", type=str, default="",
                        help="Only scan files under this prefix/folder (e.g. 'games/')")
    parser.add_argument("--cleanup", action="store_true",
                        help="Remove DB entries for files no longer on Wasabi")
    args = parser.parse_args()

    sync(prefix=args.prefix, cleanup=args.cleanup)


if __name__ == "__main__":
    main()
