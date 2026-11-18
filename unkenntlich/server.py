"""Browser-Oberfläche und Programmschnittstelle. Läuft nur auf dem eigenen Rechner; keine externen Aufrufe,
keine Statistik, keine Cookies. Die Content-Security-Policy erlaubt nur Inhalte von dieser Adresse.
"""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

from fastapi import Body, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__, bericht, dokument, foto, kategorien, modelle, video, vorgang

WEB = Path(__file__).resolve().parent / "web"
app = FastAPI(title="Unkenntlich", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)

CSP = ("default-src 'self'; img-src 'self' data: blob:; media-src 'self' blob:; style-src 'self'; script-src 'self'; "
       "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")


CSP_BERICHT = ("default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:; base-uri 'none'; "
               "form-action 'none'; frame-ancestors 'none'")


@app.middleware("http")
async def kopfzeilen(request, call_next):
    antwort = await call_next(request)
    # Der Prüfbericht ist eine eigenständige Datei mit eingebetteten Stilen, Schriften und Bildern, ohne Skripte.
    antwort.headers["Content-Security-Policy"] = CSP_BERICHT if request.url.path.endswith("/bericht.html") else CSP
    antwort.headers["X-Content-Type-Options"] = "nosniff"
    antwort.headers["Referrer-Policy"] = "no-referrer"
    antwort.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if request.url.path.startswith("/api/"):
        antwort.headers["Cache-Control"] = "no-store"
    return antwort


@app.on_event("startup")
def _start():
    vorgang.starten()


def _v(vid: str) -> dict:
    v = vorgang.laden(vid)
    if v is None:
        raise HTTPException(404, "Vorgang nicht gefunden")
    return v


def _d(v: dict, did: str) -> dict:
    d = vorgang.datei(v, did)
    if d is None:
        raise HTTPException(404, "Datei nicht gefunden")
    return d


@app.get("/api/gesundheit")
def gesundheit():
    return {"ok": True, "version": __version__}


@app.get("/api/info")
def info():
    return {"version": __version__, "kategorien": {k: {"name": n, "gruppe": g} for k, (n, g) in kategorien.KATEGORIEN.items()},
            "modelle": modelle.VERZEICHNIS}


@app.post("/api/vorgang")
def vorgang_neu():
    return vorgang.oeffentlich(vorgang.neu())


@app.get("/api/vorgang/{vid}")
def vorgang_lesen(vid: str):
    return vorgang.oeffentlich(_v(vid))


@app.delete("/api/vorgang/{vid}")
def vorgang_loeschen(vid: str):
    return {"geloescht": vorgang.loeschen(vid)}


@app.post("/api/vorgang/{vid}/dateien")
def dateien_ablegen(vid: str, dateien: list[UploadFile] = File(...)):
    v = _v(vid)
    try:
        for f in dateien:
            vorgang.ablegen(v, f.filename or "datei", f.file)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/beispiele")
def beispiele(vid: str):
    v = _v(vid)
    vorgang.beispiele(v)
    return vorgang.oeffentlich(v)


@app.get("/api/vorgang/{vid}/datei/{did}/seite/{n}")
def seite(vid: str, did: str, n: int, ergebnis: bool = False):
    v = _v(vid)
    d = _d(v, did)
    if ergebnis:
        _freigegeben(v, d)   # auch eine Vorschau des Ergebnisses ist ein Export
    pfad = d.get("ausgabe") if ergebnis else d["pfad"]
    if not pfad:
        raise HTTPException(404, "Noch kein Ergebnis")
    if d["art"] == "dokument":
        return Response(dokument.vorschau(pfad, n, 110), media_type="image/png")
    if d["art"] == "foto":
        return Response(foto.vorschau(pfad), media_type="image/jpeg")
    return Response(video.standbild(pfad, float(n)), media_type="image/jpeg")


@app.get("/api/vorgang/{vid}/datei/{did}/video")
def video_datei(vid: str, did: str, ergebnis: bool = False, format: str = "mp4"):
    v = _v(vid)
    d = _d(v, did)
    if ergebnis:
        _freigegeben(v, d)
    pfad = d.get("ausgabe") if ergebnis else d["pfad"]
    if d["art"] != "video" or not pfad:
        raise HTTPException(404)
    if format == "webm":
        webm = vorgang.ordner(vid) / "analyse" / did / ("ergebnis.webm" if ergebnis else "vorschau.webm")
        if webm.exists():
            return FileResponse(webm, media_type="video/webm")
    return FileResponse(pfad, media_type="video/mp4")


@app.get("/api/vorgang/{vid}/datei/{did}/spuren")
def spuren(vid: str, did: str):
    v = _v(vid)
    _d(v, did)
    pfad = vorgang.ordner(vid) / "analyse" / did / "spuren.json"
    if not pfad.exists():
        raise HTTPException(404)
    return Response(pfad.read_bytes(), media_type="application/json")


