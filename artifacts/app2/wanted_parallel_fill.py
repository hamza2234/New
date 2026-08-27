#!/usr/bin/env python3
"""Download all remaining requested brands together, Huawei-style.

Not sequential: once CircuitBit LIST succeeds, catalog REALME/XIAOMI/ITEL/OPPO/TECNO
in parallel, then download every hardware job in one worker pool, then PDFs.
"""
from __future__ import annotations

import json
import sys
import time
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
STATE = Path("/tmp/wanted_parallel_state.json")
LIB = Path("/workspace/artifacts/app2/library")


def write_state(payload: dict) -> None:
    STATE.write_text(json.dumps(payload, ensure_ascii=False, indent=2))


def wait_subscription() -> None:
    """Block until hardware LIST works, then start every brand together."""
    t0 = time.time()
    while True:
        dl.current_proxies()
        try:
            items = dl.list_items(brand="ITEL")
            dl.log(
                f"subscription OK items={len(items)} hops={len(dl.current_proxies())} "
                f"waited={int(time.time()-t0)}s — start ALL brands together"
            )
            return
        except Exception as e:
            err = str(e)
            dl.log(f"wait subscription ({int(time.time()-t0)}s) hops={len(dl.current_proxies())}: {err[:160]}")
            write_state(
                {
                    "phase": "wait_subscription",
                    "error": err[:200],
                    "hops": len(dl.current_proxies()),
                    "brands": BRANDS,
                }
            )
            time.sleep(20 if "403" in err or "Subscription" in err else 6)


def collect_brand(brand: str) -> list[dict]:
    jobs: list[dict] = []
    api = dl.API_BRAND.get(brand, brand)
    last = None
    root = None
    for attempt in range(8):
        try:
            root = dl.list_items_retry(brand=api, label=brand)
            break
        except Exception as e:
            last = e
            dl.log(f"ROOT retry {attempt+1}/8 {brand}: {e}")
            time.sleep(2 * (attempt + 1))
    if root is None:
        dl.log(f"ROOT FAIL {brand}: {last}")
        return []
    folders = [i for i in root if i.get("type") == "folder" and i.get("node")]
    files = [i for i in root if i.get("type") == "file" and i.get("node")]
    dl.log(f"ROOT {brand} folders={len(folders)} files={len(files)}")
    for f in files:
        jobs.append(
            {
                "brand": brand,
                "model": brand,
                "path": [],
                "name": f.get("name") or "file",
                "node": f["node"],
            }
        )

    def rec(node: str, path: list[str]) -> list[dict]:
        try:
            items = dl.list_items_retry(node=node, label=f"{brand} / " + " / ".join(path))
        except Exception as e:
            dl.log(f"LIST skip {brand} {' / '.join(path)}: {e}")
            return []
        ff = [i for i in items if i.get("type") == "file" and i.get("node")]
        fol = [i for i in items if i.get("type") == "folder" and i.get("node")]
        dl.log(f"LIST {brand} {' / '.join(path)}: folders={len(fol)} files={len(ff)}")
        local = []
        model = path[-1]
        for f in ff:
            local.append(
                {
                    "brand": brand,
                    "model": model,
                    "path": path,
                    "name": f.get("name") or "file",
                    "node": f["node"],
                }
            )
        child: list[dict] = []
        if fol:
            with ThreadPoolExecutor(max_workers=min(6, len(fol))) as ex:
                futs = [
                    ex.submit(rec, x["node"], path + [x.get("name") or "folder"])
                    for x in fol
                ]
                for fut in as_completed(futs):
                    child.extend(fut.result())
        return local + child

    if folders:
        with ThreadPoolExecutor(max_workers=min(6, len(folders))) as ex:
            futs = [
                ex.submit(rec, fol["node"], [fol.get("name") or "folder"])
                for fol in folders
            ]
            for fut in as_completed(futs):
                jobs.extend(fut.result())
    dl.log(f"{brand} catalog jobs={len(jobs)}")
    return jobs


def main() -> int:
    dl.wait_until_tls("WANTED")
    nproxy = max(1, len(dl.current_proxies()))
    dl.WORKERS = max(48, 8 * nproxy)
    dl.log(f"WANTED parallel brands={BRANDS} workers={dl.WORKERS} hops={nproxy}")
    write_state({"phase": "wait_subscription", "brands": BRANDS, "hops": nproxy})
    wait_subscription()
    write_state({"phase": "catalog", "brands": BRANDS})
    all_jobs: list[dict] = []
    by_brand: dict[str, list[dict]] = {b: [] for b in BRANDS}
    with ThreadPoolExecutor(max_workers=len(BRANDS)) as ex:
        futs = {ex.submit(collect_brand, b): b for b in BRANDS}
        for fut in as_completed(futs):
            brand = futs[fut]
            jobs = fut.result()
            by_brand[brand] = jobs
            all_jobs.extend(jobs)
    pending = []
    summary = {}
    for brand, jobs in by_brand.items():
        left = 0
        for j in jobs:
            folder = dl.hw_dir(j["brand"], j.get("path") or [j["model"]], j["model"])
            if dl.existing_file(folder, j["name"]):
                continue
            pending.append(j)
            left += 1
        summary[brand] = {
            "server": len(jobs),
            "pending": left,
            "models": sorted({j["model"] for j in jobs}),
        }
        Path(f"/tmp/{brand.lower()}_fill_state.json").write_text(
            json.dumps(summary[brand], ensure_ascii=False, indent=2)
        )
    write_state({"phase": "download", "brands": summary, "pending": len(pending)})
    dl.log(f"WANTED together pending={len(pending)} of {len(all_jobs)}")
    if pending:
        dl.download_jobs(pending, "WANTED")
    write_state({"phase": "pdf", "brands": summary})
    with ThreadPoolExecutor(max_workers=len(BRANDS)) as ex:
        futs = [
            ex.submit(dl.download_pdfs_for_company, b, PDF_NAME[b]) for b in BRANDS
        ]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                dl.log(f"PDF fail {e}")
    for brand in BRANDS:
        root = LIB / brand
        r1, s1, _ = ar.rename_tree(root / "Hardware", "hardware")
        r2, s2, _ = ar.rename_tree(root / "PDF", "pdf")
        dl.log(f"{brand} arabic hardware={r1}/{s1} pdf={r2}/{s2}")
    write_state({"phase": "done", "brands": summary})
    dl.log("WANTED parallel fill done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
