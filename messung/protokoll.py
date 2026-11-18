"""Schreibt nachweis/PROTOKOLL.md aus messwerte.json (deutsche Zahlen, alles Simulierte als simuliert benannt)."""
from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

NAMEN = {"name": "Namen", "anschrift": "Anschriften", "telefon": "Telefonnummern", "email": "E-Mail-Adressen",
         "iban": "IBAN", "steuer_id": "Steuer-ID", "geburtsdatum": "Geburtsdaten", "aktenzeichen": "Akten-, Kunden- und Personalnummern",
         "kennzeichen": "Kfz-Kennzeichen im Text", "unterschrift": "Unterschriften", "stempel": "Stempel"}
KAT = {"gesicht": "Gesichter ohne erkannte Person (oft sehr kurz)", "kennzeichen": "Kennzeichen", "person": "Personen", "hintergrund": "Personen im Hintergrund",
       "name": "Namen", "anschrift": "Anschriften", "telefon": "Telefon", "email": "E-Mail", "unterschrift": "Unterschriften",
       "stempel": "Stempel"}
KAT_FOTO = {**KAT, "gesicht": "Gesichter"}
BILD_KATEGORIEN = {"unterschrift", "stempel"}
HANDBLICK_VIDEO = ("Die Gesichter vorn sind abgedeckt, ebenso der Kopf der Schaufensterpuppe in der ersten Szene (ein "
                   "Mensch würde ihn sichtbar lassen); die Bronzestatue der zweiten Szene wird nicht vorgeschlagen. Jedes "
                   "der drei Kennzeichen ist eine eigene Spur und abgedeckt.")
# Von Hand angesehen, nach dem Messlauf eingetragen (das Foto ist erzeugt, die Beschreibung stimmt nur für dieses Bild).
HANDBLICK_FOTO = ("Im Marktplatz-Foto sind die Gesichter der drei Personen vorn, fünf kleine Gesichter im Hintergrund, "
                  "das Gesicht der Bronzestatue und beide Kennzeichen vorgeschlagen und abgedeckt; die Statue würde ein "
                  "Mensch sichtbar lassen (kein Personenbezug), der Rundgang zeigt das.")


def verworfen(n: int) -> str:
    if n == 0:
        return "kein Fund verworfen"
    return (f"{n} Fund{'e' if n != 1 else ''} nicht als Rest gezählt (Gesicht oder Kennzeichen im Ergebnis, das im Original "
            "an derselben Stelle nicht erkannt wird; meist hält ein Modell eine deckende Fläche selbst dafür)")


def uebernahmen(runden: int) -> str:
    n = runden - 1
    return {1: "einmal", 2: "zweimal", 3: "dreimal"}.get(n, f"{n}-mal") + " übernommen"


def z(x, n=1) -> str:
    s = f"{x:,.{n}f}"
    return s.replace(",", "§").replace(".", ",").replace("§", ".")


def spanne(werte, n=1) -> str:
    a, b = z(min(werte), n), z(max(werte), n)
    return a if a == b else f"{a}–{b}"


def pz(a, b) -> str:
    return f"{a} von {b} ({z(100 * a / b, 1)} %)" if b else "–"


