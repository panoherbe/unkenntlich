"""PDF-Dokumente, digital oder gescannt: Vorschläge finden, Stellen wirklich entfernen, Metadaten leeren.

Koordinaten sind PDF-Punkte (1/72 Zoll) der jeweiligen Seite, Ursprung oben links (wie PyMuPDF).
"""
from __future__ import annotations

import numpy as np
import pymupdf

from . import bild, text_erkennen, text_layout

OCR_DPI = 300
BILD_DPI = 150
RAND = 1.2  # Punkte Zugabe um jeden Textbalken


def seite_als_bild(seite, dpi: int) -> np.ndarray:
    pix = seite.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, 3).copy()


def ist_scan(seite) -> bool:
    flaeche = abs(seite.rect)
    bilder = sum(abs(pymupdf.Rect(i["bbox"]) & seite.rect) for i in seite.get_image_info())
    return bilder >= 0.5 * flaeche or not seite.get_text().strip()


def metadaten_inventar(doc) -> list[dict]:
    """Was ein PDF außer dem sichtbaren Inhalt mitträgt; der Wert selbst wird nie gespeichert."""
    funde = []
    namen = {"author": "Autor", "title": "Titel", "subject": "Betreff", "keywords": "Stichwörter",
             "creator": "Erstellt mit", "producer": "Hersteller", "creationDate": "Erstellt am",
             "modDate": "Geändert am"}
    for k, n in namen.items():
        if (doc.metadata or {}).get(k):
            funde.append({"feld": n, "art": "Dokumentinfo"})
    if doc.get_xml_metadata().strip():
        funde.append({"feld": "XMP-Metadaten", "art": "Dokumentinfo"})
    if doc.embfile_count():
        funde.append({"feld": f"{doc.embfile_count()} Dateianhang/-anhänge", "art": "Anhang"})
    anm = sum(1 for s in doc for a in s.annots() or [])
    if anm:
        funde.append({"feld": f"{anm} Anmerkung(en)", "art": "Anmerkung"})
    felder = sum(1 for s in doc for w in s.widgets() or [])
    if felder:
        funde.append({"feld": f"{felder} Formularfeld(er)", "art": "Formular"})
    if any(s.get_links() for s in doc):
        funde.append({"feld": "Verknüpfungen", "art": "Verknüpfung"})
    if doc.get_toc():
        funde.append({"feld": "Lesezeichen", "art": "Gliederung"})
    return funde


def _rechteck_plus(r, rand=RAND):
    return [round(r[0] - rand, 2), round(r[1] - rand * 0.6, 2), round(r[2] + rand, 2), round(r[3] + rand * 0.6, 2)]


def text_stellen(layout: text_layout.Layout, seite_nr: int, quelle_zusatz: str = "") -> list[dict]:
    stellen = []
    for f in text_erkennen.finde_alles(layout.text):
        rechtecke = layout.rechtecke(f.start, f.ende)
        if not rechtecke:
            continue
        stellen.append({"kategorie": f.kategorie, "grund": f.grund, "quelle": f.quelle + quelle_zusatz,
                        "sicherheit": round(f.sicherheit, 3), "seite": seite_nr,
                        "rechtecke": [_rechteck_plus(r) for r in rechtecke],
                        "text": layout.woerter_von(f.start, f.ende)})
    return stellen


def _gleich(a: dict, b: dict) -> bool:
    if a["seite"] != b["seite"]:
        return False
    for ra in a["rechtecke"]:
        for rb in b["rechtecke"]:
            if bild.iou(tuple(ra), tuple(rb)) > 0.25 or bild.anteil_in(tuple(ra), tuple(rb)) > 0.6 \
                    or bild.anteil_in(tuple(rb), tuple(ra)) > 0.6:
                return True
    return False


def zusammenlegen(stellen: list[dict]) -> list[dict]:
    """Doppelte Vorschläge (Textschicht und Texterkennung derselben Stelle) zu einem machen."""
    out: list[dict] = []
    for s in stellen:
        gleiche = next((o for o in out if _gleich(o, s) and (o["kategorie"] == s["kategorie"]
                                                             or {o["kategorie"], s["kategorie"]} <= {"name", "anschrift"})), None)
        if gleiche is None:
            out.append(s)
            continue
        for r in s["rechtecke"]:
            if not any(bild.anteil_in(tuple(r), tuple(q)) > 0.8 for q in gleiche["rechtecke"]):
                gleiche["rechtecke"].append(r)
        if s["quelle"] not in gleiche["quelle"]:
            gleiche["quelle"] += " · " + s["quelle"]
    return out