@app.get("/api/vorgang/{vid}/datei/{did}/spur/{sid}.jpg")
def spur_bild(vid: str, did: str, sid: str):
    _v(vid)
    pfad = vorgang.ordner(vid) / "analyse" / did / f"spur-{sid}.jpg"
    if not sid.isalnum() or not pfad.exists():
        raise HTTPException(404)
    return FileResponse(pfad, media_type="image/jpeg")


@app.post("/api/vorgang/{vid}/entscheidungen")
def entscheidungen(vid: str, aenderungen: list[dict] = Body(...)):
    v = _v(vid)
    vorgang.entscheiden(v, aenderungen)
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/bereich")
def bereich(vid: str, daten: dict = Body(...)):
    v = _v(vid)
    d = _d(v, daten.get("datei", ""))
    r = daten.get("rechteck")
    if d["art"] == "video" or not isinstance(r, list) or len(r) != 4:
        raise HTTPException(400, "Bereich nur auf Seiten und Bildern")
    vorgang.eigener_bereich(v, d["id"], int(daten.get("seite", 0)), r)
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/datei/{did}/seite/{n}/geprueft")
def geprueft(vid: str, did: str, n: int):
    v = _v(vid)
    _d(v, did)
    vorgang.seite_geprueft(v, did, n)
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/gegenprobe")
def gegenprobe(vid: str):
    v = _v(vid)
    ok, grund = vorgang.bereit(v)
    if not ok:
        raise HTTPException(409, grund)
    vorgang.gegenprobe_starten(v)
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/reste")
def reste(vid: str):
    v = _v(vid)
    vorgang.reste_uebernehmen(v)
    return vorgang.oeffentlich(v)


@app.post("/api/vorgang/{vid}/datei/{did}/ausnehmen")
def ausnehmen(vid: str, did: str):
    v = _v(vid)
    _d(v, did)
    try:
        vorgang.ausnehmen(v, did)
    except ValueError as e:
        raise HTTPException(409, str(e))
    return vorgang.oeffentlich(v)


def _freigegeben(v: dict, d: dict | None = None) -> None:
    g = v.get("gegenprobe") or {}
    if g.get("status") != "fertig" or g.get("reste") != 0:
        raise HTTPException(423, "Export gesperrt: Die Gegenprobe muss ohne Reste abgeschlossen sein.")
    if d is not None and d.get("ausgenommen"):
        raise HTTPException(404, "Diese Datei ist vom Export ausgenommen und wird nicht herausgegeben.")


@app.get("/api/vorgang/{vid}/ergebnis/{did}")
def ergebnis(vid: str, did: str):
    v = _v(vid)
    d = _d(v, did)
    _freigegeben(v, d)
    return FileResponse(d["ausgabe"], filename=Path(d["ausgabe"]).name.split("-", 1)[1])


@app.get("/api/vorgang/{vid}/bericht.{art}")
def pruefbericht(vid: str, art: str):
    v = _v(vid)
    g = v.get("gegenprobe") or {}
    if g.get("status") != "fertig":
        raise HTTPException(409, "Noch keine Gegenprobe")
    pfad = vorgang.ordner(vid) / "ausgabe" / f"pruefbericht.{art}"
    if art not in ("html", "pdf") or not pfad.exists():
        raise HTTPException(404)
    vorgang.protokoll(v, "Prüfbericht geöffnet", art.upper())
    vorgang.speichern(v)
    return FileResponse(pfad, media_type="text/html" if art == "html" else "application/pdf",
                        filename=f"pruefbericht-{vid}.{art}" if art == "pdf" else None)


@app.get("/api/vorgang/{vid}/export.zip")
def export(vid: str):
    v = _v(vid)
    _freigegeben(v)
    puffer = io.BytesIO()
    heraus = [d for d in v["dateien"] if not d.get("ausgenommen")]   # ausgenommene Dateien bleiben draußen
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        for d in heraus:
            z.write(d["ausgabe"], Path(d["ausgabe"]).name.split("-", 1)[1])
        for art in ("pdf", "html"):
            p = vorgang.ordner(vid) / "ausgabe" / f"pruefbericht.{art}"
            if p.exists():
                z.write(p, f"pruefbericht.{art}")
    ohne = len(v["dateien"]) - len(heraus)
    vorgang.protokoll(v, "Export heruntergeladen", f"{len(heraus)} Dateien und Prüfbericht als ZIP"
                      + (f" ({ohne} vom Export ausgenommen)" if ohne else ""))
    vorgang.speichern(v)
    return Response(puffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="unkenntlich-{vid}.zip"'})


app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
