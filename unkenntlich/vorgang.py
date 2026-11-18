"""Ein Vorgang: abgelegte Dateien, Vorschläge (Stellen), Entscheidungen, Gegenprobe, Prüfbericht und Protokoll.

Alles liegt in einem Ordner auf dem eigenen Rechner (UNKENNTLICH_DATEN/vorgaenge/<id>) und wird mit „Alles löschen“
vollständig entfernt. Rechenarbeit läuft nacheinander in einem Hintergrund-Faden.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import queue
import secrets
import shutil
import threading
import time
import traceback
from pathlib import Path
from zoneinfo import ZoneInfo

from . import __version__, dokument, foto, gegenprobe, kategorien, video

DATEN = Path(os.environ.get("UNKENNTLICH_DATEN", "/daten")) / "vorgaenge"
BEISPIELE = Path(__file__).resolve().parent.parent / "pruefsatz"
ZONE = ZoneInfo("Europe/Berlin")
ARTEN = {".pdf": "dokument", ".jpg": "foto", ".jpeg": "foto", ".png": "foto", ".mp4": "video", ".mov": "video"}

_sperre = threading.RLock()
_vorgaenge: dict[str, dict] = {}
_auftraege: "queue.Queue[tuple]" = queue.Queue()


def _mal(n: int, eins: str, mehr: str) -> str:
    return f"{n} {eins if n == 1 else mehr}"


def jetzt() -> str:
    return dt.datetime.now(ZONE).isoformat(timespec="seconds")


def sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with open(pfad, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


# --- Zustand -----------------------------------------------------------------------------------------------------

def ordner(vid: str) -> Path:
    return DATEN / vid


def neu() -> dict:
    vid = secrets.token_hex(6)
    v = {"id": vid, "erstellt": jetzt(), "version": __version__, "phase": "ablegen", "dateien": [], "stellen": [],
         "protokoll": [], "gegenprobe": None, "zaehler": 0}
    for unter in ("eingang", "analyse", "ausgabe"):
        (ordner(vid) / unter).mkdir(parents=True, exist_ok=True)
    with _sperre:
        _vorgaenge[vid] = v
        protokoll(v, "Vorgang angelegt", "auf diesem Rechner, ohne Verbindung nach außen")
        speichern(v)
    return v


def laden(vid: str) -> dict | None:
    with _sperre:
        if vid in _vorgaenge:
            return _vorgaenge[vid]
        pfad = ordner(vid) / "zustand.json"
        if not vid.isalnum() or not pfad.exists():
            return None
        v = json.loads(pfad.read_text())
        _vorgaenge[vid] = v
        return v


def _json(o):
    """numpy-Zahlen und -Felder aus den Modellen als normale Zahlen speichern."""
    if hasattr(o, "tolist"):
        return o.tolist()
    if hasattr(o, "item"):
        return o.item()
    raise TypeError(type(o).__name__)


def speichern(v: dict) -> None:
    with _sperre:
        pfad = ordner(v["id"]) / "zustand.json"
        tmp = pfad.with_suffix(".tmp")
        tmp.write_text(json.dumps(v, ensure_ascii=False, default=_json))
        tmp.replace(pfad)


def loeschen(vid: str) -> bool:
    with _sperre:
        _vorgaenge.pop(vid, None)
        p = ordner(vid)
        if p.exists() and p.parent == DATEN:
            shutil.rmtree(p)
            return True
    return False


def protokoll(v: dict, ereignis: str, details: str = "") -> None:
    v["protokoll"].append({"zeit": jetzt(), "ereignis": ereignis, "details": details})


def datei(v: dict, did: str) -> dict | None:
    return next((d for d in v["dateien"] if d["id"] == did), None)


def oeffentlich(v: dict) -> dict:
    """Zustand für die Oberfläche (ohne Dateipfade)."""
    with _sperre:
        out = json.loads(json.dumps(v, default=_json))
    for d in out["dateien"]:
        d.pop("pfad", None)
        d.pop("ausgabe", None)
    out["bereit_fuer_gegenprobe"] = bereit(v)[0]
    out["offen"] = bereit(v)[1]
    return out


def bereit(v: dict) -> tuple[bool, str]:
    if not v["dateien"]:
        return False, "Noch keine Datei abgelegt."
    if any(d["status"] != "bereit" for d in v["dateien"]):
        return False, "Die Erkennung läuft noch."
    aktiv = {d["id"] for d in v["dateien"] if not d.get("ausgenommen")}
    offen_seiten = sum(1 for d in v["dateien"] if d["id"] in aktiv for s in d["seiten"] if not s["geprueft"])
    offen_stellen = sum(1 for s in v["stellen"] if s["entscheidung"] == "offen" and s["datei"] in aktiv)
    if offen_seiten or offen_stellen:
        teile = []
        if offen_seiten:
            teile.append(f"{offen_seiten} Seite(n) bzw. Datei(en) noch nicht angesehen")
        if offen_stellen:
            teile.append(f"{offen_stellen} Stelle(n) ohne Entscheidung")
        return False, "; ".join(teile) + "."
    return True, ""


# --- Dateien ablegen und erkennen --------------------------------------------------------------------------------

def ablegen(v: dict, name: str, quelle) -> dict:
    endung = Path(name).suffix.lower()
    art = ARTEN.get(endung)
    if not art:
        raise ValueError(f"Dateityp {endung or '?'} wird im Prototyp nicht unterstützt (PDF, JPG, PNG, MP4, MOV).")
    with _sperre:
        v["zaehler"] += 1
        did = f"d{v['zaehler']}"
    ziel = ordner(v["id"]) / "eingang" / f"{did}{endung}"
    if isinstance(quelle, (str, Path)):
        shutil.copyfile(quelle, ziel)
    else:
        with open(ziel, "wb") as f:
            shutil.copyfileobj(quelle, f)
    d = {"id": did, "name": Path(name).name, "art": art, "pfad": str(ziel), "groesse": ziel.stat().st_size,
         "sha256": sha256(ziel), "status": "wartet", "fortschritt": 0.0, "meldung": "wartet", "seiten": [],
         "metadaten": [], "abgelegt": jetzt()}
    with _sperre:
        v["dateien"].append(d)
        v["phase"] = "ablegen"
        v["gegenprobe"] = None
        protokoll(v, "Datei abgelegt", f"{d['name']} ({kategorien_art(art)}, {d['groesse']} Byte, SHA-256 {d['sha256']})")
        speichern(v)
    _auftraege.put(("analyse", v["id"], did))
    return d


def kategorien_art(art: str) -> str:
    return {"dokument": "Dokument", "foto": "Bild", "video": "Video"}[art]


def beispiele(v: dict) -> None:
    for pfad in (BEISPIELE / "dokumente" / "01-bescheid-scan-ocr.pdf", BEISPIELE / "fotos" / "marktplatz.jpg",
                 BEISPIELE / "video" / "fussgaengerzone.mp4"):
        name = {"01-bescheid-scan-ocr.pdf": "bescheid-scan.pdf"}.get(pfad.name, pfad.name)
        ablegen(v, name, pfad)


def _fortschritt(v, d):
    def f(anteil, text):
        with _sperre:
            d["fortschritt"] = round(float(anteil), 3)
            d["meldung"] = text
    return f


def _analyse(v: dict, d: dict) -> None:
    d["status"] = "liest"
    t0 = time.time()
    ziel = ordner(v["id"]) / "analyse" / d["id"]
    ziel.mkdir(parents=True, exist_ok=True)
    if d["art"] == "dokument":
        erg = dokument.analysieren(d["pfad"], _fortschritt(v, d))
    elif d["art"] == "foto":
        erg = foto.analysieren(d["pfad"], _fortschritt(v, d))
        d["schriftstueck"] = erg.get("schriftstueck", False)
        d["format"] = erg.get("format")
    else:
        erg = video.analysieren(d["pfad"], ziel, _fortschritt(v, d))
        d["video"] = {k: erg["video"][k] for k in ("fps", "bilder", "breite", "hoehe", "dauer", "ton")}
        d["video"]["schnitte"] = erg["video"].get("schnitte", [])
    with _sperre:
        for s in erg["stellen"]:
            v["zaehler"] += 1
            s["id"] = f"s{v['zaehler']}"
            s["datei"] = d["id"]
            s["entscheidung"] = "offen"
            s.setdefault("modus", None)
            s["neu"] = False
            v["stellen"].append(s)
        d["seiten"] = erg["seiten"]
        d["metadaten"] = erg["metadaten"]
        d["dauer_analyse"] = round(time.time() - t0, 2)
        d["status"] = "bereit"
        d["fortschritt"] = 1.0
        d["meldung"] = "bereit"
        anzahl = len(erg["stellen"])
        protokoll(v, "Erkennung fertig", f"{d['name']}: {anzahl} Vorschläge, {len(d['metadaten'])} Metadaten-Felder, "
                  f"{d['dauer_analyse']:.1f} s")
        if all(x["status"] == "bereit" for x in v["dateien"]):
            v["phase"] = "pruefen"
        speichern(v)


# --- Entscheidungen ----------------------------------------------------------------------------------------------

def entscheiden(v: dict, aenderungen: list[dict]) -> None:
    with _sperre:
        for a in aenderungen:
            s = next((x for x in v["stellen"] if x["id"] == a.get("id")), None)
            if not s:
                continue
            alt = (s["entscheidung"], s.get("modus"))
            if a.get("entscheidung") in ("offen", "unkenntlich", "sichtbar"):
                s["entscheidung"] = a["entscheidung"]
            if a.get("modus") in ("gesicht", "person") and s["kategorie"] == "person":
                s["modus"] = a["modus"]
            if "begruendung" in a:
                s["begruendung"] = str(a["begruendung"] or "")[:200]
            if (s["entscheidung"], s.get("modus")) != alt:
                protokoll(v, "Entscheidung", f"{s['id']} ({kategorien.bezeichnung(s['kategorie'])}, {_ort(v, s)}): "
                          + {"unkenntlich": "unkenntlich", "sichtbar": "bleibt sichtbar", "offen": "offen"}[s["entscheidung"]]
                          + (f", Modus {'ganze Person' if s.get('modus') == 'person' else 'Gesicht'}" if s["kategorie"] == "person" else "")
                          + (f" – {s['begruendung']}" if s["entscheidung"] == "sichtbar" and s.get("begruendung") else ""))
        v["gegenprobe"] = None
        if v["phase"] in ("gegenprobe", "fertig"):
            v["phase"] = "pruefen"
        speichern(v)


def _ort(v: dict, s: dict) -> str:
    d = datei(v, s["datei"])
    if d and d["art"] == "video":
        z = s.get("zeit") or {}
        return f"{d['name']}, {z.get('von', 0):.1f}–{z.get('bis', 0):.1f} s"
    if d and d["art"] == "dokument":
        return f"{d['name']}, Seite {s['seite'] + 1}"
    return d["name"] if d else "?"


def eigener_bereich(v: dict, did: str, seite: int, rechteck: list[float]) -> dict:
    with _sperre:
        v["zaehler"] += 1
        s = {"id": f"s{v['zaehler']}", "datei": did, "kategorie": "eigener_bereich", "grund": "von Hand markiert",
             "quelle": "Mensch", "sicherheit": 1.0, "seite": seite, "rechtecke": [[round(float(x), 2) for x in rechteck]],
             "text": None, "entscheidung": "unkenntlich", "modus": None, "neu": False}
        v["stellen"].append(s)
        v["gegenprobe"] = None
        protokoll(v, "Eigener Bereich", f"{s['id']} ({_ort(v, s)}) von Hand markiert: unkenntlich")
        speichern(v)
    return s


def seite_geprueft(v: dict, did: str, seite: int) -> None:
    """Die Seite (bzw. das Bild oder Video) wurde angesehen; noch offene Stellen darauf werden unkenntlich."""
    with _sperre:
        d = datei(v, did)
        if not d or seite >= len(d["seiten"]):
            return
        offene = [s for s in v["stellen"] if s["datei"] == did and s.get("seite", 0) == seite
                  and s["entscheidung"] == "offen"]
        for s in offene:
            s["entscheidung"] = "unkenntlich"
        d["seiten"][seite]["geprueft"] = True
        protokoll(v, "Angesehen und bestätigt", f"{d['name']}" + (f", Seite {seite + 1}" if d["art"] == "dokument" else "")
                  + f": {len(offene)} offene Vorschläge als unkenntlich bestätigt")
        speichern(v)


# --- Unkenntlich machen und Gegenprobe ---------------------------------------------------------------------------

def gegenprobe_starten(v: dict, kontrolle: dict | None = None) -> None:
    with _sperre:
        v["phase"] = "gegenprobe"
        v["gegenprobe"] = {"status": "laeuft", "start": jetzt(), "ergebnisse": {}, "reste": None,
                           "fortschritt": 0.0, "meldung": "beginnt"}
        protokoll(v, "Gegenprobe gestartet", "Dateien werden unkenntlich gemacht und erneut geprüft")
        speichern(v)
    _auftraege.put(("gegenprobe", v["id"], kontrolle))


def ausgabe_pfad(v: dict, d: dict) -> Path:
    endung = Path(d["pfad"]).suffix.lower()
    if d["art"] == "video":
        endung = ".mp4"
    stamm = Path(d["name"]).stem
    return ordner(v["id"]) / "ausgabe" / f"{d['id']}-{stamm}-unkenntlich{endung}"


def _gegenprobe(v: dict, kontrolle: dict | None) -> None:
    g = v["gegenprobe"]
    gesamt = 0
    aktiv = [d for d in v["dateien"] if not d.get("ausgenommen")]   # ausgenommene Dateien gibt es nicht heraus
    n = max(1, len(aktiv))
    t_alles = time.time()
    for k, d in enumerate(aktiv):
        stellen = [s for s in v["stellen"] if s["datei"] == d["id"]]
        best = [s for s in stellen if s["entscheidung"] == "unkenntlich"]
        sicht = [s for s in stellen if s["entscheidung"] == "sichtbar"]
        aus = ausgabe_pfad(v, d)

        def f(anteil, text, k=k, d=d):
            with _sperre:
                g["fortschritt"] = round((k + anteil) / n, 3)
                g["meldung"] = f"{d['name']}: {text}"
        t0 = time.time()
        if d["art"] == "dokument":
            f(0.0, "unkenntlich machen")
            dokument.schwaerzen(d["pfad"], aus, best, nur_ueberdecken=bool(kontrolle and kontrolle.get("nur_ueberdecken")),
                                neu_aufbauen=bool(d.get("neu_aufbauen")))
            t1 = time.time()
            erg = gegenprobe.dokument_pruefen(aus, best, sicht, lambda a, t: f(0.1 + 0.9 * a, t))
        elif d["art"] == "foto":
            f(0.0, "unkenntlich machen")
            foto.schwaerzen(d["pfad"], aus, best, d.get("schriftstueck", False))
            t1 = time.time()
            erg = gegenprobe.foto_pruefen(aus, best, sicht, d.get("schriftstueck", False), lambda a, t: f(0.1 + 0.9 * a, t),
                                          original=d["pfad"])
        else:
            spuren = json.loads((ordner(v["id"]) / "analyse" / d["id"] / "spuren.json").read_text())
            auslassen = set(kontrolle.get("auslassen", [])) if kontrolle else None
            video.schwaerzen(d["pfad"], aus, best, spuren, auslassen, lambda a, t: f(0.4 * a, "unkenntlich machen: " + t))
            t1 = time.time()
            video.vorschau_webm(aus, ordner(v["id"]) / "analyse" / d["id"] / "ergebnis.webm")
            erg = gegenprobe.video_pruefen(aus, best, sicht, spuren, 1, lambda a, t: f(0.4 + 0.6 * a, "Gegenprobe: " + t),
                                           original=d["pfad"])
        erg["sha256_aus"] = sha256(aus)
        erg["groesse_aus"] = aus.stat().st_size
        erg["dauer_schwaerzen"] = round(t1 - t0, 2)
        erg["dauer_gegenprobe"] = round(time.time() - t1, 2)
        with _sperre:
            g["ergebnisse"][d["id"]] = erg
            d["ausgabe"] = str(aus)
        gesamt += len(erg["reste"])
    from . import bericht
    with _sperre:
        g["reste"] = gesamt
        g["ende"] = jetzt()
        g["dauer"] = round(time.time() - t_alles, 2)
        protokoll(v, "Gegenprobe fertig", f"{gesamt} Reste" + (" – Export freigegeben" if gesamt == 0 else " – Export gesperrt"))
    g["meldung"] = "Prüfbericht"
    bericht.schreiben(v)  # vor „fertig“: wer den Bericht abruft, findet ihn vor
    with _sperre:
        g["status"] = "fertig"
        g["fortschritt"] = 1.0
        v["phase"] = "fertig" if gesamt == 0 else "gegenprobe"
        speichern(v)


def reste_uebernehmen(v: dict) -> int:
    """Reste der Gegenprobe werden neue, offene Vorschläge; die betroffenen Seiten müssen erneut angesehen werden.

    Ein Rest ohne Ort (etwa Metadaten oder Anmerkungen, die das Schwärzen nicht entfernt hat) lässt sich nicht als
    Bereich übernehmen. Damit der Export nicht für immer gesperrt bleibt, wird ein solches Dokument beim nächsten
    Durchlauf aus Seitenbildern neu aufgebaut: ohne Textschicht, ohne alles, was man nicht sieht.

    Fotos und Videos: Ab der zweiten Übernahme in derselben Datei werden Reste großzügig abgedeckt (siehe
    `foto.rest_stellen` und `video.spuren_aus_resten`). Bleibt danach noch etwas, ist der letzte Ausweg `ausnehmen`."""
    g = v.get("gegenprobe") or {}
    neu = 0
    with _sperre:
        for did, erg in (g.get("ergebnisse") or {}).items():
            d = datei(v, did)
            if not d or d.get("ausgenommen") or not erg.get("reste"):
                continue
            d["runden"] = d.get("runden", 0) + 1   # wie oft Reste dieser Datei übernommen wurden
            grosszuegig = d["art"] in ("foto", "video") and d["runden"] >= 2
            if grosszuegig:
                protokoll(v, "Großzügiger abdecken", f"{d['name']}: auch nach {_mal(d['runden'] - 1, 'Übernahme', 'Übernahmen')} "
                          f"{_mal(len(erg['reste']), 'Rest', 'Reste')}; die neuen Vorschläge sind doppelt so groß und mit "
                          "angrenzenden Flächen zusammengelegt")
            if d["art"] == "video":
                pfad = ordner(v["id"]) / "analyse" / did / "spuren.json"
                spuren = json.loads(pfad.read_text())
                neue = video.spuren_aus_resten(erg["reste"], spuren, d["video"]["fps"], d["video"]["bilder"],
                                               grosszuegig=grosszuegig, schnitte=d["video"].get("schnitte"))
                for st in neue:
                    v["zaehler"] += 1
                    st.update({"id": f"s{v['zaehler']}", "datei": did, "entscheidung": "offen", "neu": True})
                    v["stellen"].append(st)
                    neu += 1
                pfad.write_text(json.dumps(spuren))
                if neue:
                    d["seiten"][0]["geprueft"] = False
            elif d["art"] == "foto":
                best = [s for s in v["stellen"] if s["datei"] == did and s["entscheidung"] == "unkenntlich"]
                seite = d["seiten"][0]
                for st in foto.rest_stellen(erg["reste"], best, grosszuegig, seite["breite"], seite["hoehe"]):
                    v["zaehler"] += 1
                    kat = st["kategorie"] if st["kategorie"] in kategorien.KATEGORIEN else "eigener_bereich"
                    v["stellen"].append({**st, "id": f"s{v['zaehler']}", "datei": did, "kategorie": kat,
                                         "quelle": "Gegenprobe", "sicherheit": 1.0, "seite": 0, "text": None,
                                         "entscheidung": "offen", "modus": None, "neu": True})
                    seite["geprueft"] = False
                    neu += 1
            else:
                ohne_ort = [r for r in erg["reste"] if r.get("rechteck") is None]
                if ohne_ort and d["art"] == "dokument" and not d.get("neu_aufbauen"):
                    d["neu_aufbauen"] = True
                    protokoll(v, "Neu aufbauen", f"{d['name']}: {len(ohne_ort)} Rest(e) ohne Ort "
                              f"({', '.join(sorted({r['pruefung'] for r in ohne_ort}))}); das Dokument wird beim "
                              "nächsten Durchlauf aus Seitenbildern neu aufgebaut, ohne Textschicht")
                for r in erg["reste"]:
                    if r.get("rechteck") is None:
                        continue
                    v["zaehler"] += 1
                    kat = r["kategorie"] if r["kategorie"] in kategorien.KATEGORIEN else "eigener_bereich"
                    v["stellen"].append({"id": f"s{v['zaehler']}", "datei": did, "kategorie": kat,
                                         "grund": f"Rest aus der Gegenprobe ({r['pruefung']})", "quelle": "Gegenprobe",
                                         "sicherheit": 1.0, "seite": r.get("seite") or 0, "rechtecke": [r["rechteck"]],
                                         "text": None, "entscheidung": "offen", "modus": None, "neu": True})
                    d["seiten"][r.get("seite") or 0]["geprueft"] = False
                    neu += 1
        v["gegenprobe"] = None
        v["phase"] = "pruefen"
        protokoll(v, "Reste übernommen", f"{neu} Reste als neue Vorschläge zum Prüfen")
        speichern(v)
    return neu


def ausnehmen(v: dict, did: str) -> None:
    """Letzter Ausweg, wenn die Gegenprobe in einer Datei auch nach Übernahmen noch Reste findet: Die Datei wird nicht
    herausgegeben. Ihr Ergebnis kommt nicht in den Export und ist nicht abrufbar; der Prüfbericht nennt sie mit ihren
    Resten. Sind die übrigen Dateien ohne Rest, wird ihr Export frei. Nur nach mindestens einer Übernahme."""
    with _sperre:
        d = datei(v, did)
        g = v.get("gegenprobe") or {}
        erg = (g.get("ergebnisse") or {}).get(did) or {}
        if not d or g.get("status") != "fertig" or not erg.get("reste") or d.get("ausgenommen"):
            raise ValueError("Ausnehmen geht nur für eine Datei, in der die letzte Gegenprobe Reste fand.")
        if d.get("runden", 0) < 1:
            raise ValueError("Erst die Reste übernehmen und erneut prüfen; ausnehmen ist der letzte Ausweg.")
        d["ausgenommen"] = {"zeit": jetzt(), "runden": d.get("runden", 0), "reste": erg["reste"],
                            "pruefungen": erg.get("pruefungen", [])}
        g["reste"] = sum(len(e.get("reste", [])) for k, e in g["ergebnisse"].items()
                         if not (datei(v, k) or {}).get("ausgenommen"))
        protokoll(v, "Vom Export ausgenommen", f"{d['name']}: {_mal(len(erg['reste']), 'Rest', 'Reste')} nach "
                  f"{_mal(d.get('runden', 0), 'Übernahme', 'Übernahmen')}; die Datei wird nicht herausgegeben"
                  + (" – Export der übrigen Dateien freigegeben" if g["reste"] == 0 else ""))
        if g["reste"] == 0:
            v["phase"] = "fertig"
        speichern(v)
    from . import bericht
    bericht.schreiben(v)


# --- Hintergrund ------------------------------------------------------------------------------------------------

def _arbeiter() -> None:
    while True:
        art, vid, extra = _auftraege.get()
        v = laden(vid)
        if v is None:
            continue
        try:
            if art == "analyse":
                d = datei(v, extra)
                if d:
                    _analyse(v, d)
            elif art == "gegenprobe":
                _gegenprobe(v, extra)
        except Exception as e:  # pragma: no cover
            traceback.print_exc()
            with _sperre:
                if art == "analyse" and (d := datei(v, extra)):
                    d["status"] = "fehler"
                    d["meldung"] = f"Fehler: {e}"
                elif v.get("gegenprobe"):
                    v["gegenprobe"]["status"] = "fehler"
                    v["gegenprobe"]["meldung"] = f"Fehler: {e}"
                protokoll(v, "Fehler", str(e)[:200])
                speichern(v)


def starten() -> None:
    DATEN.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=_arbeiter, name="unkenntlich-arbeiter", daemon=True).start()


def warten(v: dict, zeit: float = 3600) -> None:
    """Für Kommandozeile und Tests: warten, bis keine Arbeit mehr ansteht."""
    ende = time.time() + zeit
    while time.time() < ende:
        with _sperre:
            laeuft = any(d["status"] in ("wartet", "liest") for d in v["dateien"]) or \
                (v.get("gegenprobe") or {}).get("status") == "laeuft"
        if not laeuft and _auftraege.empty():
            return
        time.sleep(0.2)
