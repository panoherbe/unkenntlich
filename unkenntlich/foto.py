"""Fotos und Bilder von Schreiben (JPG, PNG): Gesichter, Köpfe, Kennzeichen, Text im Bild, Unterschriften und
Stempel; deckend überschreiben und ohne Metadaten neu speichern. Koordinaten in Pixeln des aufrecht gedrehten Bildes.
"""
from __future__ import annotations

import io

import cv2
import numpy as np
from PIL import Image, ImageOps

from . import bild, dokument, text_layout

FUELLUNG_FOTO = (27, 34, 38)
FUELLUNG_SCHRIFT = (0, 0, 0)

EXIF_NAMEN = {0x010F: "Kamerahersteller", 0x0110: "Kameramodell", 0x0131: "Software", 0x0132: "Datum",
              0x013B: "Urheber (Artist)", 0x8298: "Copyright", 0x010E: "Bildbeschreibung", 0x9286: "Kommentar",
              0x927C: "Herstellerdaten (MakerNote)", 0xA430: "Besitzer der Kamera", 0xA431: "Seriennummer"}


def laden(pfad) -> tuple[np.ndarray, list[dict], str]:
    """Bild aufrecht (EXIF-Ausrichtung angewandt) als RGB, dazu die Liste der Metadaten (ohne Werte)."""
    roh = Image.open(pfad)
    fmt = roh.format or "JPEG"
    inventar = []
    exif = roh.getexif()
    for tag, name in EXIF_NAMEN.items():
        if tag in exif or tag in exif.get_ifd(0x8769):
            inventar.append({"feld": name, "art": "EXIF"})
    if exif.get_ifd(0x8825):
        inventar.append({"feld": "GPS-Position", "art": "EXIF"})
    if 0x9003 in exif.get_ifd(0x8769):
        inventar.append({"feld": "Aufnahmezeit", "art": "EXIF"})
    if "xmp" in roh.info or "XML:com.adobe.xmp" in roh.info:
        inventar.append({"feld": "XMP-Metadaten", "art": "XMP"})
    if "photoshop" in roh.info or "iptc" in roh.info:
        inventar.append({"feld": "IPTC-Angaben", "art": "IPTC"})
    for k in roh.info:
        if k in ("Comment", "comment", "Description", "Author", "Title", "Software"):
            inventar.append({"feld": f"Textfeld „{k}“", "art": "Datei"})
    aufrecht = ImageOps.exif_transpose(roh).convert("RGB")
    return np.array(aufrecht), inventar, fmt


def gesicht_stellen(rgb: np.ndarray, quelle_zusatz: str = "") -> list[dict]:
    h, w = rgb.shape[:2]
    bgr = rgb[..., ::-1].copy()
    stellen = []
    gesichter = bild.gesichter(bgr, 0.5)
    for box, s in gesichter:
        stellen.append({"kategorie": "gesicht", "grund": "Gesicht erkannt", "quelle": "YuNet" + quelle_zusatz,
                        "sicherheit": round(s, 3), "rechtecke": [list(map(lambda v: round(v, 1),
                                                                         bild.erweitern(box, 0.3, w, h, oben=0.12)))]})
    for k in bild.koepfe(bgr):
        if not k["kopf"]:
            continue
        kopf = bild.erweitern(k["kopf"], 0.1, w, h)
        if any(bild.anteil_in(tuple(st["rechtecke"][0]), kopf) > 0.3 or bild.iou(tuple(st["rechtecke"][0]), kopf) > 0.2
               for st in stellen):
            continue
        stellen.append({"kategorie": "gesicht", "grund": "Kopf aus der Körperhaltung (Gesicht nicht frontal)",
                        "quelle": "YOLO26-pose" + quelle_zusatz, "sicherheit": round(k["score"], 3),
                        "rechtecke": [[round(v, 1) for v in kopf]]})
    return stellen


def kennzeichen_stellen(rgb: np.ndarray) -> list[dict]:
    h, w = rgb.shape[:2]
    return [{"kategorie": "kennzeichen", "grund": "Kfz-Kennzeichen erkannt", "quelle": "YOLO26 · YOLOv9 (Kennzeichen)",
             "sicherheit": round(s, 3), "rechtecke": [[round(v, 1) for v in bild.erweitern(box, 0.12, w, h)]]}
            for box, s in bild.kennzeichen_beide(rgb[..., ::-1].copy())]