NICHT_NAMEN = {"Frau", "Herr", "Herrn", "Familie", "Sehr", "Geehrte", "Geehrter", "Guten", "Tag", "Personalabteilung"}


def weitere_vorkommen(layouts: dict[int, list], stellen: list[dict]) -> list[dict]:
    """Jeder vorgeschlagene Name wird im ganzen Dokument gesucht, auch als Nachname allein („Frau Albers“)."""
    import re
    teile = set()
    for s in stellen:
        if s["kategorie"] == "name" and s.get("text"):
            for t in re.findall(r"[A-ZÄÖÜ][\wäöüßıçğşé\-]{2,}", s["text"]):
                if t not in NICHT_NAMEN:
                    teile.add(t)
    neu = []
    for nr, liste in layouts.items():
        for layout in liste:
            for t in sorted(teile):
                for m in re.finditer(rf"(?<![\wäöüß]){re.escape(t)}(?![\wäöüß])", layout.text):
                    for r in layout.rechtecke(m.start(), m.end()):
                        r = _rechteck_plus(r)
                        if any(x["seite"] == nr and any(bild.anteil_in(tuple(r), tuple(q)) > 0.5 for q in x["rechtecke"])
                               for x in stellen + neu):
                            continue
                        # Der Grund nennt den Namen nicht: Er steht im Prüfbericht, der keine Daten enthalten darf.
                        neu.append({"kategorie": "name", "grund": "Weiteres Vorkommen eines vorgeschlagenen Namens",
                                    "quelle": "Abgleich",
                                    "sicherheit": 1.0, "seite": nr, "rechtecke": [r], "text": t})
    return neu


def analysieren(pfad, fortschritt=lambda anteil, text: None) -> dict:
    doc = pymupdf.open(pfad)
    seiten, stellen, layouts = [], [], {}
    n = len(doc)
    for nr, seite in enumerate(doc):
        fortschritt(nr / n, f"Seite {nr + 1} von {n}: Text")
        scan = ist_scan(seite)
        lay = text_layout.aus_pdf_seite(seite)
        layouts[nr] = [lay]
        kandidaten = text_stellen(lay, nr, " (Textschicht)")
        if scan:
            fortschritt((nr + 0.3) / n, f"Seite {nr + 1} von {n}: Texterkennung")
            pixel = seite_als_bild(seite, OCR_DPI)
            lay = text_layout.aus_bild(pixel, faktor=72 / OCR_DPI)
            layouts[nr].append(lay)
            kandidaten += text_stellen(lay, nr, " (Texterkennung)")
        fortschritt((nr + 0.7) / n, f"Seite {nr + 1} von {n}: Unterschriften, Stempel, Gesichter")
        pixel = seite_als_bild(seite, BILD_DPI)
        f = 72 / BILD_DPI
        for box, kat, s in bild.unterschriften_stempel(pixel):
            kandidaten.append({"kategorie": kat, "grund": "Bildmodell erkennt " + ("eine Unterschrift" if kat ==
                               "unterschrift" else "einen Stempel"), "quelle": "RF-DETR", "sicherheit": round(s, 3),
                               "seite": nr, "rechtecke": [[round(v * f, 2) for v in bild.erweitern(box, 0.06, *pixel.shape[1::-1])]],
                               "text": None})
        for box, s in bild.gesichter(pixel[..., ::-1].copy()):
            kandidaten.append({"kategorie": "gesicht", "grund": "Gesicht im Dokument (z. B. Passbild)",
                               "quelle": "YuNet", "sicherheit": round(s, 3), "seite": nr,
                               "rechtecke": [[round(v * f, 2) for v in bild.erweitern(box, 0.25, *pixel.shape[1::-1], oben=0.1)]],
                               "text": None})
        stellen += zusammenlegen(kandidaten)
        seiten.append({"breite": round(seite.rect.width, 2), "hoehe": round(seite.rect.height, 2), "scan": scan,
                       "geprueft": False})
    stellen += zusammenlegen(weitere_vorkommen(layouts, stellen))
    fortschritt(1.0, "fertig")
    return {"seiten": seiten, "stellen": stellen, "metadaten": metadaten_inventar(doc)}


