#!/usr/bin/env python3
"""Keep a pool of live WARP SOCKS hops that pass CircuitBit TLS with the app UA.

CircuitBit TLS-bans this VM IP and burns each Cloudflare WARP exit after ~10-20
minutes of heavy traffic. This supervisor registers fresh wgcf accounts, starts
wireproxy, UA-tests circuitbitapp.com, and writes live SOCKS URLs atomically.

Never TLS-probes CircuitBit on the VM IP. Kill hops by PID only (never pkill -f).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

EGRESS = Path("/tmp/egress")
WGCF = EGRESS / "wgcf"
WIREPROXY = EGRESS / "wireproxy"
LIVE = EGRESS / "live_proxies.txt"
STATE = EGRESS / "hop_state.json"
LOG = EGRESS / "hop_farm.log"

UA = "CB_Secure_Engine_v3.0_17"
TLS_URL = "https://circuitbitapp.com/"
TARGET_LIVE = int(os.environ.get("CB_HOP_TARGET", "5") or "5")
PREWARM = int(os.environ.get("CB_HOP_PREWARM", "12") or "12")
# Port formula used throughout this VM: 25343 + wgcf index (w370 -> 25713)
PORT_BASE = 25343
PROBE_CONNECT = "8"
PROBE_MAX = "12"
KEEP_WIREPROXY_MAX = TARGET_LIVE + 3
START_INDEX = int(os.environ.get("CB_HOP_START", "0") or "0")


def log(msg: str) -> None:
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    EGRESS.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def next_index() -> int:
    nums = []
    for p in EGRESS.glob("w[0-9]*"):
        n = p.name[1:]
        if n.isdigit():
            nums.append(int(n))
    if START_INDEX:
        nums.append(START_INDEX - 1)
    return max(nums) + 1 if nums else 370


def port_for(n: int) -> int:
    return PORT_BASE + n


def proxy_url(port: int) -> str:
    return f"socks5h://127.0.0.1:{port}"


def conf_path(n: int) -> Path:
    return EGRESS / f"wp{n}.conf"


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return {"hops": {}}


def save_state(st: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=2))
    tmp.replace(STATE)


def write_live(urls: list[str]) -> None:
    tmp = LIVE.with_suffix(".tmp")
    tmp.write_text("\n".join(urls) + ("\n" if urls else ""))
    tmp.replace(LIVE)


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def kill_pid(pid: int) -> None:
    if pid <= 1:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(20):
        if not pid_alive(pid):
            return
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def running_wireproxy() -> dict[int, int]:
    """index -> pid for live wireproxy processes we started."""
    out: dict[int, int] = {}
    try:
        p = subprocess.run(["pgrep", "-a", "wireproxy"], capture_output=True, text=True)
    except Exception:
        return out
    for line in (p.stdout or "").splitlines():
        parts = line.split(None, 1)
        if not parts:
            continue
        try:
            pid = int(parts[0])
        except ValueError:
            continue
        if "wp" not in line or ".conf" not in line:
            continue
        # .../wp123.conf
        try:
            name = line.rsplit("wp", 1)[-1]
            n = int(name.split(".conf", 1)[0])
        except Exception:
            continue
        out[n] = pid
    return out


def register_one(n: int) -> bool:
    d = EGRESS / f"w{n}"
    d.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [str(WGCF), "register", "--accept-tos"],
            cwd=d,
            check=True,
            capture_output=True,
            timeout=30,
        )
        subprocess.run(
            [str(WGCF), "generate"],
            cwd=d,
            check=True,
            capture_output=True,
            timeout=20,
        )
    except Exception as e:
        log(f"register FAIL w{n}: {e}")
        return False
    src = d / "wgcf-profile.conf"
    if not src.exists():
        return False
    dst = conf_path(n)
    text = src.read_text()
    if "[Socks5]" not in text:
        text += f"\n[Socks5]\nBindAddress = 127.0.0.1:{port_for(n)}\n"
    dst.write_text(text)
    os.chmod(dst, 0o600)
    log(f"registered w{n} :{port_for(n)}")
    return True


def unused_confs() -> list[int]:
    live = running_wireproxy()
    floor = max(400, next_index() - 40)
    nums = []
    for p in EGRESS.glob("wp[0-9]*.conf"):
        n = p.name[2:].split(".conf")[0]
        if n.isdigit() and int(n) not in live and int(n) >= floor:
            nums.append(int(n))
    return sorted(nums, reverse=True)


def start_hop(n: int) -> int | None:
    dst = conf_path(n)
    if not dst.exists():
        return None
    logf = EGRESS / f"wp{n}.log"
    proc = subprocess.Popen(
        [str(WIREPROXY), "-c", str(dst)],
        stdout=logf.open("a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log(f"started w{n} :{port_for(n)} pid={proc.pid}")
    return proc.pid


def curl(proxy: str, url: str, ua: str | None, connect: str, max_time: str) -> tuple[str, str]:
    cmd = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}",
        "--connect-timeout",
        connect,
        "--max-time",
        max_time,
        "-x",
        proxy,
    ]
    if ua:
        cmd.extend(["-A", ua])
    cmd.append(url)
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=int(max_time) + 4)
        code = (p.stdout or b"").decode().strip() or "000"
        err = (p.stderr or b"").decode("utf-8", "replace")[:80]
        return code, err
    except Exception as e:
        return "000", str(e)[:80]


def handshake_ok(port: int) -> bool:
    code, _ = curl(proxy_url(port), "https://1.1.1.1/", None, "8", "10")
    return code.isdigit() and code != "000"


def tls_ok(port: int) -> bool:
    code, _ = curl(
        proxy_url(port),
        f"{TLS_URL}?cb_tls={port}",
        UA,
        PROBE_CONNECT,
        PROBE_MAX,
    )
    return code == "200"


def prune_extra(keep: set[int]) -> None:
    running = running_wireproxy()
    if len(running) <= KEEP_WIREPROXY_MAX:
        return
    extra = [n for n in sorted(running) if n not in keep]
    for n in extra:
        if len(running) <= KEEP_WIREPROXY_MAX:
            break
        pid = running.pop(n, None)
        if pid:
            log(f"prune extra w{n} pid={pid}")
            kill_pid(pid)


def main() -> int:
    if not WGCF.exists() or not WIREPROXY.exists():
        log(f"missing {WGCF} or {WIREPROXY}")
        return 1
    EGRESS.mkdir(parents=True, exist_ok=True)
    live: dict[int, int] = {}  # index -> pid
    next_n = next_index()
    last_tls_check = 0.0
    log(f"FARM start target={TARGET_LIVE} next=w{next_n} prewarm={PREWARM}")
    for n, pid in running_wireproxy().items():
        log(f"startup kill leftover w{n} pid={pid}")
        kill_pid(pid)
    write_live([])

    while True:
        running = running_wireproxy()
        for n in list(live):
            pid = live[n]
            if running.get(n) != pid or not pid_alive(pid):
                log(f"dead process w{n} pid={pid}")
                live.pop(n, None)

        now = time.time()
        # CircuitBit-test live hops at most every 45s — probing them every loop burns exits.
        if live and (now - last_tls_check >= 45 or len(live) < TARGET_LIVE):
            still: dict[int, int] = {}
            for n, pid in list(live.items()):
                if tls_ok(port_for(n)):
                    still[n] = pid
                elif tls_ok(port_for(n)):
                    still[n] = pid
                    log(f"w{n} recovered on retest")
                else:
                    log(f"TLS dead w{n} :{port_for(n)} pid={pid} — kill")
                    kill_pid(pid)
            live = still
            last_tls_check = time.time()
            urls = [proxy_url(port_for(n)) for n in sorted(live)]
            write_live(urls)
            log(f"live={len(live)} {urls}")

        # pre-register unused confs
        unused = unused_confs()
        missing = PREWARM - len(unused)
        if missing > 0:
            batch = list(range(next_n, next_n + missing))
            next_n += missing
            with ThreadPoolExecutor(max_workers=min(8, len(batch))) as ex:
                list(ex.map(register_one, batch))
            unused = unused_confs()

        # fill up to TARGET_LIVE
        if len(live) < TARGET_LIVE:
            candidates = [n for n in unused if n not in live][:3]
            started: list[int] = []
            for n in candidates:
                pid = start_hop(n)
                if pid:
                    started.append(n)
                    live_try_pid = pid
                    # stash pid even before TLS so we can kill it
                    live[n] = live_try_pid
            time.sleep(3)
            # handshake then UA TLS; test new hops a few at a time
            fresh = [n for n in started if n in live]
            ok_new: dict[int, int] = {}
            for i in range(0, len(fresh), 3):
                batch = fresh[i : i + 3]
                with ThreadPoolExecutor(max_workers=len(batch)) as ex:
                    futs = {ex.submit(handshake_ok, port_for(n)): n for n in batch}
                    hs_ok = {futs[f]: f.result() for f in as_completed(futs)}
                tls_batch = [n for n in batch if hs_ok.get(n)]
                for n in batch:
                    if not hs_ok.get(n):
                        log(f"handshake FAIL w{n}")
                with ThreadPoolExecutor(max_workers=max(1, len(tls_batch))) as ex:
                    futs = {ex.submit(tls_ok, port_for(n)): n for n in tls_batch}
                    tls_map = {futs[f]: f.result() for f in as_completed(futs)}
                for n in tls_batch:
                    if tls_map.get(n):
                        ok_new[n] = live[n]
                        log(f"TLS 200 w{n} :{port_for(n)}")
                    else:
                        # isolated retest before kill
                        if tls_ok(port_for(n)):
                            ok_new[n] = live[n]
                            log(f"TLS 200 w{n} :{port_for(n)} (retest)")
                        else:
                            log(f"TLS FAIL w{n} :{port_for(n)}")
            # keep previous live + new 200s; kill the rest of this round
            keep_pids = {**{k: v for k, v in live.items() if k not in started}, **ok_new}
            for n in started:
                if n not in ok_new:
                    pid = live.get(n)
                    if pid:
                        kill_pid(pid)
            live = keep_pids
            urls = [proxy_url(port_for(n)) for n in sorted(live)]
            write_live(urls)
            log(f"live={len(live)} {urls}")

        prune_extra(set(live))
        # if we are at target, sleep; if short, loop immediately
        if len(live) >= TARGET_LIVE:
            time.sleep(25)
        else:
            time.sleep(1)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("FARM stop")
        sys.exit(0)
