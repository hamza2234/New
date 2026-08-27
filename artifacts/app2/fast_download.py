#!/usr/bin/env python3
"""Fast remaining iPhone hardware original downloads. Prints every file."""
from __future__ import annotations

import hashlib
import json
import random
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
HW_CAT = ROOT / "hardware_catalog.json"
LOG = ROOT / "fast_download.log"
KEYS = Path("/tmp/cb_keys.py")
TRIAL = Path("/tmp/cb_trial.py")

UA = "CB_Secure_Engine_v3.0_17"
SEARCH = "https://circuitbitapp.com/api_data/api_link/search_models.php"
OT = "648401d618a963cd9c8b0da2de1af06b6d5402f8e147f592e6640a857ab63530"
PLACEHOLDER_WH = (900, 400)
MIN_REAL = 20_000
WORKERS = 8

ns: dict = {}
exec(KEYS.read_text(), ns)
exec(TRIAL.read_text(), ns)
SECRET, SALT = ns["SECRET"], ns["SALT"]
MOBILE = "+" + str(ns["MOBILE"]).lstrip("+")
DEV = ns["DEV"]

print_lock = threading.Lock()
stats_lock = threading.Lock()
stats = {"ok": 0, "skip": 0, "fail": 0, "bytes": 0}


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with print_lock:
        print(line, flush=True)
        with LOG.open("a") as f:
            f.write(line + "\n")


def fake_ip() -> str:
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"


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
    return None


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
            if png_size(p.read_bytes()[:24]) != PLACEHOLDER_WH:
                return p
    return None


def save(model: str, name: str, body: bytes) -> Path:
    ext = detect(body) or ".bin"
    folder = HW_DIR / safe(model)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{safe(name)}{ext}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def models() -> list[str]:
    jobs = json.loads(HW_CAT.read_text())["jobs"]
    seen = []
    for j in jobs:
        if j["model"] not in seen:
            seen.append(j["model"])
    return seen


def fetch_model(model: str) -> list[dict]:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    last = None
    for attempt in range(5):
        try:
            data = json.loads(http_get(url, timeout=45))
            for row in data.get("data") or []:
                if str(row.get("model") or "").upper() == model.upper():
                    return [
                        {"name": s.get("name") or "file", "url": s["file"]}
                        for s in (row.get("hardware_solutions") or [])
                        if s.get("file")
                    ]
            return []
        except Exception as e:
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise RuntimeError(f"search fail {model}: {last}")


def download_one(model: str, name: str, url: str, idx: int, total: int) -> None:
    if existing(model, name):
        with stats_lock:
            stats["skip"] += 1
        return
    last = ""
    for attempt in range(5):
        try:
            body = http_get(url, timeout=180)
            if png_size(body) == PLACEHOLDER_WH:
                last = "placeholder"
                time.sleep(0.3)
                continue
            if not detect(body) or len(body) < MIN_REAL:
                last = f"bad {body[:12]!r} len={len(body)}"
                time.sleep(0.3)
                continue
            dest = save(model, name, body)
            with stats_lock:
                stats["ok"] += 1
                stats["bytes"] += len(body)
                ok = stats["ok"]
                fail = stats["fail"]
            log(
                f"[{idx}/{total}] ORIGINAL {len(body)/1048576:.1f}MB {model} / {name} "
                f"| new={ok} fail={fail} -> {dest.name}"
            )
            return
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            time.sleep(0.5 * (attempt + 1))
        except Exception as e:
            last = str(e)
            time.sleep(0.5 * (attempt + 1))
    with stats_lock:
        stats["fail"] += 1
        fail = stats["fail"]
        ok = stats["ok"]
    log(f"[{idx}/{total}] FAIL {model} / {name} ({last}) | new={ok} fail={fail}")


def inventory() -> tuple[int, int]:
    files = [p for p in HW_DIR.rglob("*") if p.is_file() and not p.name.endswith(".part")]
    orig = 0
    for p in files:
        if p.stat().st_size >= MIN_REAL and png_size(p.read_bytes()[:24]) != PLACEHOLDER_WH:
            orig += 1
    catalog = len(json.loads(HW_CAT.read_text())["jobs"])
    return orig, catalog


def main() -> int:
    HW_DIR.mkdir(parents=True, exist_ok=True)
    have, catalog = inventory()
    log(f"START hardware original {have}/{catalog} remaining={catalog-have} workers={WORKERS}")
    pending_n = 0
    done_models = 0
    all_models = models()
    for model in all_models:
        try:
            sols = fetch_model(model)
        except Exception as e:
            log(f"SEARCH FAIL {model}: {e}")
            continue
        pending = [s for s in sols if not existing(model, s["name"])]
        skipped = len(sols) - len(pending)
        with stats_lock:
            stats["skip"] += skipped
        if not pending:
            log(f"MODEL {model}: already complete {len(sols)}/{len(sols)}")
            done_models += 1
            continue
        log(f"MODEL {model}: downloading {len(pending)}/{len(sols)} now")
        pending_n += len(pending)
        # refresh URLs are ~60s; pull this model immediately
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(pending))) as ex:
            futs = []
            for i, s in enumerate(pending, 1):
                futs.append(ex.submit(download_one, model, s["name"], s["url"], i, len(pending)))
            for fut in as_completed(futs):
                fut.result()
        have, catalog = inventory()
        log(f"AFTER {model}: original {have}/{catalog} remaining={catalog-have}")
    have, catalog = inventory()
    log(
        f"DONE original={have}/{catalog} remaining={catalog-have} "
        f"new={stats['ok']} skip={stats['skip']} fail={stats['fail']} "
        f"MB={stats['bytes']/1048576:.1f}"
    )
    return 0 if stats["fail"] == 0 and have >= catalog else 1


if __name__ == "__main__":
    sys.exit(main())
