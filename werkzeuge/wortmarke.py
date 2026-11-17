"""Erzeugt die Wortmarke: „unkenntlich“ in Kleinbuchstaben, deren Ende in Pixelquadrate zerfällt.

    python werkzeuge/wortmarke.py <AlbertSans[wght].ttf>

Schreibt unkenntlich/web/bilder/wortmarke.svg (Farben über CSS: currentColor und --akzent) und
medien/wortmarke-hell.svg / medien/wortmarke-dunkel.svg (feste Farben, für README und Bericht).
Buchstaben als Pfade, keine Schrift nötig. Zufall mit festem Startwert, das Ergebnis ist immer gleich.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageDraw, ImageFont

WORT = "unkenntlich"
GEWICHT = 640
GROESSE = 100           # Einheiten der SVG-Fläche je em
ZERFALL_AB = "unkenntl"  # bis hierher klare Buchstaben; „ich“ zerfällt
ZELLE = 5.0             # Kantenlänge eines Pixelquadrats in SVG-Einheiten


def pfade(schrift: Path):
    font = instantiateVariableFont(TTFont(schrift), {"wght": GEWICHT})
    cmap = font.getBestCmap()
    glyphen = font.getGlyphSet()
    upm = font["head"].unitsPerEm
    skala = GROESSE / upm
    asc = font["hhea"].ascent * skala
    x = 0.0
    teile = []
    for z in WORT:
        name = cmap[ord(z)]
        pen = SVGPathPen(glyphen)
        glyphen[name].draw(TransformPen(pen, (skala, 0, 0, -skala, x, asc)))
        teile.append((z, x, pen.getCommands()))
        x += glyphen[name].width * skala
    hoehe = (font["hhea"].ascent - font["hhea"].descent) * skala
    return teile, x, hoehe, asc


def raster(schrift: Path, breite: float, hoehe: float, asc: float):
    """Dieselben Buchstaben gerastert, eine Zelle = ZELLE Einheiten."""
    faktor = 8
    f = ImageFont.truetype(str(schrift), int(GROESSE * faktor))
    f.set_variation_by_axes([GEWICHT])
    b = Image.new("L", (int(breite * faktor) + 8, int(hoehe * faktor) + 8), 0)
    ImageDraw.Draw(b).text((0, asc * faktor), WORT, font=f, fill=255, anchor="ls")
    zellen = []
    s = int(ZELLE * faktor)
    for j in range(0, b.height - s, s):
        for i in range(0, b.width - s, s):
            ausschnitt = b.crop((i, j, i + s, j + s))
            if sum(ausschnitt.tobytes()) / (s * s * 255) > 0.45:
                zellen.append((i / faktor, j / faktor))
    return zellen


def bauen(schrift: Path, ziel: Path) -> None:
    teile, breite, hoehe, asc = pfade(schrift)
    grenze = sum(1 for _ in ZERFALL_AB)
    x_klar = teile[grenze][1]  # Beginn von „i“
    rng = random.Random(11)
    quadrate = []
    for (x, y) in raster(schrift, breite, hoehe, asc):
        if x + ZELLE <= x_klar:
            continue
        t = (x - x_klar) / max(1.0, breite - x_klar)          # 0 am Beginn des Zerfalls, 1 am Ende
        if rng.random() < 0.08 + 0.42 * t:                     # nach rechts fallen mehr Zellen aus
            continue
        dx = (t ** 1.6) * rng.uniform(4, 22)                    # und wandern nach rechts oben
        dy = -(t ** 1.6) * rng.uniform(0, 8)
        quadrate.append((x + dx, y + dy, max(0.35, 1 - 0.55 * t)))
    # ein paar lose Zellen weiter rechts
    for _ in range(9):
        t = rng.uniform(0.75, 1.0)
        quadrate.append((breite + rng.uniform(0, 26), asc - rng.uniform(10, 60), rng.uniform(0.25, 0.6)))
    gesamt_breite = breite + 30
    klar = "".join(c for z, _x, c in teile[:grenze])
    rechtecke = "".join(f'<rect x="{x:.1f}" y="{y:.1f}" width="{ZELLE * 0.86:.2f}" height="{ZELLE * 0.86:.2f}" '
                        f'rx="0.6" opacity="{o:.2f}"/>' for x, y, o in quadrate)
    for name, farbe_text, farbe_akzent in (("web", "currentColor", "var(--akzent, #0b5866)"),
                                           ("hell", "#14191c", "#0b5866"), ("dunkel", "#e8eef0", "#5fb3c0")):
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 {-4:.0f} {gesamt_breite:.1f} {hoehe:.1f}" '
               f'role="img" aria-label="unkenntlich"><title>unkenntlich</title>'
               f'<path d="{klar}" fill="{farbe_text}"/><g fill="{farbe_akzent}">{rechtecke}</g></svg>')
        orte = [ziel / "unkenntlich" / "web" / "bilder" / ("wortmarke.svg" if name == "web" else f"wortmarke-{name}.svg")]
        if name != "web":
            orte.append(ziel / "medien" / f"wortmarke-{name}.svg")
        for p in orte:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(svg)
            print(p, len(svg), "Byte")


if __name__ == "__main__":
    bauen(Path(sys.argv[1]), Path(__file__).resolve().parent.parent)
