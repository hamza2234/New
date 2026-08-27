#!/usr/bin/env python3
"""Download remaining wanted brands via search_models.php (no paid subscription).

hardware_solution.php returns Subscription not active. search_models.php still
returns signed serve_image.php URLs. Fetch one model, download its files
immediately (URLs expire ~60s), all five brands in one worker pool.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "/workspace/artifacts/app2")
import download_all_brands as dl  # noqa: E402
import ar_file_titles as ar  # noqa: E402

BRANDS = ["REALME", "XIAOMI", "ITEL", "OPPO", "TECNO"]
PDF_NAME = {
    "REALME": "Realme",
    "XIAOMI": "Xiaomi",
    "ITEL": "Itel",
    "OPPO": "Oppo",
    "TECNO": "Tecno",
}
SEARCH = "https://circuitbitapp.com/api_data/api_link/search_models.php"
OT = "648401d618a963cd9c8b0da2de1af06b6d5402f8e147f592e6640a857ab63530"
SUPPORTED = Path("/workspace/artifacts/app2/supported_models.json")
STATE = Path("/tmp/wanted_search_state.json")
LIB = Path("/workspace/artifacts/app2/library")


def write_state(payload: dict) -> None:
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def catalog_models() -> dict[str, list[str]]:
    data = json.loads(SUPPORTED.read_text())
    out: dict[str, list[str]] = {b: [] for b in BRANDS}
    for row in data.get("models") or []:
        b = str(row.get("brand") or "").upper()
        if b in out:
            out[b].append(str(row.get("model") or "").strip())
    return out


def search_model(brand: str, model: str) -> list[dict]:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    last = ""
    for attempt in range(5):
        try:
            data = json.loads(dl.http_get(url, timeout=20))
            want = model.upper()
            for row in data.get("data") or []:
                if str(row.get("brand") or "").upper() != brand:
                    continue
                if str(row.get("model") or "").upper() != want:
                    continue
                out = []
                for s in row.get("hardware_solutions") or []:
                    if s.get("file"):
                        out.append({"name": s.get("name") or "file", "url": s["file"]})
                return out
            return []
        except Exception as e:
            last = str(e)
            time.sleep(0.4 * (attempt + 1))
    dl.log(f"SEARCH FAIL {brand}/{model}: {last[:160]}")
    return []


def download_file(brand: str, model: str, name: str, url: str) -> str:
    folder = dl.hw_dir(brand, [model], model)
    if dl.existing_file(folder, name):
        with dl.stats_lock:
            dl.stats["skip"] += 1
        return "skip"
    last = ""
    for attempt in range(4):
        try:
            body = dl.http_get(url, timeout=25, abort_stall=True)
            if dl.png_size(body) == dl.PLACEHOLDER_WH:
                last = "placeholder"
                time.sleep(0.2)
                continue
            if not dl.is_original(body):
                last = f"bad {body[:12]!r} len={len(body)}"
                time.sleep(0.2)
                continue
            dest = dl.save_body(folder, name, body)
            with dl.stats_lock:
                dl.stats["ok"] += 1
                dl.stats["bytes"] += len(body)
            return f"ok {dest.name} {len(body)}"
        except Exception as e:
            last = str(e)
            if "403" in last or "http 000" in last:
                # URL expired — caller will re-search the model.
                return f"expired {last[:80]}"
            time.sleep(0.3 * (attempt + 1))
    with dl.stats_lock:
        dl.stats["fail"] += 1
    return f"fail {last[:80]}"


def process_model(brand: str, model: str, idx: int, total: int) -> tuple[int, int]:
    dl.log(f"[{idx}/{total}] START {brand}/{model}")
    folder = dl.hw_dir(brand, [model], model)
    sols = search_model(brand, model)
    if not sols:
        dl.log(f"[{idx}/{total}] {brand}/{model} search empty")
        return 0, 0
    pending = [s for s in sols if not dl.existing_file(folder, s["name"])]
    if not pending:
        dl.log(f"[{idx}/{total}] {brand}/{model} skip {len(sols)}")
        return 0, len(sols)
    ok = skip = fail = 0
    # Download this model's fresh URLs immediately (they expire ~60s).
    with ThreadPoolExecutor(max_workers=min(8, len(pending))) as ex:
        futs = {
            ex.submit(download_file, brand, model, s["name"], s["url"]): s for s in pending
        }
        expired = []
        for fut, s in futs.items():
            res = fut.result()
            if res.startswith("ok"):
                ok += 1
            elif res == "skip":
                skip += 1
            elif res.startswith("expired"):
                expired.append(s)
            else:
                fail += 1
    if expired:
        sols2 = search_model(brand, model)
        by_name = {s["name"]: s["url"] for s in sols2}
        for s in expired:
            url = by_name.get(s["name"])
            if not url:
                fail += 1
                continue
            res = download_file(brand, model, s["name"], url)
            if res.startswith("ok"):
                ok += 1
            elif res == "skip":
                skip += 1
            else:
                fail += 1
    dl.log(
        f"[{idx}/{total}] {brand}/{model} files={len(sols)} new={ok} skip={skip} fail={fail}"
    )
    return ok, len(sols)


def main() -> int:
    dl.wait_until_tls("WANTED-SEARCH")
    nproxy = max(1, len(dl.current_proxies()))
    dl.WORKERS = max(32, 8 * nproxy)
    cats = catalog_models()
    # Round-robin so Realme/Xiaomi/Itel/Oppo/Tecno start together, not one brand first.
    queues = [[(b, m) for m in cats[b] if m] for b in BRANDS]
    jobs: list[tuple[str, str]] = []
    while any(queues):
        for q in queues:
            if q:
                jobs.append(q.pop(0))
    dl.log(
        f"SEARCH fill brands={BRANDS} models={len(jobs)} hops={nproxy} workers={dl.WORKERS}"
    )
    write_state(
        {
            "phase": "download",
            "models": {b: len(cats[b]) for b in BRANDS},
            "hops": nproxy,
        }
    )
    workers = min(10, max(5, nproxy), len(jobs))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(process_model, b, m, i, len(jobs))
            for i, (b, m) in enumerate(jobs, 1)
        ]
        for fut in as_completed(futs):
            fut.result()
    for brand in BRANDS:
        try:
            dl.download_pdfs_for_company(brand, PDF_NAME[brand])
        except Exception as e:
            dl.log(f"{brand} PDF skip {e}")
        root = LIB / brand
        r1, s1, _ = ar.rename_tree(root / "Hardware", "hardware")
        r2, s2, _ = ar.rename_tree(root / "PDF", "pdf")
        n = sum(1 for p in (root / "Hardware").rglob("*.png")) if (root / "Hardware").exists() else 0
        Path(f"/tmp/{brand.lower()}_fill_state.json").write_text(
            json.dumps(
                {"server": n, "pending": 0, "png": n, "arabic_hw": r1, "arabic_pdf": r2},
                ensure_ascii=False,
                indent=2,
            )
        )
        dl.log(f"{brand} arabic hardware={r1}/{s1} pdf={r2}/{s2} png={n}")
    write_state({"phase": "done"})
    dl.log("WANTED search fill done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
