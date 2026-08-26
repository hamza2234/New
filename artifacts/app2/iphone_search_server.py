#!/usr/bin/env python3
"""Temporary Arabic search site for CircuitBit originals on this agent."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import tempfile
import threading
import time
import zipfile
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

LIB = Path("/workspace/artifacts/app2/library")
IPHONE = Path("/workspace/artifacts/app2/iphone_originals")
READY = Path("/workspace/artifacts/export")
SUPPORTED = Path("/workspace/artifacts/app2/supported_models.json")
STATUS = LIB / "STATUS.txt"
LOG = LIB / "download.log"
HUAWEI_LOG = Path("/tmp/huawei_fill.log")
HUAWEI_STATE = Path("/tmp/huawei_fill_state.json")
HOP_LIVE = Path("/tmp/egress/live_proxies.txt")
DRIVE_LOG = Path("/tmp/gdrive-fit-upload.log")
IPHONE_DRIVE_LOG = Path("/tmp/gdrive-iphone-upload.log")
HOST = "0.0.0.0"
PORT = int(os.environ.get("IPHONE_SITE_PORT", "8765"))
TOKEN = os.environ.get("IPHONE_SITE_TOKEN", "cbiphone")
REINDEX_SEC = 60
PLACEHOLDER_WH = (900, 400)

INDEX: list[dict] = []
INDEX_LOCK = threading.Lock()


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


def brand_root(brand: str) -> Path | None:
    for name, root in roots():
        if name == brand:
            return root
    return None


def phone_files(brand: str, model: str) -> list[tuple[Path, str]]:
    """Original PNG+PDF for one phone. Arc names: BRAND/model/filename."""
    if not brand or not model or "/" in model or "\\" in model or model in (".", ".."):
        return []
    root = brand_root(brand)
    if root is None:
        return []
    out: list[tuple[Path, str]] = []
    seen: set[Path] = set()
    used_names: set[str] = set()
    for folder_name in ("Hardware", "PDF"):
        folder = root / folder_name
        if folder.is_symlink():
            try:
                folder = folder.resolve()
            except OSError:
                continue
        if not folder.exists():
            continue
        for p in folder.rglob("*"):
            if p.parent.name != model or not is_real_file(p):
                continue
            key = p.resolve()
            if key in seen:
                continue
            seen.add(key)
            name = p.name
            if name in used_names:
                name = f"{folder_name.lower()}_{p.name}"
            used_names.add(name)
            out.append((p, f"{brand}/{model}/{name}"))
    out.sort(key=lambda x: x[1].lower())
    return out


def models_payload(brand: str = "", q: str = "") -> dict:
    brand = (brand or "").strip().upper()
    q = re.sub(r"\s+", " ", q or "").strip().lower()
    groups: dict[tuple[str, str], dict] = {}
    with INDEX_LOCK:
        rows = list(INDEX)
    for row in rows:
        b, m = row["brand"], row["model"]
        if brand and b.upper() != brand:
            continue
        if q:
            blob = f"{b} {m}".lower()
            if not all(p in blob for p in q.split()):
                continue
        key = (b, m)
        g = groups.get(key)
        if g is None:
            g = {"brand": b, "model": m, "files": 0, "bytes": 0, "pdf": 0, "hardware": 0}
            groups[key] = g
        g["files"] += 1
        g[row["kind"]] = g.get(row["kind"], 0) + 1
        g["bytes"] += int(round(float(row["mb"]) * 1048576))
    models = []
    for g in sorted(groups.values(), key=lambda x: (x["brand"].lower(), x["model"].lower())):
        mb = round(g["bytes"] / 1048576, 1)
        models.append(
            {
                "brand": g["brand"],
                "model": g["model"],
                "files": g["files"],
                "hardware": g.get("hardware", 0),
                "pdf": g.get("pdf", 0),
                "mb": mb,
                "zip": f"/zip/{g['brand']}/{g['model']}.zip",
            }
        )
    return {"count": len(models), "models": models[:800]}


def safe_under(base: Path, rel: str) -> Path | None:
    try:
        target = (base / rel).resolve()
        base_r = base.resolve()
        if base_r not in target.parents and target != base_r:
            return None
        if not target.is_file():
            return None
        return target
    except Exception:
        return None


def roots() -> list[tuple[str, Path]]:
    out: list[tuple[str, Path]] = []
    if LIB.exists():
        for brand_dir in sorted(p for p in LIB.iterdir() if p.is_dir() and p.name != "catalogs"):
            out.append((brand_dir.name, brand_dir))
    if IPHONE.exists() and not any(b == "IPHONE" for b, _ in out):
        out.append(("IPHONE", IPHONE))
    return out


def build_index() -> None:
    items = []
    for brand, root in roots():
        for kind, folder_name in (("pdf", "PDF"), ("hardware", "Hardware")):
            folder = root / folder_name
            if not folder.exists():
                continue
            for p in folder.rglob("*"):
                if not p.is_file() or p.name.endswith(".part"):
                    continue
                rel = f"{brand}/{kind}/{p.relative_to(folder).as_posix()}"
                items.append(
                    {
                        "kind": kind,
                        "brand": brand,
                        "model": p.parent.name,
                        "name": p.stem,
                        "filename": p.name,
                        "rel": rel,
                        "mb": round(p.stat().st_size / 1048576, 1),
                        "ext": p.suffix.lower(),
                    }
                )
    items.sort(
        key=lambda x: (x["brand"].lower(), x["kind"], x["model"].lower(), x["name"].lower())
    )
    with INDEX_LOCK:
        INDEX.clear()
        INDEX.extend(items)


def search(q: str) -> list[dict]:
    q = re.sub(r"\s+", " ", q).strip().lower()
    with INDEX_LOCK:
        rows = list(INDEX)
    if not q:
        # compact model summary
        return rows
    parts = q.split()
    out = []
    for row in rows:
        blob = f"{row['kind']} {row.get('brand','')} {row['model']} {row['name']} {row['filename']}".lower()
        if all(p in blob for p in parts):
            out.append(row)
    return out


HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>بحث ملفات CircuitBit</title>
<style>
  :root { --bg:#0f1419; --card:#1a2330; --txt:#eef3f8; --mut:#9bb0c3; --acc:#3d9cf0; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,-apple-system,Segoe UI,Tahoma,sans-serif; background:var(--bg); color:var(--txt); }
  header { padding:16px 14px 8px; position:sticky; top:0; background:var(--bg); }
  h1 { font-size:18px; margin:0 0 10px; }
  input { width:100%; padding:12px 14px; border-radius:12px; border:1px solid #2b3b4d; background:#121a24; color:var(--txt); font-size:16px; }
  .meta { color:var(--mut); font-size:13px; margin:8px 0 0; }
  .list { padding:8px 12px 24px; display:flex; flex-direction:column; gap:8px; }
  a.item { display:block; text-decoration:none; color:inherit; background:var(--card); border-radius:12px; padding:12px; }
  .kind { font-size:11px; color:var(--acc); }
  .name { font-size:15px; margin-top:2px; }
  .sub { font-size:12px; color:var(--mut); margin-top:4px; }
  iframe, embed, img { width:100%; border:0; background:#000; }
  .viewer { padding:0 12px 20px; }
  .back { display:inline-block; margin:8px 14px; color:var(--acc); }
</style>
</head>
<body>
<header>
  <h1>بحث ملفات CircuitBit</h1>
  <div class="meta"><a class="back" href="#" id="homeLink">مراقبة التقدم</a> · <a class="back" href="#" id="driveLink">شاشة رفع درايف</a> · <a class="back" href="#" id="progLink">مخرجات التحميل</a> · <a class="back" href="#" id="dlLink">تنزيل آيفون + سامسونج</a></div>
  <input id="q" type="search" placeholder="ابحث: samsung a15 / infinix hot 30 / vivo y17 / lcd" autofocus/>
  <div class="meta" id="meta">جاري التحميل...</div>
</header>
<div class="list" id="list"></div>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
const homeLink = document.getElementById('homeLink');
if (homeLink) homeLink.href = base + '/';
const driveLink = document.getElementById('driveLink');
if (driveLink) driveLink.href = base + '/drive';
const progLink = document.getElementById('progLink');
if (progLink) progLink.href = base + '/progress';
const dlLink = document.getElementById('dlLink');
if (dlLink) dlLink.href = base + '/ready';
const qel = document.getElementById('q');
const list = document.getElementById('list');
const meta = document.getElementById('meta');
let t = null;
function openUrl(it){
  return base + '/open/' + it.kind + '/' + encodeURIComponent(it.rel);
}
function render(items, total){
  meta.textContent = 'النتيجة: ' + items.length + ' من ' + total;
  list.innerHTML = items.slice(0, 200).map(it => `
    <a class="item" href="${openUrl(it)}" target="_blank">
      <div class="kind">${it.brand || ''} · ${it.kind === 'pdf' ? 'مخطط PDF' : 'صورة هاردوير PNG'}</div>
      <div class="name">${it.model} — ${it.name}</div>
      <div class="sub">${it.filename} · ${it.mb} MB</div>
    </a>`).join('') || '<div class="meta">لا توجد نتائج</div>';
}
async function run(){
  const q = qel.value.trim();
  const r = await fetch(base + '/api/search?q=' + encodeURIComponent(q));
  const data = await r.json();
  render(data.items, data.total);
}
qel.addEventListener('input', () => { clearTimeout(t); t = setTimeout(run, 150); });
run();
</script>
</body>
</html>
"""


