# Tinfoil Icon Issue - Ongoing Investigation

## Problem

Shop feed loads and game list appears correctly in Tinfoil, but game icons display at a very low rate.

Observed behavior:

- On one Switch, only 4 games show icons:
  - Balatro
  - Astral Chain
  - 30-in-1 Game Collection
  - Animal Well
- On other Switch consoles using the same shop, the number and type of visible icons are different.
- In general, icon coverage is low on all tested consoles.

This inconsistency across devices is the key symptom.

## Environment

- Tinfoil installed as NSP/system app
- Atmosphere: `1.10.1`
- Hekate: `6.4.2`
- Some tested consoles use `90DNS`, so Nintendo domains are blocked
- Backend server: `180.93.35.196`
- Stack: `Ubuntu 24.04 + nginx + FastAPI + PostgreSQL + Wasabi`
- Shop feed: `http://180.93.35.196/shop/`
- Current content volume:
  - `1402` files in shop feed
  - `1333` titledb entries in payload
  - `1057` titledb entries with `iconUrl`
  - `1289` titledb entries with `bannerUrl`
- From live payload analysis:
  - `1112` files can be mapped to a `title_id` and have `iconUrl`
  - `284` files currently do not have `iconUrl`
  - `6` files do not expose a parsable `title_id` in the URL fragment

## Attempts

### 1. Proxy icon URLs through our own server

What we tried:

- Rewrote `titledb.iconUrl` to `http://180.93.35.196/shop/assets/icon/{title_id}`
- Added local icon and banner endpoints on the backend

Result:

- Feed returns the rewritten local URLs correctly
- Some historical server logs showed requests to `/shop/assets/icon/...`
- But the most recent real Switch session only requested `GET /shop/` and did not request any icon endpoint

Meaning:

- Tinfoil may use custom icon URLs in some situations, but not reliably
- It is not safe to assume that `iconUrl` from the custom shop is the primary source for grid icons

### 2. Save icons locally on the VPS

What we tried:

- Downloaded and cached TitleDB icons/banners to:
  - `/opt/tinfoilstore/asset_cache/iconUrl/`
  - `/opt/tinfoilstore/asset_cache/bannerUrl/`
- Verified files exist on disk for games such as Balatro

Result:

- Local cache works
- Example:
  - `Balatro` icon exists at `/opt/tinfoilstore/asset_cache/iconUrl/0100CD801CE5E000.jpg`
- Manual requests to the endpoint return `200 OK`

Meaning:

- Missing icon display is not caused by “server has no icon file”

### 3. Optimize image size and format

What we tried:

- Resized cached images with Pillow
- Reduced many icons to small thumbnails suitable for grid display

Result:

- Example live log:
  - `shop asset served field=iconUrl title_id=0100CD801CE5E000 size_bytes=18048`

Meaning:

- Slow or oversized server icons are not the main blocker anymore

### 4. Add fallback mapping for update/DLC/base title

What we tried:

- Added fallback from update/DLC title IDs to base game title ID
- Added additional name-based matching heuristics when direct TitleDB match is missing

Result:

- Feed coverage improved significantly
- Example:
  - many files now resolve to some `iconUrl`
- But some titles still have no source icon at all

Example confirmed missing from current data:

- `Cooking Mama Cookstar [010060700EFBA000]`
  - `icon_source_id = null`
  - `icon_exists_on_disk = false`

Meaning:

- Some missing icons are genuine metadata coverage gaps
- But this does not explain the very low display rate on the consoles, because many other titles do have valid icon metadata

### 5. Watermark test on server icon

What we tried:

- Added a visible watermark to the Balatro icon stored on our server

Result:

- Tinfoil still showed the normal Balatro icon, not the watermarked one

Meaning:

- At least for that test, Tinfoil was not using our server icon for that title
- It likely used its own cache, internal DB, or another source

### 7. Reverse engineer icons.db and build custom file

What we tried:

- Fully reverse engineered the META binary format of `icons.db`
- Discovered correct structure:
  - Header: 24 bytes — `META` magic (4) + used data bytes uint32 LE (4) + 16 zero bytes
  - Index: **65,535 slots** × 56 bytes = 3,669,960 bytes (NOT 65,414 — that was wrong)
  - Data section: starts at offset 3,669,984, pre-allocated to exactly 32 MB (33,554,432 bytes)
  - Each slot: uint64 TID + uint64 packed `(size << 32 | offset)` + 40 zero bytes
  - Slot assignment is **sequential** (insertion order), not a hash table
