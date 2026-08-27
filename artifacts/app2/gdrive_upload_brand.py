#!/usr/bin/env python3
"""Upload one CircuitBit brand to Google Drive with bilingual filenames.

Rule: every file must keep the English name and add Arabic in parentheses,
e.g. LCD (مخطط عطل الشاشة).png

Usage: python3 gdrive_upload_brand.py "GOOGLE PIXEL"
Remote is always gdrive_user (OAuth). Never the service-account remote `gdrive`.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import ar_file_titles as ar

LIB = Path("/workspace/artifacts/app2/library")
REMOTE = "gdrive_user"


def _run(cmd: list[str], log: Path | None = None) -> int:
    print("+", " ".join(cmd), flush=True)
    with subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    ) as proc:
        assert proc.stdout is not None
        for line in proc.stdout:
            sys.stdout.write(line)
            if log:
                log.parent.mkdir(parents=True, exist_ok=True)
                with log.open("a", encoding="utf-8") as fh:
                    fh.write(line)
        return int(proc.wait() or 0)


def _rclone_json(args: list[str]) -> dict:
    p = subprocess.run(
        ["rclone", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if p.returncode != 0:
        raise SystemExit(p.stderr or p.stdout or "rclone failed")
    return json.loads(p.stdout or "{}")


def _about() -> tuple[int, int]:
    d = _rclone_json(["about", f"{REMOTE}:", "--json"])
    return int(d.get("free") or 0), int(d.get("used") or 0)


def _local_size(path: Path) -> int:
    if not path.exists():
        return 0
    d = _rclone_json(["size", str(path), "--json"])
    return int(d.get("bytes") or 0)


def prepare_brand(brand: str) -> Path:
    root = LIB / brand
    if not root.is_dir():
        raise SystemExit(f"missing local folder {root}")
    r1, s1, _ = ar.rename_tree(root / "Hardware", "hardware")
    r2, s2, _ = ar.rename_tree(root / "PDF", "pdf")
    print(f"{brand} arabic hardware renamed={r1} skip={s1} pdf renamed={r2} skip={s2}", flush=True)
    ar.assert_arabic_parens(root)
    print(f"{brand} arabic gate OK", flush=True)
    return root


def upload_brand(brand: str, remote_name: str | None = None) -> int:
    remote_name = remote_name or brand
    root = prepare_brand(brand)
    free, used = _about()
    need = _local_size(root / "Hardware") + _local_size(root / "PDF")
    print(
        f"quota used={used/1024**3:.2f}GiB free={free/1024**3:.2f}GiB need={need/1024**3:.2f}GiB",
        flush=True,
    )
    if need > free:
        short = (need - free) / 1024**3
        raise SystemExit(
            f"REFUSE rclone: {brand} needs {need/1024**3:.2f}GiB, Drive free {free/1024**3:.2f}GiB "
            f"(short {short:.2f}GiB)"
        )
    log = Path(f"/tmp/gdrive-{brand.replace(' ', '_').lower()}-upload.log")
    rc = 0
    for section in ("Hardware", "PDF"):
        src = root / section
        if not src.exists():
            continue
        dest = f"{REMOTE}:{remote_name}/{section}"
        remote_id = dest.split(":", 1)[0]
        if remote_id != "gdrive_user":
            raise SystemExit(
                f"REFUSE: only gdrive_user is allowed, got {remote_id!r}"
            )
        rc = _run(
            [
                "rclone",
                "copy",
                str(src),
                dest,
                "--transfers",
                "4",
                "--checkers",
                "8",
                "--drive-chunk-size",
                "64M",
                "-v",
            ],
            log,
        )
        if rc != 0:
            raise SystemExit(f"rclone copy {section} failed rc={rc}")
        print(f"{section}_EXIT={rc}", flush=True)
        with log.open("a", encoding="utf-8") as fh:
            fh.write(f"{section}_EXIT={rc}\n")
    return 0


def delete_english_only_on_drive(remote_folder: str) -> int:
    """Remove Drive files that were uploaded before Arabic parentheses existed."""
    p = subprocess.run(
        ["rclone", "lsf", f"{REMOTE}:{remote_folder}", "--recursive", "--files-only"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    if p.returncode != 0:
        print(p.stderr, file=sys.stderr)
        return p.returncode
    n = 0
    for rel in p.stdout.splitlines():
        rel = rel.strip()
        if not rel:
            continue
        name = rel.rsplit("/", 1)[-1]
        stem = name.rsplit(".", 1)[0]
        if ar.already_bilingual(stem):
            continue
        dest = f"{REMOTE}:{remote_folder}/{rel}"
        print(f"delete english-only {dest}", flush=True)
        d = subprocess.run(["rclone", "deletefile", dest], capture_output=True, text=True)
        if d.returncode == 0:
            n += 1
        else:
            print(d.stderr or d.stdout, file=sys.stderr)
    print(f"deleted_english_only={n}", flush=True)
    return 0


def main() -> int:
    if len(sys.argv) < 2:
        raise SystemExit('usage: gdrive_upload_brand.py "BRAND" [remote-folder]')
    brand = sys.argv[1]
    remote = sys.argv[2] if len(sys.argv) > 2 else brand
    upload_brand(brand, remote)
    for section in ("Hardware", "PDF"):
        delete_english_only_on_drive(f"{remote}/{section}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
