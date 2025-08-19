from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import requests, io, datetime, urllib.parse
from bs4 import BeautifulSoup

app = FastAPI(title="DeepsearchAgent – Social + Dating")

# 1) Doğrudan kontrol edilecek sosyal platformlar (public profil URL kontrolü)
DIRECT_PLATFORMS = [
    ("Twitter/X",   "https://twitter.com/{u}"),
    ("Instagram",   "https://www.instagram.com/{u}/"),
    ("TikTok",      "https://www.tiktok.com/@{u}"),
    ("YouTube",     "https://www.youtube.com/@{u}"),
    ("Reddit",      "https://www.reddit.com/user/{u}/"),
    ("GitHub",      "https://github.com/{u}"),
    ("Pinterest",   "https://www.pinterest.com/{u}/"),
    ("Facebook",    "https://www.facebook.com/{u}"),
    ("Medium",      "https://medium.com/@{u}"),
    ("Twitch",      "https://www.twitch.tv/{u}"),
    ("Telegram",    "https://t.me/{u}"),
]

# 2) Arkadaşlık / sohbet (DE ağırlıklı) – çoğu login duvarlı; o yüzden "site:" ile kanıt linkleri
DATING_DOMAINS = [
    "tinder.com","bumble.com","badoo.com","lovoo.com","finya.de","parship.de","edarling.de",
    "elitepartner.de","neu.de","single.de","knuddels.de","spin.de","jaumo.com","okcupid.com",
    "plentyoffish.com","hinge.co","once.app","lablue.de","happn.com","lovescout24.de"
]

UA = {"User-Agent": "Mozilla/5.0 (compatible; DeepsearchAgent/1.2)"}
NOTFOUND_MARKERS = ["not found", "page not found", "sorry, this page isn't available"]

# ---------- Yardımcılar ----------

def http_exists(url: str):
    """HEAD→GET ile URL’i yokla; login duvarına takılsa da 200/3xx + notfound metni yoksa FOUND say."""
    try:
        r = requests.head(url, allow_redirects=True, timeout=10, headers=UA)
        if r.status_code >= 400 or r.status_code == 405:
            r = requests.get(url, allow_redirects=True, timeout=12, headers=UA)
        text = (r.text or "").lower()
        exists = (200 <= r.status_code < 400) and not any(m in text for m in NOTFOUND_MARKERS)
        status = "FOUND" if exists else ("MAYBE" if r.status_code in (301,302) else "NOT FOUND")
        return status, r.status_code, url
    except Exception as e:
        return "ERROR", 0, f"{url} (error: {e})"

def ddg_decode(href: str) -> str:
    """DuckDuckGo redirect linkindeki gerçek URL’i ayıkla (/l/?uddg=...)."""
    if href.startswith("http"):
        return href
    # /l/?kh=-1&uddg=<encoded>
    try:
        parsed = urllib.parse.urlparse(href)
        qs = urllib.parse.parse_qs(parsed.query)
        if "uddg" in qs:
            return urllib.parse.unquote(qs["uddg"][0])
    except Exception:
        pass
    return href