def schreiben(w: dict, ziel: Path) -> None:
    beginn = dt.datetime.fromisoformat(w["beginn"])
    d = w["dokumente"]
    dat = d["dateien"]
    gesamt = sum(x["angaben"] for x in dat)
    erkannt = sum(x["erkannt"] for x in dat)
    seiten = sum(x["seiten"] for x in dat)
    fehl = sum(x["fehlvorschlaege"] for x in dat)
    reste = sum(x["reste_gegenprobe"] for x in dat)
    lesbar = sum(x["zweite_pruefung_lesbar"] for x in dat)
    gesucht = sum(x["zweite_pruefung_gesucht"] for x in dat)
    analyse_pdf = [x["dauer_analyse_s"] / x["seiten"] for x in dat if x["art"] == "digital"]
    analyse_scan = [x["dauer_analyse_s"] / x["seiten"] for x in dat if x["art"] in ("scan", "scan_ocr", "jpg")]
    gp_seite = [x["dauer_gegenprobe_s"] / x["seiten"] for x in dat]
    kontrolle = d["kontrolle"]
    f = w["fotos"]["dateien"]
    v = w["video"]
    t = []
    a = t.append
    a("# Messprotokoll")
    a("")
    a(f"Messlauf vom {beginn:%d.%m.%Y}, {beginn:%H:%M} Uhr (deutsche Zeit), Unkenntlich {w['version']}. Erzeugt von "
      "[`messung/messen.py`](../messung/messen.py) über `compose.nachweis.yaml`; Rohdaten in "
      "[`messwerte.json`](messwerte.json), Bilder in [`bilder/`](bilder/).")
    a("")
    a(f"**Rechner:** {w['rechner']}; {w['faeden']} Rechenfäden; Grafikkarte: {w['grafikkarte']}; Netz: {w['netz']}. "
      f"Tesseract {w['tesseract']}. Gesamtdauer des Laufs {z(w['dauer_gesamt_s'] / 60)} min.")
    a("")
    a("**Was simuliert ist:** Alle zwölf Schreiben sind erfunden (Personen, Anschriften, Nummern, Unterschriften, "
      "Stempel; erzeugt von [`pruefsatz/erzeugen.py`](../pruefsatz/erzeugen.py), Scans mit simuliertem Rauschen). "
      "Fotos und Video sind mit offenen Modellen erzeugt: keine echten Personen, keine echten Kennzeichen "
      "([`pruefsatz/QUELLEN.md`](../pruefsatz/QUELLEN.md)). Ihre Metadaten (Kamera, GPS, Urheber) und die Tonspur "
      "(Testton und Rauschen) sind eingesetzt und erfunden. Der Mensch, der die Vorschläge bestätigt, ist ein Skript "
      "(Regeln oben in `messen.py`).")
    a("")
    a("## Ergebnis auf einen Blick")
    a("")
    a("| Was | Ergebnis |")
    a("|---|---|")
    text_g = sum(x["gesamt"] for k, x in d["kategorien"].items() if k not in BILD_KATEGORIEN)
    text_e = sum(x["erkannt"] for k, x in d["kategorien"].items() if k not in BILD_KATEGORIEN)
    a(f"| Eingesetzte Angaben in 12 Schreiben (simuliert), vor jeder Bestätigung vorgeschlagen | Angaben im Text: "
      f"**{pz(text_e, text_g)}**; mit Unterschriften und Stempeln: **{pz(erkannt, gesamt)}**; auf {seiten} Seiten |")
    a(f"| Vorschläge ohne eingesetzte Angabe (z. B. Anschrift und Zentrale der Behörde, die der Mensch sichtbar lässt) | {fehl}, also {z(fehl / seiten)} je Seite |")
    r1 = sum(x.get("reste_erste_gegenprobe", x["reste_gegenprobe"]) for x in dat)
    d1 = sum(1 for x in dat if x.get("reste_erste_gegenprobe", 0))
    a(f"| Gegenprobe nach dem Unkenntlichmachen, 12 Schreiben | erste Gegenprobe: {r1} Rest{'e' if r1 != 1 else ''} in {d1} "
      f"Datei{'en' if d1 != 1 else ''} (Export gesperrt); "
      f"Reste übernommen und bestätigt, danach **{reste} Reste** |" if r1 else f"| Gegenprobe nach dem Unkenntlichmachen, 12 Schreiben | **{reste} Reste** |")
    inhalt = sum(1 for k in kontrolle if k.get("inhalt", k["textschicht"]))
    a(f"| Zweite, unabhängige Prüfung: eingesetzte Angaben im Textauszug und in neuer Texterkennung des Ergebnisses gesucht | {lesbar} von {gesucht} noch lesbar |")
    a(f"| Kontrollversuch „nur schwarz übermalt“ (typischer Fehler), {len(kontrolle)} PDFs | Gegenprobe sperrt in "
      f"{sum(1 for k in kontrolle if k['gesperrt'])} von {len(kontrolle)}; Inhalt unter den Kästen gefunden in {inhalt} von "
      f"{len(kontrolle)} (Text in der Textschicht in {sum(1 for k in kontrolle if k['textschicht'])}, Bildpunkte unter "
      f"den Flächen in {sum(1 for k in kontrolle if k.get('bildpunkte'))}) |")
    f1 = sum(x.get("reste_erste_gegenprobe", 0) for x in f)
    a(f"| Fotos ({len(f)}, erzeugt): Gegenprobe | " + (f"erste Gegenprobe {f1} Rest{'e' if f1 != 1 else ''}, übernommen und bestätigt, danach " if f1 else "")
      + f"**{sum(x['reste_gegenprobe'] for x in f)} Reste**; {verworfen(sum(x.get('nur_auf_flaechen', 0) for x in f))}; "
      f"Metadaten danach: {'keine' if not any(x['metadaten_nachher'] for x in f) else 'noch vorhanden'} |")
    vz = v["spuren"]
    a(f"| Video ({z(v['dauer_video_s'], 1)} s, {v['aufloesung']}, {v['bilder']} Einzelbilder, erzeugt): Spuren | "
      + ", ".join(f"{n} {KAT.get(k, k)}" for k, n in vz.items()) + " |")
    schleife = (f"erste Gegenprobe {v['reste_erste_gegenprobe']} Reste (Export gesperrt), Reste {uebernahmen(v['runden'])} und "
                f"bestätigt, danach **{v['reste_gegenprobe']} Reste**" if v.get("runden", 1) > 1 else f"**{v['reste_gegenprobe']} Reste**")
    a(f"| Video: Gegenprobe über {v['gegenprobe_bilder']['bilder']} von {v['gegenprobe_bilder']['von']} Einzelbildern | {schleife}; "
      f"in der ersten Gegenprobe {verworfen(v.get('nur_auf_flaechen_erste_gegenprobe', 0))}; "
      f"Ton danach: {'ja' if v['ton_nachher'] else 'entfernt'}; Metadaten danach: {', '.join(v['tags_nachher']) or 'keine'} |")
    kv = v["kontrolle"]
    a(f"| Kontrollversuch Video: jedes zehnte Einzelbild unbearbeitet ({kv['ausgelassen']} Bilder) | Gegenprobe meldet Reste in {kv['bilder_mit_rest']} Bildern, davon {kv['davon_ausgelassen']} ausgelassene; Export gesperrt: {'ja' if kv['gesperrt'] else 'nein'} |")
    a("")
    a("## Laufzeiten auf der CPU")
    a("")
    a("| Was | Dauer |")
    a("|---|---|")
    if analyse_pdf:
        a(f"| Erkennen, digitales PDF | {spanne(analyse_pdf)} s je Seite |")
    if analyse_scan:
        a(f"| Erkennen, Scan oder Foto eines Schreibens (mit Texterkennung) | {spanne(analyse_scan)} s je Seite |")
    a(f"| Gegenprobe, Schreiben | {spanne(gp_seite)} s je Seite |")
    fa = [x["dauer_analyse_s"] for x in f]
    a(f"| Erkennen, Foto ({f[0]['pixel']} px) | {spanne(fa)} s |")
    a(f"| Erkennen, Video ({v['aufloesung']}) | {z(v['dauer_analyse_s'], 0)} s für {z(v['dauer_video_s'], 1)} s Video, also {z(v['dauer_analyse_s'] / v['dauer_video_s'])} s je Videosekunde |")
    a(f"| Unkenntlich machen, Video | {z(v['dauer_schwaerzen_s'], 0)} s |")
    a(f"| Gegenprobe, Video | {z(v['dauer_gegenprobe_s'], 0)} s, also {z(v['dauer_gegenprobe_s'] / v['dauer_video_s'])} s je Videosekunde |")
    a("")
    a("Die Modelle werden beim ersten Aufruf geladen; die erste Datei eines Laufs ist deshalb einige Sekunden langsamer.")
    a("")
    a("## Schreiben: Erkennung je Kategorie (simuliert)")
    a("")
    a("Eine Angabe zählt als erkannt, wenn Vorschläge mindestens 60 % ihrer Fläche abdecken (bei Scans ist die Wahrheit "
      "das Rechteck der gedrehten Zeile und damit etwas größer als die Zeile selbst).")
    a("")
    a("| Kategorie | eingesetzt | vorgeschlagen | davon mit richtiger Kategorie |")
    a("|---|---:|---:|---:|")
    for k, x in sorted(d["kategorien"].items(), key=lambda kv: -kv[1]["gesamt"]):
        a(f"| {NAMEN.get(k, k)} | {x['gesamt']} | {pz(x['erkannt'], x['gesamt'])} | {x['richtige_kategorie']} |")
    a("")
    a("## Schreiben: je Datei")
    a("")
    a("| Datei | Art | Seiten | erkannt | verpasst | Fehlvorschläge | Erkennen | Gegenprobe | Reste (erste → zuletzt) | zweite Prüfung lesbar |")
    a("|---|---|---:|---:|---|---:|---:|---:|---:|---:|")
    art = {"digital": "digitales PDF", "scan": "Scan (PDF, nur Bild)", "scan_ocr": "Scan mit Textschicht", "jpg": "Foto eines Schreibens (JPG)"}
    for x in dat:
        verp = ", ".join(NAMEN.get(e["kategorie"], e["kategorie"]) for e in x["verpasst"]) or "–"
        a(f"| {x['datei']} | {art[x['art']]} | {x['seiten']} | {x['erkannt']} von {x['angaben']} | {verp} | {x['fehlvorschlaege']} | "
          f"{z(x['dauer_analyse_s'])} s | {z(x['dauer_gegenprobe_s'])} s | {x.get('reste_erste_gegenprobe', x['reste_gegenprobe'])} → {x['reste_gegenprobe']} | {x['zweite_pruefung_lesbar']} von {x['zweite_pruefung_gesucht']} |")
    a("")
    a("Verpasste Angaben zieht der simulierte Mensch als eigenen Bereich nach; erst danach laufen Unkenntlichmachen und "
      "Gegenprobe. Ohne diesen Schritt blieben sie lesbar: Die Gegenprobe findet nur, was ihre Erkenner erkennen. Findet "
      "die Gegenprobe etwas, übernimmt der simulierte Mensch jeden Rest als eigenen Bereich, und alles läuft noch einmal "
      "(so wie in der Oberfläche mit „Reste als Vorschläge übernehmen“). Die Gegenprobe sucht im Text jede bestätigte "
      "Angabe wörtlich (Textschicht und neue Texterkennung) und lässt die festen Regeln erneut laufen; das Sprachmodell "
      "läuft dort nicht mit, weil es nach dem Schwärzen den veränderten Satz anders liest (in einem früheren Lauf am "
      "selben Tag hielt es „Herr“ allein für einen Namen und ein Eintrittsdatum für ein Geburtsdatum).")
    a("")
    a("## Fotos (erzeugt, Metadaten simuliert)")
    a("")
    a("| Datei | Größe | Vorschläge | Metadaten vorher | Erkennen | Gegenprobe | Reste (erste → zuletzt) |")
    a("|---|---|---|---|---:|---:|---:|")
    for x in f:
        vs = ", ".join(f"{n} {KAT_FOTO.get(k, k)}" for k, n in x["vorschlaege"].items()) or "–"
        a(f"| {x['datei']} | {x['pixel']} px | {vs} | {', '.join(x['metadaten_vorher'])} | {z(x['dauer_analyse_s'])} s | {z(x['dauer_gegenprobe_s'])} s | {x.get('reste_erste_gegenprobe', x['reste_gegenprobe'])} → {x['reste_gegenprobe']} |")
    a("")
    a("Für die Fotos gibt es keine vollständige Wahrheit; der simulierte Mensch bestätigt jeden Vorschlag. Von Hand "
      f"angesehen (Bild [`foto-ergebnis.jpg`](bilder/foto-ergebnis.jpg)): {HANDBLICK_FOTO}")
    a("")
    a("## Video (erzeugt, Metadaten und Ton simuliert)")
    a("")
    sch = v.get("schnitte") or []
    szenen = (f"{len(sch) + 1} Szenen (Schnitte erkannt bei Einzelbild {', '.join(str(x) for x in sch)}; danach beginnt jede "
              "Spur neu)" if sch else "eine Szene")
    a(f"{v['datei']}: {z(v['dauer_video_s'], 1)} s, {v['aufloesung']}, {v['bilder']} Einzelbilder, {szenen}. Metadaten vorher: "
      f"{', '.join(v['metadaten_vorher'])}. Der simulierte Mensch bestätigt jede Spur (Personen: Gesicht unkenntlich). "
      f"Von Hand angesehen (Stichprobe unten): {HANDBLICK_VIDEO}")
    a("")
    a("Eine Trefferquote für das Video ist nicht gemessen: Dafür müsste jedes Gesicht in jedem der "
      f"{v['bilder']} Einzelbilder von Hand markiert sein. Stattdessen: Gegenprobe über jedes Einzelbild, ein "
      "Kontrollversuch mit absichtlich ausgelassenen Bildern und eine Stichprobe zum Ansehen "
      "([`video-ergebnis-stichprobe.jpg`](bilder/video-ergebnis-stichprobe.jpg), ein Bild je Sekunde aus dem Ergebnis).")
    a("")
    a("## Grenzen dieser Messung")
    a("")
    a("- Die Schreiben sind erfunden und folgen drei Vorlagen; echte Akten sind vielfältiger. Die Zahlen zeigen, dass der "
      "Ablauf funktioniert, nicht, wie gut er auf beliebigen Unterlagen ist.")
    a("- Die Gegenprobe nutzt dieselben Erkennerfamilien wie die Erkennung (plus eine zweite Meinung für Kennzeichen und "
      "Augen aus Körperpunkten). Was keiner davon erkennt, findet auch die Gegenprobe nicht; darum bleibt der Blick des "
      "Menschen auf jede Seite Pflicht.")
    a("- Gemessen nur auf der CPU (die Grafikkarte des Rechners war nicht eingebunden); andere Programme auf dem "
      "Rechner liefen weiter. Andere Rechner sind schneller oder langsamer.")
    a("- Fotos und Video sind erzeugt, nicht aufgenommen. Echte Aufnahmen haben andere Lichtverhältnisse, Unschärfe "
      "und Gedränge; die Zahlen zeigen den Ablauf, keine Trefferquote für echte Bilder.")
    ziel.write_text("\n".join(t) + "\n", encoding="utf-8")


if __name__ == "__main__":
    pfad = Path(sys.argv[1] if len(sys.argv) > 1 else "nachweis/messwerte.json")
    schreiben(json.loads(pfad.read_text()), pfad.parent / "PROTOKOLL.md")
