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


def hw_bilingual_stem(stem: str) -> str:
    if already_bilingual(stem):
        return stem
    ar = HW_AR.get(stem)
    if not ar:
        ar = HW_AR.get(stem.upper())
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


def main() -> int:
    hw = IPHONE / "Hardware"
    pdf = IPHONE / "PDF"
    r1, s1, miss = rename_tree(hw, "hardware")
    r2, s2, _ = rename_tree(pdf, "pdf")
    print(f"hardware renamed={r1} unchanged={s1}")
    print(f"pdf renamed={r2} unchanged={s2}")
    if miss:
        uniq = sorted(set(miss))
        print("untranslated stems:")
        for n in uniq:
            print(" ", n)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
