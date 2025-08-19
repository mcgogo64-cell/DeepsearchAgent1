from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
import requests
from bs4 import BeautifulSoup

app = FastAPI(title="DeepsearchAgent – with Tinder Search")

UA = {"User-Agent": "Mozilla/5.0 (compatible; DeepsearchAgent/1.0)"}

# sadece dating siteleri (Tinder dahil)
DATING_SITES = [
    "tinder.com",
    "bumble.com",
    "badoo.com",
    "lovoo.com",
    "finya.de",
    "parship.de",
    "edarling.de",
    "elitepartner.de",
    "jaumo.com",
    "okcupid.com",
    "plentyoffish.com",
    "hinge.co",
    "once.app",
    "lablue.de"
]

def site_search(domain: str, username: str, limit=5):
    """DuckDuckGo'da site:domain username araması yapar"""
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
    except Exception as e:
        return [f"(error: {e})"]

@app.get("/", response_class=HTMLResponse)
def form():
    return """<html><body>
    <h2>Dating Search (Tinder + others)</h2>
    <form method="post" action="/search">
      <input name="username" placeholder="Enter username" style="width:250px;padding:6px"/>
      <button>Search</button>
    </form>
    </body></html>"""

@app.post("/search", response_class=HTMLResponse)
def search(username: str = Form(...)):
    u = username.strip()
    html = [f"<h3>Results for: {u}</h3><ul>"]
    for site in DATING_SITES:
        links = site_search(site, u)
        if links:
            html.append(f"<li><b>{site}</b>:<br/>" + "<br/>".join([f"<a href='{l}' target='_blank'>{l}</a>" for l in links]) + "</li>")
        else:
            html.append(f"<li><b>{site}</b>: no hits</li>")
    html.append("</ul><p><a href='/'>← New search</a></p>")
    return "".join(html)