def vorschau(pfad, seite_nr: int, dpi: int = 110) -> bytes:
    doc = pymupdf.open(pfad)
    return doc[seite_nr].get_pixmap(dpi=dpi, alpha=False).tobytes("png")


def anmerkungen_loeschen(seite) -> int:
    """Alle Anmerkungen (Notiz, Freitext, Hervorhebung, Stempel, Dateianhang …) und Formularfelder einer Seite
    löschen. Sie liegen nicht im Seiteninhalt, darum entfernt das Schwärzen sie nicht, und sie können Namen tragen."""
    n = 0
    w = seite.first_widget
    while w:
        w = seite.delete_widget(w)
        n += 1
    a = seite.first_annot
    while a:
        a = seite.delete_annot(a)
        n += 1
    return n


def schwaerzen(eingang, ausgang, stellen: list[dict], nur_ueberdecken: bool = False, neu_aufbauen: bool = False) -> dict:
    """Bestätigte Stellen wirklich entfernen: Text unter dem Balken, Bildpunkte darunter, Vektorgrafik, die er
    überdeckt; dann Anmerkungen, Formularfelder, Lesezeichen, Metadaten, XMP, Anhänge, Verknüpfungen und Skripte
    löschen und ohne alte Versionen neu schreiben.

    `neu_aufbauen=True` ist der Ausweg für Reste ohne Ort (etwa Metadaten, die sich nicht löschen lassen): Jede Seite
    wird danach als Bild in ein neues, leeres PDF gesetzt, ohne Textschicht und ohne alles, was nicht sichtbar ist.

    `nur_ueberdecken=True` ist nur für den Kontrollversuch der Messung: schwarze Kästen über den Text gemalt, wie es
    bei missglückten Schwärzungen passiert. Die Gegenprobe muss das finden."""
    doc = pymupdf.open(eingang)
    je_seite: dict[int, list] = {}
    for s in stellen:
        je_seite.setdefault(s["seite"], []).extend(s["rechtecke"])
    for nr, rechtecke in je_seite.items():
        seite = doc[nr]
        for r in rechtecke:
            if nur_ueberdecken:
                seite.draw_rect(pymupdf.Rect(r), color=(0, 0, 0), fill=(0, 0, 0))
            else:
                seite.add_redact_annot(pymupdf.Rect(r), fill=(0, 0, 0))
        if not nur_ueberdecken:
            seite.apply_redactions(images=pymupdf.PDF_REDACT_IMAGE_PIXELS,
                                   graphics=pymupdf.PDF_REDACT_LINE_ART_REMOVE_IF_COVERED,
                                   text=pymupdf.PDF_REDACT_TEXT_REMOVE)
    if not nur_ueberdecken:
        for seite in doc:
            anmerkungen_loeschen(seite)
        doc.scrub(attached_files=True, clean_pages=True, embedded_files=True, hidden_text=False, javascript=True,
                  metadata=True, redactions=False, redact_images=0, remove_links=True, reset_fields=True,
                  reset_responses=True, thumbnails=True, xml_metadata=True)
        if doc.get_toc():
            doc.set_toc([])
        doc.set_metadata({})
        doc.del_xml_metadata()
    if neu_aufbauen and not nur_ueberdecken:
        return als_bilder_neu(doc, ausgang)
    doc.save(ausgang, garbage=4, deflate=True, clean=True)
    return {"seiten": len(doc)}


def als_bilder_neu(doc, ausgang, dpi: int = 200) -> dict:
    """Jede Seite als Bild (ohne Anmerkungen) in ein neues PDF: keine Textschicht, keine Metadaten, keine Anhänge,
    keine Formulare, keine Lesezeichen. Was danach im PDF steht, ist nur noch, was man sieht."""
    neu = pymupdf.open()
    for seite in doc:
        pix = seite.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csRGB, annots=False)
        ziel = neu.new_page(width=seite.rect.width, height=seite.rect.height)
        ziel.insert_image(ziel.rect, stream=pix.tobytes("jpg", jpg_quality=88))
    neu.set_metadata({})
    neu.del_xml_metadata()
    neu.save(ausgang, garbage=4, deflate=True, clean=True)
    return {"seiten": len(neu), "neu_aufgebaut": True}
