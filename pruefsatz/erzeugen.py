"""Erzeugt den Prüfsatz der Dokumente: zwölf erfundene deutsche Schreiben (simuliert), dazu die Wahrheit je Datei.

    docker run --rm --network none -u "$(id -u):$(id -g)" -v "$PWD":/app -w /app unkenntlich:0.2.0 python pruefsatz/erzeugen.py

Alle Personen, Anschriften, Nummern, Unterschriften und Stempel sind erfunden (Zufallsgenerator mit festem Startwert);
IBAN und Steuer-ID haben gültig gerechnete Prüfziffern, damit die Regeln greifen können. Bankleitzahlen beginnen mit 0
oder 9 (diese Bereiche sind keiner Bank zugeteilt), Rufnummern stammen aus den Bereichen, die die Bundesnetzagentur für
Medien freihält (Mitteilung 148/2021, „Drama Numbers“). Sechs Schreiben sind digitale
PDFs, vier simulierte Scans (zwei davon mit unsichtbarer Textschicht wie aus einem Scanner mit Texterkennung), zwei
Fotos eines Schreibens (JPG). `wahrheit.json` nennt je Datei und Seite jede eingesetzte Angabe mit Kategorie und
Rechteck in PDF-Punkten bzw. Pixeln. Lizenz der erzeugten Dateien: CC0 1.0.
"""
from __future__ import annotations

import io
import json
import math
import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image, ImageDraw, ImageFont

HIER = Path(__file__).resolve().parent
SCHRIFTEN = HIER / "schriften"
ZIEL = HIER / "dokumente"
MM = 72 / 25.4
DPI_SCAN = 200
START = 20261116

VORNAMEN_W = ["Jana", "Svenja", "Mira", "Leonie", "Katrin", "Aylin", "Greta", "Ronja", "Nadine", "Petra"]
VORNAMEN_M = ["Jonas", "Malte", "Deniz", "Florian", "Henrik", "Tobias", "Arne", "Lukas", "Mehmet", "Bernd"]
NACHNAMEN = ["Brackmann", "Oltrogge", "Wiesenthal", "Kaltenbach", "Rosendahl", "Steinbrink", "Hollmann",
             "Dreesen", "Lindqvist", "Marquardt", "Tegtmeyer", "Albers", "Kühnel", "Yıldız", "Sanders"]
STRASSEN = ["Lindenstraße", "Am Kirchberg", "Gartenweg", "Birkenallee", "Mühlenstraße", "Hafenstraße",
            "Rosenweg", "Feldstraße", "Schulstraße", "Ahornring"]
ORTE = [("Musterhausen", "12345"), ("Beispielstadt", "54321"), ("Neudorf am Feld", "24680"),
        ("Talheim", "13579"), ("Waldhagen", "97531")]


# --- erfundene Nummern mit gültigen Prüfziffern ------------------------------------------------------------------

def iban(rng: random.Random) -> str:
    # Die erste Ziffer der Bankleitzahl ist das Clearinggebiet (1 bis 8); 0 und 9 sind keiner Bank zugeteilt.
    blz = rng.choice("09") + "".join(str(rng.randint(0, 9)) for _ in range(7))
    konto = "".join(str(rng.randint(0, 9)) for _ in range(10))
    bban = blz + konto
    zahl = int(bban + "131400")  # D=13, E=14, 00
    pruef = 98 - zahl % 97
    s = f"DE{pruef:02d}{bban}"
    return " ".join(s[i:i + 4] for i in range(0, len(s), 4))


def steuer_id(rng: random.Random) -> str:
    while True:
        ziffern = [rng.randint(1, 9)] + [rng.randint(0, 9) for _ in range(9)]
        zehn = "".join(map(str, ziffern))
        haeufig = sorted((zehn.count(z) for z in set(zehn)), reverse=True)
        if haeufig[0] not in (2, 3) or sum(1 for h in haeufig if h > 1) != 1:
            continue
        produkt = 10
        for z in zehn:
            summe = (int(z) + produkt) % 10 or 10
            produkt = (summe * 2) % 11
        s = zehn + str((11 - produkt) % 10)
        return f"{s[:2]} {s[2:5]} {s[5:8]} {s[8:]}"