PROGRESS_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>مخرجات تحميل CircuitBit</title>
<style>
  :root { --bg:#0b1016; --card:#151d28; --txt:#eef3f8; --mut:#9bb0c3; --acc:#5ee0a0; --warn:#f0c14d; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; background:var(--bg); color:var(--txt); }
  header { padding:14px 14px 6px; position:sticky; top:0; background:var(--bg); border-bottom:1px solid #223044; }
  h1 { font-size:17px; margin:0 0 6px; font-family:system-ui,Tahoma,sans-serif; }
  .meta { color:var(--mut); font-size:13px; font-family:system-ui,Tahoma,sans-serif; }
  a { color:var(--acc); }
  pre.status { white-space:pre-wrap; background:var(--card); margin:10px 12px; padding:12px; border-radius:10px; font-size:13px; line-height:1.45; }
  pre.log { white-space:pre-wrap; background:#070b10; margin:0 12px 20px; padding:12px; border-radius:10px; font-size:12px; line-height:1.5; min-height:50vh; border:1px solid #223044; }
  .ok { color:var(--acc); } .fail { color:#ff8a8a; }
</style>
</head>
<body>
<header>
  <h1>مخرجات التحميل المباشرة</h1>
  <div class="meta">يتحدث كل 3 ثوانٍ · <a id="home" href="#">مراقبة التقدم</a> · <a id="drive" href="#">شاشة رفع درايف</a> · <a id="back" href="#">البحث</a> · <span id="tick">...</span></div>
</header>
<pre class="status" id="status">جاري التحميل...</pre>
<pre class="log" id="log"></pre>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
document.getElementById('home').href = base + '/';
document.getElementById('back').href = base + '/search';
document.getElementById('drive').href = base + '/drive';
async function tick(){
  try {
    const r = await fetch(base + '/api/progress?n=60', {cache:'no-store'});
    const d = await r.json();
    document.getElementById('status').textContent = d.status || '';
    document.getElementById('log').textContent = (d.log || []).join('\n');
    document.getElementById('tick').textContent = d.now + ' · أسطر السجل: ' + (d.log||[]).length;
  } catch (e) {
    document.getElementById('tick').textContent = 'تعذر التحديث';
  }
}
tick();
setInterval(tick, 3000);
</script>
</body>
</html>
"""

READY_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>تنزيل آيفون وسامسونج</title>
<style>
  :root { --bg:#0f1419; --card:#1a2330; --txt:#eef3f8; --mut:#9bb0c3; --acc:#3d9cf0; }
  body { margin:0; font-family:system-ui,Tahoma,sans-serif; background:var(--bg); color:var(--txt); padding:18px; }
  a { color:var(--acc); }
  .card { background:var(--card); border-radius:14px; padding:16px; margin:12px 0; }
  .mut { color:var(--mut); font-size:14px; }
  h1 { font-size:20px; }
</style>
</head>
<body>
<h1>تنزيل المكتمل فقط</h1>
<p class="mut">آيفون + سامسونج. مجلد لكل شركة، ومجلد لكل هاتف (صور + PDF). فكّ الملف بـ 7-Zip أو WinRAR.</p>
<p class="mut"><a href="#" id="home">مراقبة التقدم</a> · <a href="#" id="back">البحث</a> · <a href="#" id="drive">شاشة رفع درايف</a> · <a href="#" id="prog">المخرجات</a></p>
<div class="card" id="box">جاري فحص الأرشيف...</div>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
document.getElementById('home').href = base + '/';
document.getElementById('back').href = base + '/search';
document.getElementById('drive').href = base + '/drive';
document.getElementById('prog').href = base + '/progress';
async function go(){
  const r = await fetch(base + '/api/ready', {cache:'no-store'});
  const d = await r.json();
  const box = document.getElementById('box');
  box.innerHTML = (d.files||[]).map(f => {
    if (!f.ready) return '<p><b>'+f.name+'</b><br>جارٍ تجهيز الأرشيف... '+f.note+'</p>';
    return '<p><a href="'+base+'/ready/'+encodeURIComponent(f.name)+'">تنزيل '+f.name+'</a><br><span class="mut">'+f.gb+' GB · '+f.note+'</span></p>';
  }).join('') || 'لا يوجد أرشيف بعد';
}
go();
setInterval(go, 5000);
</script>
</body>
</html>
"""


DRIVE_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>رفع الآيفون إلى جوجل درايف</title>
<style>
  :root { --bg:#0b1016; --card:#151d28; --txt:#eef3f8; --mut:#9bb0c3; --acc:#5ee0a0; --bar:#3d9cf0; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Tahoma,sans-serif; background:var(--bg); color:var(--txt); }
  header { padding:18px 16px 8px; }
  h1 { font-size:22px; margin:0 0 6px; }
  .mut { color:var(--mut); font-size:14px; }
  a { color:var(--bar); }
  .card { background:var(--card); border-radius:16px; padding:16px; margin:12px 16px; }
  .big { font-size:28px; font-weight:700; }
  .bar { height:16px; background:#0e1620; border-radius:99px; overflow:hidden; margin:12px 0 6px; }
  .bar > span { display:block; height:100%; background:linear-gradient(90deg,#3d9cf0,#5ee0a0); width:0%; transition:width .4s; }
  .row { display:flex; justify-content:space-between; gap:8px; margin:8px 0; font-size:15px; }
  .ok { color:var(--acc); } .run { color:#f0c14d; } .bad { color:#ff8a8a; }
  ul { margin:8px 0 0; padding-right:18px; font-size:13px; color:var(--mut); }
  li { margin:4px 0; word-break:break-word; }
</style>
</head>
<body>
<header>
  <h1>رفع إلى جوجل درايف</h1>
  <div class="mut">المجلد: <b>Phone X</b> · جوجل بكسل ثم أسوس · التحديث كل 3 ثوانٍ</div>
  <div class="mut" style="margin-top:8px"><a href="#" id="home">مراقبة التقدم</a> · <a href="#" id="search">البحث</a> · <a href="#" id="prog">سجل التحميل</a></div>
</header>
<div class="card">
  <div id="state" class="big run">جاري القراءة...</div>
  <div class="bar"><span id="fill"></span></div>
  <div class="row"><span>التقدم الكلي</span><span id="pct">0%</span></div>
  <div class="row"><span>صور الهاردوير</span><span id="hw">—</span></div>
  <div class="row"><span>ملفات PDF</span><span id="pdf">—</span></div>
  <div class="row"><span>الحجم المرفوع</span><span id="gb">—</span></div>
  <div class="mut" id="note"></div>
</div>
<div class="card">
  <div>آخر الملفات المرفوعة</div>
  <ul id="recent"></ul>
</div>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
document.getElementById('home').href = base + '/';
document.getElementById('search').href = base + '/search';
document.getElementById('prog').href = base + '/progress';
function arState(s){
  if (s === 'done') return ['اكتمل الرفع إلى درايف', 'ok'];
  if (s === 'pdf') return ['جارٍ رفع ملفات PDF', 'run'];
  if (s === 'hardware') return ['جارٍ رفع الملفات إلى درايف', 'run'];
  if (s === 'stopped') return ['توقف الرفع — سأعيد المحاولة', 'bad'];
  return ['جارٍ الرفع إلى جوجل درايف', 'run'];
}
async function tick(){
  try {
    const r = await fetch(base + '/api/drive', {cache:'no-store'});
    const d = await r.json();
    const [txt, cls] = arState(d.state);
    const st = document.getElementById('state');
    st.textContent = txt;
    st.className = 'big ' + cls;
    document.getElementById('fill').style.width = (d.pct || 0) + '%';
    document.getElementById('pct').textContent = (d.pct || 0) + '%';
    document.getElementById('hw').textContent = (d.hw_up || 0) + ' من ' + (d.hw_need || 0);
    document.getElementById('pdf').textContent = (d.pdf_up || 0) + ' من ' + (d.pdf_need || 0);
    document.getElementById('gb').textContent = (d.gb || 0) + ' جيجا';
    document.getElementById('note').textContent = d.note || '';
    document.getElementById('recent').innerHTML = (d.recent || []).map(x => '<li>'+x+'</li>').join('') || '<li>لا شيء بعد</li>';
  } catch (e) {
    document.getElementById('state').textContent = 'تعذر تحديث الصفحة';
  }
}
tick();
setInterval(tick, 3000);
</script>
</body>
</html>
"""


MONITOR_HTML = r"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>مراقبة التقدم</title>
<style>
  :root { --bg:#0b1016; --card:#151d28; --txt:#eef3f8; --mut:#9bb0c3; --acc:#5ee0a0; --bar:#3d9cf0; --warn:#f0c14d; --bad:#ff8a8a; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:system-ui,Tahoma,sans-serif; background:var(--bg); color:var(--txt); }
  header { padding:18px 16px 6px; }
  h1 { font-size:24px; margin:0 0 6px; }
  h2 { font-size:16px; margin:0 0 10px; }
  .mut { color:var(--mut); font-size:14px; }
  a { color:var(--bar); }
  .card { background:var(--card); border-radius:16px; padding:16px; margin:12px 16px; }
  .big { font-size:26px; font-weight:700; }
  .pct { font-size:42px; font-weight:800; }
  .bar { height:18px; background:#0e1620; border-radius:99px; overflow:hidden; margin:12px 0 8px; }
  .bar > span { display:block; height:100%; background:linear-gradient(90deg,#3d9cf0,#5ee0a0); width:0%; transition:width .4s; }
  .row { display:flex; justify-content:space-between; gap:8px; margin:8px 0; font-size:15px; }
  .ok { color:var(--acc); } .run { color:var(--warn); } .wait { color:var(--mut); } .bad { color:var(--bad); }
  .brand { display:flex; flex-direction:column; gap:4px; padding:10px 0; border-bottom:1px solid #223044; }
  .brand:last-child { border-bottom:0; }
  .brand .top { display:flex; justify-content:space-between; gap:8px; align-items:baseline; }
  .mini { height:8px; background:#0e1620; border-radius:99px; overflow:hidden; }
  .mini > span { display:block; height:100%; background:#3d9cf0; }
  .mini.done > span { background:#5ee0a0; }
  .nav { display:flex; flex-wrap:wrap; gap:10px; margin-top:10px; }
  .nav a { background:#121a24; padding:8px 12px; border-radius:10px; text-decoration:none; }
</style>
</head>
<body>
<header>
  <h1>تحميل هواوي الآن</h1>
  <div class="mut" id="tick">يتحدث كل ثانيتين</div>
  <div class="nav">
    <a href="#" id="drive">رفع درايف</a>
    <a href="#" id="search">البحث في الملفات</a>
    <a href="#" id="prog">سجل التحميل</a>
    <a href="#" id="ready">تنزيل الأرشيف</a>
  </div>
</header>
<div class="card">
  <h2>هواوي من سيرفر CircuitBit</h2>
  <div id="hwState" class="big run">جاري القراءة...</div>
  <div class="pct" id="hwPct">—</div>
  <div class="bar"><span id="hwFill"></span></div>
  <div class="row"><span>صور الهاردوير</span><span id="hwFiles">—</span></div>
  <div class="row"><span>الموديلات</span><span id="hwModels">—</span></div>
  <div class="row"><span>ملفات PDF</span><span id="hwPdf">—</span></div>
  <div class="row"><span>السرعة (آخر دقيقة)</span><span id="hwRate">—</span></div>
  <div class="row"><span>هوبات WARP</span><span id="hwHops">—</span></div>
  <div class="row"><span>الحجم على القرص</span><span id="hwGb">—</span></div>
  <div class="mut" id="hwNote"></div>
  <ul id="hwRecent" style="margin:10px 0 0;padding-right:18px;color:var(--mut);font-size:13px"></ul>
</div>
<div class="card">
  <h2>رفع إلى جوجل درايف</h2>
  <div id="driveState" class="big run">جاري القراءة...</div>
  <div class="pct" id="drivePct">—</div>
  <div class="bar"><span id="driveFill"></span></div>
  <div class="row"><span>صور الهاردوير</span><span id="hw">—</span></div>
  <div class="row"><span>ملفات PDF</span><span id="pdf">—</span></div>
  <div class="row"><span>الحجم في المجلد Phone X</span><span id="gb">—</span></div>
  <div class="mut" id="driveNote"></div>
</div>
<div class="card">
  <h2>باقي الشركات</h2>
  <div id="dlState" class="big run">جاري القراءة...</div>
  <div class="mut" id="dlNote"></div>
  <div class="bar"><span id="dlFill"></span></div>
  <div class="row"><span>الشركات المكتملة</span><span id="dlCount">—</span></div>
  <div id="brands"></div>
</div>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
document.getElementById('drive').href = base + '/drive';
document.getElementById('search').href = base + '/search';
document.getElementById('prog').href = base + '/progress';
document.getElementById('ready').href = base + '/ready';
function driveTxt(s){
  if (s === 'done') return ['اكتمل الرفع إلى درايف', 'ok'];
  if (s === 'pdf') return ['جارٍ رفع ملفات PDF', 'run'];
  if (s === 'hardware') return ['جارٍ رفع الملفات إلى درايف', 'run'];
  if (s === 'stopped') return ['توقف الرفع', 'bad'];
  return ['جارٍ الرفع', 'run'];
}
function hwCls(s){
  if (s === 'run' || s === 'pdf') return 'ok';
  if (s === 'wait_hop') return 'run';
  if (s === 'done') return 'ok';
  return 'bad';
}
function brandHtml(b){
  const cls = (b.state === 'done' || b.state === 'run' || b.state === 'pdf') ? 'ok' : (b.state === 'paused' || b.state === 'wait_hop' ? 'run' : 'wait');
  const mini = b.state === 'done' ? 'done' : '';
  return `<div class="brand">
    <div class="top"><b>${b.ar}</b><span class="${cls}">${b.state_ar} · ${b.pct}%</span></div>
    <div class="mini ${mini}"><span style="width:${b.pct}%"></span></div>
    <div class="mut">موديلات ${b.models} من ${b.catalog} · صور ${b.hardware} · PDF ${b.pdf}</div>
  </div>`;
}
async function tick(){
  try {
    const r = await fetch(base + '/api/monitor', {cache:'no-store'});
    const d = await r.json();
    const hw = d.huawei || {};
    const st = document.getElementById('hwState');
    st.textContent = hw.state_ar || d.download_ar || '';
    st.className = 'big ' + hwCls(hw.state);
    document.getElementById('hwPct').textContent = (hw.pct || 0) + '%';
    document.getElementById('hwFill').style.width = (hw.pct || 0) + '%';
    document.getElementById('hwFiles').textContent = (hw.png || 0) + ' من ' + (hw.server || 0) + ' · متبقي ' + (hw.left || 0);
    document.getElementById('hwModels').textContent = (hw.models || 0) + ' من ' + (hw.catalog_models || 0);
    document.getElementById('hwPdf').textContent = String(hw.pdf || 0);
    document.getElementById('hwRate').textContent = (hw.rate_per_min || 0) + ' ملف/دقيقة';
    document.getElementById('hwHops').textContent = String(hw.hops || 0);
    document.getElementById('hwGb').textContent = (hw.gb || 0) + ' جيجا';
    document.getElementById('hwNote').textContent = hw.note || '';
    document.getElementById('hwRecent').innerHTML = (hw.recent || []).map(x => '<li>'+x+'</li>').join('') || '';
    const drv = d.drive || {};
    const [txt, cls] = driveTxt(drv.state);
    const dst = document.getElementById('driveState');
    dst.textContent = txt;
    dst.className = 'big ' + cls;
    document.getElementById('drivePct').textContent = (drv.pct || 0) + '%';
    document.getElementById('driveFill').style.width = (drv.pct || 0) + '%';
    document.getElementById('hw').textContent = (drv.hw_up || 0) + ' من ' + (drv.hw_need || 0);
    document.getElementById('pdf').textContent = (drv.pdf_up || 0) + ' من ' + (drv.pdf_need || 0);
    document.getElementById('gb').textContent = (drv.gb || 0) + ' جيجا';
    document.getElementById('driveNote').textContent = drv.note || '';
    document.getElementById('dlState').textContent = (d.done_brands || 0) + ' شركات مكتملة';
    document.getElementById('dlState').className = 'big ok';
    document.getElementById('dlNote').textContent = 'هواوي هي الجاري تحميلها الآن. سامسونج وإنفينكس وفيفو لن تُرفع إلا بطلبك.';
    document.getElementById('dlFill').style.width = (d.download_pct || 0) + '%';
    document.getElementById('dlCount').textContent = (d.done_brands || 0) + ' من ' + (d.total_brands || 0);
    document.getElementById('brands').innerHTML = (d.brands || []).map(brandHtml).join('');
    document.getElementById('tick').textContent = 'آخر تحديث ' + (d.now || '') + ' · يتحدث كل ثانيتين';
  } catch (e) {
    document.getElementById('hwState').textContent = 'تعذر تحديث الصفحة';
  }
}
tick();
setInterval(tick, 2000);
</script>
</body>
</html>
"""


_drive_size_cache: dict = {"t": 0.0, "hw": 0, "pdf": 0, "bytes": 0}


def _rclone_running() -> bool:
    try:
        import subprocess

        p = subprocess.run(["pgrep", "-a", "rclone"], capture_output=True, text=True, timeout=2)
        return "gdrive_user:" in (p.stdout or "")
    except Exception:
        return False


def _count_disk() -> tuple[int, int]:
    """Current Drive job: Pixel + ASUS hardware (no PDF on server)."""
    n_hw = 0
    for brand in ("GOOGLE PIXEL", "ASUS"):
        hw = LIB / brand / "Hardware"
        if hw.is_symlink():
            try:
                hw = hw.resolve()
            except OSError:
                continue
        if hw.exists():
            n_hw += sum(
                1
                for p in hw.rglob("*")
                if p.is_file() and p.suffix.lower() in {".png", ".jpg"}
            )
    return n_hw, 0


def _parse_drive_log() -> dict:
    copied = 0
    errors = 0
    recent: list[str] = []
    hw_done = pdf_done = False
    text = DRIVE_LOG.read_text(encoding="utf-8", errors="replace") if DRIVE_LOG.exists() else ""
    for line in text.splitlines():
        if "Copied (new)" in line or "Copied (replaced)" in line:
            copied += 1
            name = line.split("INFO  :", 1)[-1].split(":", 1)[0].strip()
            if name:
                recent.append(name)
        if " ERROR " in line or "Failed to copy" in line:
            errors += 1
        if "PIXEL_EXIT=" in line:
            hw_done = line.split("PIXEL_EXIT=", 1)[-1].split()[0] == "0" or hw_done
        if "ASUS_EXIT=" in line:
            pdf_done = line.split("ASUS_EXIT=", 1)[-1].split()[0] == "0" or pdf_done
        if "HARDWARE_EXIT=" in line:
            hw_done = line.split("HARDWARE_EXIT=", 1)[-1].split()[0] == "0"
        if "PDF_EXIT=" in line:
            pdf_done = line.split("PDF_EXIT=", 1)[-1].split()[0] == "0"
    return {
        "copied": copied,
        "errors": errors,
        "recent": recent[-8:][::-1],
        "hw_done": hw_done,
        "pdf_done": pdf_done,
        "has_pdf_phase": (
            "gdrive_user:ASUS" in text
            or "ASUS_EXIT=" in text
            or "gdrive_user:PDF" in text
            or "PDF_EXIT=" in text
        ),
    }


def drive_payload() -> dict:
    hw_need, pdf_need = _count_disk()
    parsed = _parse_drive_log()
    running = _rclone_running()
    now = time.time()
    if now - float(_drive_size_cache["t"]) > 12:
        try:
            import subprocess

            def _sz(sub: str) -> tuple[int, int]:
                p = subprocess.run(
                    ["rclone", "size", f"gdrive_user:{sub}", "--json"],
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if p.returncode != 0 or not (p.stdout or "").strip():
                    return 0, 0
                d = json.loads(p.stdout)
                return int(d.get("count") or 0), int(d.get("bytes") or 0)

            hw_n, hw_b = _sz("GOOGLE PIXEL/Hardware")
            as_n, as_b = _sz("ASUS/Hardware")
            ip_n, ip_b = _sz("Hardware")
            ipp_n, ipp_b = _sz("PDF")
            _drive_size_cache.update(
                t=now,
                hw=hw_n + as_n,
                pdf=0,
                bytes=hw_b + as_b + ip_b + ipp_b,
            )
        except Exception:
            pass
    hw_up = int(_drive_size_cache.get("hw") or 0)
    pdf_up = int(_drive_size_cache.get("pdf") or 0)
    total_need = max(1, hw_need + pdf_need)
    total_up = min(total_need, hw_up + pdf_up)
    pct = round(100.0 * total_up / total_need)
    if parsed["pdf_done"] and parsed["hw_done"]:
        state = "done"
        note = "افتح درايف → Phone X · مجلدات GOOGLE PIXEL و ASUS (الآيفون موجود مسبقاً)"
    elif running and parsed["has_pdf_phase"]:
        state = "pdf"
        note = "جوجل بكسل اكتمل تقريباً — بدأ رفع أسوس"
    elif running:
        state = "hardware"
        note = "رفع جوجل بكسل ثم أسوس إلى Phone X"
    elif parsed["copied"] and not running:
        state = "stopped"
        note = "توقف الرفع — سيتم استئنافه إن لم يكتمل"
    else:
        state = "hardware"
        note = "جاري تجهيز رفع جوجل بكسل وأسوس"
    if parsed["errors"]:
        note += f" · عدد الأخطاء: {parsed['errors']}"
    return {
        "state": state,
        "pct": pct,
        "hw_up": hw_up,
        "hw_need": hw_need,
        "pdf_up": pdf_up,
        "pdf_need": pdf_need,
        "gb": round(int(_drive_size_cache.get("bytes") or 0) / 1e9, 2),
        "copied_log": parsed["copied"],
        "errors": parsed["errors"],
        "running": running,
        "recent": parsed["recent"],
        "note": note,
        "now": time.strftime("%H:%M:%S UTC", time.gmtime()),
    }


BRAND_AR = {
    "SAMSUNG": "سامسونج",
    "INFINIX": "إنفينكس",
    "VIVO": "فيفو",
    "ASUS": "أسوس",
    "GOOGLE PIXEL": "جوجل بكسل",
    "IPHONE": "آيفون + آيباد",
    "HUAWEI": "هواوي",
    "ITEL": "آيتل",
    "JIO": "جيو",
    "LAVA": "لافا",
    "LENOVO": "لينوفو",
    "MICROMAX": "مايكرومكس",
    "MOTOROLA": "موتورولا",
    "NOKIA": "نوكيا",
    "NOTING PHONE": "نوثينج فون",
    "ONEPLUS": "ون بلس",
    "OPPO": "أوبو",
    "REALME": "ريلمي",
    "SONY": "سوني",
    "TECNO": "تكنو",
    "XIAOMI": "شاومي",
    "ZTE": "زد تي إي",
}
DONE_BRANDS = {"SAMSUNG", "INFINIX", "VIVO", "ASUS", "GOOGLE PIXEL", "IPHONE"}
HUAWEI_SERVER_HW = 2635
HUAWEI_SERVER_MODELS = 140

_hw_live_cache: dict = {"t": 0.0}


def _tail_lines(path: Path, n: int) -> list[str]:
    if not path.exists():
        return []
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()[-n:]
    except OSError:
        return []


def _proc_running(needles: tuple[str, ...]) -> bool:
    try:
        import subprocess

        p = subprocess.run(["ps", "-eo", "args="], capture_output=True, text=True, timeout=2)
        text = p.stdout or ""
    except Exception:
        return False
    return any(n in text for n in needles)


def _hop_urls() -> list[str]:
    if not HOP_LIVE.exists():
        return []
    try:
        return [ln.strip() for ln in HOP_LIVE.read_text().splitlines() if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def huawei_payload() -> dict:
    now = time.time()
    if now - float(_hw_live_cache.get("t") or 0) < 1.5 and _hw_live_cache.get("png") is not None:
        d = dict(_hw_live_cache)
        d.pop("t", None)
        return d
    hw = LIB / "HUAWEI" / "Hardware"
    pdf = LIB / "HUAWEI" / "PDF"
    pngs = list(hw.rglob("*.png")) if hw.exists() else []
    pdfs = list(pdf.rglob("*.pdf")) if pdf.exists() else []
    models = {p.parent.name for p in pngs}
    nbytes = 0
    recent60 = 0
    for p in pngs:
        try:
            st = p.stat()
        except OSError:
            continue
        nbytes += st.st_size
        if now - st.st_mtime < 60:
            recent60 += 1
    for p in pdfs:
        try:
            nbytes += p.stat().st_size
        except OSError:
            pass
    server = HUAWEI_SERVER_HW
    pending = None
    try:
        stj = json.loads(HUAWEI_STATE.read_text()) if HUAWEI_STATE.exists() else {}
        server = int(stj.get("server") or server)
        if stj.get("pending") is not None:
            pending = int(stj["pending"])
    except Exception:
        pass
    png_n = len(pngs)
    left = max(0, server - png_n)
    pct = round(100.0 * png_n / server, 1) if server else 0
    hops = _hop_urls()
    fill_on = _proc_running(("python3 -u /tmp/huawei_fill.py",))
    farm_on = _proc_running(("farm_warp_hops.py",))
    log_lines = [ln for ln in _tail_lines(HUAWEI_LOG, 12) if ln.strip()]
    recent = []
    for ln in reversed(log_lines):
        if "ORIGINAL" in ln and " -> " in ln:
            recent.append(ln.split(" -> ", 1)[-1].strip())
        if len(recent) >= 6:
            break
    waiting = any("waiting for live WARP hop" in ln for ln in log_lines[-8:])
    if fill_on and png_n >= server and left == 0:
        state, state_ar = "pdf", "جارٍ تحميل PDF"
    elif fill_on and waiting and not hops:
        state, state_ar = "wait_hop", "بانتظار هوب WARP"
    elif fill_on and hops:
        state, state_ar = "run", "التحميل يعمل الآن"
    elif fill_on:
        state, state_ar = "run", "التحميل يعمل الآن"
    elif png_n >= server:
        state, state_ar = "done", "اكتمل التحميل من السيرفر"
    else:
        state, state_ar = "paused", "التحميل متوقف"
    note = (
        f"من السيرفر {server} صورة / {HUAWEI_SERVER_MODELS} موديل. "
        f"متبقي {left} صورة. "
        + ("المزرعة شغالة. " if farm_on else "المزرعة متوقفة. ")
        + ("الهوبات: " + str(len(hops)) + ". " )
        + "الأسماء بالإنجليزي مع عربي بين قوسين."
    )
    payload = {
        "brand": "HUAWEI",
        "ar": "هواوي",
        "state": state,
        "state_ar": state_ar,
        "pct": pct,
        "png": png_n,
        "server": server,
        "left": left,
        "models": len(models),
        "catalog_models": HUAWEI_SERVER_MODELS,
        "pdf": len(pdfs),
        "gb": round(nbytes / 1e9, 2),
        "rate_per_min": recent60,
        "hops": len(hops),
        "fill_running": fill_on,
        "farm_running": farm_on,
        "waiting_hop": waiting and not hops,
        "pending_wave": pending,
        "recent": recent,
        "log": log_lines[-8:],
        "note": note,
        "now": time.strftime("%H:%M:%S UTC", time.gmtime()),
    }
    _hw_live_cache.clear()
    _hw_live_cache.update(payload)
    _hw_live_cache["t"] = now
    return payload


def _catalog_models() -> dict[str, int]:
    if not SUPPORTED.exists():
        return {}
    try:
        data = json.loads(SUPPORTED.read_text())
        out: dict[str, int] = {}
        for m in data.get("models") or []:
            b = str(m.get("brand") or "").upper()
            out[b] = out.get(b, 0) + 1
        return out
    except Exception:
        return {}


def progress_payload(n_log: int = 50) -> dict:
    n_log = max(10, min(int(n_log or 50), 200))
    status = STATUS.read_text(encoding="utf-8", errors="replace") if STATUS.exists() else ""
    lines: list[str] = []
    if HUAWEI_LOG.exists():
        raw = HUAWEI_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = raw[-n_log:]
    elif LOG.exists():
        raw = LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        lines = raw[-n_log:]
    cat = _catalog_models()
    brands = []
    for brand, root in roots():
        hw = root / "Hardware"
        pdf = root / "PDF"
        if hw.is_symlink():
            hw = hw.resolve()
        if pdf.is_symlink():
            pdf = pdf.resolve()
        png = list(hw.rglob("*.png")) if hw.exists() else []
        pdfs = list(pdf.rglob("*.pdf")) if pdf.exists() else []
        models = {p.parent.name for p in png}
        brands.append(
            {
                "brand": brand,
                "hardware": len(png),
                "models": len(models),
                "catalog": cat.get(brand, 0),
                "pdf": len(pdfs),
            }
        )
    return {
        "now": time.strftime("%H:%M:%S UTC", time.gmtime()),
        "status": status.strip(),
        "log": lines,
        "brands": brands,
    }


def monitor_payload() -> dict:
    hw = huawei_payload()
    try:
        drive = drive_payload()
    except Exception:
        drive = {}
    cat = _catalog_models()
    by: dict[str, dict] = {}
    with INDEX_LOCK:
        for row in INDEX:
            g = by.get(row["brand"])
            if g is None:
                g = {"hardware": 0, "pdf": 0, "models": set()}
                by[row["brand"]] = g
            if row["kind"] in ("hardware", "pdf"):
                g[row["kind"]] += 1
            g["models"].add(row["model"])
    brands = []
    for brand, ncat in sorted(cat.items(), key=lambda kv: BRAND_AR.get(kv[0], kv[0])):
        b = by.get(brand) or {"hardware": 0, "models": set(), "pdf": 0}
        ms = b.get("models") or set()
        models = len(ms) if not isinstance(ms, int) else int(ms)
        hardware = int(b.get("hardware") or 0)
        pdf = int(b.get("pdf") or 0)
        pct = round(100.0 * models / ncat) if ncat else 0
        if brand == "HUAWEI":
            state, state_ar, pct = hw["state"], hw["state_ar"], hw["pct"]
            models = hw["models"]
            hardware = hw["png"]
            pdf = hw["pdf"]
            ncat = hw["catalog_models"]
        elif brand in DONE_BRANDS or (ncat and models >= ncat):
            state, state_ar, pct = "done", "مكتمل", 100 if models else pct
        elif hardware > 0:
            state, state_ar = "paused", "متوقف"
        else:
            state, state_ar, pct = "waiting", "لم يبدأ", 0
        brands.append(
            {
                "brand": brand,
                "ar": BRAND_AR.get(brand, brand),
                "models": models,
                "catalog": ncat,
                "hardware": hardware,
                "pdf": pdf,
                "state": state,
                "state_ar": state_ar,
                "pct": pct,
            }
        )
    order = {"run": 0, "wait_hop": 0, "pdf": 0, "paused": 1, "done": 2, "waiting": 3}
    brands.sort(key=lambda x: (order.get(x["state"], 9), x["ar"]))
    total_n = len(brands) or 1
    done_n = sum(1 for b in brands if b["state"] == "done")
    running = hw.get("fill_running")
    return {
        "now": time.strftime("%H:%M:%S UTC", time.gmtime()),
        "drive": drive,
        "huawei": hw,
        "brands": brands,
        "done_brands": done_n,
        "total_brands": total_n,
        "download_pct": hw.get("pct") or 0,
        "download_paused": not running,
        "download_ar": hw.get("state_ar") or "",
        "download_note": hw.get("note") or "",
    }


READY_FILES = {
    "IPHONE.tar": "آيفون — مجلد لكل هاتف (صور + PDF)",
    "SAMSUNG.tar": "سامسونج — مجلد لكل هاتف (صور + PDF)",
}


def ready_payload() -> dict:
    files = []
    for name, note in READY_FILES.items():
        p = READY / name
        part = READY / (name + ".part")
        if p.is_file() and p.stat().st_size > 1_000_000:
            files.append(
                {
                    "name": name,
                    "ready": True,
                    "gb": round(p.stat().st_size / 1e9, 2),
                    "note": note,
                }
            )
        elif part.is_file():
            files.append(
                {
                    "name": name,
                    "ready": False,
                    "gb": round(part.stat().st_size / 1e9, 2),
                    "note": f"جارٍ الضغط {round(part.stat().st_size / 1e9, 2)} GB — {note}",
                }
            )
        else:
            files.append({"name": name, "ready": False, "gb": 0, "note": "لم يبدأ الأرشيف بعد — " + note})
    return {"files": files}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args) -> None:
        print(f"{self.address_string()} {fmt % args}", flush=True)

    def _prefix(self) -> str:
        return f"/{TOKEN}"

    def _ok(self, body: bytes, ctype: str = "text/html; charset=utf-8", extra: dict | None = None) -> None:
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if extra:
            for k, v in extra.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _err(self, code: int, msg: str) -> None:
        b = msg.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def _send_ready_tar(self, name: str) -> None:
        if name not in READY_FILES:
            return self._err(404, "not found")
        path = READY / name
        if not path.is_file() or path.stat().st_size < 1_000_000:
            return self._err(404, "archive not ready yet")
        size = path.stat().st_size
        start, end = 0, size - 1
        rng = self.headers.get("Range") or ""
        code = 200
        if rng.startswith("bytes="):
            spec = rng.split("=", 1)[1].split(",")[0].strip()
            a, _, b = spec.partition("-")
            try:
                if a:
                    start = int(a)
                if b:
                    end = int(b)
            except ValueError:
                start, end = 0, size - 1
            if start < 0 or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            end = min(end, size - 1)
            code = 206
        length = end - start + 1
        self.send_response(code)
        self.send_header("Content-Type", "application/x-tar")
        self.send_header("Content-Length", str(length))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Disposition", f'attachment; filename="{name}"')
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(start)
            left = length
            while left > 0:
                chunk = f.read(min(1024 * 1024, left))
                if not chunk:
                    break
                self.wfile.write(chunk)
                left -= len(chunk)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        prefix = self._prefix()
        if path in ("/", prefix, prefix + "/", prefix + "/monitor", prefix + "/monitor/"):
            return self._ok(MONITOR_HTML.encode())
        if path in (prefix + "/search", prefix + "/search/"):
            return self._ok(HTML.encode())
        if path in (prefix + "/progress", prefix + "/progress/"):
            return self._ok(PROGRESS_HTML.encode())
        if path in (prefix + "/drive", prefix + "/drive/"):
            return self._ok(DRIVE_HTML.encode())
        if path in (prefix + "/ready", prefix + "/ready/"):
            return self._ok(READY_HTML.encode())
        if not path.startswith(prefix + "/") and path != prefix:
            return self._err(404, "not found")
        rest = path[len(prefix) :] or "/"

        if rest.startswith("/api/ready"):
            payload = json.dumps(ready_payload(), ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/api/drive"):
            payload = json.dumps(drive_payload(), ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/api/monitor"):
            payload = json.dumps(monitor_payload(), ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/ready/"):
            return self._send_ready_tar(rest.split("/ready/", 1)[1])

        if rest.startswith("/api/progress"):
            n = parse_qs(parsed.query).get("n", ["50"])[0]
            try:
                n_log = int(n)
            except ValueError:
                n_log = 50
            payload = json.dumps(progress_payload(n_log), ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/api/log"):
            n = parse_qs(parsed.query).get("n", ["80"])[0]
            try:
                n_log = max(10, min(int(n), 200))
            except ValueError:
                n_log = 80
            text = ""
            if LOG.exists():
                text = "\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-n_log:])
            return self._ok(text.encode(), "text/plain; charset=utf-8")

        if rest.startswith("/api/search"):
            q = parse_qs(parsed.query).get("q", [""])[0]
            with INDEX_LOCK:
                total = len(INDEX)
            items = search(q)
            if not q:
                # group: return all, client slices
                pass
            payload = json.dumps({"total": total, "count": len(items), "items": items[:400]}, ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/api/stats"):
            with INDEX_LOCK:
                n_pdf = sum(1 for x in INDEX if x["kind"] == "pdf")
                n_hw = sum(1 for x in INDEX if x["kind"] == "hardware")
            payload = json.dumps({"pdf": n_pdf, "hardware": n_hw, "total": n_pdf + n_hw}, ensure_ascii=False).encode()
            return self._ok(payload, "application/json; charset=utf-8")

        if rest.startswith("/open/pdf/") or rest.startswith("/open/hardware/"):
            # rel = BRAND/kind/model/file  (kind duplicated in path prefix)
            kind, rel = rest.split("/", 3)[2], rest.split("/", 3)[3]
            parts = rel.split("/", 2)
            if len(parts) < 3:
                return self._err(404, "file not found")
            brand, _kind_in_rel, inner = parts[0], parts[1], parts[2]
            brand_root = None
            for b, root in roots():
                if b == brand:
                    brand_root = root
                    break
            if brand_root is None:
                return self._err(404, "file not found")
            folder = brand_root / ("PDF" if kind == "pdf" else "Hardware")
            target = safe_under(folder, inner)
            if not target:
                return self._err(404, "file not found")
            ctype = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            data = target.read_bytes()
            disp = "inline"
            return self._ok(data, ctype, {"Content-Disposition": f'{disp}; filename="{target.name}"'})

        return self._err(404, "not found")


def reindex_loop() -> None:
    while True:
        time.sleep(REINDEX_SEC)
        try:
            build_index()
            print(f"reindexed {len(INDEX)} files", flush=True)
        except Exception as e:
            print(f"reindex error {e}", flush=True)


def main() -> None:
    build_index()
    print(f"indexed {len(INDEX)} files", flush=True)
    threading.Thread(target=reindex_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"listening http://127.0.0.1:{PORT}/{TOKEN}/", flush=True)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
