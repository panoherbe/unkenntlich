"""Messlauf: Erkennung, Gegenprobe und Laufzeiten auf dem Prüfsatz; schreibt nachweis/messwerte.json,
nachweis/PROTOKOLL.md und Bilder nach nachweis/bilder/.

    docker compose -f compose.nachweis.yaml run --rm messung

Läuft ohne Netz (network_mode: none) und nur auf der CPU. Der Mensch ist simuliert: Ein Skript bestätigt jeden
Vorschlag, der eine eingesetzte Angabe trifft, lässt die übrigen sichtbar und zieht für jede verpasste Angabe einen
eigenen Bereich, so wie es ein Mensch beim Durchsehen täte. Für Fotos und das Video gibt es keine vollständige
Wahrheit; dort bestätigt der simulierte Mensch jeden Vorschlag, und die Zahlen zeigen Vorschläge, Gegenprobe und
Laufzeiten, keine Trefferquote. Fotos und Video sind mit offenen Modellen erzeugt (keine echten Personen,
pruefsatz/QUELLEN.md).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import platform
import re
import subprocess
import sys
import time
from pathlib import Path
from zoneinfo import ZoneInfo

import cv2
import numpy as np
import pymupdf

HIER = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HIER))
os.environ.setdefault("UNKENNTLICH_DATEN", "/tmp/messung-daten")

from unkenntlich import __version__, bild, dokument, foto, gegenprobe, modelle, text_layout, video  # noqa: E402

PRUEF = HIER / "pruefsatz"
NACHWEIS = HIER / "nachweis"
BILDER = NACHWEIS / "bilder"
ARBEIT = Path("/tmp/messung")
GRUPPEN = {"name": "Namen", "anschrift": "Anschriften", "telefon": "Telefon", "email": "E-Mail", "iban": "IBAN",
           "steuer_id": "Steuer-ID", "geburtsdatum": "Geburtsdatum", "aktenzeichen": "Akten- und Kundennummern",
           "kennzeichen": "Kfz-Kennzeichen", "unterschrift": "Unterschriften", "stempel": "Stempel"}


def norm(t: str) -> str:
    return re.sub(r"[\s .,;:()\-/]", "", t or "").lower()


def abgedeckt(gt: list, stellen: list[dict], seite: int) -> tuple[float, dict | None]:
    """Anteil der Wahrheits-Fläche, den Vorschläge auf derselben Seite abdecken, und der beste Vorschlag."""
    beste, wert = None, 0.0
    summe = 0.0
    for s in stellen:
        if s.get("seite", 0) != seite:
            continue
        a = sum(bild.anteil_in(tuple(gt), tuple(r)) for r in s["rechtecke"])
        summe += a
        if a > wert:
            beste, wert = s, a
    return min(1.0, summe), beste


def cpu() -> str:
    try:
        aus = subprocess.run(["lscpu"], capture_output=True, text=True).stdout
        m = re.search(r"Model name:\s*(.+)", aus)
        return f"{m.group(1).strip()}, {os.cpu_count()} Threads" if m else platform.processor()
    except Exception:
        return platform.processor()


def dokumente() -> dict:
    wahrheit = json.loads((PRUEF / "dokumente" / "wahrheit.json").read_text())
    ergebnis = {"dateien": [], "kategorien": {}, "kontrolle": []}
    for name, w in wahrheit.items():
        pfad = PRUEF / "dokumente" / name
        t0 = time.perf_counter()
        if w["art"] == "jpg":
            erg = foto.analysieren(pfad)
        else:
            erg = dokument.analysieren(pfad)
        dauer = time.perf_counter() - t0
        stellen = erg["stellen"]
        seiten = len(erg["seiten"])
        getroffen, verpasst = [], []
        treffer_stellen = set()
        for nr, eintraege in enumerate(w["seiten"]):
            for e in eintraege:
                anteil, beste = abgedeckt(e["rechteck"], stellen, nr)
                kat = e["kategorie"]
                k = ergebnis["kategorien"].setdefault(kat, {"gesamt": 0, "erkannt": 0, "richtige_kategorie": 0})
                k["gesamt"] += 1
                if anteil >= 0.6:
                    k["erkannt"] += 1
                    getroffen.append(e)
                    if beste and beste["kategorie"] == kat:
                        k["richtige_kategorie"] += 1
                    for s in stellen:
                        if s.get("seite", 0) == nr and any(bild.anteil_in(tuple(e["rechteck"]), tuple(r)) > 0.2
                                                           for r in s["rechtecke"]):
                            treffer_stellen.add(id(s))
                else:
                    verpasst.append({**e, "seite": nr, "abgedeckt": round(anteil, 2)})
        fehl = [s for s in stellen if id(s) not in treffer_stellen]
        # simulierter Mensch: Treffer bestätigen, Fehlvorschläge sichtbar lassen, Verpasstes als eigener Bereich
        best = [s for s in stellen if id(s) in treffer_stellen]
        sicht = fehl
        for e in verpasst:
            best.append({"seite": e["seite"], "kategorie": "eigener_bereich", "rechtecke": [e["rechteck"]], "text": e["text"]})
        aus = ARBEIT / f"aus-{name}"
        t1 = time.perf_counter()
        def schwaerzen_und_pruefen():
            if w["art"] == "jpg":
                foto.schwaerzen(pfad, aus, best, True)
                return gegenprobe.foto_pruefen(aus, best, sicht, True, original=pfad)
            dokument.schwaerzen(pfad, aus, best)
            return gegenprobe.dokument_pruefen(aus, best, sicht)
        if w["art"] == "jpg":
            foto.schwaerzen(pfad, aus, best, True)
            t2 = time.perf_counter()
            gp = gegenprobe.foto_pruefen(aus, best, sicht, True, original=pfad)
        else:
            dokument.schwaerzen(pfad, aus, best)
            t2 = time.perf_counter()
            gp = gegenprobe.dokument_pruefen(aus, best, sicht)
        t3 = time.perf_counter()
        reste_1 = len(gp["reste"])
        runden = 1
        while gp["reste"] and runden < 3:   # simulierter Mensch übernimmt jeden Rest und bestätigt ihn
            best += [{"seite": r.get("seite") or 0, "kategorie": "eigener_bereich", "rechtecke": [r["rechteck"]], "text": None}
                     for r in gp["reste"] if r.get("rechteck")]
            gp = schwaerzen_und_pruefen()
            runden += 1
        # zweite, unabhängige Prüfung: jede eingesetzte Angabe im Textauszug und in neuer Texterkennung suchen
        texte = {norm(e["text"]) for s in w["seiten"] for e in s if e.get("text") and len(norm(e["text"])) >= 4}
        lesbar = set()
        if w["art"] == "jpg":
            from PIL import Image
            lay = text_layout.aus_bild(np.array(Image.open(aus).convert("RGB")), min_sicherheit=30)
            alle = norm(lay.text)
        else:
            d = pymupdf.open(aus)
            alle = "".join(norm(s.get_text()) for s in d)
            alle += "".join(norm(text_layout.aus_bild(dokument.seite_als_bild(s, 300), min_sicherheit=30).text) for s in d)
            meta_leer = not any(v for k, v in (d.metadata or {}).items() if k not in ("format", "encryption")) \
                and not d.get_xml_metadata().strip() and d.embfile_count() == 0
        for t in texte:
            if t in alle:
                lesbar.add(t)
        eintrag = {"datei": name, "art": w["art"], "seiten": seiten, "angaben": sum(len(s) for s in w["seiten"]),
                   "erkannt": len(getroffen), "verpasst": [{k: v for k, v in e.items() if k != "text"} for e in verpasst],
                   "vorschlaege": len(stellen), "fehlvorschlaege": len(fehl),
                   "fehlvorschlaege_art": sorted({s["kategorie"] for s in fehl}),
                   "dauer_analyse_s": round(dauer, 2), "dauer_schwaerzen_s": round(t2 - t1, 2),
                   "dauer_gegenprobe_s": round(t3 - t2, 2), "reste_erste_gegenprobe": reste_1, "runden": runden,
                   "reste_gegenprobe": len(gp["reste"]),
                   "reste_details": [{k: r[k] for k in ("kategorie", "pruefung", "hinweis")} for r in gp["reste"]],
                   "zweite_pruefung_lesbar": len(lesbar), "zweite_pruefung_gesucht": len(texte),
                   "metadaten_vorher": len(erg["metadaten"])}
        if w["art"] != "jpg":
            eintrag["metadaten_nachher_leer"] = meta_leer
        ergebnis["dateien"].append(eintrag)
        print(f"{name}: {len(getroffen)}/{eintrag['angaben']} erkannt, {len(fehl)} Fehlvorschläge, "
              f"{dauer:.1f} s, Reste {len(gp['reste'])}, lesbar {len(lesbar)}/{len(texte)}", flush=True)
        # Kontrollversuch: nur schwarze Kästen darübermalen (typischer Fehler); die Gegenprobe muss es finden
        if w["art"] != "jpg":
            falsch = ARBEIT / f"falsch-{name}"
            dokument.schwaerzen(pfad, falsch, best, nur_ueberdecken=True)
            gpf = gegenprobe.dokument_pruefen(falsch, best, sicht)
            gefunden = sum(1 for r in gpf["reste"] if r["pruefung"] == "Textschicht")
            bildpunkte = sum(1 for r in gpf["reste"] if r["pruefung"] == "Bildpunkte unter den Flächen")
            ergebnis["kontrolle"].append({"datei": name, "reste": len(gpf["reste"]), "textschicht": gefunden,
                                          "bildpunkte": bildpunkte, "inhalt": bool(gefunden or bildpunkte),
                                          "metadaten": any(r["kategorie"] == "metadaten" for r in gpf["reste"]),
                                          "gesperrt": len(gpf["reste"]) > 0})
            if name.startswith("01-"):
                bild_seite(aus, BILDER / "dokument-ergebnis.png")
                bild_seite(pfad, BILDER / "dokument-original.png")
    return ergebnis


def bild_seite(pfad, ziel: Path) -> None:
    d = pymupdf.open(pfad)
    d[0].get_pixmap(dpi=60).save(ziel)


def fotos() -> dict:
    out = []
    for name in ("marktplatz.jpg", "parkplatz.jpg", "werkstatt.jpg", "flohmarkt.jpg"):
        pfad = PRUEF / "fotos" / name
        t0 = time.perf_counter()
        erg = foto.analysieren(pfad)
        dauer = time.perf_counter() - t0
        best = erg["stellen"]
        aus = ARBEIT / f"aus-{name}"
        t1 = time.perf_counter()
        foto.schwaerzen(pfad, aus, best)
        t2 = time.perf_counter()
        gp = gegenprobe.foto_pruefen(aus, best, [], original=pfad)
        t3 = time.perf_counter()
        reste_1, nur_1, runden = len(gp["reste"]), gp.get("nur_ergebnis", 0), 1
        while gp["reste"] and runden < 3:   # wie „Reste übernehmen“ in der Oberfläche: ab der zweiten Übernahme großzügig
            seite = erg["seiten"][0]
            best = best + [{**st, "seite": 0} for st in
                           foto.rest_stellen(gp["reste"], best, runden >= 2, seite["breite"], seite["hoehe"])]
            foto.schwaerzen(pfad, aus, best)
            gp = gegenprobe.foto_pruefen(aus, best, [], original=pfad)
            runden += 1
        from PIL import Image
        b = Image.open(aus)
        zaehlung = {}
        for s in best:
            zaehlung[s["kategorie"]] = zaehlung.get(s["kategorie"], 0) + 1
        out.append({"datei": name, "pixel": f"{erg['seiten'][0]['breite']} × {erg['seiten'][0]['hoehe']}",
                    "vorschlaege": zaehlung, "metadaten_vorher": [m["feld"] for m in erg["metadaten"]],
                    "metadaten_nachher": bool(b.getexif()) or any(k in b.info for k in ("xmp", "icc_profile", "exif")),
                    "dauer_analyse_s": round(dauer, 2), "dauer_schwaerzen_s": round(t2 - t1, 2),
                    "dauer_gegenprobe_s": round(t3 - t2, 2), "reste_erste_gegenprobe": reste_1,
                    "nur_auf_flaechen": nur_1, "runden": runden, "reste_gegenprobe": len(gp["reste"]),
                    "reste_details": [{k: r[k] for k in ("kategorie", "pruefung", "hinweis")} for r in gp["reste"]]})
        print(f"{name}: {zaehlung}, {dauer:.1f} s, Reste {len(gp['reste'])}", flush=True)
        if name == "marktplatz.jpg":
            klein = lambda p: cv2.resize(cv2.imread(str(p)), (960, 640))  # noqa: E731
            cv2.imwrite(str(BILDER / "foto-ergebnis.jpg"), klein(aus), [cv2.IMWRITE_JPEG_QUALITY, 82])
    return {"dateien": out}


def film() -> dict:
    pfad = PRUEF / "video" / "fussgaengerzone.mp4"
    ordner = ARBEIT / "video"
    ordner.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    erg = video.analysieren(pfad, ordner)
    dauer = time.perf_counter() - t0
    spuren = json.loads((ordner / "spuren.json").read_text())
    best = [{**s, "modus": "gesicht" if s["kategorie"] == "person" else None} for s in erg["stellen"]]
    aus = ARBEIT / "aus-fussgaengerzone.mp4"
    t1 = time.perf_counter()
    video.schwaerzen(pfad, aus, best, spuren)
    t2 = time.perf_counter()
    gp = gegenprobe.video_pruefen(aus, best, [], spuren, original=pfad)
    t3 = time.perf_counter()
    reste_1 = len(gp["reste"])
    nur_ergebnis_1 = gp.get("nur_ergebnis", 0)
    runden = 1
    while gp["reste"] and runden < 3:
        # simulierter Mensch: übernimmt jeden Rest als neuen Vorschlag und bestätigt ihn
        best += [{**s, "entscheidung": "unkenntlich"} for s in
                 video.spuren_aus_resten(gp["reste"], spuren, erg["video"]["fps"], erg["video"]["bilder"],
                                         grosszuegig=runden >= 2, schnitte=erg["video"].get("schnitte"))]
        video.schwaerzen(pfad, aus, best, spuren)
        gp = gegenprobe.video_pruefen(aus, best, [], spuren, original=pfad)
        runden += 1
    i = video.info(aus)
    zaehlung = {}
    for s in erg["stellen"]:
        k = "hintergrund" if s["kategorie"] == "person" and s["zeit"].get("hintergrund") else s["kategorie"]
        zaehlung[k] = zaehlung.get(k, 0) + 1
    # Kontrollversuch: jedes zehnte Einzelbild bleibt unbearbeitet; die Gegenprobe muss dort Gesichter finden
    auslassen = set(range(5, erg["video"]["bilder"], 10))
    falsch = ARBEIT / "falsch-fussgaengerzone.mp4"
    video.schwaerzen(pfad, falsch, best, spuren, auslassen)
    gpf = gegenprobe.video_pruefen(falsch, best, [], spuren, original=pfad)
    bilder_mit_rest = {r["bild"] for r in gpf["reste"] if r.get("bild") is not None}
    # Stichprobe: ein Einzelbild je Sekunde aus dem Ergebnis als Kontaktbogen
    kontaktbogen(aus, BILDER / "video-ergebnis-stichprobe.jpg")
    print(f"Video: {zaehlung}, Analyse {dauer:.1f} s, Reste {len(gp['reste'])}, Kontrolle {len(bilder_mit_rest)} Bilder",
          flush=True)
    return {"datei": "fussgaengerzone.mp4", "dauer_video_s": erg["video"]["dauer"], "bilder": erg["video"]["bilder"],
            "aufloesung": f"{erg['video']['breite']} × {erg['video']['hoehe']}", "spuren": zaehlung,
            "schnitte": erg["video"].get("schnitte", []),
            "metadaten_vorher": [m["feld"] for m in erg["metadaten"]], "ton_nachher": i["ton"], "tags_nachher": i["tags"],
            "dauer_analyse_s": round(dauer, 1), "dauer_schwaerzen_s": round(t2 - t1, 1),
            "dauer_gegenprobe_s": round(t3 - t2, 1), "reste_erste_gegenprobe": reste_1,
            "nur_auf_flaechen_erste_gegenprobe": nur_ergebnis_1, "runden": runden, "reste_gegenprobe": len(gp["reste"]),
            "gegenprobe_bilder": gp["geprueft"], "reste_details": gp["reste"][:20],
            "kontrolle": {"ausgelassen": len(auslassen), "bilder_mit_rest": len(bilder_mit_rest),
                          "davon_ausgelassen": len(bilder_mit_rest & auslassen), "reste": len(gpf["reste"]),
                          "gesperrt": len(gpf["reste"]) > 0}}


def kontaktbogen(pfad, ziel: Path) -> None:
    cap = cv2.VideoCapture(str(pfad))
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    bilder, nr = [], 0
    while True:
        ok, f = cap.read()
        if not ok:
            break
        if nr % int(round(fps)) == int(fps) // 2:
            bilder.append(cv2.resize(f, (384, 216)))
        nr += 1
    zeilen = [np.hstack(bilder[i:i + 5] + [np.zeros_like(bilder[0])] * (5 - len(bilder[i:i + 5])))
              for i in range(0, len(bilder), 5)]
    cv2.imwrite(str(ziel), np.vstack(zeilen), [cv2.IMWRITE_JPEG_QUALITY, 80])


def main() -> int:
    ARBEIT.mkdir(parents=True, exist_ok=True)
    BILDER.mkdir(parents=True, exist_ok=True)
    beginn = dt.datetime.now(ZoneInfo("Europe/Berlin"))
    t = time.perf_counter()
    werte = {"version": __version__, "beginn": beginn.isoformat(timespec="seconds"), "rechner": cpu(),
             "faeden": modelle.FADEN, "grafikkarte": "keine genutzt (nur CPU)", "netz": "ohne (network_mode: none)",
             "modelle": modelle.VERZEICHNIS, "tesseract": text_layout.tesseract_version()}
    werte["dokumente"] = dokumente()
    werte["fotos"] = fotos()
    werte["video"] = film()
    werte["dauer_gesamt_s"] = round(time.perf_counter() - t, 1)
    (NACHWEIS / "messwerte.json").write_text(json.dumps(werte, ensure_ascii=False, indent=1, default=str))
    from protokoll import schreiben
    schreiben(werte, NACHWEIS / "PROTOKOLL.md")
    print("fertig", werte["dauer_gesamt_s"], "s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
