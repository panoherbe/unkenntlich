"""Unkenntlich machen und Gegenprobe an kleinen, im Test erzeugten Dateien (erfundene Angaben)."""
import json

import numpy as np
import piexif
import pymupdf
from PIL import Image

from unkenntlich import dokument, foto, gegenprobe

NAME = "Jana Albers"
IBAN = "DE68 9001 2345 0123 4567 89"


def kleines_pdf(pfad):
    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 100), f"Frau {NAME}", fontsize=12)
    s.insert_text((72, 130), f"IBAN {IBAN}", fontsize=12)
    s.insert_text((72, 160), "Unsere Zentrale: Rathausplatz 1", fontsize=12)
    doc.set_metadata({"author": NAME, "title": "Schreiben"})
    doc.embfile_add("notiz.txt", NAME.encode())
    doc.save(pfad)
    return pfad


def stellen_zu(pfad, *texte):
    doc = pymupdf.open(pfad)
    out = []
    for t in texte:
        for r in doc[0].search_for(t):
            out.append({"seite": 0, "kategorie": "name", "rechtecke": [list(r)], "text": t})
    return out


def test_text_wird_entfernt_nicht_nur_ueberdeckt(tmp_path):
    ein = kleines_pdf(tmp_path / "ein.pdf")
    aus = tmp_path / "aus.pdf"
    best = stellen_zu(ein, NAME, IBAN)
    dokument.schwaerzen(ein, aus, best)
    doc = pymupdf.open(aus)
    text = doc[0].get_text()
    assert NAME not in text and "3704" not in text
    assert "Rathausplatz" in text                       # Rest der Seite bleibt lesbar
    assert not any(doc.metadata.get(k) for k in ("author", "title"))
    assert doc.embfile_count() == 0 and not doc.get_xml_metadata()


def test_gegenprobe_findet_nur_ueberdeckten_text(tmp_path):
    ein = kleines_pdf(tmp_path / "ein.pdf")
    best = stellen_zu(ein, NAME, IBAN)
    falsch = tmp_path / "falsch.pdf"
    dokument.schwaerzen(ein, falsch, best, nur_ueberdecken=True)
    erg = gegenprobe.dokument_pruefen(falsch, best, [])
    pruefungen = {r["pruefung"] for r in erg["reste"]}
    assert "Textschicht" in pruefungen                  # der Text steht unter dem schwarzen Kasten noch da
    assert any(r["kategorie"] == "metadaten" for r in erg["reste"])
    richtig = tmp_path / "richtig.pdf"
    dokument.schwaerzen(ein, richtig, best)
    sicht = stellen_zu(ein, "Rathausplatz 1")
    erg = gegenprobe.dokument_pruefen(richtig, best, sicht)
    assert erg["reste"] == [], erg["reste"]


def test_foto_ohne_metadaten_und_gefuellt(tmp_path):
    a = np.full((240, 320, 3), 200, np.uint8)
    exif = piexif.dump({"0th": {piexif.ImageIFD.Artist: b"Erika Beispiel"},
                        "GPS": {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: ((50, 1), (1, 1), (0, 1))}})
    ein = tmp_path / "ein.jpg"
    Image.fromarray(a).save(ein, exif=exif)
    _, inventar, _ = foto.laden(ein)
    assert {"Urheber (Artist)", "GPS-Position"} <= {m["feld"] for m in inventar}
    aus = tmp_path / "aus.jpg"
    foto.schwaerzen(ein, aus, [{"kategorie": "gesicht", "rechtecke": [[40, 40, 140, 160]]}])
    b = Image.open(aus)
    assert not b.getexif() and "icc_profile" not in b.info
    px = np.array(b)
    assert px[100, 90].mean() < 60 and px[10, 300].mean() > 180


