from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import requests, io, datetime, re
from bs4 import BeautifulSoup

app = FastAPI(title="DeepsearchAgent")

# 1) Doğrudan profil URL kontrolü (sosyal ağlar - kamuya açık)
DIRECT_PLATFORMS = [
    ("Twitter/X", "https://twitter.com/{u}"),
    ("Instagram", "https://www.instagram.com/{u}/"),
    ("TikTok", "https://www.tiktok.com/@{u}"),
    ("YouTube", "https://www.youtube.com/@{u}"),
    ("Reddit", "https://www.reddit.com/user/{u}/"),
    ("GitHub", "https://github.com/{u}"),
    ("Pinterest", "https://www.pinterest.com/{u}/"),
    ("Facebook", "https://www.facebook.com/{u}"),
    ("SoundCloud", "https://soundcloud.com/{u}"),
    ("Twitch", "https://www.twitch.tv/{u}"),
    ("Telegram", "https://t.me/{u}"),
    ("Vimeo", "https://vimeo.com/{u}"),
]

# 2) Almanya odaklı arkadaşlık/sohbet/dating alanları (çoğu login wall, o yüzden "site:" araması)
DATING_DOMAINS_DE = [
    "parship.de","edarling.de","elitepartner.de","finya.de","lovoo.com",
    "badoo.com","neu.de","single.de","spontacts.com","knuddels.de","spin.de",
    "jaumo.com","okcupid.com","plentyoffish.com","hinge.co","once.app",
    "joingirl.de","lablue.de"
]

UA = {"User-Agent": "Mozilla/5.0 (compatible; DeepsearchAgent/1.1)"}
NOTFOUND_MARKERS = ["not found", "page not found", "sorry, this page isn't available"]

def http_exists(url: str):
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

# API’siz “site:” araması → DuckDuckGo HTML (hafif ve pratik)
def site_search(domain: str, username: str, limit: int = 5):
    q = f'site:{domain} "{username}"'
    url = "https://duckduckgo.com/html/"
    try:
        r = requests.post(url, data={"q": q}, headers=UA, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        links = []
        for a in soup.select("a.result__a")[:limit]:
            href = a.get("href")
            if href and domain in href:
                links.append(href)
        return links
    except Exception:
        return []

def render_table(username: str, rows_direct: list, rows_dating: list):
    css = """
    <style>
    body{font-family:system-ui,Arial;margin:24px;max-width:900px}
    table{width:100%;border-collapse:collapse;margin-top:12px}
    th,td{padding:8px;border-bottom:1px solid #eee;text-align:left}
    .tag{padding:2px 8px;border-radius:12px;font-size:12px}
    .ok{background:#e6ffed} .maybe{background:#fffbe6} .no{background:#ffeaea}
    button{padding:10px 14px;border:none;border-radius:8px;background:#111;color:#fff}
    </style>
    """
    tag = lambda s: f"<span class='tag {'ok' if s=='FOUND' else ('maybe' if s=='MAYBE' else 'no')}'>{s}</span>"
    html = [f"<!doctype html><html><head><meta charset='utf-8'><title>Results - {username}</title>{css}</head><body>"]
    html += [f"<h2>Results for <code>{username}</code></h2>"]

    html += ["<h3>Social profiles</h3><table><tr><th>Platform</th><th>Status</th><th>HTTP</th><th>Link</th></tr>"]
    for name, status, code, url in rows_direct:
        html += [f"<tr><td>{name}</td><td>{tag(status)}</td><td>{code}</td><td><a target='_blank' href='{url}'>{url}</a></td></tr>"]
    html += ["</table>"]

    html += ["<h3>Dating & chat sites (site: search)</h3><table><tr><th>Domain</th><th>Evidence links</th></tr>"]
    for domain, links in rows_dating:
        if links:
            lis = "<br/>".join([f"<a target='_blank' href='{l}'>{l}</a>" for l in links])
        else:
            lis = "<span style='color:#777'>No public hits</span>"
        html += [f"<tr><td>{domain}</td><td>{lis}</td></tr>"]
    html += ["</table>"]

    html += [f"""
    <form method="post" action="/export">
      <input type="hidden" name="username" value="{username}">
      <button type="submit">Download PDF</button>
    </form>
    <p><a href="/">← New search</a></p>
    </body></html>"""]
    return "".join(html)

@app.get("/", response_class=HTMLResponse)
def home():
    return """<!doctype html><html><body style="font-family:Arial;max-width:680px;margin:24px auto">
    <h2>DeepsearchAgent – Username Search</h2>
    <form method="post" action="/search">
      <label>Enter username</label><br/>
      <input name="username" required style="width:100%;padding:12px;border:1px solid #ccc;border-radius:8px"/>
      <p style="color:#666;font-size:12px">Public OSINT only. We don't log in or bypass restrictions.</p>
      <button style="padding:10px 14px;border:none;border-radius:8px;background:#111;color:#fff">Search</button>
    </form></body></html>"""

@app.post("/search", response_class=HTMLResponse)
def search(username: str = Form(...)):
    u = username.strip()

    # 1) Doğrudan kontrol edilen sosyal ağlar
    direct_rows = []
    for name, tpl in DIRECT_PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = http_exists(url)
        direct_rows.append((name, status, code, final_url))

    # 2) Dating alanları için "site:" aramaları (kanıt linkleri)
    dating_rows = []
    for domain in DATING_DOMAINS_DE:
        links = site_search(domain, u, limit=5)
        dating_rows.append((domain, links))

    return render_table(u, direct_rows, dating_rows)

@app.post("/export")
def export_pdf(username: str = Form(...)):
    # Yukarıdaki aramaları tekrar çalıştırıp PDF’e dök
    u = username.strip()

    direct_rows = []
    for name, tpl in DIRECT_PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = http_exists(url)
        direct_rows.append((name, status, code, final_url))

    dating_rows = []
    for domain in DATING_DOMAINS_DE:
        links = site_search(domain, u, limit=5)
        dating_rows.append((domain, links))

    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w,h = A4; y = h - 2*cm
    c.setTitle(f"DeepsearchAgent Report - {u}")

    c.setFont("Helvetica-Bold", 16); c.drawString(2*cm, y, f"DeepsearchAgent Report – {u}"); y -= 0.9*cm
    c.setFont("Helvetica", 10); c.drawString(2*cm, y, f"Generated: {datetime.datetime.utcnow().isoformat()}Z"); y -= 0.7*cm

    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Social profiles"); y -= 0.5*cm
    c.setFont("Helvetica", 10)
    for name, status, code, url in direct_rows:
        line = f"{name:12} | {status:9} | {code:3} | {url}"
        for chunk in [line[i:i+95] for i in range(0, len(line), 95)]:
            if y < 2*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, chunk); y -= 0.45*cm

    if y < 3*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Dating & chat (site: search)"); y -= 0.5*cm
    c.setFont("Helvetica", 10)
    for domain, links in dating_rows:
        base = f"{domain}: "
        if not links: base += "no public hits"
        for i, link in enumerate(links or [""]):
            text = base + (link if link else "")
            for chunk in [text[i:i+95] for i in range(0, len(text), 95)]:
                if y < 2*cm: c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
                c.drawString(2*cm, y, chunk); y -= 0.45*cm
            base = " " * (len(domain) + 2)  # sonraki satırlar hizalı

    c.showPage(); c.save(); buf.seek(0)
    fname = f"{u}_report.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
