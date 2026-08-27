#!/usr/bin/env python3
"""Download remaining wanted brands via search_models.php (no paid subscription).

hardware_solution.php returns Subscription not active. search_models.php still
returns signed serve_image.php URLs (~60s expiry). Search one model, download
its files immediately, all five brands interleaved in one pool.

Lightning path: fail-fast on 403 (re-search), 3 hop retries not 8, more model
workers, public SOCKS hops. Resume-safe. Arabic filenames via save_body().
"""
from __future__ import annotations

import json
import sys
import threading
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

_stop = threading.Event()
_fast = getattr(dl, "http_get_fast", dl.http_get)


def write_state(payload: dict) -> None:
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def catalog_models() -> dict[str, list[str]]:
    data = json.loads(SUPPORTED.read_text())
    out: dict[str, list[str]] = {b: [] for b in BRANDS}
    for row in data.get("models") or []:
        b = str(row.get("brand") or "").upper()
        if b in out:
            out[b].append(str(row.get("model") or "").strip())
    # Black Shark serve_image URLs 404 on every hop; skip them so Redmi/POCO get retries.
    out["XIAOMI"] = [
        m for m in out["XIAOMI"] if not m.upper().startswith("BLACK SHARK")
    ]
    out["XIAOMI"].sort(
        key=lambda m: (
            0
            if m.upper().startswith("REDMI")
            else 1
            if m.upper().startswith("POCO")
            else 2
            if m.upper().startswith("MI ")
            else 3,
            m.upper(),
        )
    )
    return out


def search_model(brand: str, model: str) -> list[dict]:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    last = ""
    for attempt in range(3):
        try:
            data = json.loads(_fast(url, timeout=20))
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
            if "403" in last:
                time.sleep(0.05)
                continue
            time.sleep(0.15 * (attempt + 1))
    dl.log(f"SEARCH FAIL {brand}/{model}: {last[:160]}")
    return []


def download_file(brand: str, model: str, name: str, url: str) -> str:
    folder = dl.hw_dir(brand, [model], model)
    if dl.existing_file(folder, name):
        with dl.stats_lock:
            dl.stats["skip"] += 1
        return "skip"
    try:
        body = _fast(url, timeout=40)
        if dl.png_size(body) == dl.PLACEHOLDER_WH:
            return "fail placeholder"
        if not dl.is_original(body):
            return f"fail bad {body[:12]!r} len={len(body)}"
        dest = dl.save_body(folder, name, body)
        with dl.stats_lock:
            dl.stats["ok"] += 1
            dl.stats["bytes"] += len(body)
        return f"ok {dest.name} {len(body)}"
    except Exception as e:
        last = str(e)
        if "403" in last or "http 000" in last:
            return f"expired {last[:80]}"
        with dl.stats_lock:
            dl.stats["fail"] += 1
        return f"fail {last[:80]}"


def _run_files(brand: str, model: str, pending: list[dict]) -> tuple[int, int, int, list[dict], str]:
    ok = skip = fail = 0
    expired: list[dict] = []
    first = ""
    inner = min(3, max(1, len(pending)))
    with ThreadPoolExecutor(max_workers=inner) as ex:
        futs = {
            ex.submit(download_file, brand, model, s["name"], s["url"]): s for s in pending
        }
        for fut, s in futs.items():
            res = fut.result()
            if res.startswith("ok"):
                ok += 1
            elif res == "skip":
                skip += 1
            elif res.startswith("expired"):
                expired.append(s)
                if not first:
                    first = res
            else:
                fail += 1
                if not first:
                    first = res
    return ok, skip, fail, expired, first


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
    first = ""
    # Fresh URLs die in ~60s — pull immediately, re-search leftovers twice.
    for wave in range(3):
        n_ok, n_skip, n_fail, expired, err = _run_files(brand, model, pending)
        ok += n_ok
        skip += n_skip
        fail += n_fail
        if err and not first:
            first = err
        if not expired:
            break
        sols2 = search_model(brand, model)
        by_name = {s["name"]: s for s in sols2}
        pending = [by_name[s["name"]] for s in expired if s["name"] in by_name]
        fail += len(expired) - len(pending)
        if not pending:
            break
        if wave == 2:
            fail += len(pending)
            pending = []
    extra = f" err={first[:80]}" if first and ok == 0 else ""
    dl.log(
        f"[{idx}/{total}] {brand}/{model} files={len(sols)} new={ok} skip={skip} fail={fail}{extra}"
    )
    return ok, len(sols)


def _rate_loop() -> None:
    prev_ok = 0
    prev_b = 0
    t0 = time.time()
    while not _stop.wait(15):
        ok = int(dl.stats.get("ok") or 0)
        skip = int(dl.stats.get("skip") or 0)
        fail = int(dl.stats.get("fail") or 0)
        b = int(dl.stats.get("bytes") or 0)
        dt = max(1.0, time.time() - t0)
        dl.log(
            f"RATE ok={ok} (+{ok - prev_ok}/15s) skip={skip} fail={fail} "
            f"{b / 1e6:.1f}MB {(b - prev_b) / 1e6 / dt:.1f}MB/s "
            f"hops={len(dl.current_proxies())}"
        )
        prev_ok, prev_b, t0 = ok, b, time.time()


def _clear_stale_fill_state() -> None:
    """Monitor treats pending=0 as 100%. Drop leftovers while a pass is running."""
    for brand in BRANDS:
        path = Path(f"/tmp/{brand.lower()}_fill_state.json")
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _run_pass(cats: dict[str, list[str]]) -> None:
    def run_brand(brand: str, models: list[str]) -> None:
        n = max(2, min(6, max(2, len(dl.current_proxies()) // len(BRANDS))))
        with ThreadPoolExecutor(max_workers=n) as ex:
            futs = [
                ex.submit(process_model, brand, m, i, len(models))
                for i, m in enumerate(models, 1)
            ]
            for fut in as_completed(futs):
                fut.result()

    with ThreadPoolExecutor(max_workers=len(BRANDS)) as ex:
        futs = [ex.submit(run_brand, b, cats[b]) for b in BRANDS]
        for fut in as_completed(futs):
            fut.result()
    for brand in BRANDS:
        root = LIB / brand
        r1, s1, _ = ar.rename_tree(root / "Hardware", "hardware")
        r2, s2, _ = ar.rename_tree(root / "PDF", "pdf")
        n = (
            sum(1 for p in (root / "Hardware").rglob("*.png"))
            if (root / "Hardware").exists()
            else 0
        )
        dl.log(f"{brand} arabic hardware={r1}/{s1} pdf={r2}/{s2} png={n}")


def main() -> int:
    dl.wait_until_tls("WANTED-SEARCH")
    threading.Thread(target=_rate_loop, name="rate", daemon=True).start()
    pass_n = 0
    while True:
        pass_n += 1
        _clear_stale_fill_state()
        nproxy = max(1, len(dl.current_proxies()))
        dl.WORKERS = max(32, 8 * nproxy)
        cats = catalog_models()
        jobs = sum(len(cats[b]) for b in BRANDS)
        per = max(2, min(6, max(2, nproxy // len(BRANDS))))
        dl.log(
            f"LIGHTNING fill pass={pass_n} brands={BRANDS} models={jobs} "
            f"hops={nproxy} per_brand={per}"
        )
        write_state(
            {
                "phase": "download",
                "pass": pass_n,
                "models": {b: len(cats[b]) for b in BRANDS},
                "hops": nproxy,
                "per_brand": per,
            }
        )
        _run_pass(cats)
        dl.log(f"WANTED search fill pass {pass_n} done — retry leftovers")
        time.sleep(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