# Rufnummern für Medienproduktionen der Bundesnetzagentur (Mitteilung 148/2021): dauerhaft niemandem zugeteilt.
FESTNETZ = ["030 23125", "069 90009", "040 66969", "0221 4710", "089 99998"]   # je 000 bis 999
MOBIL = ["0171 39200", "0176 040690"]                                         # je 00 bis 99


def telefon(rng: random.Random, mobil: bool = False) -> str:
    if mobil:
        block = rng.choice(MOBIL)
        return f"{block[:4]} {block[5:]}{rng.randint(0, 99):02d}"
    return f"{rng.choice(FESTNETZ)} {rng.randint(200, 999)}"


def kennzeichen(rng: random.Random) -> str:
    return f"{rng.choice(['XZ', 'QM', 'YJ'])}-{rng.choice('ABCDEFGHKLMNPRSTUVWZ')}{rng.choice('ABCDEFGHKLMNPRSTUVWZ')} {rng.randint(10, 9999)}"


def person(rng: random.Random, weiblich: bool) -> dict:
    vor = rng.choice(VORNAMEN_W if weiblich else VORNAMEN_M)
    nach = rng.choice(NACHNAMEN)
    ort, plz = rng.choice(ORTE)
    return {"vorname": vor, "nachname": nach, "name": f"{vor} {nach}", "anrede": "Frau" if weiblich else "Herr",
            "strasse": f"{rng.choice(STRASSEN)} {rng.randint(1, 120)}{rng.choice(['', '', 'a', 'b'])}",
            "plz_ort": f"{plz} {ort}", "geb": f"{rng.randint(1, 28):02d}.{rng.randint(1, 12):02d}.{rng.randint(1948, 2004)}",
            "iban": iban(rng), "steuer_id": steuer_id(rng), "telefon": telefon(rng),
            "mobil": telefon(rng, True), "email": f"{vor.lower()}.{nach.lower().replace('ı', 'i')}@example.org"
            .replace("ü", "ue").replace("ö", "oe").replace("ä", "ae"), "kennzeichen": kennzeichen(rng)}


# --- Unterschrift und Stempel als Bild ---------------------------------------------------------------------------