def site_search(domain: str, username: str, limit: int = 5):
    """DuckDuckGo HTML sonuçlarından domain+username içeren public linkleri çek."""
    q = f'site:{domain} "{username}"'
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.post(url, data={"q": q}, headers=UA, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.select("a.result__a"):
            href = a.get("href")
            if not href:
                continue
            real = ddg_decode(href)
            if domain in real:
                links.append(real)
            if len(links) >= limit:
                break
        return links
    except Exception:
        return []

def render_html(username: str, rows_direct: list, rows_dating: list):
    css = """
    <style>
    body{font-family:system-ui,Arial;margin:24px;max-width:980px}
    h2{margin-bottom:8px}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{padding:8px;border-bottom:1px solid #eee;text-align:left;vertical-align:top}
    .tag{padding:2px 8px;border-radius:12px;font-size:12px}
    .ok{background:#e6ffed} .maybe{background:#fffbe6} .no{background:#ffeaea}
    button{padding:10px 14px;border:none;border-radius:8px;background:#111;color:#fff;cursor:pointer}
    input{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px}
    .card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0}
    </style>
    """
    tag = lambda s: f"<span class='tag {'ok' if s=='FOUND' else ('maybe' if s=='MAYBE' else 'no')}'>{s}</span>"
    html = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>{css}<title>Results - {username}</title></head><body>"]
    html += [f"<h2>Results for <code>{username}</code></h2>"]

    # Social table
    html += ["<div class='card'><h3>Social profiles</h3><table><tr><th>Platform</th><th>Status</th><th>HTTP</th><th>Link</th></tr>"]
    for name, status, code, url in rows_direct:
        html += [f"<tr><td>{name}</td><td>{tag(status)}</td><td>{code}</td><td><a target='_blank' href='{url}'>{url}</a></td></tr>"]
    html += ["</table></div>"]

    # Dating table
    html += ["<div class='card'><h3>Dating & chat (site: search)</h3><table><tr><th>Domain</th><th>Evidence links</th></tr>"]
    for domain, links in rows_dating:
        if links:
            links_html = "<br/>".join([f"<a target='_blank' href='{l}'>{l}</a>" for l in links])
        else:
            links_html = "<span style='color:#777'>No public hits</span>"
        html += [f"<tr><td>{domain}</td><td>{links_html}</td></tr>"]
    html += ["</table></div>"]

    # Export button + back
    html += [f"""
    <form method="post" action="/export">
      <input type="hidden" name="username" value="{username}">
      <button type="submit">Download PDF</button>
    </form>
    <p><a href="/">← New search</a></p>
    </body></html>"""]
    return "".join(html)

# ---------- Endpoints ----------

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>DeepsearchAgent – Username Search</title>
<style>
body{font-family:system-ui,Arial;margin:24px;max-width:680px}
input{width:100%;padding:12px;border:1px solid #ccc;border-radius:8px}
button{padding:10px 14px;border:none;border-radius:8px;background:#111;color:#fff;cursor:pointer}
.card{border:1px solid #ddd;border-radius:12px;padding:16px;margin:12px 0}
.small{color:#666;font-size:12px}
</style></head>
<body>
  <h2>DeepsearchAgent – Username Search</h2>
  <div class="card">
    <form method="post" action="/search">
      <label>Enter username</label><br/>
      <input name="username" placeholder="e.g. samet_28_55" required />
      <p class="small">Public OSINT only. No logins, no bypass.</p>
      <button type="submit">Search</button>
    </form>
  </div>
</body></html>"""

@app.post("/search", response_class=HTMLResponse)
def search(username: str = Form(...)):
    u = username.strip()

    # Social: doğrudan kontrol
    rows_direct = []
    for name, tpl in DIRECT_PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = http_exists(url)
        rows_direct.append((name, status, code, final_url))

    # Dating: site: araması (Tinder dahil)
    rows_dating = []
    for domain in DATING_DOMAINS:
        links = site_search(domain, u, limit=5)
        rows_dating.append((domain, links))

    return render_html(u, rows_direct, rows_dating)

@app.post("/export")
def export_pdf(username: str = Form(...)):
    u = username.strip()

    # Aramaları yeniden çalıştır (stateless PDF)
    rows_direct = []
    for name, tpl in DIRECT_PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = http_exists(url)
        rows_direct.append((name, status, code, final_url))

    rows_dating = []
    for domain in DATING_DOMAINS:
        links = site_search(domain, u, limit=5)
        rows_dating.append((domain, links))

    # PDF üret
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 2*cm
    c.setTitle(f"DeepsearchAgent Report - {u}")

    c.setFont("Helvetica-Bold", 16); c.drawString(2*cm, y, f"DeepsearchAgent Report – {u}"); y -= 0.9*cm
    c.setFont("Helvetica", 10); c.drawString(2*cm, y, f"Generated: {datetime.datetime.utcnow().isoformat()}Z"); y -= 0.7*cm

    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Social profiles"); y -= 0.5*cm
    c.setFont("Helvetica", 10)
    for name, status, code, url in rows_direct:
        line = f"{name:12} | {status:9} | {code:3} | {url}"
        for chunk in [line[i:i+95] for i in range(0, len(line), 95)]:
            if y < 2*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, chunk); y -= 0.45*cm

    if y < 3*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Dating & chat (site: search)"); y -= 0.5*cm
    c.setFont("Helvetica", 10)
    for domain, links in rows_dating:
        base = f"{domain}: "
        line = base + ("; ".join(links) if links else "no public hits")
        for chunk in [line[i:i+95] for i in range(0, len(line), 95)]:
            if y < 2*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, chunk); y -= 0.45*cm

    c.showPage(); c.save(); buf.seek(0)
    fname = f"{u}_report.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
