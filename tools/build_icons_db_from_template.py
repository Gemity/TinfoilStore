import argparse
import base64
import hashlib
import json
import re
import struct
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


HEADER_SIZE = 24
SLOT_SIZE = 56
MAX_SLOTS = 65535
DATA_SECTION_SIZE = 32 * 1024 * 1024
DATA_START = HEADER_SIZE + (MAX_SLOTS * SLOT_SIZE)
TITLE_ID_RE = re.compile(r"#.*\[([0-9A-Fa-f]{16})\]")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Patch a working Tinfoil icons.db template with icons from a custom shop feed."
    )
    parser.add_argument("--template", required=True, help="Path to working icons.db template")
    parser.add_argument("--output", required=True, help="Path to write patched icons.db")
    parser.add_argument("--feed-url", required=True, help="Shop feed URL, e.g. http://host/shop/")
    parser.add_argument("--username", required=True, help="Basic auth username for the shop feed")
    parser.add_argument("--password", required=True, help="Basic auth password for the shop feed")
    parser.add_argument(
        "--report",
        help="Optional JSON report path describing patched/skipped title IDs",
    )
    return parser.parse_args()


def fetch_json(url: str, username: str, password: str) -> dict:
    request = Request(url)
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request.add_header("Authorization", f"Basic {token}")
    with urlopen(request, timeout=120) as response:
        return json.load(response)


def fetch_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "TinfoilStore icons.db builder"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def parse_template(path: Path) -> tuple[bytearray, int, dict[str, int]]:
    raw = bytearray(path.read_bytes())
    if len(raw) != DATA_START + DATA_SECTION_SIZE:
        raise ValueError(f"Unexpected template size: {len(raw)}")
    if raw[:4] != b"META":
        raise ValueError("Template is missing META magic")
    used_bytes = struct.unpack("<I", raw[4:8])[0]
    slot_map: dict[str, int] = {}
    for slot_index in range(MAX_SLOTS):
        slot_offset = HEADER_SIZE + (slot_index * SLOT_SIZE)
        tid = struct.unpack("<Q", raw[slot_offset : slot_offset + 8])[0]
        if tid:
            slot_map[f"{tid:016X}"] = slot_offset
    return raw, used_bytes, slot_map


def collect_patch_plan(payload: dict, slot_map: dict[str, int]) -> tuple[list[str], dict[str, str], dict[str, str]]:
    shop_title_ids: set[str] = set()
    for file_entry in payload.get("files", []):
        match = TITLE_ID_RE.search(file_entry.get("url") or "")
        if match:
            shop_title_ids.add(match.group(1).upper())

    icon_urls: dict[str, str] = {}
    skipped: dict[str, str] = {}
    for title_id in sorted(shop_title_ids):
        titledb_entry = payload.get("titledb", {}).get(title_id, {})
        icon_url = titledb_entry.get("iconUrl")
        if title_id not in slot_map:
            skipped[title_id] = "no_slot_in_template"
            continue
        if not icon_url:
            skipped[title_id] = "no_icon_in_feed"
            continue
        icon_urls[title_id] = icon_url
    return sorted(shop_title_ids), icon_urls, skipped


def patch_template(
    template: bytearray,
    used_bytes: int,
    slot_map: dict[str, int],
    icon_urls: dict[str, str],
    skipped: dict[str, str],
) -> tuple[bytearray, dict]:
    offset_by_hash: dict[str, tuple[int, int]] = {}
    next_offset = used_bytes
    patched = 0
    fetch_errors: dict[str, str] = {}

    for title_id, icon_url in icon_urls.items():
        try:
            body = fetch_bytes(icon_url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            fetch_errors[title_id] = f"fetch_error:{type(exc).__name__}"
            continue

        digest = hashlib.sha256(body).hexdigest()
        if digest not in offset_by_hash:
            size = len(body)
            end_offset = next_offset + size
            if end_offset > DATA_SECTION_SIZE:
                fetch_errors[title_id] = "data_section_full"
                continue
            data_offset = DATA_START + next_offset
            template[data_offset : data_offset + size] = body
            offset_by_hash[digest] = (next_offset, size)
            next_offset = end_offset

        relative_offset, size = offset_by_hash[digest]
        slot_offset = slot_map[title_id]
        template[slot_offset : slot_offset + 8] = struct.pack("<Q", int(title_id, 16))
        template[slot_offset + 8 : slot_offset + 16] = struct.pack("<Q", (size << 32) | relative_offset)
        patched += 1

    template[4:8] = struct.pack("<I", next_offset)
    report = {
        "shop_title_ids": len(icon_urls) + len(skipped),
        "patched_title_ids": patched,
        "skipped_title_ids": len(skipped),
        "fetch_errors": len(fetch_errors),
        "unique_new_images": len(offset_by_hash),
        "new_image_bytes": sum(size for _, size in offset_by_hash.values()),
        "used_data_bytes": next_offset,
        "data_capacity_bytes": DATA_SECTION_SIZE,
        "skipped": skipped,
        "fetch_errors_by_title": fetch_errors,
    }
    return template, report


def main() -> None:
    args = parse_args()
    template_path = Path(args.template)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = fetch_json(args.feed_url, args.username, args.password)
    template, used_bytes, slot_map = parse_template(template_path)
    _, icon_urls, skipped = collect_patch_plan(payload, slot_map)
    patched_template, report = patch_template(template, used_bytes, slot_map, icon_urls, skipped)
    output_path.write_bytes(patched_template)

    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