def analysieren(pfad, fortschritt=lambda anteil, text: None) -> dict:
    rgb, inventar, fmt = laden(pfad)
    h, w = rgb.shape[:2]
    fortschritt(0.05, "Gesichter und Köpfe")
    stellen = gesicht_stellen(rgb)
    fortschritt(0.35, "Kennzeichen")
    stellen += kennzeichen_stellen(rgb)
    fortschritt(0.5, "Text im Bild")
    layout = text_layout.aus_bild(rgb, faktor=1.0, min_sicherheit=55)
    schriftstueck = len(layout.woerter) >= 40
    for s in dokument.text_stellen(layout, 0, " (Texterkennung)"):
        s["rechtecke"] = [[round(v, 1) for v in r] for r in s["rechtecke"]]
        if not schriftstueck and s["kategorie"] in ("anschrift",) and s.get("sicherheit", 1) < 0.9:
            continue
        stellen.append(s)
    if schriftstueck:
        fortschritt(0.8, "Unterschriften und Stempel")
        for box, kat, s in bild.unterschriften_stempel(rgb):
            stellen.append({"kategorie": kat, "grund": "Bildmodell erkennt " + (
                "eine Unterschrift" if kat == "unterschrift" else "einen Stempel"), "quelle": "RF-DETR",
                "sicherheit": round(s, 3), "rechtecke": [[round(v, 1) for v in bild.erweitern(box, 0.06, w, h)]]})
    for s in stellen:
        s["seite"] = 0
    stellen = dokument.zusammenlegen(stellen)
    stellen += dokument.zusammenlegen(dokument.weitere_vorkommen({0: [layout]}, stellen))
    for s in stellen:
        s["seite"] = 0
    fortschritt(1.0, "fertig")
    return {"seiten": [{"breite": w, "hoehe": h, "scan": schriftstueck, "geprueft": False}], "stellen": stellen,
            "metadaten": inventar, "format": fmt, "schriftstueck": schriftstueck}


def fuellen(rgb: np.ndarray, stellen: list[dict], schriftstueck: bool = False) -> np.ndarray:
    out = rgb.copy()
    for s in stellen:
        farbe = FUELLUNG_SCHRIFT if (schriftstueck or s["kategorie"] not in ("gesicht", "person", "kennzeichen")) \
            else FUELLUNG_FOTO
        for r in s["rechtecke"]:
            x0, y0, x1, y1 = (int(round(v)) for v in r)
            radius = 0 if farbe == FUELLUNG_SCHRIFT else int(min(x1 - x0, y1 - y0) * 0.18)
            gefuelltes_rechteck(out, (x0, y0, x1, y1), farbe, radius)
    return out


def gefuelltes_rechteck(bild_arr: np.ndarray, r, farbe, radius: int = 0) -> None:
    x0, y0, x1, y1 = r
    h, w = bild_arr.shape[:2]
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(w, x1), min(h, y1)
    if x1 <= x0 or y1 <= y0:
        return
    if radius <= 1:
        bild_arr[y0:y1, x0:x1] = farbe
        return
    cv2.rectangle(bild_arr, (x0 + radius, y0), (x1 - radius, y1 - 1), farbe, -1)
    cv2.rectangle(bild_arr, (x0, y0 + radius), (x1 - 1, y1 - radius), farbe, -1)
    for cx, cy in ((x0 + radius, y0 + radius), (x1 - radius - 1, y0 + radius), (x0 + radius, y1 - radius - 1),
                   (x1 - radius - 1, y1 - radius - 1)):
        cv2.circle(bild_arr, (cx, cy), radius, farbe, -1, lineType=cv2.LINE_8)


def speichern(rgb: np.ndarray, ausgang, fmt: str) -> None:
    """Nur die Bildpunkte, keine EXIF-, XMP-, IPTC- oder Textfelder, kein Farbprofil."""
    bild_neu = Image.fromarray(rgb)
    if fmt.upper() == "PNG":
        bild_neu.save(ausgang, "PNG", optimize=True)
    else:
        bild_neu.save(ausgang, "JPEG", quality=92, optimize=True)


def schwaerzen(eingang, ausgang, stellen: list[dict], schriftstueck: bool = False) -> dict:
    rgb, _inv, fmt = laden(eingang)
    speichern(fuellen(rgb, stellen, schriftstueck), ausgang, fmt)
    return {"breite": rgb.shape[1], "hoehe": rgb.shape[0]}


def vorschau(pfad, max_seite: int = 1800) -> bytes:
    rgb, _inv, _fmt = laden(pfad)
    b = Image.fromarray(rgb)
    b.thumbnail((max_seite, max_seite))
    out = io.BytesIO()
    b.save(out, "JPEG", quality=86)
    return out.getvalue()