- Built custom `icons.db` from 391 cached icons on server
- First attempt: wrong MAX_SLOTS (65,414) → file silently rejected
- Second attempt: correct MAX_SLOTS (65,535) → file size exactly matches original (37,224,416 bytes)
- Confirmed JPEG data at correct data section offset (0xFFD8FFE0)
- Served at `http://180.93.35.196/icons.db`

Result:

- User copied file to `SD:/switch/tinfoil/db/icons.db`
- File becomes 0 bytes after Tinfoil opens — same behavior as working shop's file
- **Zero icons displayed** despite structurally correct file

Key observation from comparison with working shop's `.rar`:

| | Working shop file | Our file |
|---|---|---|
| File → 0B after Tinfoil | ✓ | ✓ |
| Icons displayed | ~50% | 0% |

Meaning:

- Both files become 0B → Tinfoil reads the file first, then reinitializes it
- Working shop file is read and imported successfully by Tinfoil
- Our file is either not read at all, or read but fails an internal validation step
- The 0B truncation is NOT the cause of icons not showing — it is normal Tinfoil behavior

Remaining unknowns:

- Tinfoil may validate something in the file before accepting it (version, checksum, TID count, etc.)
- OR icons.db alone is not sufficient — `Images*.db` shards may also be required
- We have not been able to inspect the contents of the working shop's `.rar` to compare

### 6. Add live logging for icon requests

What we tried:

- Added detailed logging to `/shop/assets/icon/{title_id}`
- Added admin debug endpoint:
  - `GET /admin/icon-debug/{title_id}`

Result:

- We can now verify, per title:
  - whether server has an icon
  - where the icon was mapped from
  - whether the icon exists on disk
- Recent live observation:
  - Switch session at `2026-04-05 00:58:54 +07` requested only `GET /shop/`
  - No icon requests followed in that session

Meaning:

- In at least that session, the client did not even attempt to use our custom icon endpoints

## Results

Current strongest facts:

1. The server is providing far more icon metadata than what is visible on the Switch.
2. The server can successfully serve local cached icons.
3. Different Switch consoles show different icon subsets while consuming the same shop feed.
4. At least some sessions do not request `/shop/assets/icon/...` at all.
5. Some titles genuinely have no icon metadata available, but that only explains a minority of missing icons.
6. `icons.db` binary format is fully reverse engineered (META, 65535 slots, 32MB pre-alloc, sequential slot assignment).
7. A structurally correct `icons.db` with 391 icons was built and deployed — still 0 icons shown.
8. Tinfoil truncates `icons.db` to 0B on open — this is normal behavior for BOTH working and non-working files.
9. The working shop's file works despite also becoming 0B → Tinfoil reads then reinitializes. Our file fails silently.

## Hypotheses

### Hypothesis A: Tinfoil uses its own icon/image database or cache as the main source

Why this fits:

- Different consoles show different visible icons
- Watermark test did not reflect server icon changes
- Some sessions do not request icon endpoints at all

Status:

- Strongly supported by current evidence

Additional internet evidence:

- Public Tinfoil changelog says it added `preload meta images`
- Public Tinfoil changelog also says it started storing images in `image databases rather than on the file system`
- Community reports mention files such as:
  - `icons.db`
  - `Images1.db`
  - `Images2.db`
  - `Images3.db`
  - `Images4.db`
  - `Images5.db`

This strongly suggests Tinfoil maintains an internal image database/cache layer, not just plain image files.

### Hypothesis B: Tinfoil may sometimes use custom `iconUrl`, but only in limited or unstable conditions

Why this fits:

- Historical logs did show requests to `/shop/assets/icon/...`
- Current sessions do not do this consistently

Status:

- Plausible
- Not reliable enough to build the system around

### Hypothesis C: Icon display depends on more than `titledb.iconUrl`

Possible factors:

- internal image database
- metadata cache
- prior downloads on that console
- Tinfoil version differences
- hidden client settings such as icon preload behavior

Status:

- Very likely

### Hypothesis D: The remaining `284` files without icon metadata are not the main reason for the current issue

Why:

- Over `1100` files already map to an icon
- Yet consoles still display only a tiny subset

Status:

- Strongly supported

### Hypothesis E: The `.rar` package seen in community videos may contain prebuilt local metadata/image databases

