"""Text mit Wortpositionen: aus der Textschicht eines PDFs oder aus der Texterkennung (Tesseract).

Beide liefern dieselbe Form: eine Liste von Wörtern mit Rechteck, daraus ein Fließtext mit Zeilenumbrüchen und
die Zuordnung Zeichen → Wort. So lässt sich jeder Textfund auf Rechtecke zurückführen (je Zeile eines).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Wort:
    text: str
    rechteck: tuple[float, float, float, float]
    zeile: tuple  # Schlüssel der Zeile (Block, Absatz, Zeile)
    sicherheit: float = 100.0


@dataclass
class Layout:
    woerter: list[Wort]
    text: str = ""
    zeichen_wort: list[int] = field(default_factory=list)  # je Zeichen der Index des Wortes oder -1

    def aufbauen(self) -> "Layout":
        """Fließtext; ein großer waagrechter Abstand in einer Zeile (zwei Spalten, z. B. Anschrift links und
        Infoblock rechts) zählt als Zeilenwechsel, damit Muster nicht über Spalten hinweg greifen."""
        teile, zuordnung = [], []
        vorige_zeile, vorige_box = None, None
        for i, w in enumerate(self.woerter):
            if vorige_zeile is not None:
                hoehe = max(1.0, w.rechteck[3] - w.rechteck[1])
                luecke = w.rechteck[0] - vorige_box[2]
                gleiche = w.zeile == vorige_zeile and -hoehe < luecke < 2.5 * hoehe
                trenner = " " if gleiche else "\n"
                teile.append(trenner)
                zuordnung.append(-1)
            teile.append(w.text)
            zuordnung.extend([i] * len(w.text))
            vorige_zeile, vorige_box = w.zeile, w.rechteck
        self.text = "".join(teile)
        self.zeichen_wort = zuordnung
        return self

    def rechtecke(self, start: int, ende: int) -> list[tuple[float, float, float, float]]:
        """Rechtecke (eines je Zeile) für den Zeichenbereich [start, ende)."""
        idx = sorted({self.zeichen_wort[i] for i in range(start, min(ende, len(self.zeichen_wort)))
                      if self.zeichen_wort[i] >= 0})
        je_zeile: dict = {}
        for i in idx:
            w = self.woerter[i]
            je_zeile.setdefault(w.zeile, []).append(w.rechteck)
        out = []
        for r in je_zeile.values():
            a = np.array(r)
            out.append((float(a[:, 0].min()), float(a[:, 1].min()), float(a[:, 2].max()), float(a[:, 3].max())))
        return out

    def woerter_von(self, start: int, ende: int) -> str:
        idx = sorted({self.zeichen_wort[i] for i in range(start, min(ende, len(self.zeichen_wort)))
                      if self.zeichen_wort[i] >= 0})
        return " ".join(self.woerter[i].text for i in idx)


def aus_pdf_seite(seite) -> Layout:
    """Wörter der Textschicht (auch unsichtbarer Text, z. B. die Texterkennung eines Scanners)."""
    woerter = []
    for x0, y0, x1, y1, t, block, zeile, _nr in seite.get_text("words", sort=True):
        if t.strip():
            woerter.append(Wort(t, (x0, y0, x1, y1), (block, zeile)))
    return Layout(woerter).aufbauen()


def aus_bild(bild_rgb: np.ndarray, faktor: float = 1.0, min_sicherheit: float = 30.0, psm: int = 3) -> Layout:
    """Texterkennung mit Tesseract (Deutsch). `faktor` rechnet Pixel in die Zielkoordinaten um (z. B. PDF-Punkte)."""
    import pytesseract
    from PIL import Image

    daten = pytesseract.image_to_data(Image.fromarray(bild_rgb), lang="deu", config=f"--psm {psm}",
                                      output_type=pytesseract.Output.DICT)
    woerter = []
    for i, t in enumerate(daten["text"]):
        t = (t or "").strip()
        conf = float(daten["conf"][i])
        if not t or conf < min_sicherheit:
            continue
        x, y, b, h = daten["left"][i], daten["top"][i], daten["width"][i], daten["height"][i]
        woerter.append(Wort(t, (x * faktor, y * faktor, (x + b) * faktor, (y + h) * faktor),
                            (daten["block_num"][i], daten["par_num"][i], daten["line_num"][i]), conf))
    return Layout(woerter).aufbauen()


def tesseract_version() -> str:
    import pytesseract
    try:
        return str(pytesseract.get_tesseract_version())
    except Exception:  # pragma: no cover
        return os.environ.get("TESSERACT_VERSION", "?")
