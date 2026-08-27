#!/usr/bin/env python3
"""Keep extra public SOCKS hops that reach CircuitBit with the app UA.

Never TLS-probes CircuitBit on the VM IP — every probe goes through the
candidate SOCKS hop. Writes /tmp/egress/extra_proxies.txt which farm_warp_hops
unions into live_proxies.txt.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter

EGRESS = Path("/tmp/egress")
EXTRA = EGRESS / "extra_proxies.txt"
LIVE = EGRESS / "live_proxies.txt"
HITS = EGRESS / "public_hits.txt"
LOG = EGRESS / "public_socks.log"
UA = "CB_Secure_Engine_v3.0_17"
TLS_URL = "https://circuitbitapp.com/"
LISTS = (
    "https://raw.githubusercontent.com/TheSpeedX/SOCKS-List/master/socks5.txt",
    "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
    "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
    "https://raw.githubusercontent.com/mmpx12/proxy-list/master/socks5.txt",
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=socks5&timeout=5000",
)
IPPORT = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}:\d{2,5}$")


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    EGRESS.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def to_url(line: str) -> str | None:
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    if line.startswith("socks5h://"):
        return line
    if line.startswith("socks5://"):
        return "socks5h://" + line[len("socks5://") :]
    if IPPORT.match(line):
        return f"socks5h://{line}"
    return None


def load_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    try:
        return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]
    except OSError:
        return []


def fetch_lists() -> list[str]:
    found: list[str] = []
    for url in LISTS:
        try:
            r = requests.get(url, timeout=20)
            if r.status_code != 200:
                continue
            for ln in r.text.splitlines():
                u = to_url(ln)
                if u:
                    found.append(u)
        except Exception as e:
            log(f"list fail {url[:60]} {type(e).__name__}")
    return list(dict.fromkeys(found))


def probe(proxy: str) -> tuple[str, bool]:
    s = requests.Session()
    s.headers.update({"User-Agent": UA})
    s.proxies = {"http": proxy, "https": proxy}
    ad = HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
    s.mount("https://", ad)
    s.mount("http://", ad)
    try:
        r = s.get(TLS_URL, timeout=7)
        return proxy, r.status_code == 200 and len(r.content) > 1000
    except Exception:
        return proxy, False
    finally:
        s.close()


def write_extra(urls: list[str]) -> None:
    EXTRA.write_text("\n".join(urls) + ("\n" if urls else ""))
    HITS.write_text("\n".join(urls) + ("\n" if urls else ""))
    # Keep live usable even while WARP farm reports live=0.
    live = [u for u in load_lines(LIVE) if u.startswith("socks5h://127.0.0.1:")]
    merged = list(dict.fromkeys([*live, *urls]))
    LIVE.write_text("\n".join(merged) + ("\n" if merged else ""))


def cycle() -> int:
    known = list(dict.fromkeys([*load_lines(EXTRA), *load_lines(HITS), *load_lines(LIVE)]))
    known = [u for u in known if u.startswith("socks5h://") and "127.0.0.1" not in u]
    fresh = fetch_lists()
    log(f"lists={len(fresh)} known={len(known)}")
    # Probe known first, then a slice of new candidates.
    cands = list(dict.fromkeys([*known, *fresh]))[:400]
    ok: list[str] = []
    with ThreadPoolExecutor(max_workers=64) as ex:
        futs = [ex.submit(probe, p) for p in cands]
        for fut in as_completed(futs):
            p, good = fut.result()
            if good:
                ok.append(p)
    ok = list(dict.fromkeys(ok))
    if not ok:
        log("public hops working=0 keep previous")
        return 0
    write_extra(ok)
    log(f"public hops working={len(ok)}")
    return len(ok)


def main() -> int:
    EGRESS.mkdir(parents=True, exist_ok=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log(f"cycle err {type(e).__name__}: {e}")
        time.sleep(90)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
