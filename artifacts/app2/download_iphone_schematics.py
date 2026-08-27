#!/usr/bin/env python3
"""Refresh per-model signed URLs, then download remaining iPhone hardware schematics."""
from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path("/workspace/artifacts/app2/iphone_schematics")
KEYS = Path("/tmp/cb_keys.py")
OT = "648401d618a963cd9c8b0da2de1af06b6d5402f8e147f592e6640a857ab63530"
UA = "CB_Secure_Engine_v3.0_17"
SEARCH = "https://circuitbitapp.com/api_data/api_link/search_models.php"

ns: dict = {}
exec(KEYS.read_text(), ns)
SECRET, SALT = ns["SECRET"], ns["SALT"]

MODELS = [
    "IPHONE 5S",
    "IPHONE 6",
    "IPHONE 6 PLUS",
    "IPHONE 6S",
    "IPHONE 6S PLUS",
    "IPHONE SE",
    "IPHONE SE 2020",
    "IPHONE SE 2022",
    "IPHONE 7 INTEL",
    "IPHONE 7 QCM",
    "IPHONE 7 PLUS INTEL",
    "IPHONE 7 PLUS QCM",
    "IPHONE 8 INTEL",
    "IPHONE 8 QCM",
    "IPHONE 8 PLUS INTEL",
    "IPHONE 8 PLUS QCM",
    "IPHONE X INTEL",
    "IPHONE X QCM",
    "IPHONE XR",
    "IPHONE XS",
    "IPHONE XS MAX",
    "IPHONE 11",
    "IPHONE 11 PRO",
    "IPHONE 11 PRO MAX",
    "IPHONE 12",
    "IPHONE 12 MINI",
    "IPHONE 12 PRO",
    "IPHONE 12 PRO MAX",
    "IPHONE 13",
    "IPHONE 13 MINI",
    "IPHONE 13 PRO",
    "IPHONE 13 PRO MAX",
    "IPHONE 14",
    "IPHONE 14 PLUS",
    "IPHONE 14 PRO",
    "IPHONE 14 PRO MAX",
    "IPHONE 15",
    "IPHONE 15 PLUS",
    "IPHONE 15 PRO",
    "IPHONE 15 PRO MAX",
    "IPHONE 15 PRO USA",
    "IPHONE 15 PRO MAX USA",
]


def sign(ts: str) -> str:
    return hashlib.sha512((ts + SECRET + SALT).encode()).hexdigest()


def headers() -> dict[str, str]:
    ts = str(int(time.time()))
    return {"User-Agent": UA, "X-Timestamp": ts, "X-Signature": sign(ts)}


def safe(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name).strip()
    name = re.sub(r"\s+", " ", name)
    return name[:120] or "unnamed"


def fetch_model(model: str) -> dict | None:
    url = SEARCH + "?ot=" + OT + "&q=" + urllib.parse.quote(model)
    last = None
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers=headers())
            with urllib.request.urlopen(req, timeout=60) as r:
                data = json.loads(r.read())
            want = model.upper()
            for row in data.get("data") or []:
                if str(row.get("model", "")).upper() == want:
                    return row
            return None
        except Exception as e:
            last = e
            time.sleep(2 * (attempt + 1))
    print(f"catalog fail {model}: {last}", flush=True)
    return None


def dest_for(model: str, sol_name: str) -> Path:
    folder = ROOT / safe(model)
    folder.mkdir(parents=True, exist_ok=True)
    base = folder / safe(sol_name)
    for ext in (".png", ".jpg"):
        p = Path(str(base) + ext)
        if p.exists() and p.stat().st_size > 1000:
            return p
    return Path(str(base) + ".png")


def already(model: str, sol_name: str) -> bool:
    p = dest_for(model, sol_name)
    return p.exists() and p.stat().st_size > 1000


def download(model: str, sol: dict) -> dict:
    name = sol.get("name") or "schematic"
    if already(model, name):
        p = dest_for(model, name)
        return {"model": model, "name": name, "ok": True, "skipped": True, "bytes": p.stat().st_size}
    url = sol.get("file") or ""
    last_err = ""
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=headers())
            with urllib.request.urlopen(req, timeout=180) as r:
                body = r.read()
            if body.startswith(b"\x89PNG"):
                ext = ".png"
            elif body.startswith(b"\xff\xd8\xff"):
                ext = ".jpg"
            else:
                last_err = f"not image {body[:60]!r}"
                time.sleep(2)
                continue
            folder = ROOT / safe(model)
            dest = folder / f"{safe(name)}{ext}"
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(body)
            tmp.replace(dest)
            return {"model": model, "name": name, "ok": True, "skipped": False, "bytes": len(body)}
        except Exception as e:
            last_err = str(e)
            time.sleep(2 * (attempt + 1))
    return {"model": model, "name": name, "ok": False, "error": last_err}


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    stats = {"downloaded": 0, "skipped": 0, "failed": 0, "bytes": 0, "results": []}
    for model in MODELS:
        row = fetch_model(model)
        if not row:
            print(f"missing catalog {model}", flush=True)
            continue
        sols = row.get("hardware_solutions") or []
        pending = [s for s in sols if not already(model, s.get("name") or "schematic")]
        print(f"{model}: {len(sols)} listed, {len(sols)-len(pending)} have, {len(pending)} todo", flush=True)
        if not pending:
            stats["skipped"] += len(sols)
            continue
        with ThreadPoolExecutor(max_workers=3) as ex:
            futs = [ex.submit(download, model, s) for s in pending]
            for fut in as_completed(futs):
                rec = fut.result()
                stats["results"].append(rec)
                if rec.get("ok") and rec.get("skipped"):
                    stats["skipped"] += 1
                    stats["bytes"] += rec.get("bytes") or 0
                elif rec.get("ok"):
                    stats["downloaded"] += 1
                    stats["bytes"] += rec.get("bytes") or 0
                    print(f"  ok {rec['name']} {rec['bytes']/1048576:.1f}MB", flush=True)
                else:
                    stats["failed"] += 1
                    print(f"  FAIL {rec['name']} {rec.get('error')}", flush=True)
        time.sleep(0.4)
    (ROOT / "download_report.json").write_text(json.dumps({k: stats[k] for k in stats if k != "results"}, indent=2))
    (ROOT / "download_results.json").write_text(json.dumps(stats["results"], indent=2))
    print("DONE", {k: stats[k] for k in ("downloaded", "skipped", "failed", "bytes")})


if __name__ == "__main__":
    main()
