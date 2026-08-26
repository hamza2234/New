#!/usr/bin/env python3
"""Download remaining iPhone hardware originals.

serve_image.php URLs expire in ~60s (query param e=). Fetch one model, download
its missing files immediately with trial headers, then move on.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/workspace/artifacts/app2/iphone_originals")
HW_DIR = ROOT / "Hardware"
LOG = ROOT / "download_fresh.log"
STATE = ROOT / "hardware_state.json"
HW_CAT = ROOT / "hardware_catalog.json"

KEYS = Path("/tmp/cb_keys.py")
TRIAL = Path("/tmp/cb_trial.py")

UA = "CB_Secure_Engine_v3.0_17"
SEARCH = "https://circuitbitapp.com/api_data/api_link/search_models.php"
OT = "648401d618a963cd9c8b0da2de1af06b6d5402f8e147f592e6640a857ab63530"
PLACEHOLDER_WH = (900, 400)
MIN_REAL = 20_000
WORKERS = 4

ns: dict = {}
exec(KEYS.read_text(), ns)
exec(TRIAL.read_text(), ns)
SECRET, SALT = ns["SECRET"], ns["SALT"]
MOBILE = "+" + str(ns["MOBILE"]).lstrip("+")
DEV = ns["DEV"]

print_lock = threading.Lock()


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with print_lock:
        print(line, flush=True)
        with LOG.open("a") as f:
            f.write(line + "\n")


def headers() -> dict[str, str]:
    ts = str(int(time.time()))
    sig = hashlib.sha512((ts + SECRET + SALT).encode()).hexdigest()
    return {
        "User-Agent": UA,
        "X-Timestamp": ts,
        "X-Signature": sig,
        "X-Mobile": MOBILE,
        "X-Device-Id": DEV,
    }


def safe(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
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
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


def is_placeholder(data: bytes) -> bool:
    return png_size(data) == PLACEHOLDER_WH


def http_get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def existing(model: str, name: str) -> Path | None:
    folder = HW_DIR / safe(model)
    if not folder.exists():
        return None
    base = safe(name)
    for p in folder.iterdir():
        if p.is_file() and p.stem == base and p.stat().st_size >= MIN_REAL:
            return p
    return None


def models() -> list[str]:
    jobs = json.loads(HW_CAT.read_text()).get("jobs") or []
    seen = []
    for j in jobs:
        m = j["model"]
        if m not in seen:
            seen.append(m)
    return seen


def fetch_model(model: str) -> list[dict]:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    data = json.loads(http_get(url, timeout=60))
    want = model.upper()
    for row in data.get("data") or []:
        if str(row.get("model") or "").upper() == want:
            out = []
            for s in row.get("hardware_solutions") or []:
                if s.get("file"):
                    out.append({"name": s.get("name") or "file", "url": s["file"]})
            return out
    return []


def save_body(model: str, name: str, body: bytes) -> Path:
    ext = detect(body) or ".bin"
    folder = HW_DIR / safe(model)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{safe(name)}{ext}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def download_url(model: str, name: str, url: str) -> dict:
    if existing(model, name):
        p = existing(model, name)
        return {"ok": True, "skipped": True, "bytes": p.stat().st_size, "name": name}
    try:
        body = http_get(url, timeout=180)
    except urllib.error.HTTPError as e:
        return {"ok": False, "name": name, "error": f"HTTP {e.code}"}
    except Exception as e:
        return {"ok": False, "name": name, "error": str(e)}
    if is_placeholder(body):
        return {"ok": False, "name": name, "error": f"placeholder {len(body)}"}
    if body[:1] in (b"{", b"["):
        return {"ok": False, "name": name, "error": body[:120].decode("utf-8", "replace")}
    if not detect(body):
        return {"ok": False, "name": name, "error": f"magic {body[:16]!r}"}
    dest = save_body(model, name, body)
    return {"ok": True, "skipped": False, "bytes": len(body), "name": name, "path": str(dest)}


def download_model(model: str) -> dict:
    stats = {"model": model, "downloaded": 0, "skipped": 0, "failed": 0, "failures": []}
    # up to 3 fresh-search rounds for leftovers
    for round_i in range(3):
        missing_before = None
        try:
            sols = fetch_model(model)
        except Exception as e:
            log(f"{model} search fail round {round_i}: {e}")
            time.sleep(3)
            continue
        pending = [s for s in sols if not existing(model, s["name"])]
        if not pending:
            stats["skipped"] += len(sols)
            return stats
        log(f"{model} round {round_i+1}: {len(sols)} listed, {len(pending)} todo")
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(pending))) as ex:
            futs = [ex.submit(download_url, model, s["name"], s["url"]) for s in pending]
            for fut in as_completed(futs):
                rec = fut.result()
                if rec.get("ok") and rec.get("skipped"):
                    stats["skipped"] += 1
                elif rec.get("ok"):
                    stats["downloaded"] += 1
                    log(f"  ok {model} / {rec['name']} {rec['bytes']/1048576:.1f}MB")
                else:
                    stats["failures"].append(rec)
        # drop failures that later succeeded
        still = [s["name"] for s in pending if not existing(model, s["name"])]
        stats["failures"] = [f for f in stats["failures"] if f.get("name") in still]
        if not still:
            stats["failed"] = 0
            return stats
        time.sleep(2)
    stats["failed"] = len({f.get("name") for f in stats["failures"]})
    return stats


def inventory() -> dict:
    files = [p for p in HW_DIR.rglob("*") if p.is_file() and not p.name.endswith(".part")]
    by_ext: dict[str, int] = {}
    for p in files:
        by_ext[p.suffix.lower()] = by_ext.get(p.suffix.lower(), 0) + 1
    return {
        "hardware_files": len(files),
        "hardware_bytes": sum(p.stat().st_size for p in files),
        "hardware_ext": by_ext,
        "model_count": len({p.parent.name for p in files}),
    }


def main() -> int:
    HW_DIR.mkdir(parents=True, exist_ok=True)
    totals = {"downloaded": 0, "skipped": 0, "failed": 0, "failures": []}
    for model in models():
        rec = download_model(model)
        totals["downloaded"] += rec["downloaded"]
        totals["skipped"] += rec["skipped"]
        totals["failed"] += rec["failed"]
        totals["failures"].extend({"model": model, **f} for f in rec["failures"])
        log(f"{model} done dl={rec['downloaded']} skip={rec['skipped']} fail={rec['failed']}")
        time.sleep(0.4)
    inv = inventory()
    totals.update(inv)
    STATE.write_text(json.dumps(totals, indent=2))
    log(f"DONE files={inv['hardware_files']} models={inv['model_count']} "
        f"mb={inv['hardware_bytes']/1e6:.1f} failed={totals['failed']}")
    if totals["failures"]:
        (ROOT / "hardware_failures.json").write_text(json.dumps(totals["failures"], indent=2))
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
