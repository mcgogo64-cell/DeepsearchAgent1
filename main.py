from fastapi import FastAPI, Form
from fastapi.responses import FileResponse, HTMLResponse

app = FastAPI()

# Ana sayfa: index.html'i göster
@app.get("/", response_class=HTMLResponse)
def home():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

# Form POST: rapor üret ve indir
@app.post("/report")
def generate_report(username: str = Form(...)):
    content = (
        f"DeepsearchAgent report for: {username}\n"
        f"- Twitter: https://twitter.com/{username}\n"
        f"- Instagram: https://instagram.com/{username}\n"
    )
    fname = f"{username}_report.txt"
    with open(fname, "w", encoding="utf-8") as f:
        f.write(content)
    return FileResponse(fname, media_type="text/plain", filename=fname)
