#!/usr/bin/env python3
"""Finish one CircuitBit brand (hardware+PDF) then Arabic filenames. Resume-safe."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, "/workspace/artifacts/app2")
import download_all_brands as dl  # noqa: E402
import ar_file_titles as ar  # noqa: E402

BRAND = (sys.argv[1] if len(sys.argv) > 1 else "").strip().upper()
PDF_NAME = {
    "HUAWEI": "Huawei",
    "REALME": "Realme",
    "XIAOMI": "Xiaomi",
    "INFINIX": "Infinix",
    "ITEL": "Itel",
    "OPPO": "Oppo",
    "TECNO": "Tecno",
    "VIVO": "Vivo",
    "SAMSUNG": "Samsung",
}
if not BRAND:
    raise SystemExit("usage: brand_fill.py BRAND")
OUT = Path(f"/tmp/{BRAND.lower()}_fill_state.json")
ROOT = Path("/workspace/artifacts/app2/library") / BRAND


def collect_jobs() -> list[dict]:
    jobs: list[dict] = []
    api = dl.API_BRAND.get(BRAND, BRAND)
    root = None
    last = None
    for attempt in range(6):
        try:
            root = dl.list_items_retry(brand=api, label=BRAND)
            break
        except Exception as e:
            last = e
            dl.log(f"ROOT retry {attempt+1}/6 {BRAND}: {e}")
            time.sleep(8)
    if root is None:
        raise last or RuntimeError(f"ROOT LIST failed {BRAND}")
    folders = [i for i in root if i.get("type") == "folder" and i.get("node")]
    files = [i for i in root if i.get("type") == "file" and i.get("node")]
    dl.log(f"ROOT {BRAND} folders={len(folders)} files={len(files)}")
    for f in files:
        jobs.append(
            {
                "brand": BRAND,
                "model": BRAND,
                "path": [],
                "name": f.get("name") or "file",
                "node": f["node"],
            }
        )

    def rec(node: str, path: list[str]) -> list[dict]:
        try:
            items = dl.list_items_retry(node=node, label=" / ".join(path))
        except Exception as e:
            dl.log(f"LIST skip {BRAND} {' / '.join(path)}: {e}")
            return []
        ff = [i for i in items if i.get("type") == "file" and i.get("node")]
        fol = [i for i in items if i.get("type") == "folder" and i.get("node")]
        dl.log(f"LIST {BRAND} {' / '.join(path)}: folders={len(fol)} files={len(ff)}")
        local = []
        model = path[-1]
        for f in ff:
            local.append(
                {
                    "brand": BRAND,
                    "model": model,
                    "path": path,
                    "name": f.get("name") or "file",
                    "node": f["node"],
                }
            )
        child: list[dict] = []
        if fol:
            with ThreadPoolExecutor(max_workers=min(8, len(fol))) as ex:
                futs = [
                    ex.submit(rec, x["node"], path + [x.get("name") or "folder"])
                    for x in fol
                ]
                for fut in as_completed(futs):
                    child.extend(fut.result())
        return local + child

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(folders)))) as ex:
        futs = [
            ex.submit(rec, fol["node"], [fol.get("name") or "folder"]) for fol in folders
        ]
        for fut in as_completed(futs):
            jobs.extend(fut.result())
    return jobs


def main() -> int:
    dl.wait_until_tls(BRAND)
    jobs = collect_jobs()
    pending = []
    for j in jobs:
        folder = dl.hw_dir(j["brand"], j.get("path") or [j["model"]], j["model"])
        if dl.existing_file(folder, j["name"]):
            continue
        pending.append(j)
    dl.log(f"{BRAND} fill server={len(jobs)} pending={len(pending)}")
    OUT.write_text(
        json.dumps(
            {
                "server": len(jobs),
                "pending": len(pending),
                "models": sorted({j["model"] for j in jobs}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if pending:
        dl.download_jobs(pending, BRAND)
    left = []
    for j in jobs:
        folder = dl.hw_dir(j["brand"], j.get("path") or [j["model"]], j["model"])
        if not dl.existing_file(folder, j["name"]):
            left.append("/".join((j.get("path") or []) + [j["name"]]))
    dl.log(f"{BRAND} hardware left={len(left)} of {len(jobs)}")
    company = PDF_NAME.get(BRAND)
    if company:
        dl.log(f"==== {BRAND} PDF ====")
        try:
            dl.download_pdfs_for_company(BRAND, company)
        except Exception as e:
            dl.log(f"{BRAND} PDF fail {e}")
    r1, s1, _ = ar.rename_tree(ROOT / "Hardware", "hardware")
    r2, s2, _ = ar.rename_tree(ROOT / "PDF", "pdf")
    dl.log(f"{BRAND} arabic hardware={r1}/{s1} pdf={r2}/{s2}")
    OUT.write_text(
        json.dumps(
            {
                "server": len(jobs),
                "left": len(left),
                "missing": left[:200],
                "arabic_hw": r1,
                "arabic_pdf": r2,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    dl.log(f"{BRAND} fill done left={len(left)} of {len(jobs)}")
    return 0 if not left else 1


if __name__ == "__main__":
    raise SystemExit(main())
