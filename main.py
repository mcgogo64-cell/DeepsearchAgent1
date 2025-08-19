from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, StreamingResponse
import requests, io, datetime

app = FastAPI(title="DeepsearchAgent")

# Aranacak platformlar (API gerektirmez – direkt profil URL kontrolü)
PLATFORMS = [
    ("Twitter/X", "https://twitter.com/{u}"),
    ("Instagram", "https://www.instagram.com/{u}/"),
    ("TikTok", "https://www.tiktok.com/@{u}"),
    ("YouTube", "https://www.youtube.com/@{u}"),
    ("Reddit", "https://www.reddit.com/user/{u}/"),
    ("GitHub", "https://github.com/{u}"),
    ("Pinterest", "https://www.pinterest.com/{u}/"),
    ("Facebook", "https://www.facebook.com/{u}"),
    ("Medium", "https://medium.com/@{u}"),
    ("SoundCloud", "https://soundcloud.com/{u}"),
    ("Twitch", "https://www.twitch.tv/{u}"),
    ("Telegram", "https://t.me/{u}"),
    ("Steam", "https://steamcommunity.com/id/{u}"),
    ("Vimeo", "https://vimeo.com/{u}"),
    ("DeviantArt", "https://www.deviantart.com/{u}"),
]

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; DeepsearchAgent/1.0)"}

def check_url(url: str):
    """URL var mı? HEAD→GET fallback, not-found metinlerini filtrele."""
    notfound = ["not found", "page not found", "sorry, this page isn't available"]
    try:
        r = requests.head(url, allow_redirects=True, timeout=10, headers=HEADERS)
        if r.status_code >= 400 or r.status_code == 405:
            r = requests.get(url, allow_redirects=True, timeout=12, headers=HEADERS)
        text = (r.text or "").lower()
        exists = (200 <= r.status_code < 400) and not any(m in text for m in notfound)
        status = "FOUND" if exists else ("MAYBE" if r.status_code in (301, 302) else "NOT FOUND")
        return status, r.status_code, url
    except Exception as e:
        return "ERROR", 0, f"{url} (error: {e})"

def render_results(username: str, rows: list):
    # HTML tablo + PDF indirme butonu
    badge = {"FOUND":"ok","MAYBE":"maybe","NOT FOUND":"no","ERROR":"no"}
    html = [f"""<!doctype html><html><head><meta charset=utf-8>
<style>
body{{font-family:system-ui,Arial;margin:24px;max-width:880px}}
table{{width:100%;border-collapse:collapse;margin-top:12px}}
th,td{{padding:8px;border-bottom:1px solid #eee;text-align:left}}
.tag{{padding:2px 8px;border-radius:12px;font-size:12px}}
.ok{{background:#e6ffed}} .maybe{{background:#fffbe6}} .no{{background:#ffeaea}}
button{{padding:10px 14px;border:none;border-radius:8px;background:#111;color:#fff}}
a{{text-decoration:none}}
</style></head><body>"""]
    html.append(f"<h2>Results for <code>{username}</code></h2>")
    html.append("<table><tr><th>Platform</th><th>Status</th><th>Code</th><th>Link</th></tr>")
    for name, status, code, url in rows:
        cls = badge.get(status, "maybe")
        html.append(f"<tr><td>{name}</td><td><span class='tag {cls}'>{status}</span></td><td>{code}</td>"
                    f"<td><a href='{url}' target='_blank'>{url}</a></td></tr>")
    html.append("</table>")
    html.append(f"""
    <form method="post" action="/export">
      <input type="hidden" name="username" value="{username}">
      <button type="submit">Download PDF</button>
    </form>
    <p><a href="/">← New search</a></p>
    </body></html>""")
    return "".join(html)

@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html","r",encoding="utf-8") as f:
        return f.read()

@app.post("/search", response_class=HTMLResponse)
def search(username: str = Form(...)):
    u = username.strip()
    rows = []
    for name, tpl in PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = check_url(url)
        rows.append((name, status, code, final_url))
    # tablo için (name, status, code, url) sırasına göre düzenle
    rows_html = [(n,s,c,u) for (n,s,c,u) in rows]
    return render_results(u, rows_html)

@app.post("/export")
def export_pdf(username: str = Form(...)):
    # Aynı kontrolü tekrar yapıp PDF üretelim (stateless)
    u = username.strip()
    rows = []
    for name, tpl in PLATFORMS:
        url = tpl.format(u=u)
        status, code, final_url = check_url(url)
        rows.append((name, status, code, final_url))

    # PDF (ReportLab)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.units import cm

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w,h = A4
    y = h - 2*cm
    c.setTitle(f"DeepsearchAgent Report - {u}")
    c.setFont("Helvetica-Bold", 16); c.drawString(2*cm, y, f"DeepsearchAgent Report – {u}")
    y -= 0.9*cm
    c.setFont("Helvetica", 10); c.drawString(2*cm, y, f"Generated: {datetime.datetime.utcnow().isoformat()}Z")
    y -= 0.7*cm
    c.setFont("Helvetica-Bold", 12); c.drawString(2*cm, y, "Matches")
    y -= 0.5*cm; c.setFont("Helvetica", 10)

    for name, status, code, url in rows:
        line = f"{name:12} | {status:9} | {code:3} | {url}"
        # sayfa taşarsa yeni sayfa
        for chunk in [line[i:i+95] for i in range(0, len(line), 95)]:
            if y < 2*cm:
                c.showPage(); y = h - 2*cm; c.setFont("Helvetica", 10)
            c.drawString(2*cm, y, chunk); y -= 0.45*cm

    c.showPage(); c.save(); buf.seek(0)
    fname = f"{u}_report.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})
