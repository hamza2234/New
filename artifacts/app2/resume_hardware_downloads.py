#!/usr/bin/env python3
"""Resume hardware downloads whenever the CircuitBit IP download window reopens.

serve_image.php URLs last ~60s. Download limit is per-IP (new trial from the same
network still returns the 900x400 placeholder). This process polls, then grabs
as many fresh originals as the window allows.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/workspace/artifacts/app2/iphone_originals")
HW_DIR = ROOT / "Hardware"
HW_CAT = ROOT / "hardware_catalog.json"
STATUS = ROOT / "resume_status.json"
LOG = ROOT / "resume.log"
KEYS = Path("/tmp/cb_keys.py")
TRIAL = Path("/tmp/cb_trial.py")

UA = "CB_Secure_Engine_v3.0_17"
SEARCH = "https://circuitbitapp.com/api_data/api_link/search_models.php"
OT = "648401d618a963cd9c8b0da2de1af06b6d5402f8e147f592e6640a857ab63530"
PLACEHOLDER_WH = (900, 400)
MIN_REAL = 20_000
WORKERS = 3

ns: dict = {}
exec(KEYS.read_text(), ns)
exec(TRIAL.read_text(), ns)
SECRET, SALT = ns["SECRET"], ns["SALT"]
MOBILE = "+" + str(ns["MOBILE"]).lstrip("+")
DEV = ns["DEV"]


def log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
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
    return None


def http_get(url: str, timeout: int = 180) -> bytes:
    req = urllib.request.Request(url, headers=headers())
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def existing(model: str, name: str) -> bool:
    folder = HW_DIR / safe(model)
    if not folder.exists():
        return False
    base = safe(name)
    return any(p.is_file() and p.stem == base and p.stat().st_size >= MIN_REAL for p in folder.iterdir())


def jobs() -> list[dict]:
    return json.loads(HW_CAT.read_text()).get("jobs") or []


def missing() -> list[tuple[str, str]]:
    out = []
    seen = set()
    for j in jobs():
        key = (j["model"], j["name"])
        if key in seen:
            continue
        seen.add(key)
        if not existing(j["model"], j["name"]):
            out.append(key)
    return out


def fetch_model(model: str) -> list[dict]:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    data = json.loads(http_get(url, timeout=60))
    for row in data.get("data") or []:
        if str(row.get("model") or "").upper() == model.upper():
            return [
                {"name": s.get("name") or "file", "url": s["file"]}
                for s in (row.get("hardware_solutions") or [])
                if s.get("file")
            ]
    return []


def save(model: str, name: str, body: bytes) -> Path:
    ext = detect(body) or ".bin"
    folder = HW_DIR / safe(model)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / f"{safe(name)}{ext}"
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dest


def canary() -> str:
    """Try one missing file. Returns 'ok', 'limited', or 'error'."""
    miss = missing()
    if not miss:
        return "done"
    model, name = miss[0]
    try:
        sols = fetch_model(model)
        sol = next((s for s in sols if s["name"] == name), None)
        if not sol:
            return "error"
        body = http_get(sol["url"], timeout=180)
    except Exception as e:
        log(f"canary error {e}")
        return "error"
    if png_size(body) == PLACEHOLDER_WH:
        return "limited"
    if not detect(body) or len(body) < MIN_REAL:
        log(f"canary bad magic {body[:20]!r} len={len(body)}")
        return "error"
    dest = save(model, name, body)
    log(f"canary saved {dest} {len(body)/1048576:.1f}MB")
    return "ok"


def drain_window() -> int:
    """Download as many as possible with fresh per-model URLs. Stop on placeholder."""
    got = 0
    blocked = False
    for model in sorted({m for m, _ in missing()}):
        if blocked:
            break
        try:
            sols = fetch_model(model)
        except Exception as e:
            log(f"{model} search fail {e}")
            time.sleep(2)
            continue
        pending = [s for s in sols if not existing(model, s["name"])]
        if not pending:
            continue
        log(f"{model}: {len(pending)} todo")
        with ThreadPoolExecutor(max_workers=min(WORKERS, len(pending))) as ex:
            futs = {ex.submit(http_get, s["url"]): s for s in pending}
            for fut in as_completed(futs):
                s = futs[fut]
                try:
                    body = fut.result()
                except Exception as e:
                    log(f"  fail {model}/{s['name']}: {e}")
                    continue
                if png_size(body) == PLACEHOLDER_WH:
                    log("window closed (placeholder)")
                    blocked = True
                    break
                if detect(body) and len(body) >= MIN_REAL:
                    save(model, s["name"], body)
                    got += 1
                    log(f"  ok {model}/{s['name']} {len(body)/1048576:.1f}MB")
        time.sleep(0.3)
    return got


def write_status(extra: dict) -> None:
    files = [p for p in HW_DIR.rglob("*") if p.is_file() and not p.name.endswith(".part")]
    miss = missing()
    payload = {
        "updated": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "hardware_have": len(files),
        "hardware_missing": len(miss),
        "hardware_bytes": sum(p.stat().st_size for p in files),
        "models_have": sorted({p.parent.name for p in files}),
        **extra,
    }
    STATUS.write_text(json.dumps(payload, indent=2))


def main() -> int:
    HW_DIR.mkdir(parents=True, exist_ok=True)
    sleeps = [600, 600, 900, 1200, 1800, 1800, 1800]
    i = 0
    log(f"resume start missing={len(missing())}")
    write_status({"state": "start"})
    while missing():
        result = canary()
        log(f"canary {result} missing={len(missing())}")
        if result == "done":
            break
        if result == "ok":
            n = drain_window()
            log(f"drained {n} files missing={len(missing())}")
            write_status({"state": "draining", "last_batch": n})
            i = 0
            continue
        wait = sleeps[min(i, len(sleeps) - 1)]
        i += 1
        write_status({"state": "limited", "sleep_s": wait, "canary": result})
        log(f"LIMIT hit | original_hw={len(jobs())-len(missing())}/{len(jobs())} remaining={len(missing())} | sleep {wait}s")
        end = time.time() + wait
        while time.time() < end:
            left = int(end - time.time())
            have_n = len(jobs()) - len(missing())
            log(f"waiting {left}s | have_original={have_n}/{len(jobs())} remaining={len(missing())} | next check soon")
            time.sleep(min(15, max(1, left)))
    miss = missing()
    write_status({"state": "complete" if not miss else "stopped", "missing": len(miss)})
    log(f"finished missing={len(miss)}")
    return 0 if not miss else 2


if __name__ == "__main__":
    sys.exit(main())
