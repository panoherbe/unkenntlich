"""Prüfbericht als HTML und PDF: welche Kategorie wo unkenntlich wurde, was sichtbar blieb und warum, Ergebnis der
Gegenprobe, Prüfsummen, Modelle, Protokoll. Der Klartext der unkenntlich gemachten Daten steht nie darin; die
Vorschaubilder zeigen nur das Ergebnis, und nur, wenn die Gegenprobe es freigegeben hat.
"""
from __future__ import annotations

import base64
import datetime as dt
import io
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from . import __version__, dokument, kategorien, modelle, video

HIER = Path(__file__).resolve().parent
_env = Environment(loader=FileSystemLoader(HIER / "vorlagen"), autoescape=select_autoescape(["html"]))


def _datum(iso: str) -> str:
    try:
        t = dt.datetime.fromisoformat(iso)
        return t.strftime("%d.%m.%Y, %H:%M:%S")
    except Exception:
        return iso


def _zahl(x: float, stellen: int = 1) -> str:
    return f"{x:,.{stellen}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def _bild_daten(jpg: bytes) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(jpg).decode()


def _klein(daten: bytes, breite: int) -> bytes:
    b = Image.open(io.BytesIO(daten)).convert("RGB")
    b.thumbnail((breite, breite * 2))
    out = io.BytesIO()
    b.save(out, "JPEG", quality=78)
    return out.getvalue()


def _vorschauen(d: dict, freigegeben: bool) -> list[str]:
    aus = d.get("ausgabe")
    if not freigegeben or not aus or not Path(aus).exists():
        return []
    if d["art"] == "dokument":
        return [_bild_daten(_klein(dokument.vorschau(aus, i, 60), 360)) for i in range(min(3, len(d["seiten"])))]
    if d["art"] == "foto":
        return [_bild_daten(_klein(Path(aus).read_bytes(), 520))]
    dauer = d["video"]["dauer"]
    return [_bild_daten(_klein(video.standbild(aus, dauer * t, 640), 300)) for t in (0.15, 0.4, 0.65, 0.9)]


def _ort(d: dict, s: dict) -> str:
    if d["art"] == "video":
        z = s.get("zeit") or {}
        return f"{_zahl(z.get('von', 0))}–{_zahl(z.get('bis', 0))} s ({z.get('bilder', 0)} Einzelbilder)"
    r = s["rechtecke"][0] if s.get("rechtecke") else None
    einheit = "pt" if d["art"] == "dokument" else "px"
    teil = f"Seite {s.get('seite', 0) + 1}, " if d["art"] == "dokument" else ""
    if r:
        teil += f"x {r[0]:.0f}, y {r[1]:.0f}, {r[2] - r[0]:.0f} × {r[3] - r[1]:.0f} {einheit}"
        if len(s["rechtecke"]) > 1:
            teil += f" (+{len(s['rechtecke']) - 1} Zeile/n)"
    return teil


def _grund(s: dict) -> str:
    """Der Grund eines Vorschlags, ohne die Angabe selbst: Steht ein Teil des gefundenen Textes darin, wird er durch
    die Kategorie ersetzt (zweite Sicherung; die Erkenner formulieren ihre Gründe schon ohne Daten)."""
    grund = s.get("grund") or ""
    teile = {t for t in re.split(r"[\s,.;:()/„“\"'-]+", s.get("text") or "") if len(t) >= 3}
    if any(t.lower() in grund.lower() for t in teile):
        return f"{kategorien.bezeichnung(s['kategorie'])} (Grund enthielt die Angabe und ist gekürzt)"
    return grund


def daten(v: dict) -> dict:
    g = v.get("gegenprobe") or {}
    freigegeben = g.get("status") == "fertig" and g.get("reste") == 0
    dateien = []
    for d in v["dateien"]:
        erg = (g.get("ergebnisse") or {}).get(d["id"], {})
        stellen = []
        for s in sorted((x for x in v["stellen"] if x["datei"] == d["id"]),
                        key=lambda x: (x.get("seite", 0), (x.get("zeit") or {}).get("von", 0),
                                       (x.get("rechtecke") or [[0, 0]])[0][1])):
            modus = ""
            if s["kategorie"] == "person":
                modus = "ganze Person" if s.get("modus") == "person" else "Gesicht"
            stellen.append({"nr": s["id"], "kategorie": kategorien.bezeichnung(s["kategorie"]),
                            "gruppe": kategorien.gruppe(s["kategorie"]), "ort": _ort(d, s),
                            "entscheidung": s["entscheidung"], "modus": modus,
                            "begruendung": s.get("begruendung") or "", "quelle": s["quelle"], "grund": _grund(s)})
        dateien.append({"name": d["name"], "art": {"dokument": "Dokument", "foto": "Bild", "video": "Video"}[d["art"]],
                        "umfang": (f"{len(d['seiten'])} Seite(n)" if d["art"] == "dokument" else
                                   f"{d['seiten'][0]['breite']} × {d['seiten'][0]['hoehe']} px" if d["art"] == "foto" else
                                   f"{_zahl(d['video']['dauer'])} s, {d['video']['bilder']} Einzelbilder, "
                                   f"{d['video']['breite']} × {d['video']['hoehe']} px"),
                        "sha_ein": d["sha256"], "sha_aus": erg.get("sha256_aus", "–"),
                        "groesse_ein": d["groesse"], "groesse_aus": erg.get("groesse_aus"),
                        "stellen": stellen, "unkenntlich": sum(1 for s in stellen if s["entscheidung"] == "unkenntlich"),
                        "sichtbar": sum(1 for s in stellen if s["entscheidung"] == "sichtbar"),
                        "metadaten": d["metadaten"], "reste": erg.get("reste", []),
                        "pruefungen": erg.get("pruefungen", []), "vorschauen": _vorschauen(d, freigegeben),
                        "dauer": _zahl(erg.get("dauer_schwaerzen", 0) + erg.get("dauer_gegenprobe", 0))})
    return {"v": v, "version": __version__, "erstellt": _datum(g.get("ende") or v["erstellt"]),
            "begonnen": _datum(v["erstellt"]), "reste": g.get("reste"), "dateien": dateien,
            "protokoll": [{**p, "zeit": _datum(p["zeit"])} for p in v["protokoll"]],
            "modelle": modelle.VERZEICHNIS, "albert": _schrift("albert-sans.woff2"), "mono": _schrift("plex-mono.woff2"),
            "wortmarke": (HIER / "web" / "bilder" / "wortmarke-hell.svg").read_text()}


def _schrift(name: str) -> str:
    """Schriften als data-URI, damit der HTML-Bericht auf jedem Rechner gleich aussieht."""
    return "data:font/woff2;base64," + base64.b64encode((HIER / "web" / "schrift" / name).read_bytes()).decode()


def html(v: dict) -> str:
    return _env.get_template("bericht.html").render(**daten(v))


def schreiben(v: dict) -> tuple[Path, Path]:
    from weasyprint import HTML

    from .vorgang import ordner
    text = html(v)
    p_html = ordner(v["id"]) / "ausgabe" / "pruefbericht.html"
    p_pdf = ordner(v["id"]) / "ausgabe" / "pruefbericht.pdf"
    p_html.write_text(text, encoding="utf-8")
    HTML(string=text, base_url=str(HIER)).write_pdf(p_pdf)
    return p_html, p_pdf
