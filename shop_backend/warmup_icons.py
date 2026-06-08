"""Pre-cache all titledb icons/banners for enabled content.

Run on VPS:
    cd /opt/tinfoilstore && source venv/bin/activate
    nohup python -m shop_backend.warmup_icons > /tmp/icon_warmup.log 2>&1 &
"""

import sys
import time

from shop_backend.db.session import SessionLocal
from shop_backend.services.shop_service import (
    _extract_title_id,
    _load_titledb,
    ensure_titledb_asset_cached,
)
from shop_backend.db.models import ContentObject


def main():
    db = SessionLocal()
    titledb = _load_titledb()

    items = (
        db.query(ContentObject)
        .filter(ContentObject.is_enabled.is_(True))
        .all()
    )

    seen = set()
    ok = 0
    fail = 0
    skip = 0
    total = len(items)

    print(f"Warming up icon cache for {total} content items...")

    for i, item in enumerate(items, 1):
        title_id = _extract_title_id(item.title)
        if not title_id or title_id in seen:
            skip += 1
            continue
        seen.add(title_id)

        for field in ("iconUrl", "bannerUrl"):
            try:
                ensure_titledb_asset_cached(title_id, field)
                ok += 1
            except FileNotFoundError:
                pass
            except Exception as e:
                fail += 1
                print(f"  FAIL {title_id} {field}: {e}")

        if i % 50 == 0:
            print(f"  [{i}/{total}] ok={ok} fail={fail} skip={skip}")
            sys.stdout.flush()

    db.close()
    print(f"\nDone! ok={ok} fail={fail} skip={skip} unique_titles={len(seen)}")


if __name__ == "__main__":
    main()
