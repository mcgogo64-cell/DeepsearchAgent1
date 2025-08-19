from fastapi import FastAPI, Form
from fastapi.responses import FileResponse
from fpdf import FPDF

app = FastAPI()

@app.get("/")
def home():
    return {"message": "DeepSearchAgent is running"}

@app.post("/report")
def generate_report(username: str = Form(...)):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt=f"Report for {username}", ln=True, align="C")
    pdf.output("report.pdf")
    return FileResponse("report.pdf", media_type="application/pdf", filename="report.pdf")