def unterschrift_png(text: str, schrift: str, rng: random.Random) -> bytes:
    f = ImageFont.truetype(str(SCHRIFTEN / schrift), 120)
    w = int(f.getlength(text)) + 120
    bild = Image.new("RGBA", (w, 230), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    tinte = rng.choice([(28, 52, 140, 235), (20, 30, 60, 235), (30, 70, 160, 225)])
    d.text((40, 30), text, font=f, fill=tinte)
    # Schwung unter dem Namen
    pts = [(40 + i * (w - 80) / 30, 185 + 14 * math.sin(i / 4.2 + rng.random())) for i in range(31)]
    d.line(pts, fill=tinte, width=5)
    bild = bild.rotate(rng.uniform(-6, 4), resample=Image.BICUBIC, expand=True)
    bild = bild.crop(bild.getchannel("A").getbbox())
    out = io.BytesIO()
    bild.save(out, "PNG")
    return out.getvalue()


def _tinte(bild: Image.Image, rng: random.Random, fleck: float = 0.10) -> Image.Image:
    """Stempelfarbe ungleichmäßig: einzelne Stellen blasser, Ränder leicht ausgefranst."""
    a = np.array(bild)
    zufall = np.random.default_rng(rng.randint(0, 10**6))
    maske = zufall.random(a.shape[:2]) < fleck
    a[..., 3][maske] = (a[..., 3][maske] * 0.45).astype(np.uint8)
    wolke = cv2.GaussianBlur(zufall.random(a.shape[:2]).astype(np.float32), (0, 0), 18)
    wolke = (wolke - wolke.min()) / max(1e-6, wolke.max() - wolke.min())
    a[..., 3] = (a[..., 3] * (0.55 + 0.45 * wolke)).astype(np.uint8)
    return Image.fromarray(a)


def stempel_png(oben: str, mitte: str, farbe: tuple, rng: random.Random) -> bytes:
    """Rundes Dienstsiegel: doppelter Ring, Umschrift, Mitte mit Kürzel und Stern."""
    groesse = 600
    bild = Image.new("RGBA", (groesse, groesse), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    c = groesse / 2
    d.ellipse((10, 10, groesse - 10, groesse - 10), outline=farbe, width=18)
    d.ellipse((128, 128, groesse - 128, groesse - 128), outline=farbe, width=10)
    f = ImageFont.truetype(str(SCHRIFTEN / "IBMPlexSerif-Bold.ttf"), 64)
    winkel_gesamt = 300
    for i, z in enumerate(oben):
        w = math.radians(-90 - winkel_gesamt / 2 + winkel_gesamt * (i + 0.5) / len(oben))
        r = c - 72
        x, y = c + r * math.cos(w), c + r * math.sin(w)
        zeichen = Image.new("RGBA", (96, 96), (0, 0, 0, 0))
        ImageDraw.Draw(zeichen).text((48, 48), z, font=f, fill=farbe, anchor="mm")
        zeichen = zeichen.rotate(-math.degrees(w) - 90, resample=Image.BICUBIC)
        bild.alpha_composite(zeichen, (int(x - 48), int(y - 48)))
    f2 = ImageFont.truetype(str(SCHRIFTEN / "IBMPlexSerif-Bold.ttf"), 78)
    d.text((c, c - 10), mitte, font=f2, fill=farbe, anchor="mm")
    d.text((c, c + 70), "★", font=ImageFont.truetype(str(SCHRIFTEN / "IBMPlexSans[wdth,wght].ttf"), 60), fill=farbe,
           anchor="mm")
    bild = _tinte(bild, rng).rotate(rng.uniform(-14, 14), resample=Image.BICUBIC)
    bild = bild.crop(bild.getchannel("A").getbbox())
    out = io.BytesIO()
    bild.save(out, "PNG")
    return out.getvalue()


def firmenstempel_png(zeilen: list[str], farbe: tuple, rng: random.Random) -> bytes:
    """Rechteckiger Firmenstempel mit Rahmen, vier Zeilen."""
    f1 = ImageFont.truetype(str(SCHRIFTEN / "IBMPlexSans[wdth,wght].ttf"), 62)
    f2 = ImageFont.truetype(str(SCHRIFTEN / "IBMPlexSans[wdth,wght].ttf"), 44)
    breite = int(max(f1.getlength(zeilen[0]), *(f2.getlength(z) for z in zeilen[1:]))) + 80
    hoehe = 70 + 62 + 52 * (len(zeilen) - 1) + 50
    bild = Image.new("RGBA", (breite, hoehe), (0, 0, 0, 0))
    d = ImageDraw.Draw(bild)
    d.rounded_rectangle((6, 6, breite - 6, hoehe - 6), radius=14, outline=farbe, width=9)
    d.text((breite / 2, 70), zeilen[0], font=f1, fill=farbe, anchor="mm")
    for i, z in enumerate(zeilen[1:]):
        d.text((breite / 2, 140 + 52 * i), z, font=f2, fill=farbe, anchor="mm")
    bild = _tinte(bild, rng).rotate(rng.uniform(-5, 5), resample=Image.BICUBIC, expand=True)
    bild = bild.crop(bild.getchannel("A").getbbox())
    out = io.BytesIO()
    bild.save(out, "PNG")
    return out.getvalue()


# --- Vorlagen ----------------------------------------------------------------------------------------------------

CSS = """
@font-face { font-family: Serif; src: url("%(pfad)s/IBMPlexSerif-Regular.ttf"); }
@font-face { font-family: Serif; src: url("%(pfad)s/IBMPlexSerif-Bold.ttf"); font-weight: bold; }
@font-face { font-family: Sans; src: url("%(pfad)s/IBMPlexSans[wdth,wght].ttf"); }
@page { size: A4; margin: 0; }
body { margin: 0; font-family: %(schrift)s; font-size: 10.4pt; line-height: 1.42; color: #111; }
.seite { position: relative; width: 210mm; height: 297mm; page-break-after: always; overflow: hidden; }
.seite:last-child { page-break-after: auto; }
.kopf { position: absolute; left: 25mm; top: 16mm; right: 20mm; font-family: Sans; }
.kopf .absender-gross { font-size: 15pt; font-weight: 600; color: %(farbe)s; }
.absenderzeile { position: absolute; left: 25mm; top: 47mm; font-size: 7pt; font-family: Sans; color: #444; }
.empfaenger { position: absolute; left: 25mm; top: 52mm; width: 85mm; }
.info { position: absolute; left: 125mm; top: 50mm; width: 68mm; font-family: Sans; font-size: 8.4pt; line-height: 1.5; }
.info b { font-weight: 600; }
.text { position: absolute; left: 25mm; top: 100mm; right: 20mm; }
.text p { margin: 0 0 3.2mm 0; }
.betreff { font-weight: bold; margin-bottom: 5mm !important; }
.fuss { position: absolute; left: 25mm; right: 20mm; bottom: 12mm; font-family: Sans; font-size: 7pt; color: #555;
        border-top: 0.4pt solid #999; padding-top: 2mm; }
.zeichnung { display: flex; align-items: center; gap: 8mm; height: 26mm; margin: 1mm 0 1mm 0; }
.zeichnung img { display: block; }
.nw { white-space: nowrap; }
"""


def vorlage_bescheid(p: dict, sb: dict, az: str, rng: random.Random) -> tuple[str, list]:
    stadt, plz_stadt = "Stadt Musterhausen", "12345 Musterhausen"
    seite1 = f"""
<div class="seite">
 <div class="kopf"><div class="absender-gross">{stadt}</div><div>Bürgerbüro · Fachdienst Wohngeld</div></div>
 <div class="absenderzeile">{stadt} · Rathausplatz 1 · {plz_stadt}</div>
 <div class="empfaenger">{p['anrede']}<br>{p['name']}<br>{p['strasse']}<br>{p['plz_ort']}</div>
 <div class="info"><b>Aktenzeichen:</b> {az}<br><b>Bearbeitet von:</b> {sb['name']}<br><b>Telefon:</b> {sb['telefon']}<br>
   <b>E-Mail:</b> {sb['email']}<br><b>Datum:</b> 12.11.2026</div>
 <div class="text">
  <p class="betreff">Bewilligung von Wohngeld</p>
  <p>Sehr geehrte{'' if p['anrede'] == 'Herr' else ''} {p['anrede']} {p['nachname']},</p>
  <p>auf Ihren Antrag vom 02.10.2026 bewilligen wir Ihnen für die Zeit vom 01.11.2026 bis 31.10.2027 Wohngeld in Höhe
  von monatlich 214,00 Euro. Berücksichtigt sind Sie selbst (geboren am {p['geb']}) und die Angaben aus Ihrem Antrag.</p>
  <p>Die Zahlung erfolgt jeweils zum Monatsanfang auf Ihr Konto mit der IBAN {p['iban']}. Ihre steuerliche
  Identifikationsnummer {p['steuer_id']} haben wir für den Datenabgleich nach § 33 WoGG verwendet.</p>
  <p>Bitte teilen Sie uns Änderungen Ihres Einkommens oder Ihrer Miete unverzüglich mit. Bei Rückfragen erreichen Sie
  mich unter {sb['telefon']} oder per E-Mail an {sb['email']}. Unsere Zentrale erreichen Sie unter 069 90009 100.</p>
  <p>Mit freundlichen Grüßen<br>Im Auftrag</p>
  @@ZEICHNUNG@@
  <p>{sb['name']}</p>
 </div>
 <div class="fuss">{stadt} · Rathausplatz 1 · {plz_stadt} · www.musterhausen.example · Zentrale 069 90009 100 ·
  Stadtkasse IBAN {iban(random.Random(7))}</div>
</div>"""
    seite2 = f"""
<div class="seite">
 <div class="kopf"><div class="absender-gross">{stadt}</div></div>
 <div class="text" style="top: 40mm">
  <p class="betreff">Rechtsbehelfsbelehrung</p>
  <p>Gegen diesen Bescheid kann innerhalb eines Monats nach Bekanntgabe Widerspruch erhoben werden. Der Widerspruch ist
  schriftlich oder zur Niederschrift bei der {stadt}, Bürgerbüro, Rathausplatz 1, {plz_stadt}, einzulegen.</p>
  <p>Hinweis zum Datenschutz: Ihre Angaben verarbeiten wir zur Entscheidung über Ihren Antrag. Weitere Informationen
  erhalten Sie im Bürgerbüro oder auf www.musterhausen.example/datenschutz.</p>
 </div>
 <div class="fuss">Aktenzeichen {az} · {p['name']} · Seite 2 von 2</div>
</div>"""
    bilder = [("unterschrift", 46, unterschrift_png(sb['nachname'], rng.choice(
        ["MrsSaintDelafield-Regular.ttf", "HerrVonMuellerhoff-Regular.ttf"]), rng)),
              ("stempel", 32, stempel_png("STADT MUSTERHAUSEN · BÜRGERBÜRO ·", "WoGG", (38, 64, 168, 235), rng))]
    werte = [(p['name'], "name"), (p['nachname'], "name"), (p['strasse'], "anschrift"), (p['plz_ort'], "anschrift"),
             (az, "aktenzeichen"), (sb['name'], "name"), (sb['telefon'], "telefon"), (sb['email'], "email"),
             (p['geb'], "geburtsdatum"), (p['iban'], "iban"), (p['steuer_id'], "steuer_id")]
    return seite1 + seite2, bilder, werte


def vorlage_vermieterin(p: dict, v: dict, nr: str, rng: random.Random) -> tuple[str, list]:
    seite = f"""
<div class="seite">
 <div class="kopf"><div class="absender-gross" style="font-size: 13pt">{v['name']}</div>
   <div>{v['strasse']} · {v['plz_ort']}</div><div>Telefon {v['telefon']} · Mobil {v['mobil']}</div><div>{v['email']}</div></div>
 <div class="absenderzeile">{v['name']} · {v['strasse']} · {v['plz_ort']}</div>
 <div class="empfaenger">{p['anrede']}<br>{p['name']}<br>{p['strasse']}<br>{p['plz_ort']}</div>
 <div class="info"><b>Mieternummer:</b> {nr}<br><b>Datum:</b> 09.11.2026</div>
 <div class="text">
  <p class="betreff">Betriebskostenabrechnung 2025 und Stellplatz</p>
  <p>Guten Tag {p['anrede']} {p['nachname']},</p>
  <p>anbei erhalten Sie die Abrechnung der Betriebskosten für das Jahr 2025. Es ergibt sich ein Guthaben von
  86,40 Euro, das ich Ihnen in den nächsten Tagen auf Ihr Konto {p['iban']} überweise.</p>
  <p>Den Stellplatz Nr. 4 im Hof können Sie ab Dezember für Ihr Fahrzeug mit dem Kennzeichen {p['kennzeichen']}
  nutzen. Die Miete dafür von 30,00 Euro im Monat überweisen Sie bitte zusammen mit der Wohnungsmiete auf mein Konto
  {v['iban']}.</p>
  <p>Für Rückfragen bin ich unter {v['mobil']} erreichbar, am besten abends. Ihre Nachricht vom 28.10.2026 an
  {p['email']} habe ich erhalten; die Reparatur des Fensters ist für den 20.11.2026 beauftragt.</p>
  <p>Viele Grüße</p>
  @@ZEICHNUNG@@
  <p>{v['name']}</p>
 </div>
</div>"""
    bilder = [("unterschrift", 42, unterschrift_png(v['vorname'] + " " + v['nachname'][0] + ".",
                                                             "Allura-Regular.ttf", rng))]
    werte = [(v['name'], "name"), (v['strasse'], "anschrift"), (v['plz_ort'], "anschrift"), (v['telefon'], "telefon"),
             (v['mobil'], "telefon"), (v['email'], "email"), (p['name'], "name"), (p['nachname'], "name"),
             (p['strasse'], "anschrift"), (p['plz_ort'], "anschrift"), (nr, "aktenzeichen"), (p['iban'], "iban"),
             (p['kennzeichen'], "kennzeichen"), (v['iban'], "iban"), (p['email'], "email")]
    return seite, bilder, werte


def vorlage_arbeitgeber(p: dict, hr: dict, nr: str, rng: random.Random) -> tuple[str, list]:
    seite = f"""
<div class="seite">
 <div class="kopf"><div class="absender-gross">Beispiel Logistik GmbH</div><div>Personalabteilung</div></div>
 <div class="absenderzeile">Beispiel Logistik GmbH · Industriestraße 40 · 54321 Beispielstadt</div>
 <div class="empfaenger">{p['anrede']}<br>{p['name']}<br>{p['strasse']}<br>{p['plz_ort']}</div>
 <div class="info"><b>Personalnummer:</b> {nr}<br><b>Ansprechpartnerin:</b> {hr['name']}<br>
   <b>Telefon:</b> {hr['telefon']}<br><b>E-Mail:</b> {hr['email']}<br><b>Datum:</b> 05.11.2026</div>
 <div class="text">
  <p class="betreff">Bescheinigung über das Beschäftigungsverhältnis</p>
  <p>Hiermit bestätigen wir, dass {p['anrede']} {p['name']}, geboren am {p['geb']}, wohnhaft {p['strasse']},
  {p['plz_ort']}, seit dem 01.04.2021 in unserem Unternehmen als Disponent{'in' if p['anrede'] == 'Frau' else ''}
  in Vollzeit beschäftigt ist. Das Arbeitsverhältnis ist unbefristet und ungekündigt.</p>
  <p>Für die Lohnabrechnung liegt uns die steuerliche Identifikationsnummer {p['steuer_id']} vor. Das Gehalt
  überweisen wir monatlich auf das Konto {p['iban']}.</p>
  <p>Diese Bescheinigung wird auf Wunsch zur Vorlage bei der Wohnungsgenossenschaft ausgestellt. Für Rückfragen
  erreichen Sie {hr['name']} unter {hr['telefon']}. Private Rufnummer laut Personalakte: {p['telefon']}.</p>
  <p>Mit freundlichen Grüßen<br>Beispiel Logistik GmbH</p>
  @@ZEICHNUNG@@
  <p>{hr['name']}, Personalabteilung</p>
 </div>
 <div class="fuss">Beispiel Logistik GmbH · Industriestraße 40 · 54321 Beispielstadt · Amtsgericht Beispielstadt HRB 99999 ·
  Telefon 040 66969 100</div>
</div>"""
    bilder = [("unterschrift", 44, unterschrift_png(hr['nachname'], "HerrVonMuellerhoff-Regular.ttf", rng)),
              ("stempel", 52, firmenstempel_png(["Beispiel Logistik GmbH", "Personalabteilung", "Industriestraße 40",
                                                 "54321 Beispielstadt"], (32, 58, 150, 235), rng))]
    werte = [(p['name'], "name"), (p['strasse'], "anschrift"), (p['plz_ort'], "anschrift"), (nr, "aktenzeichen"),
             (hr['name'], "name"), (hr['telefon'], "telefon"), (hr['email'], "email"), (p['geb'], "geburtsdatum"),
             (p['steuer_id'], "steuer_id"), (p['iban'], "iban"), (p['telefon'], "telefon")]
    return seite, bilder, werte


# --- Bau ---------------------------------------------------------------------------------------------------------

def pdf_bauen(html: str, bilder: list, schrift: str, farbe: str) -> bytes:
    """HTML → PDF mit WeasyPrint; Unterschrift und Stempel als Bilder im Textfluss über dem Namen."""
    from weasyprint import HTML
    teile = []
    for i, (art, breite, png) in enumerate(bilder):
        pfad = ZIEL / f".bild-{i}.png"
        pfad.write_bytes(png)
        teile.append(f'<img src="{pfad}" style="width:{breite}mm">')
    html = html.replace("@@ZEICHNUNG@@", '<div class="zeichnung">' + "".join(teile) + "</div>", 1)
    css = CSS % {"schrift": schrift, "farbe": farbe, "pfad": SCHRIFTEN}
    return HTML(string=f"<html lang='de'><head><style>{css}</style></head><body>{html}</body></html>",
                base_url=str(ZIEL) + "/").write_pdf()


def wahrheit_suchen(pdf: bytes, werte: list, bilder: list) -> list[list[dict]]:
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    seiten = []
    for nr, seite in enumerate(doc):
        eintraege, gesehen = [], set()
        for text, kat in sorted(werte, key=lambda w: -len(w[0])):
            for r in seite.search_for(text):
                schluessel = (round(r.x0), round(r.y0))
                # kürzere Werte (Nachname) nicht doppelt zählen, wenn sie in einem längeren Treffer liegen
                if any(abs(r.y0 - g[1]) < 2 and g[0] - 1 <= r.x0 <= g[2] for g in gesehen):
                    continue
                gesehen.add((r.x0, r.y0, r.x1))
                eintraege.append({"kategorie": kat, "text": text, "rechteck": [round(v, 2) for v in r]})
        info = sorted(seite.get_image_info(), key=lambda i: i["bbox"][0])
        if nr == 0 and len(info) == len(bilder):
            for (art, _breite, _png), i in zip(bilder, info):
                eintraege.append({"kategorie": art, "text": None, "rechteck": [round(v, 2) for v in i["bbox"]]})
        seiten.append(eintraege)
    return seiten


def scan(pdf: bytes, rng: random.Random) -> tuple[list[np.ndarray], list[np.ndarray]]:
    """Seiten als simulierter Scan: leicht gedreht, Papierton, Rauschen, Unschärfe, JPEG."""
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    bilder, matrizen = [], []
    for seite in doc:
        pix = seite.get_pixmap(dpi=DPI_SCAN)
        a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[..., :3].copy()
        h, w = a.shape[:2]
        winkel = rng.uniform(-0.9, 0.9)
        m = cv2.getRotationMatrix2D((w / 2, h / 2), winkel, 1.0)
        m[:, 2] += (rng.uniform(-12, 12), rng.uniform(-12, 12))
        a = cv2.warpAffine(a, m, (w, h), borderValue=(250, 250, 248))
        a = (a.astype(np.float32) * np.array([0.97, 0.965, 0.94]) + 4).clip(0, 255)
        a += np.random.default_rng(rng.randint(0, 10**6)).normal(0, 5.5, a.shape)
        a = cv2.GaussianBlur(a.clip(0, 255).astype(np.uint8), (3, 3), 0.55)
        ok, jpg = cv2.imencode(".jpg", a[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 72])
        a = cv2.imdecode(jpg, cv2.IMREAD_COLOR)[..., ::-1]
        bilder.append(a)
        matrizen.append(m)
    return bilder, matrizen


def ocr_schicht(seite, bild: np.ndarray, faktor: float) -> None:
    """Unsichtbare Textschicht wie ein Scanner mit Texterkennung (Tesseract, Darstellungsmodus 3)."""
    import pytesseract
    d = pytesseract.image_to_data(Image.fromarray(bild), lang="deu", output_type=pytesseract.Output.DICT)
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        if not t or float(d["conf"][i]) < 0:
            continue
        x, y, w, h = (d[k][i] / faktor for k in ("left", "top", "width", "height"))
        groesse = max(4.0, h * 1.05)
        breite_text = pymupdf.get_text_length(t, fontname="helv", fontsize=groesse)
        seite.insert_text((x, y + h * 0.85), t, fontsize=groesse, fontname="helv", render_mode=3,
                          morph=(pymupdf.Point(x, y + h), pymupdf.Matrix(w / max(breite_text, 0.1), 1)))


def rechteck_drehen(r: list, m: np.ndarray, faktor: float) -> list:
    ecken = np.array([[r[0], r[1]], [r[2], r[1]], [r[0], r[3]], [r[2], r[3]]]) * faktor
    p = (m[:, :2] @ ecken.T).T + m[:, 2]
    return [round(float(v), 2) for v in (p[:, 0].min(), p[:, 1].min(), p[:, 0].max(), p[:, 1].max())]


def bauen() -> int:
    ZIEL.mkdir(exist_ok=True)
    rng = random.Random(START)
    plan = [  # (Vorlage, Art)
        ("bescheid", "scan_ocr"), ("vermieterin", "digital"), ("arbeitgeber", "scan"), ("bescheid", "digital"),
        ("vermieterin", "jpg"), ("arbeitgeber", "digital"), ("bescheid", "scan"), ("vermieterin", "scan_ocr"),
        ("arbeitgeber", "jpg"), ("bescheid", "digital"), ("vermieterin", "digital"), ("arbeitgeber", "digital"),
    ]
    wahrheit = {}
    for i, (vorlage, art) in enumerate(plan, start=1):
        p = person(rng, rng.random() < 0.5)
        zweite = person(rng, True)
        # Zwei Personen eines Schreibens tragen nie denselben Familiennamen (in Schreiben 02 zog der Zufall für
        # Mieterin und Vermieterin einmal denselben Namen). Nachgezogen wird mit eigenem Startwert, damit die übrigen
        # Schreiben unverändert bleiben.
        nachziehen = random.Random(START * 100 + i)
        while zweite["nachname"] == p["nachname"]:
            zweite = person(nachziehen, True)
        if vorlage == "bescheid":
            html, bilder, werte = vorlage_bescheid(p, zweite, f"WG-{rng.randint(100, 999)}/{rng.randint(1000, 9999)}-26", rng)
        elif vorlage == "vermieterin":
            html, bilder, werte = vorlage_vermieterin(p, zweite, f"M-{rng.randint(10000, 99999)}", rng)
        else:
            html, bilder, werte = vorlage_arbeitgeber(p, zweite, f"{rng.randint(100000, 999999)}", rng)
        for wert, _kat in sorted(werte, key=lambda w: -len(w[0])):
            html = html.replace(f" {wert}", f" <span class=\"nw\">{wert}</span>").replace(f">{wert}<", f"><span class=\"nw\">{wert}</span><")
        schrift = rng.choice(["Serif", "Sans"])
        pdf = pdf_bauen(html, bilder, schrift, rng.choice(["#0b4f6c", "#5a2d82", "#1d5e3a", "#7a1f1f"]))
        seiten = wahrheit_suchen(pdf, werte, bilder)
        name = f"{i:02d}-{vorlage}-{art.replace('_', '-')}"
        if art == "digital":
            doc = pymupdf.open(stream=pdf, filetype="pdf")
            doc.set_metadata({"author": zweite["name"], "title": f"Schreiben an {p['name']}",
                              "subject": werte[4][0] if len(werte) > 4 else "", "keywords": p["email"],
                              "creator": "Textverarbeitung", "producer": "WeasyPrint"})
            doc.set_xml_metadata(f'<?xpacket begin=""?><x:xmpmeta xmlns:x="adobe:ns:meta/"><rdf:RDF '
                                 f'xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"><rdf:Description '
                                 f'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:creator>{zweite["name"]}'
                                 f'</dc:creator></rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end="w"?>')
            doc.embfile_add("notiz.txt", f"Rückruf {p['name']} unter {p['telefon']}".encode(), filename="notiz.txt")
            datei = ZIEL / f"{name}.pdf"
            doc.save(datei, garbage=3, deflate=True)
            einheit = "pt"
        else:
            bilder_scan, matrizen = scan(pdf, rng)
            faktor = DPI_SCAN / 72
            neu = []
            for eintraege, m in zip(seiten, matrizen):
                neu.append([{**e, "rechteck": rechteck_drehen(e["rechteck"], m, faktor)} for e in eintraege])
            if art == "jpg":
                datei = ZIEL / f"{name}.jpg"
                Image.fromarray(bilder_scan[0]).save(datei, quality=86)
                seiten = neu[:1]
                einheit = "px"
            else:
                doc = pymupdf.open()
                for a in bilder_scan:
                    s = doc.new_page(width=a.shape[1] / faktor, height=a.shape[0] / faktor)
                    ok, jpg = cv2.imencode(".jpg", a[..., ::-1], [cv2.IMWRITE_JPEG_QUALITY, 80])
                    s.insert_image(s.rect, stream=jpg.tobytes())
                    if art == "scan_ocr":
                        ocr_schicht(s, a, faktor)
                doc.set_metadata({"author": "Poststelle", "producer": "ScanStation (simuliert)",
                                  "title": f"Scan {p['name']}", "creationDate": "D:20261112093000+01'00'"})
                datei = ZIEL / f"{name}.pdf"
                doc.save(datei, garbage=3, deflate=True)
                seiten = [[{**e, "rechteck": [round(v / faktor, 2) for v in e["rechteck"]]} for e in s] for s in neu]
                einheit = "pt"
        wahrheit[datei.name] = {"vorlage": vorlage, "art": art, "einheit": einheit, "seiten": seiten}
        print(f"{datei.name}: {sum(len(s) for s in seiten)} Angaben")
    for f in ZIEL.glob(".bild-*.png"):
        f.unlink()
    (ZIEL / "wahrheit.json").write_text(json.dumps(wahrheit, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(bauen())
