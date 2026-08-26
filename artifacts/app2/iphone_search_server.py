#!/usr/bin/env python3
"""Temporary Arabic search site for CircuitBit originals on this agent."""
from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

LIB = Path("/workspace/artifacts/app2/library")
IPHONE = Path("/workspace/artifacts/app2/iphone_originals")
HOST = "0.0.0.0"
PORT = int(os.environ.get("IPHONE_SITE_PORT", "8765"))
TOKEN = os.environ.get("IPHONE_SITE_TOKEN", "cbiphone")
REINDEX_SEC = 60

INDEX: list[dict] = []
INDEX_LOCK = threading.Lock()


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
  <input id="q" type="search" placeholder="ابحث: samsung a15 / infinix hot 30 / vivo y17 / lcd" autofocus/>
  <div class="meta" id="meta">جاري التحميل...</div>
</header>
<div class="list" id="list"></div>
<script>
const TOKEN = location.pathname.split('/').filter(Boolean)[0] || '';
const base = TOKEN ? '/' + TOKEN : '';
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

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        prefix = self._prefix()
        if path in ("/", prefix, prefix + "/"):
            return self._ok(HTML.encode())
        if not path.startswith(prefix + "/") and path != prefix:
            return self._err(404, "not found")
        rest = path[len(prefix) :] or "/"

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