def test_bericht_ohne_klartext(tmp_path, monkeypatch):
    from unkenntlich import bericht, vorgang
    monkeypatch.setattr(vorgang, "DATEN", tmp_path)
    ein = kleines_pdf(tmp_path / "ein.pdf")
    v = vorgang.neu()
    d = {"id": "d1", "name": "brief.pdf", "art": "dokument", "pfad": str(ein), "groesse": ein.stat().st_size,
         "sha256": vorgang.sha256(ein), "status": "bereit", "metadaten": [{"feld": "Autor", "art": "Dokumentinfo"}],
         "seiten": [{"breite": 595, "hoehe": 842, "geprueft": True}]}
    v["dateien"].append(d)
    for s in stellen_zu(ein, NAME, IBAN):
        s.update({"id": "s1", "datei": d["id"], "entscheidung": "unkenntlich", "quelle": "Regel", "grund": "Test"})
        v["stellen"].append(s)
    v["gegenprobe"] = {"status": "fertig", "reste": 0, "ergebnisse": {}, "ende": vorgang.jetzt()}
    html = bericht.html(v)
    assert NAME not in html and "3704" not in html and "Gegenprobe: 0 Reste" in html
    json.dumps(v)


def test_anmerkungen_werden_geloescht(tmp_path):
    """Notiz, Freitext und Hervorhebung liegen nicht im Seiteninhalt; sie müssen nach dem Schwärzen weg sein."""
    ein = kleines_pdf(tmp_path / "ein.pdf")
    doc = pymupdf.open(ein)
    s = doc[0]
    s.add_text_annot((300, 100), f"Rückruf bei {NAME}")
    s.add_freetext_annot(pymupdf.Rect(300, 200, 500, 240), f"Bearbeitet für {NAME}")
    treffer = s.search_for("Rathausplatz")
    h = s.add_highlight_annot(treffer[0])
    h.set_info(content=f"Notiz zu {NAME}")
    h.update()
    doc.set_toc([[1, f"Schreiben an {NAME}", 1]])
    doc.save(tmp_path / "mit-anmerkungen.pdf")
    from unkenntlich import dokument as d
    assert {"Anmerkung", "Gliederung"} <= {m["art"] for m in d.metadaten_inventar(pymupdf.open(tmp_path / "mit-anmerkungen.pdf"))}
    aus = tmp_path / "aus.pdf"
    best = stellen_zu(ein, NAME, IBAN)
    dokument.schwaerzen(tmp_path / "mit-anmerkungen.pdf", aus, best)
    erg = pymupdf.open(aus)
    assert not list(erg[0].annots()) and not erg[0].annot_xrefs() and not erg.get_toc()
    assert not any("/Annot" in erg.xref_object(x) for x in range(1, erg.xref_length()))
    assert gegenprobe.dokument_pruefen(aus, best, stellen_zu(ein, "Rathausplatz 1"))["reste"] == []


def test_ausweg_bei_resten_ohne_ort(tmp_path, monkeypatch):
    """Ein Rest ohne Ort lässt sich nicht als Bereich übernehmen; das Dokument wird dann aus Seitenbildern neu
    aufgebaut, und der Export ist nicht für immer gesperrt."""
    from unkenntlich import vorgang
    monkeypatch.setattr(vorgang, "DATEN", tmp_path)
    ein = kleines_pdf(tmp_path / "ein.pdf")
    v = vorgang.neu()
    d = {"id": "d1", "name": "brief.pdf", "art": "dokument", "pfad": str(ein), "status": "bereit",
         "seiten": [{"breite": 595, "hoehe": 842, "geprueft": True}]}
    v["dateien"].append(d)
    v["gegenprobe"] = {"status": "fertig", "reste": 1, "ergebnisse": {"d1": {"reste": [
        {"seite": None, "rechteck": None, "kategorie": "metadaten", "pruefung": "Metadaten",
         "hinweis": "Dokumentinfo enthält noch: author"}]}}}
    assert vorgang.reste_uebernehmen(v) == 0 and d["neu_aufbauen"]
    assert any(p["ereignis"] == "Neu aufbauen" for p in v["protokoll"])
    aus = tmp_path / "neu.pdf"
    best = stellen_zu(ein, NAME, IBAN)
    assert dokument.schwaerzen(ein, aus, best, neu_aufbauen=True)["neu_aufgebaut"]
    neu = pymupdf.open(aus)
    assert not neu[0].get_text().strip() and not neu.get_xml_metadata() and neu.embfile_count() == 0
    assert not any(v for k, v in neu.metadata.items() if k not in ("format", "encryption"))
    assert gegenprobe.dokument_pruefen(aus, best, stellen_zu(ein, "Rathausplatz 1"))["reste"] == []


