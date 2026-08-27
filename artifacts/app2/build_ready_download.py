#!/usr/bin/env python3
"""Build IPHONE + SAMSUNG folders: company / phone / (png+pdf). Hardlinks only."""
from __future__ import annotations

import os
import re
from pathlib import Path

LIB = Path("/workspace/artifacts/app2/library")
IPHONE = Path("/workspace/artifacts/app2/iphone_originals")
EXPORT = Path("/workspace/artifacts/export/CircuitBit-IPHONE-SAMSUNG")
PLACEHOLDER_WH = (900, 400)


def png_wh(path: Path) -> tuple[int, int] | None:
    try:
        data = path.read_bytes()[:24]
    except OSError:
        return None
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def is_real_file(path: Path) -> bool:
    if not path.is_file() or path.name.endswith(".part"):
        return False
    if path.suffix.lower() == ".png" and png_wh(path) == PLACEHOLDER_WH:
        return False
    return path.stat().st_size > 0


def link_into(src: Path, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        return
    try:
        os.link(src, dest)
    except OSError:
        os.symlink(src, dest)


def norm(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().upper()


def codes(name: str) -> set[str]:
    u = name.upper()
    out = set(re.findall(r"SM-[A-Z0-9]+", u))
    out.update(re.findall(r"\b[A-Z]?\d{3,4}[A-Z]?\b", u))
    return {c.replace(" ", "") for c in out}


def match_pdf_to_hw(pdf_name: str, hw_names: list[str]) -> str | None:
    n = norm(pdf_name)
    for hw in hw_names:
        if n == norm(hw):
            return hw
    pc = codes(pdf_name)
    if not pc:
        return None
    hits = [hw for hw in hw_names if pc & codes(hw)]
    if len(hits) == 1:
        return hits[0]
    return None


def collect_hw(brand_hw: Path) -> dict[str, list[Path]]:
    models: dict[str, list[Path]] = {}
    if not brand_hw.exists():
        return models
    for p in brand_hw.rglob("*"):
        if not is_real_file(p):
            continue
        model = p.parent.name
        if model in ("Hardware", "PDF"):
            continue
        models.setdefault(model, []).append(p)
    return models


def write_readme(dest: Path, brand: str, n_phones: int, n_files: int) -> None:
    text = (
        f"{brand}\n"
        f"شركة واحدة — مجلد لكل هاتف.\n"
        f"الهواتف: {n_phones}\n"
        f"الملفات: {n_files}\n"
        f"الصور PNG أصلية + PDF إن وُجد داخل مجلد نفس الهاتف.\n"
        f"لا خلط مع شركات أخرى.\n"
    )
    (dest / "اقرأني.txt").write_text(text, encoding="utf-8")


def export_brand(brand: str, hw_root: Path, pdf_root: Path) -> tuple[int, int]:
    out = EXPORT / brand
    if out.exists():
        # remove previous tree (hardlinks only — safe)
        for p in sorted(out.rglob("*"), reverse=True):
            if p.is_symlink() or p.is_file():
                p.unlink()
            elif p.is_dir():
                p.rmdir()
        out.rmdir()
    hw = collect_hw(hw_root)
    pdf_dirs = [d for d in pdf_root.iterdir() if d.is_dir()] if pdf_root.exists() else []
    hw_names = list(hw)
    used_pdf: set[str] = set()
    n_files = 0
    for model, files in sorted(hw.items(), key=lambda x: x[0].upper()):
        phone = out / model
        for f in files:
            link_into(f, phone)
            n_files += 1
    for d in pdf_dirs:
        pdfs = [p for p in d.iterdir() if is_real_file(p)]
        if not pdfs:
            continue
        target_name = match_pdf_to_hw(d.name, hw_names) or d.name
        used_pdf.add(d.name)
        phone = out / target_name
        for f in pdfs:
            link_into(f, phone)
            n_files += 1
    n_phones = sum(1 for p in out.iterdir() if p.is_dir())
    write_readme(out, brand, n_phones, n_files)
    return n_phones, n_files


def main() -> None:
    EXPORT.mkdir(parents=True, exist_ok=True)
    ip_n, ip_f = export_brand("IPHONE", IPHONE / "Hardware", IPHONE / "PDF")
    sm_n, sm_f = export_brand(
        "SAMSUNG", LIB / "SAMSUNG" / "Hardware", LIB / "SAMSUNG" / "PDF"
    )
    top = (
        "CircuitBit — آيفون + سامسونج فقط (المكتمل)\n"
        f"IPHONE: {ip_n} هاتف / {ip_f} ملف\n"
        f"SAMSUNG: {sm_n} هاتف / {sm_f} ملف\n"
        "كل شركة مجلد، وكل هاتف مجلد داخله الصور وPDF.\n"
        "فك الضغط بـ 7-Zip أو Windows tar.\n"
    )
    (EXPORT / "اقرأني.txt").write_text(top, encoding="utf-8")
    print(f"EXPORT {EXPORT}")
    print(f"IPHONE phones={ip_n} files={ip_f}")
    print(f"SAMSUNG phones={sm_n} files={sm_f}")


if __name__ == "__main__":
    main()
