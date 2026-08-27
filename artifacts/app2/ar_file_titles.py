#!/usr/bin/env python3
"""Keep English CircuitBit filenames and append (Arabic) to the stem.

Example:  WIFI, BLUETOOTH & GPS.png
       -> WIFI, BLUETOOTH & GPS (مخطط عطل واي فاي وبلوتوث وجي بي إس).png
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

IPHONE = Path("/workspace/artifacts/app2/iphone_originals")

# Exact English stem -> Arabic in parentheses (no extra parens).
HW_AR: dict[str, str] = {
    "BEFORE AFTER VOLTAGE": "جهد قبل وبعد",
    "CPU VOLTAGE": "جهد المعالج",
    "SD CARD": "مخطط عطل كرت الذاكرة",
    "SUB BOARD": "مخطط عطل البورد الفرعي",
    "SUB BOARD A": "مخطط عطل البورد الفرعي أ",
    "SUB BOARD B": "مخطط عطل البورد الفرعي ب",
    "SUB BOARD 1": "مخطط عطل البورد الفرعي 1",
    "SUB BOARD 2": "مخطط عطل البورد الفرعي 2",
    "SUB BOARD THERMISTOR": "مخطط عطل ثرمستور البورد الفرعي",
    "UFS EMMC VOLT & PINOUT": "جهد وبنوت الذاكرة",
    "HOME KEY": "مخطط عطل زر الهوم",
    "TOUCH HOME KEY": "مخطط عطل لمس زر الهوم",
    "FRONT CAMERA": "مخطط عطل الكاميرا الأمامية",
    "BACK CAMERA": "مخطط عطل الكاميرا الخلفية",
    "CHARGER & DATA 1": "مخطط عطل الشحن والبيانات 1",
    "CHARGER & DATA 2": "مخطط عطل الشحن والبيانات 2",
    "CHARGER & DATA 3": "مخطط عطل الشحن والبيانات 3",
    "CHARGER & DATA C": "مخطط عطل الشحن والبيانات ج",
    "COMPONENT NAME MAIN": "أسماء القطع الرئيسية",
    "SIM CARD 1": "مخطط عطل الشريحة 1",
    "SIM CARD 2": "مخطط عطل الشريحة 2",
    "SIM CARD A": "مخطط عطل الشريحة أ",
    "SIM CARD B": "مخطط عطل الشريحة ب",
    "LCD SUB": "مخطط عطل الشاشة الفرعية",
    "LCD LIGHT SUB": "مخطط عطل إضاءة الشاشة الفرعية",
    "TOUCHSCREEN SUB": "مخطط عطل اللمس الفرعي",
    "TOUCHSCREEN MAIN": "مخطط عطل اللمس الرئيسي",
    "DIODA MODE (DT17DN) CONNECTOR": "وضع الدايود الكونكتر",
    "DIODA MODE (DT17DN) CPU": "وضع الدايود المعالج",
    "DIODA MODE (DT17DN) INPUT-OUTPUT": "وضع الدايود جهد الدخل والخرج",
    "DIODA MODE (SANWA-CD800A) CPU": "وضع الدايود المعالج",
    "BASEBAND": "مخطط عطل البيسباند",
    "BASEBAND A": "مخطط عطل البيسباند أ",
    "BASEBAND B": "مخطط عطل البيسباند ب",
    "BASEBAND CIRCUIT": "دائرة البيسباند",
    "BB CIRCUIT": "دائرة البيسباند",
    "CHARGER & DATA": "مخطط عطل الشحن والبيانات",
    "CHARGER & DATA A": "مخطط عطل الشحن والبيانات أ",
    "CHARGER & DATA B": "مخطط عطل الشحن والبيانات ب",
    "COMPONENT NAME": "أسماء القطع",
    "COMPONENT NAME A": "أسماء القطع أ",
    "COMPONENT NAME B": "أسماء القطع ب",
    "COMPONENT NAME C": "أسماء القطع ج",
    "COMPONENT NAMED": "أسماء القطع",
    "COMPONENT NAME BASEBAND TOP": "أسماء القطع البيسباند الوجه العلوي",
    "COMPONENT NAME BOTTOM": "أسماء القطع الوجه السفلي",
    "COMPONENT NAME CORE": "أسماء القطع النواة",
    "COMPONENT NAME CORE BOTTOM": "أسماء القطع النواة الوجه السفلي",
    "COMPONENT NAME CORE TOP": "أسماء القطع النواة الوجه العلوي",
    "COMPONENT NAME TOP": "أسماء القطع الوجه العلوي",
    "DIODA MODE (SAMWA-CD800A) INPUT-OUTPUT": "وضع الدايود جهد الدخل والخرج",
    "DIODA MODE (SANWA-CD800A) CONNECTOR": "وضع الدايود الكونكتر",
    "DIODA MODE (SANWA-CD800A) CONNECTOR A": "وضع الدايود الكونكتر أ",
    "DIODA MODE (SANWA-CD800A) CONNECTOR B": "وضع الدايود الكونكتر ب",
    "DIODA MODE (SANWA-CD800A) CONNECTOR C": "وضع الدايود الكونكتر ج",
    "DIODA MODE (SUNSHINE DT17DN) CONNECTOR": "وضع الدايود الكونكتر",
    "DIODA MODE (SUNSHINE DT17DN) CONNECTOR A": "وضع الدايود الكونكتر أ",
    "DIODA MODE (SUNSHINE DT17DN) CONNECTOR B": "وضع الدايود الكونكتر ب",
    "DIODA MODE (SUNSHINE DT17DN) CONNECTOR C": "وضع الدايود الكونكتر ج",
    "FINGERPRINT": "مخطط عطل البصمة",
    "FLOOD ILLUMINATOR": "مخطط عطل كشاف الوجه",
    "HANDSFREE": "مخطط عطل الهاندز فري",
    "INPUT OUTPUT VOLTAGE": "مخطط عطل جهد الدخل والخرج",
    "LCD": "مخطط عطل الشاشة",
    "LCD A": "مخطط عطل الشاشة أ",
    "LCD B": "مخطط عطل الشاشة ب",
    "LCD LIGHT": "مخطط عطل إضاءة الشاشة",
    "MIC SPEAKER BUZZER": "مخطط عطل المايك والسبيكر والزرار",
    "MIC SPEAKER BUZZER A": "مخطط عطل المايك والسبيكر والزرار أ",
    "MIC SPEAKER BUZZER B": "مخطط عطل المايك والسبيكر والزرار ب",
    "MIC SPEAKER BUZZER C": "مخطط عطل المايك والسبيكر والزرار ج",
    "NETWORK": "مخطط عطل الشبكة",
    "NETWORK A": "مخطط عطل الشبكة أ",
    "NETWORK B": "مخطط عطل الشبكة ب",
    "NFC": "مخطط عطل إن إف سي",
    "NFC A": "مخطط عطل إن إف سي أ",
    "NFC B": "مخطط عطل إن إف سي ب",
    "ON OFF & VOLUME KEYS": "مخطط عطل أزرار التشغيل والصوت",
    "RESISTANCE VALUE ON PAD": "قيم المقاومات على الباد",
    "SIM CARD": "مخطط عطل الشريحة",
    "TEST POINT RFFE": "نقاط فحص آر إف",
    "THERMISTOR": "مخطط عطل الثرمستور",
    "TOUCHSCREEN": "مخطط عطل اللمس",
    "TOUCHSCREEN A": "مخطط عطل اللمس أ",
    "TOUCHSCREEN B": "مخطط عطل اللمس ب",
    "TOUCHSCREEN C": "مخطط عطل اللمس ج",
    "WIFI, BLUETOOTH & GPS": "مخطط عطل واي فاي وبلوتوث وجي بي إس",
    "Screenshot 2026-04-06 111308": "لقطة شاشة",
}

_HAS_AR = re.compile(r"[\u0600-\u06FF]")


def already_bilingual(stem: str) -> bool:
    return bool(_HAS_AR.search(stem)) and stem.endswith(")")


def _hw_ar_guess(stem: str) -> str | None:
    u = stem.upper().strip()
    if u in HW_AR:
        return HW_AR[u]
    if u.startswith("BACK CAMERA"):
        return "مخطط عطل الكاميرا الخلفية"
    if u.startswith("FRONT CAMERA"):
        return "مخطط عطل الكاميرا الأمامية"
    if "DIODA MODE" in u and "CONNECTOR" in u:
        return "وضع الدايود الكونكتر"
    if "DIODA MODE" in u and "CPU" in u:
        return "وضع الدايود المعالج"
    if "DIODA MODE" in u and "INPUT" in u:
        return "وضع الدايود جهد الدخل والخرج"
    if u.startswith("CHARGER"):
        return "مخطط عطل الشحن والبيانات"
    if u.startswith("COMPONENT NAME"):
        return "أسماء القطع"
    if u.startswith("MIC SPEAKER"):
        return "مخطط عطل المايك والسبيكر والزرار"
    return "مخطط عطل"


def hw_bilingual_stem(stem: str) -> str:
    if already_bilingual(stem):
        return stem
    ar = HW_AR.get(stem) or HW_AR.get(stem.upper()) or _hw_ar_guess(stem)
    if not ar:
        return stem
    return f"{stem} ({ar})"


def pdf_bilingual_stem(stem: str) -> str:
    if already_bilingual(stem):
        return stem
    s = stem
    # Keep English, append a short Arabic description of the document type.
    low = s.lower()
    bits: list[str] = []
    if "schemat" in low or "schem" in low:
        bits.append("مخطط")
    if "pcb" in low or "brd" in low:
        bits.append("لوحة مطبوعة")
    if re.search(r"\brf\b", low) or "radio" in low:
        bits.append("التردد اللاسلكي")
    if re.search(r"\bap\b", low):
        bits.append("المعالج")
    if "topside" in low or "top side" in low:
        bits.append("الوجه العلوي")
    if "full" in low:
        bits.append("كامل")
    if not bits:
        bits.append("ملف مخطط")
    ar = " ".join(dict.fromkeys(bits))
    return f"{s} ({ar})"


def rename_tree(root: Path, kind: str) -> tuple[int, int, list[str]]:
    """Rename files in place. Returns (renamed, skipped, missing_keys)."""
    n_ok = n_skip = 0
    missing: list[str] = []
    if not root.exists():
        return 0, 0, missing
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.endswith(".part"):
            continue
        stem, suf = p.stem, p.suffix
        if kind == "hardware":
            new_stem = hw_bilingual_stem(stem)
            if new_stem == stem and stem.upper() not in {k.upper() for k in HW_AR} and not already_bilingual(stem):
                missing.append(stem)
        else:
            new_stem = pdf_bilingual_stem(stem)
        if new_stem == stem:
            n_skip += 1
            continue
        dest = p.with_name(new_stem + suf)
        if dest.exists() and dest != p:
            n_skip += 1
            continue
        p.rename(dest)
        n_ok += 1
    return n_ok, n_skip, missing


def files_missing_arabic(root: Path) -> list[Path]:
    """Files whose English stem has no Arabic (… ) suffix."""
    missing: list[Path] = []
    if not root.exists():
        return missing
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name.endswith(".part"):
            continue
        if not already_bilingual(p.stem):
            missing.append(p)
    return missing


def assert_arabic_parens(root: Path) -> None:
    """Refuse Drive upload if any file still lacks English (عربي)."""
    missing = files_missing_arabic(root)
    if not missing:
        return
    sample = "\n".join(f"  {p}" for p in missing[:20])
    raise SystemExit(
        f"REFUSE upload: {len(missing)} file(s) under {root} lack Arabic (… )\n{sample}"
    )


def main() -> int:
    roots = [Path(a) for a in sys.argv[1:]] or [IPHONE]
    total_r = total_s = 0
    all_miss: list[str] = []
    for root in roots:
        hw = root / "Hardware"
        pdf = root / "PDF"
        r1, s1, miss = rename_tree(hw, "hardware")
        r2, s2, _ = rename_tree(pdf, "pdf")
        total_r += r1 + r2
        total_s += s1 + s2
        all_miss.extend(miss)
        print(f"{root}: hardware renamed={r1} unchanged={s1} pdf renamed={r2} unchanged={s2}")
    if all_miss:
        uniq = sorted(set(all_miss))
        print("stems used generic Arabic:")
        for n in uniq[:40]:
            print(" ", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
