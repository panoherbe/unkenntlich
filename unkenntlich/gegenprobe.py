"""Gegenprobe: alle Erkenner laufen erneut über das Ergebnis, dazu unabhängige Prüfungen. Findet sie etwas,
das nicht ausdrücklich sichtbar bleiben soll, ist das ein Rest, und der Export bleibt gesperrt.

Ein Rest ist ein dict: Kategorie, Ort (Seite und Rechteck bzw. Einzelbild und Zeit), Prüfung, Hinweis. Klartext der
Daten steht nie darin.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

from . import bild, dokument, foto, text_erkennen, text_layout, video


def _norm(t: str) -> str:
    return re.sub(r"[\s .,;:()\-/]", "", (t or "")).lower()


def _erlaubt(box, sichtbar: list) -> bool:
    return any(bild.anteil_in(tuple(box), tuple(r)) > 0.5 or bild.iou(tuple(box), tuple(r)) > 0.3 for r in sichtbar)


def _gedeckt(box, flaechen: list) -> float:
    """Anteil von box, der unter deckenden Flächen liegt; 1.0, wenn die Mitte des Fundes unter einer Fläche liegt.

    Die Bildmodelle sehen eine deckende Fläche manchmal selbst als Kennzeichen oder Gesicht und melden dann ein etwas
    größeres Rechteck um sie herum. Liegt die Mitte unter der Fläche, ist der Kern des Fundes verdeckt."""
    cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
    if any(f[0] <= cx <= f[2] and f[1] <= cy <= f[3] for f in flaechen):
        return 1.0
    return min(1.0, sum(bild.anteil_in(tuple(box), tuple(f)) for f in flaechen))


def _vorhanden(bild_bgr: np.ndarray, flaechen: list, farben: list, faktor: float = 1.0) -> list:
    """Nur die deckenden Flächen, die im Ergebnis wirklich da sind: Im Inneren (ohne Rand) hat jedes Bildpixel die
    Füllfarbe. Die Gegenprobe vertraut also nicht darauf, dass gezeichnet wurde, was geplant war (Kontrollversuch:
    ausgelassene Einzelbilder)."""
    h, w = bild_bgr.shape[:2]
    out = []
    for f in flaechen:
        x0, y0, x1, y1 = (v * faktor for v in f)
        bx, by = (x1 - x0) * 0.2, (y1 - y0) * 0.2
        a, b, c, d = int(max(0, x0 + bx)), int(max(0, y0 + by)), int(min(w, x1 - bx)), int(min(h, y1 - by))
        if c - a < 2 or d - b < 2:
            out.append(f)  # zu klein zum Messen: zählt nur, wenn Nachbarn es tragen; konservativ: als vorhanden
            continue
        stueck = bild_bgr[b:d, a:c].reshape(-1, 3).astype(np.int16)
        if any(np.mean(np.abs(stueck - np.array(fb, np.int16)).max(axis=1) < 28) > 0.9 for fb in farben):
            out.append(f)
    return out


def _texte(stellen: list[dict]) -> set[str]:
    out = set()
    for s in stellen:
        t = _norm(s.get("text") or "")
        if len(t) >= 4:
            out.add(t)
    return out


def _text_pruefen(layout: text_layout.Layout, seite: int, bestaetigt_texte: set, sichtbar: list, flaechen: list,
                  pruefung: str, mit_modell: bool = False) -> list[dict]:
    """(a) Jede bestätigte Angabe wird wörtlich gesucht. (b) Die festen Regeln (Prüfziffern, Muster) laufen erneut.
    Das Sprachmodell läuft hier nicht mit: Nach dem Schwärzen liest es den veränderten Satz anders und hält z. B.
    „Herr“ allein für einen Namen oder ein Eintrittsdatum für ein Geburtsdatum (Messlauf 16.11.2026)."""
    reste = []
    norm = _norm(layout.text)
    # (a) Text einer bestätigten Stelle steht noch irgendwo
    zuordnung = []
    for i, ch in enumerate(layout.text):
        if _norm(ch):
            zuordnung.append(i)
    for t in bestaetigt_texte:
        start = 0
        while (pos := norm.find(t, start)) >= 0:
            a, e = zuordnung[pos], zuordnung[pos + len(t) - 1] + 1
            for r in layout.rechtecke(a, e) or [None]:
                if r is not None and (_gedeckt(r, flaechen) > 0.6 or _erlaubt(r, sichtbar)):
                    continue
                reste.append({"seite": seite, "rechteck": [round(v, 1) for v in r] if r else None,
                              "kategorie": "text", "pruefung": pruefung,
                              "hinweis": "Text einer bestätigten Stelle ist noch lesbar"})
            start = pos + len(t)
    # (b) Regeln und Modell finden etwas Neues
    for f in text_erkennen.finde_alles(layout.text, mit_modell=mit_modell):
        for r in layout.rechtecke(f.start, f.ende):
            if _gedeckt(r, flaechen) > 0.6 or _erlaubt(r, sichtbar):
                continue
            if any(x.get("rechteck") and bild.iou(tuple(x["rechteck"]), r) > 0.5 for x in reste):
                continue
            reste.append({"seite": seite, "rechteck": [round(v, 1) for v in r], "kategorie": f.kategorie,
                          "pruefung": pruefung, "hinweis": f"{f.grund}: noch erkennbar"})
    return reste


def _rechtecke(stellen: list[dict], seite: int) -> list:
    return [r for s in stellen if s.get("seite", 0) == seite for r in s.get("rechtecke", [])]


def _bildpunkte_unter_flaechen(doc, seite, nr: int, flaechen: list) -> list[dict]:
    """Bilder der Seite (z. B. ein Scan) direkt aus der Datei lesen und prüfen, ob unter einer bestätigten Fläche noch
    Inhalt liegt. Richtig geschwärzt sind diese Bildpunkte einfarbig; ein nur darübergemalter Kasten verdeckt sie
    in der Ansicht, lässt sie aber in der Datei stehen."""
    reste = []
    if not flaechen:
        return reste
    for info in seite.get_image_info(xrefs=True):
        xref, bbox, t = info.get("xref"), pymupdf.Rect(info["bbox"]), info.get("transform") or (1, 0, 0, 1, 0, 0)
        if not xref or bbox.is_empty or abs(t[1]) > 1e-3 or abs(t[2]) > 1e-3:
            continue  # gedrehte oder gespiegelte Bilder prüft die Texterkennung auf dem Ergebnis
        try:
            pix = pymupdf.Pixmap(doc, xref)
            if pix.alpha or pix.n not in (1, 3):
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix, 0)
        except Exception:  # pragma: no cover - unlesbares Bild: zählt die Texterkennung
            continue
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n).astype(np.int16)
        sx, sy = pix.width / bbox.width, pix.height / bbox.height
        for r in flaechen:
            teil = pymupdf.Rect(r) & bbox
            if teil.is_empty or teil.width < 4 or teil.height < 4:
                continue
            bx, by = teil.width * 0.15, teil.height * 0.15
            x0, x1 = int((teil.x0 + bx - bbox.x0) * sx), int((teil.x1 - bx - bbox.x0) * sx)
            y0, y1 = int((teil.y0 + by - bbox.y0) * sy), int((teil.y1 - by - bbox.y0) * sy)
            stueck = a[max(0, y0):y1, max(0, x0):x1].reshape(-1, pix.n)
            if len(stueck) < 16:
                continue
            abweichung = np.abs(stueck - np.median(stueck, axis=0)).max(axis=1)
            if np.mean(abweichung > 40) > 0.02:
                reste.append({"seite": nr, "rechteck": [round(v, 1) for v in teil], "kategorie": "eigener_bereich",
                              "pruefung": "Bildpunkte unter den Flächen",
                              "hinweis": "Unter einer deckenden Fläche steht im Bild der Datei noch Inhalt"})
    return reste


def dokument_pruefen(pfad, bestaetigt: list[dict], sichtbar_st: list[dict], fortschritt=lambda a, t: None) -> dict:
    doc = pymupdf.open(pfad)
    reste, pruefungen = [], []
    texte = _texte(bestaetigt)
    n = len(doc)
    for nr, seite in enumerate(doc):
        flaechen = _rechtecke(bestaetigt, nr)
        sichtbar = _rechtecke(sichtbar_st, nr)
        fortschritt(nr / n, f"Seite {nr + 1}: Textschicht")
        reste += _text_pruefen(text_layout.aus_pdf_seite(seite), nr, texte, sichtbar, [], "Textschicht")
        reste += _bildpunkte_unter_flaechen(doc, seite, nr, flaechen)
        fortschritt((nr + 0.3) / n, f"Seite {nr + 1}: Texterkennung")
        pixel = dokument.seite_als_bild(seite, dokument.OCR_DPI)
        flaechen = _vorhanden(pixel[..., ::-1], flaechen, [(0, 0, 0)], dokument.OCR_DPI / 72)
        lay = text_layout.aus_bild(pixel, faktor=72 / dokument.OCR_DPI)
        reste += _text_pruefen(lay, nr, texte, sichtbar, flaechen, "Texterkennung auf dem Ergebnis")
        fortschritt((nr + 0.7) / n, f"Seite {nr + 1}: Bilder")
        px = dokument.seite_als_bild(seite, dokument.BILD_DPI)
        f = 72 / dokument.BILD_DPI
        for box, kat, s in bild.unterschriften_stempel(px):
            r = [v * f for v in box]
            if _gedeckt(r, flaechen) < 0.6 and not _erlaubt(r, sichtbar):
                reste.append({"seite": nr, "rechteck": [round(v, 1) for v in r], "kategorie": kat,
                              "pruefung": "Bildmodell auf dem Ergebnis", "hinweis": "noch erkennbar"})
        for box, s in bild.gesichter(px[..., ::-1].copy()):
            r = [v * f for v in box]
            if _gedeckt(r, flaechen) < 0.6 and not _erlaubt(r, sichtbar):
                reste.append({"seite": nr, "rechteck": [round(v, 1) for v in r], "kategorie": "gesicht",
                              "pruefung": "Gesichter auf dem Ergebnis", "hinweis": "noch erkennbar"})
    pruefungen += [f"Textschicht aller {n} Seiten durchsucht", "Bildpunkte unter jeder Fläche in der Datei geprüft",
                   f"{n} Seiten neu gelesen (Texterkennung, {dokument.OCR_DPI} dpi)",
                   "Unterschriften, Stempel und Gesichter erneut gesucht"]
    meta = {k: v for k, v in (doc.metadata or {}).items() if v and k not in ("format", "encryption")}
    if meta:
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Metadaten",
                      "hinweis": "Dokumentinfo enthält noch: " + ", ".join(sorted(meta))})
    if doc.get_xml_metadata().strip():
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Metadaten",
                      "hinweis": "XMP-Metadaten vorhanden"})
    if doc.embfile_count():
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Anhänge",
                      "hinweis": f"{doc.embfile_count()} Dateianhang/-anhänge vorhanden"})
    if any(s.annot_xrefs() for s in doc):
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Anmerkungen",
                      "hinweis": "Anmerkungen, Formularfelder oder Verknüpfungen vorhanden"})
    if doc.get_toc():
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Lesezeichen",
                      "hinweis": "Lesezeichen vorhanden"})
    pruefungen.append("Metadaten, XMP, Anhänge, Anmerkungen, Formularfelder und Lesezeichen geprüft")
    return {"reste": reste, "pruefungen": pruefungen, "geprueft": {"seiten": n}}


def foto_pruefen(pfad, bestaetigt: list[dict], sichtbar_st: list[dict], schriftstueck: bool = False,
                 fortschritt=lambda a, t: None, original=None) -> dict:
    roh = Image.open(pfad)
    rgb = np.array(roh.convert("RGB"))
    h, w = rgb.shape[:2]
    bgr = rgb[..., ::-1].copy()
    flaechen = _vorhanden(bgr, _rechtecke(bestaetigt, 0), [foto.FUELLUNG_FOTO[::-1], (0, 0, 0)])
    sichtbar = _rechtecke(sichtbar_st, 0)
    reste = []
    fortschritt(0.1, "Gesichter")
    for box, s in bild.gesichter(bgr):
        if _gedeckt(box, flaechen) < 0.6 and not _erlaubt(box, sichtbar):
            reste.append({"seite": 0, "rechteck": [round(v, 1) for v in box], "kategorie": "gesicht",
                          "pruefung": "Gesichter (YuNet) auf dem Ergebnis", "hinweis": "Gesicht noch erkennbar"})
    for k in bild.koepfe(bgr):
        for ax, ay in k["augen"]:
            punkt = (ax - 2, ay - 2, ax + 2, ay + 2)
            if _gedeckt(punkt, flaechen) < 0.5 and not _erlaubt(punkt, sichtbar):
                reste.append({"seite": 0, "rechteck": [round(v, 1) for v in bild.erweitern(punkt, 8, w, h)],
                              "kategorie": "gesicht", "pruefung": "Augen aus Körperpunkten (YOLO26-pose)",
                              "hinweis": "Augen liegen außerhalb jeder deckenden Fläche"})
                break
    fortschritt(0.4, "Kennzeichen")
    for quelle, funde in (("YOLO26-Kennzeichen", bild.kennzeichen(bgr)),
                          ("YOLOv9-Kennzeichen (zweite Meinung)", bild.kennzeichen_zweitmeinung(bgr))):
        for box, s in funde:
            if _gedeckt(box, flaechen) < 0.6 and not _erlaubt(box, sichtbar):
                reste.append({"seite": 0, "rechteck": [round(v, 1) for v in box], "kategorie": "kennzeichen",
                              "pruefung": quelle, "hinweis": "Kennzeichen noch erkennbar"})
    fortschritt(0.6, "Text im Bild")
    lay = text_layout.aus_bild(rgb, faktor=1.0, min_sicherheit=55)
    reste += _text_pruefen(lay, 0, _texte(bestaetigt), sichtbar, flaechen, "Texterkennung auf dem Ergebnis")
    if schriftstueck:
        for box, kat, s in bild.unterschriften_stempel(rgb):
            if _gedeckt(box, flaechen) < 0.6 and not _erlaubt(box, sichtbar):
                reste.append({"seite": 0, "rechteck": [round(v, 1) for v in box], "kategorie": kat,
                              "pruefung": "Bildmodell auf dem Ergebnis", "hinweis": "noch erkennbar"})
    nur_ergebnis = 0
    if original is not None:
        orig = foto.laden(original)[0][..., ::-1].copy()
        im_original = {"gesicht": [b for b, _ in bild.gesichter(orig, 0.4)] + [k["kopf"] for k in bild.koepfe(orig) if k["kopf"]],
                       "kennzeichen": [b for b, _ in bild.kennzeichen_beide(orig, 0.15)]}
        behalten = []
        for r in reste:
            liste = im_original.get(r["kategorie"])
            if liste is None or any(bild.iou(tuple(r["rechteck"]), o) > 0.2 or bild.anteil_in(tuple(r["rechteck"]), o) > 0.5
                                    or bild.anteil_in(o, tuple(r["rechteck"])) > 0.5 for o in liste):
                behalten.append(r)
            else:
                nur_ergebnis += 1
        reste = behalten
    meta = []
    if roh.getexif():
        meta.append("EXIF")
    meta += [k for k in roh.info if k.lower() in ("xmp", "xml:com.adobe.xmp", "icc_profile", "comment", "photoshop",
                                                     "iptc", "description", "author")]
    if meta:
        reste.append({"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Metadaten",
                      "hinweis": "noch vorhanden: " + ", ".join(meta)})
    pruefungen = ["Gesichter (YuNet) und Augen (YOLO26-pose) erneut gesucht",
                  "Kennzeichen mit zwei unabhängigen Modellen gesucht", "Text im Bild neu gelesen",
                  "EXIF, GPS, XMP, IPTC und Farbprofil geprüft"]
    if nur_ergebnis:
        pruefungen.append(verworfen_text(nur_ergebnis))
    return {"reste": _zusammenfassen(reste), "pruefungen": pruefungen, "geprueft": {"bilder": 1}, "nur_ergebnis": nur_ergebnis}


def video_pruefen(pfad, bestaetigt: list[dict], sichtbar_st: list[dict], spuren: dict, jedes: int = 1,
                  fortschritt=lambda a, t: None, original=None) -> dict:
    """Jedes Einzelbild des Ergebnisses: Gesichter (YuNet) und Kennzeichen (zwei Modelle). Ein Fund außerhalb der
    deckenden Flächen ist ein Rest, wenn an derselben Stelle im Original ebenfalls etwas erkannt wird. Findet ein
    Modell etwas nur im Ergebnis, hat die deckende Fläche selbst den Fund ausgelöst (eine dunkle, abgerundete Fläche
    sieht für ein Kennzeichen-Modell manchmal wie ein Kennzeichen aus); solche Funde werden gezählt, sperren aber nicht."""
    i = video.info(pfad)
    cap = cv2.VideoCapture(str(pfad))
    cap_o = cv2.VideoCapture(str(original)) if original else None
    reste, nur_ergebnis = [], 0
    nr = geprueft = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_o = cap_o.read()[1] if cap_o is not None else None
        if nr % jedes == 0:
            geprueft += 1
            flaechen = []
            for art, f in video.fuellungen(spuren, bestaetigt, nr):
                if art == "umriss":
                    a = np.array(f)
                    flaechen.append((a[:, 0].min(), a[:, 1].min(), a[:, 0].max(), a[:, 1].max()))
                else:
                    flaechen.append(tuple(f))
            flaechen = _vorhanden(frame, flaechen, [foto.FUELLUNG_FOTO[::-1]])
            sichtbar = []
            for s in sichtbar_st:
                sp = spuren.get(s.get("spur") or "", {})
                b = sp.get("boxen", {}).get(str(nr))
                if b:
                    sichtbar.append(bild.erweitern(tuple(b), 0.2, 10**5, 10**5))
            kandidaten = []
            for box, s in bild.gesichter(frame):
                if _gedeckt(box, flaechen) < 0.6 and not _erlaubt(box, sichtbar):
                    kandidaten.append((box, "gesicht", "Gesichter (YuNet) je Einzelbild", "Gesicht noch erkennbar"))
            for quelle, funde in (("YOLO26-Kennzeichen", bild.kennzeichen(frame)),
                                  ("YOLOv9-Kennzeichen (zweite Meinung)", bild.kennzeichen_zweitmeinung(frame))):
                for box, s in funde:
                    if _gedeckt(box, flaechen) < 0.6 and not _erlaubt(box, sichtbar):
                        kandidaten.append((box, "kennzeichen", quelle, "Kennzeichen noch erkennbar"))
            if kandidaten and frame_o is not None:
                im_original = {"gesicht": [b for b, _ in bild.gesichter(frame_o, 0.4)],
                               "kennzeichen": [b for b, _ in bild.kennzeichen_beide(frame_o, 0.15)]}
                behalten = []
                for k in kandidaten:
                    if any(bild.iou(k[0], o) > 0.2 or bild.anteil_in(k[0], o) > 0.5 or bild.anteil_in(o, k[0]) > 0.5
                           for o in im_original[k[1]]):
                        behalten.append(k)
                    else:
                        nur_ergebnis += 1
                kandidaten = behalten
            for box, kat, quelle, hinweis in kandidaten:
                reste.append({"bild": nr, "zeit": round(nr / i["fps"], 2), "rechteck": [round(float(v), 1) for v in box],
                              "kategorie": kat, "pruefung": quelle, "hinweis": hinweis})
        nr += 1
        if nr % 10 == 0:
            fortschritt(nr / max(1, i["bilder"]), f"Einzelbild {nr} von {i['bilder']}")
    cap.release()
    if cap_o is not None:
        cap_o.release()
    if i["ton"]:
        reste.append({"bild": None, "zeit": None, "rechteck": None, "kategorie": "ton", "pruefung": "Tonspur",
                      "hinweis": "Tonspur noch vorhanden"})
    if i["tags"]:
        reste.append({"bild": None, "zeit": None, "rechteck": None, "kategorie": "metadaten",
                      "pruefung": "Metadaten", "hinweis": "noch vorhanden: " + ", ".join(i["tags"])})
    pruefungen = [f"{geprueft} von {nr} Einzelbildern auf Gesichter geprüft (YuNet)",
                  f"{geprueft} Einzelbilder mit zwei unabhängigen Kennzeichen-Modellen geprüft",
                  "Tonspur und Metadaten der Videodatei geprüft"]
    if nur_ergebnis:
        pruefungen.append(verworfen_text(nur_ergebnis))
    return {"reste": reste, "pruefungen": pruefungen, "geprueft": {"bilder": geprueft, "von": nr},
            "nur_ergebnis": nur_ergebnis, "reste_spuren": _spuren_der_reste(reste)}


def verworfen_text(n: int) -> str:
    """Funde, die nur im Ergebnis auftauchen, sperren nicht; die Oberfläche und der Bericht nennen die Regel genau."""
    return (f"{n} Fund{'e' if n != 1 else ''} nicht als Rest gezählt: Gesicht oder Kennzeichen im Ergebnis, das im "
            "Original an derselben Stelle nicht erkannt wird (meist hält ein Modell eine deckende Fläche selbst dafür)")


def _zusammenfassen(reste: list[dict]) -> list[dict]:
    out = []
    for r in reste:
        if r.get("rechteck") and any(o.get("rechteck") and o["kategorie"] == r["kategorie"] and
                                     bild.iou(tuple(o["rechteck"]), tuple(r["rechteck"])) > 0.4 for o in out):
            continue
        out.append(r)
    return out


def _spuren_der_reste(reste: list[dict]) -> list[dict]:
    """Reste im Video zu zusammenhängenden Stücken bündeln (für Bericht und Oberfläche)."""
    v = video.Verfolger(0.1)
    je_bild: dict[int, list] = {}
    for r in reste:
        if r.get("bild") is not None:
            je_bild.setdefault(r["bild"], []).append((tuple(r["rechteck"]), 1.0))
    for nr in sorted(je_bild):
        v.schritt(nr, je_bild[nr])
    out = []
    for s in v.spuren:
        nrn = sorted(s["bilder"])
        out.append({"von_bild": nrn[0], "bis_bild": nrn[-1], "bilder": len(nrn), "rechteck": list(s["bilder"][nrn[0]])})
    return out
