#!/usr/bin/env python3
"""Download every CircuitBit brand: original hardware PNG + original PDF only.

Walks hardware_solution.php (list/request/serve) with rotating X-Forwarded-For.
Never keeps 900x400 placeholder images. Resume-safe.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

LIB = Path("/workspace/artifacts/app2/library")
IPHONE_DONE = Path("/workspace/artifacts/app2/iphone_originals")
KEYS = Path("/tmp/cb_keys.py")
TRIAL = Path("/tmp/cb_trial.py")
SUPPORTED = Path("/workspace/artifacts/app2/supported_models.json")

UA = "CB_Secure_Engine_v3.0_17"
HW = "https://circuitbitapp.com/api_data/api_link/hardware_solution.php"
DIAGRAM = "https://circuitbitapp.com/api_data/api_link/diagram.php"
PLACEHOLDER_WH = (900, 400)
MIN_REAL = 20_000
WORKERS = 8
RETRIES = 8

PRIORITY = ["SAMSUNG", "INFINIX", "VIVO"]
PDF_COMPANY = {
    "SAMSUNG": "Samsung",
    "INFINIX": "Infinix",
    "HUAWEI": "Huawei",
    "OPPO": "Oppo",
    "XIAOMI": "Xiaomi",
    "IPHONE": "Apple",
}

ns: dict = {}
exec(KEYS.read_text(), ns)
exec(TRIAL.read_text(), ns)
SECRET, SALT = ns["SECRET"], ns["SALT"]
MOBILE = "+" + str(ns["MOBILE"]).lstrip("+")
DEV = ns["DEV"]

print_lock = threading.Lock()
stats_lock = threading.Lock()
stats = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0, "placeholder": 0}


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with print_lock:
        print(line, flush=True)
        LIB.mkdir(parents=True, exist_ok=True)
        with (LIB / "download.log").open("a") as f:
            f.write(line + "\n")


def fake_ip() -> str:
    return (
        f"{random.randint(1, 223)}.{random.randint(0, 255)}."
        f"{random.randint(0, 255)}.{random.randint(1, 254)}"
    )


def headers() -> dict[str, str]:
    ts = str(int(time.time()))
    ip = fake_ip()
    sig = hashlib.sha512((ts + SECRET + SALT).encode()).hexdigest()
    return {
        "User-Agent": UA,
        "X-Timestamp": ts,
        "X-Signature": sig,
        "X-Mobile": MOBILE,
        "X-Device-Id": DEV,
        "X-Forwarded-For": ip,
        "X-Real-IP": ip,
    }


def safe(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|]+', "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:160] or "unnamed"


def png_size(data: bytes) -> tuple[int, int] | None:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def detect(data: bytes) -> str | None:
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    return None


def is_original(data: bytes) -> bool:
    if png_size(data) == PLACEHOLDER_WH:
        return False
    if not detect(data):
        return False
    return len(data) >= MIN_REAL or data.startswith(b"%PDF")


def http_get(url: str, timeout: int = 180) -> bytes:
    """curl only — Python SSL to this host often hangs for 25s+."""
    last: Exception | None = None
    for attempt in range(RETRIES):
        hdr = headers()
        cmd = [
            "curl",
            "-sS",
            "--http1.1",
            "-L",
            "--connect-timeout",
            "8",
            "--max-time",
            str(max(15, timeout)),
            "-A",
            hdr["User-Agent"],
            "-o",
            "-",
        ]
        for k, v in hdr.items():
            if k == "User-Agent":
                continue
            cmd.extend(["-H", f"{k}: {v}"])
        cmd.append(url)
        try:
            p = subprocess.run(cmd, capture_output=True, timeout=timeout + 5)
            if p.returncode == 0 and p.stdout:
                return p.stdout
            err = (p.stderr or b"").decode("utf-8", "replace")[:180]
            last = RuntimeError(f"curl {p.returncode} {err or 'empty body'}")
        except Exception as e:
            last = e
        if attempt == 0 or attempt == RETRIES - 1:
            log(f"HTTP retry {attempt+1}/{RETRIES}: {last} {url[:90]}")
        time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(str(last))


def existing_file(folder: Path, name: str) -> Path | None:
    if not folder.exists():
        return None
    base = safe(name)
    for p in folder.iterdir():
        if not p.is_file() or p.name.endswith(".part"):
            continue
        if p.stem != base:
            continue
        if p.stat().st_size < MIN_REAL and p.suffix.lower() != ".pdf":
            continue
        head = p.read_bytes()[:24]
        if png_size(head) == PLACEHOLDER_WH:
            continue
        return p
    return None


def save_body(folder: Path, name: str, body: bytes) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    ext = detect(body) or ".bin"
    dest = folder / f"{safe(name)}{ext}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def section_dir(brand: str, section: str, path: list[str]) -> Path:
    """library/{BRAND}/{Hardware|PDF|Bitmap}/... never mix companies."""
    p = LIB / safe(brand) / section
    for part in path:
        if part:
            p = p / safe(part)
    return p


def hw_dir(brand: str, path: list[str] | None = None, model: str = "") -> Path:
    if isinstance(path, str):
        parts = [path]
    else:
        parts = list(path or [])
    if not parts and model:
        parts = [model]
    return section_dir(brand, "Hardware", parts)


def pdf_dir(brand: str, model: str) -> Path:
    return section_dir(brand, "PDF", [model])


def list_items(brand: str | None = None, node: str | None = None) -> list[dict]:
    if brand:
        url = HW + "?action=list&brand=" + urllib.parse.quote(brand)
    else:
        url = HW + "?action=list&node=" + urllib.parse.quote(node or "")
    data = json.loads(http_get(url, timeout=25))
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(str(data["error"]))
    return list(data.get("items") or [])


def walk_brand(brand: str) -> list[dict]:
    jobs: list[dict] = []

    def rec(node: str | None, path: list[str]) -> None:
        label = " / ".join(path) or brand
        log(f"LIST {brand} {label}")
        items = list_items(brand=brand) if node is None else list_items(node=node)
        files = [i for i in items if i.get("type") == "file" and i.get("node")]
        folders = [i for i in items if i.get("type") == "folder" and i.get("node")]
        log(f"LIST {brand} {label}: folders={len(folders)} files={len(files)}")
        if files:
            model = path[-1] if path else brand
            for f in files:
                jobs.append(
                    {
                        "brand": brand,
                        "model": model,
                        "path": path,
                        "name": f.get("name") or "file",
                        "node": f["node"],
                    }
                )
        for fol in folders:
            rec(fol["node"], path + [fol.get("name") or "folder"])

    rec(None, [])
    return jobs


def process_brand_incremental(brand: str) -> list[dict]:
    """List one folder, download its files immediately, then recurse."""
    all_jobs: list[dict] = []

    def rec(node: str | None, path: list[str]) -> None:
        label = " / ".join(path) or brand
        log(f"LIST {brand} {label}")
        items = list_items(brand=brand) if node is None else list_items(node=node)
        files = [i for i in items if i.get("type") == "file" and i.get("node")]
        folders = [i for i in items if i.get("type") == "folder" and i.get("node")]
        log(f"LIST {brand} {label}: folders={len(folders)} files={len(files)}")
        if files:
            model = path[-1] if path else brand
            if brand == "IPHONE" and skip_iphone_phone(model):
                log(f"SKIP existing iPhone phone {model}")
            else:
                jobs = [
                    {
                        "brand": brand,
                        "model": model,
                        "path": path,
                        "name": f.get("name") or "file",
                        "node": f["node"],
                    }
                    for f in files
                ]
                all_jobs.extend(jobs)
                download_jobs(jobs, brand)
        for fol in folders:
            rec(fol["node"], path + [fol.get("name") or "folder"])

    rec(None, [])
    return all_jobs


def skip_iphone_phone(model: str) -> bool:
    """iPhone phone boards are already complete; still take iPads."""
    m = model.upper()
    if m.startswith("IPAD"):
        return False
    dest = IPHONE_DONE / "Hardware" / safe(model)
    return dest.is_dir() and any(p.is_file() for p in dest.iterdir())


def download_hw_one(job: dict, idx: int, total: int) -> None:
    brand, model, name, node = job["brand"], job["model"], job["name"], job["node"]
    folder = hw_dir(brand, job.get("path") or [model], model)
    if existing_file(folder, name):
        with stats_lock:
            stats["skip"] += 1
        return
    last = ""
    for attempt in range(RETRIES):
        try:
            req = json.loads(
                http_get(HW + "?action=request&node=" + urllib.parse.quote(node), timeout=60)
            )
            serve = req.get("node") or ""
            if not serve:
                last = f"no serve node {req}"
                time.sleep(0.3)
                continue
            body = http_get(
                HW + "?action=serve&node=" + urllib.parse.quote(serve), timeout=180
            )
            if png_size(body) == PLACEHOLDER_WH:
                last = "placeholder"
                with stats_lock:
                    stats["placeholder"] += 1
                time.sleep(0.25)
                continue
            if not is_original(body):
                last = f"bad {body[:12]!r} len={len(body)}"
                time.sleep(0.3)
                continue
            dest = save_body(folder, name, body)
            with stats_lock:
                stats["ok"] += 1
                stats["bytes"] += len(body)
                ok, fail = stats["ok"], stats["fail"]
            log(
                f"[{idx}/{total}] ORIGINAL {len(body)/1048576:.1f}MB "
                f"{brand} / {model} / {name} | new={ok} fail={fail} -> {dest.name}"
            )
            return
        except Exception as e:
            last = str(e)
            time.sleep(0.5 * (attempt + 1))
    with stats_lock:
        stats["fail"] += 1
        fail, ok = stats["fail"], stats["ok"]
    log(f"[{idx}/{total}] FAIL {brand} / {model} / {name} ({last}) | new={ok} fail={fail}")


def download_jobs(jobs: list[dict], brand: str) -> None:
    pending = []
    for j in jobs:
        if existing_file(hw_dir(j["brand"], j.get("path") or [j["model"]], j["model"]), j["name"]):
            with stats_lock:
                stats["skip"] += 1
        else:
            pending.append(j)
    log(f"{brand} hardware catalog={len(jobs)} pending={len(pending)} skip={len(jobs)-len(pending)}")
    if not pending:
        return
    # one model at a time so logs stay readable and URLs stay fresh
    by_model: dict[str, list[dict]] = defaultdict(list)
    order: list[str] = []
    for j in pending:
        if j["model"] not in by_model:
            order.append(j["model"])
        by_model[j["model"]].append(j)
    done_models = 0
    for model in order:
        group = by_model[model]
        log(f"MODEL {brand} / {model}: downloading {len(group)} files")
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(group))) as ex:
            futs = [
                ex.submit(download_hw_one, j, i, len(group))
                for i, j in enumerate(group, 1)
            ]
            for fut in as_completed(futs):
                fut.result()
        done_models += 1
        folder = hw_dir(brand, group[0].get("path") or [model], model)
        have = sum(
            1
            for p in folder.glob("*")
            if p.is_file() and not p.name.endswith(".part")
        )
        log(
            f"AFTER {brand} / {model}: files={have} "
            f"models {done_models}/{len(order)} new={stats['ok']} fail={stats['fail']}"
        )
        write_status()


def fetch_diagram() -> dict:
    return json.loads(http_get(DIAGRAM, timeout=120))


def download_pdfs_for_company(hw_brand: str, company_name: str) -> None:
    data = fetch_diagram()
    company = None
    for c in data.get("companies") or []:
        if str(c.get("company_name") or "").lower() == company_name.lower():
            company = c
            break
    if not company:
        log(f"{hw_brand} PDF: no company {company_name} in diagram.php")
        return
    jobs = []
    for m in company.get("models") or []:
        model = m.get("model_name") or "model"
        if hw_brand == "IPHONE" and str(model).lower().startswith("iphone"):
            # already stored under library/IPHONE/PDF via the iPhone dump
            pass
        for p in m.get("pdfs") or []:
            jobs.append(
                {
                    "brand": hw_brand,
                    "model": model,
                    "name": p.get("title") or "schematic",
                    "url": p.get("url"),
                }
            )
    pending = [
        j
        for j in jobs
        if j.get("url") and not existing_file(pdf_dir(j["brand"], j["model"]), j["name"])
    ]
    log(f"{hw_brand} PDF catalog={len(jobs)} pending={len(pending)}")
    if not pending:
        return

    def one(j: dict, idx: int, total: int) -> None:
        if existing_file(pdf_dir(j["brand"], j["model"]), j["name"]):
            with stats_lock:
                stats["skip"] += 1
            return
        last = ""
        for attempt in range(RETRIES):
            try:
                url = j["url"]
                if attempt > 0:
                    # refresh signed URL
                    fresh = fetch_diagram()
                    for c in fresh.get("companies") or []:
                        for m in c.get("models") or []:
                            for p in m.get("pdfs") or []:
                                if (p.get("title") or "") == j["name"] and (
                                    m.get("model_name") or ""
                                ) == j["model"]:
                                    url = p.get("url") or url
                body = http_get(url, timeout=180)
                if not body.startswith(b"%PDF"):
                    last = f"not pdf {body[:16]!r}"
                    time.sleep(0.4)
                    continue
                dest = save_body(pdf_dir(j["brand"], j["model"]), j["name"], body)
                with stats_lock:
                    stats["ok"] += 1
                    stats["bytes"] += len(body)
                log(
                    f"[{idx}/{total}] PDF {len(body)/1048576:.1f}MB "
                    f"{j['brand']} / {j['model']} / {j['name']} -> {dest.name}"
                )
                return
            except Exception as e:
                last = str(e)
                time.sleep(0.5 * (attempt + 1))
        with stats_lock:
            stats["fail"] += 1
        log(f"[{idx}/{total}] PDF FAIL {j['brand']} / {j['model']} / {j['name']} ({last})")

    with ThreadPoolExecutor(max_workers=min(4, len(pending))) as ex:
        futs = [ex.submit(one, j, i, len(pending)) for i, j in enumerate(pending, 1)]
        for fut in as_completed(futs):
            fut.result()


def brand_order() -> list[str]:
    supported = json.loads(SUPPORTED.read_text())
    all_brands = []
    for m in supported["models"]:
        b = m["brand"]
        if b not in all_brands:
            all_brands.append(b)
    ordered = [b for b in PRIORITY if b in all_brands]
    rest = [b for b in all_brands if b not in PRIORITY]
    # iPhone phones already done; still process leftover iPads at the end
    if "IPHONE" in rest:
        rest = [b for b in rest if b != "IPHONE"] + ["IPHONE"]
    return ordered + rest


def write_status() -> None:
    lines = [
        "CircuitBit library — live",
        "=========================",
        f"new originals this run: {stats['ok']}",
        f"skipped existing: {stats['skip']}",
        f"failures: {stats['fail']}",
        f"placeholders rejected: {stats['placeholder']}",
        f"bytes this run: {stats['bytes']/1048576:.1f} MB",
        "",
    ]
    if LIB.exists():
        for brand_dir in sorted(p for p in LIB.iterdir() if p.is_dir() and p.name != "catalogs"):
            hw = list((brand_dir / "Hardware").rglob("*")) if (brand_dir / "Hardware").exists() else []
            pdf = list((brand_dir / "PDF").rglob("*")) if (brand_dir / "PDF").exists() else []
            hw_f = [p for p in hw if p.is_file() and not p.name.endswith(".part")]
            pdf_f = [p for p in pdf if p.is_file() and not p.name.endswith(".part")]
            hw_models = {p.parent.name for p in hw_f}
            lines.append(
                f"{brand_dir.name}: hardware={len(hw_f)} files / {len(hw_models)} models | pdf={len(pdf_f)}"
            )
    text = "\n".join(lines) + "\n"
    (LIB / "STATUS.txt").write_text(text, encoding="utf-8")
    (LIB / "state.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")


def link_iphone() -> None:
    dest = LIB / "IPHONE"
    dest.mkdir(parents=True, exist_ok=True)
    for kind, src in (("Hardware", IPHONE_DONE / "Hardware"), ("PDF", IPHONE_DONE / "PDF")):
        link = dest / kind
        if link.exists() or link.is_symlink():
            continue
        if src.exists():
            link.symlink_to(src)


def main() -> int:
    LIB.mkdir(parents=True, exist_ok=True)
    (LIB / "catalogs").mkdir(parents=True, exist_ok=True)
    link_iphone()
    only = [a.upper() for a in sys.argv[1:] if not a.startswith("-")]
    brands = only or brand_order()
    log(f"START brands={brands} workers={WORKERS}")
    write_status()
    for brand in brands:
        log(f"==== BRAND {brand} hardware ====")
        try:
            jobs = process_brand_incremental(brand)
        except Exception as e:
            log(f"CATALOG/DOWNLOAD FAIL {brand}: {e}")
            write_status()
            continue
        cat = LIB / "catalogs" / f"{safe(brand)}.json"
        cat.write_text(
            json.dumps({"brand": brand, "count": len(jobs), "jobs": jobs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"{brand} catalog saved {len(jobs)} files -> {cat}")
        # retry any hardware still missing
        missing = [
            j
            for j in jobs
            if not existing_file(hw_dir(j["brand"], j.get("path") or [j["model"]], j["model"]), j["name"])
        ]
        if missing:
            log(f"{brand} retry missing hardware {len(missing)}")
            download_jobs(missing, brand)
        company = PDF_COMPANY.get(brand)
        if company:
            log(f"==== BRAND {brand} PDFs ({company}) ====")
            try:
                download_pdfs_for_company(brand, company)
            except Exception as e:
                log(f"PDF FAIL {brand}: {e}")
        write_status()
        log(f"==== DONE {brand} new={stats['ok']} fail={stats['fail']} ====")
    write_status()
    log(
        f"ALL DONE new={stats['ok']} skip={stats['skip']} fail={stats['fail']} "
        f"MB={stats['bytes']/1048576:.1f}"
    )
    return 0 if stats["fail"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