Why this fits:

- Community packages and mirrors reference files such as:
  - `icons.db`
  - `titles.US.en.json`
- Community discussions also reference `Images1.db` through `Images5.db`
- This matches Tinfoil's public changelog language about image databases

Important limitation:

- We have not verified the exact `.rar` package from the referenced YouTube Short
- This remains an inference, not a confirmed identification of that exact file

Status:

- Plausible and supported by surrounding evidence

## Practical Conclusion

Current evidence suggests that we cannot reliably control Tinfoil's icon display behavior purely from the custom shop server.

What we can control:

- shop feed correctness
- title ID extraction
- local icon hosting
- metadata enrichment

What we cannot currently guarantee:

- that Tinfoil will fetch our icon URLs
- that Tinfoil will use our icon URLs for grid thumbnails
- consistent icon display across different Switch consoles

## Recommended Next Steps

### Server-side

- Export the list of the remaining `284` files without icon metadata
- Continue improving metadata coverage where possible

### Client-side

- Compare one “good” console and one “bad” console after icon preload
- Inspect which Tinfoil cache/database files change before and after preload
- Test whether copying Tinfoil-generated image DB/cache between consoles improves coverage

### External support

- Ask Tinfoil maintainers/admins whether custom shop `titledb.iconUrl` is expected to drive grid icons
- Ask where icon/image databases are stored and whether they can be preloaded offline
- Ask what conditions cause Tinfoil to fetch icons from custom shop endpoints versus internal resources

### Offline preload path to investigate

- Compare file changes before and after using Tinfoil's preload icon function
- Focus on:
  - `SD:/switch/tinfoil/DB/`
  - any `icons.db`
  - any `Images*.db`
  - any `titles.US.en.json`
- If the preload process updates a stable set of DB files, test copying those files between consoles with the same Tinfoil/CFW version

### icons.db investigation — next steps

Our custom `icons.db` is structurally valid but still fails. To narrow down why:

1. **Inspect the working `.rar`** — open the working shop's archive and compare its `icons.db` byte-for-byte with ours:
   - Same MAX_SLOTS (65535)?
   - Same header structure?
   - Any extra fields we missed?
   - Does it include `Images*.db` alongside `icons.db`?

2. **Test with a single known-good TID** — copy just one icon that is confirmed in the working shop's DB into our icons.db and test whether that specific icon appears. If yes, the format is correct but our TID list is the issue.

3. **Check if `Images*.db` must also be present** — icons.db may only be an index. The actual pixel data might live in `Images1.db`–`Images7.db` shards. Without those files, `icons.db` cannot display anything regardless of correctness.

4. **Try a pure copy approach** — copy working shop's `icons.db` and swap only a few TID/offset/size entries for our own icons. If that works, the format is 100% correct and the issue is elsewhere (e.g., missing `Images*.db`).

## Useful Debug Data

- Shop endpoint:
  - `/shop/`
- Local icon endpoint:
  - `/shop/assets/icon/{title_id}`
- Admin icon debug endpoint:
  - `/admin/icon-debug/{title_id}`

Example verified title:

- `Balatro`
  - title ID: `0100CD801CE5E000`
  - local icon exists
  - endpoint serves icon successfully
  - Tinfoil still showed non-watermarked icon during test

Example verified missing-metadata title:

- `Cooking Mama Cookstar`
  - title ID: `010060700EFBA000`
  - no icon source found in current mapping

## References

- [Tinfoil Custom Index Documentation](https://blawar.github.io/tinfoil/custom_index/)
- [Tinfoil MTP Documentation](https://blawar.github.io/tinfoil/mtp/)
- [tinfoil-1 public changelog mirror](https://github.com/tiliarou/tinfoil-1)
- [Ghost eShop recurring problems](https://wiki.ghosteshop.com/de/docs/nx/recurring-problems/)
- [Ghost Land article about NX Custom DB](https://ghostland.at/news/2025-10-22-tinfoil-meta-replacement/)
- [Community discussion mentioning `icon.db` and `Images1.db - 5.db`](https://www.reddit.com/r/ghosteshop/comments/1la98kn/tinfoil_pro_shop_no_titles/)
- [Community discussion mentioning `icons.db`](https://www.reddit.com/r/SwitchPirates/comments/p4umu8)
- [Unverified package listing showing `icons.db` and `titles.US.en.json`](https://wenku.csdn.net/doc/4rtztkf086)