def test_bildpunkte_unter_uebermaltem_scan(tmp_path):
    """Ein Scan ohne Textschicht, dessen Name nur übermalt ist: Die Gegenprobe findet die Bildpunkte unter dem Kasten."""
    from PIL import ImageDraw
    a = Image.new("RGB", (1240, 1754), "white")
    zeichnen = ImageDraw.Draw(a)
    for i in range(8):
        zeichnen.text((150, 300 + 40 * i), "Jana Albers  DE68 9001 2345 0123 4567 89", fill="black", font_size=34)
    ein = tmp_path / "scan.pdf"
    doc = pymupdf.open()
    s = doc.new_page(width=595, height=842)
    puffer = __import__("io").BytesIO()
    a.save(puffer, "PNG")
    s.insert_image(s.rect, stream=puffer.getvalue())
    doc.save(ein)
    best = [{"seite": 0, "kategorie": "eigener_bereich", "rechtecke": [[60, 135, 560, 300]], "text": None}]
    falsch, richtig = tmp_path / "falsch.pdf", tmp_path / "richtig.pdf"
    dokument.schwaerzen(ein, falsch, best, nur_ueberdecken=True)
    assert any(r["pruefung"] == "Bildpunkte unter den Flächen" for r in gegenprobe.dokument_pruefen(falsch, best, [])["reste"])
    dokument.schwaerzen(ein, richtig, best)
    assert not any(r["pruefung"] == "Bildpunkte unter den Flächen" for r in gegenprobe.dokument_pruefen(richtig, best, [])["reste"])


def test_weiteres_vorkommen_ohne_namen_im_grund(tmp_path, monkeypatch):
    """Der Grund eines Vorschlags steht im Prüfbericht; er darf den Namen nicht enthalten."""
    from unkenntlich import bericht, text_layout, vorgang
    monkeypatch.setattr(vorgang, "DATEN", tmp_path)
    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 100), f"Frau {NAME}", fontsize=12)
    s.insert_text((72, 140), "Wie besprochen erhält Albers den Bescheid.", fontsize=12)
    ein = tmp_path / "ein.pdf"
    doc.save(ein)
    lay = text_layout.aus_pdf_seite(pymupdf.open(ein)[0])
    erste = [{"kategorie": "name", "text": NAME, "seite": 0, "rechtecke": [list(r) for r in pymupdf.open(ein)[0].search_for(NAME)]}]
    weitere = dokument.weitere_vorkommen({0: [lay]}, erste)
    assert weitere and all("Albers" not in w["grund"] and "Jana" not in w["grund"] for w in weitere)
    v = vorgang.neu()
    v["dateien"].append({"id": "d1", "name": "brief.pdf", "art": "dokument", "pfad": str(ein), "groesse": 1,
                         "sha256": "0", "status": "bereit", "metadaten": [], "seiten": [{"breite": 595, "hoehe": 842, "geprueft": True}]})
    for i, w in enumerate(weitere + [{**erste[0], "grund": f"Name „{NAME}“ (alter Wortlaut)", "quelle": "Regel"}]):
        v["stellen"].append({**w, "id": f"s{i}", "datei": "d1", "entscheidung": "unkenntlich", "quelle": w.get("quelle", "Abgleich")})
    v["gegenprobe"] = {"status": "fertig", "reste": 0, "ergebnisse": {}, "ende": vorgang.jetzt()}
    html = bericht.html(v)
    assert "Albers" not in html and "Jana" not in html


def test_schnitt_im_video_beginnt_neue_spuren():
    """Nach einem harten Schnitt darf keine Spur (und keine Entscheidung) auf die nächste Szene übergehen."""
    from unkenntlich import video
    rng = np.random.default_rng(1)
    strasse = np.full((360, 640, 3), (90, 120, 150), np.uint8)
    strasse[200:, :] = (60, 60, 60)
    platz = np.full((360, 640, 3), (200, 180, 120), np.uint8)
    platz[:120, :] = (230, 210, 180)
    bewegt = np.roll(strasse, 6, axis=1) + rng.integers(0, 4, strasse.shape, dtype=np.uint8)
    assert not video.ist_schnitt(video.merkmal(strasse), video.merkmal(bewegt))
    assert video.ist_schnitt(video.merkmal(strasse), video.merkmal(platz))
    v = video.Verfolger()
    v.schritt(0, [((100, 100, 140, 140), 0.9)])
    v.schnitt(1)
    v.schritt(1, [((101, 100, 141, 140), 0.9)])
    assert len(v.spuren) == 2
