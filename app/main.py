import io
import zipfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from .converter import convert_rtf

BASE = Path(__file__).parent
STATIC = BASE / "static"
ASSETS = ["portaria-css.css", "portarias_html.css", "brasao.png"]

app = FastAPI(title="Conversor de RTF para HTML", version="1.0.0")


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (BASE / "templates" / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/convert/html", response_class=HTMLResponse)
async def convert_one(
    file: UploadFile = File(...),
    revogado: bool = Form(False),
    om: str = Form("DIRETORIA DE HIDROGRAFIA E NAVEGAÇÃO"),
) -> str:
    """Converte um único RTF e devolve o HTML."""
    _check(file)
    return convert_rtf(await file.read(), revogado=revogado, om=om)


@app.post("/api/convert")
async def convert_many(
    files: list[UploadFile] = File(...),
    revogado: bool = Form(False),
    om: str = Form("DIRETORIA DE HIDROGRAFIA E NAVEGAÇÃO"),
):
    """Converte um ou mais RTF e devolve um ZIP com os HTML + CSS + brasão."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files:
            _check(f)
            html = convert_rtf(await f.read(), revogado=revogado, om=om)
            z.writestr(Path(f.filename).stem + ".html", html)
        for a in ASSETS:
            z.write(STATIC / a, a)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="portarias_html.zip"'},
    )


@app.get("/static/{name}")
def static(name: str):
    if name not in ASSETS:
        raise HTTPException(404)
    media = "image/png" if name.endswith(".png") else "text/css"
    return Response((STATIC / name).read_bytes(), media_type=media)


def _check(f: UploadFile) -> None:
    if not (f.filename or "").lower().endswith(".rtf"):
        raise HTTPException(400, f"Arquivo não é RTF: {f.filename}")
