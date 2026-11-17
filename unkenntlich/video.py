"""Videos (MP4, MOV): Personen über alle Einzelbilder verfolgen, Gesichter und Kennzeichen finden; je Person und je
Kennzeichen eine Spur, eine Karte, eine Entscheidung. Unkenntlich machen Bild für Bild, neu kodiert, ohne Ton und
ohne Metadaten. Koordinaten in Pixeln.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from . import bild, modelle
from .foto import FUELLUNG_FOTO, gefuelltes_rechteck

LUECKE = 12          # so viele Einzelbilder ohne Fund werden in einer Spur überbrückt
MIN_BILDER = 4       # kürzere Personenspuren ohne Gesicht gelten als Rauschen
NACHLAUF = 8         # Gesichter und Kennzeichen: so viele Einzelbilder vor und nach jedem Fund mit abdecken


def info(pfad) -> dict:
    aus = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                          str(pfad)], capture_output=True, text=True, check=True).stdout
    d = json.loads(aus)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    zaehler, nenner = (int(x) for x in v.get("avg_frame_rate", "25/1").split("/"))
    fps = zaehler / nenner if nenner else 25.0
    bilder = int(v.get("nb_frames") or round(float(d["format"].get("duration", 0)) * fps))
    tags = {**(d["format"].get("tags") or {}), **(v.get("tags") or {})}
    harmlos = {"major_brand", "minor_version", "compatible_brands", "encoder", "handler_name", "vendor_id",
               "language"}
    return {"fps": round(fps, 3), "bilder": bilder, "breite": int(v["width"]), "hoehe": int(v["height"]),
            "dauer": round(float(d["format"].get("duration", bilder / fps)), 2),
            "ton": any(s["codec_type"] == "audio" for s in d["streams"]),
            "tags": sorted(k for k in tags if k not in harmlos)}


def metadaten_inventar(i: dict) -> list[dict]:
    namen = {"creation_time": "Aufnahmezeit", "location": "Aufnahmeort (GPS)", "com.apple.quicktime.location.ISO6709":
             "Aufnahmeort (GPS)", "title": "Titel", "artist": "Urheber", "comment": "Kommentar",
             "com.apple.quicktime.make": "Kamerahersteller", "com.apple.quicktime.model": "Kameramodell"}
    out = [{"feld": namen.get(t, t), "art": "Videodatei"} for t in i["tags"]]
    if i["ton"]:
        out.append({"feld": "Tonspur (kann Stimmen und Namen enthalten)", "art": "Ton"})
    return out


def merkmal(frame: np.ndarray) -> tuple:
    """Kleines Abbild eines Einzelbilds (Farbverteilung und Graustufen) für die Schnitterkennung."""
    hsv = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2HSV)
    h = cv2.calcHist([hsv], [0, 1], None, [30, 32], [0, 180, 0, 256])
    grau = cv2.cvtColor(cv2.resize(frame, (64, 36), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
    return cv2.normalize(h, h).flatten(), grau.astype(np.int16)


def ist_schnitt(vorher: tuple, jetzt: tuple) -> bool:
    """Harter Schnitt zwischen zwei Einzelbildern: Farbverteilung und Helligkeit springen. Im Testvideo liegen
    Schnitte bei einer mittleren Abweichung von 52 bis 65 Graustufen, Bewegung innerhalb einer Szene bei höchstens 4."""
    korrelation = cv2.compareHist(vorher[0], jetzt[0], cv2.HISTCMP_CORREL)
    abweichung = float(np.abs(vorher[1] - jetzt[1]).mean())
    return (abweichung > 30 and korrelation < 0.9) or korrelation < 0.5


class Verfolger:
    """Einfacher Verfolger nach Überlappung (für Gesichter ohne Person und für Kennzeichen)."""

    def __init__(self, schwelle: float = 0.15):
        self.spuren: list[dict] = []
        self.schwelle = schwelle
        self.ab = 0

    def schnitt(self, nr: int) -> None:
        """Nach einem Schnitt beginnt jede Spur neu: Was davor zu sehen war, ist eine andere Szene."""
        self.ab = nr

    def schritt(self, nr: int, funde: list[tuple[tuple, float]]) -> None:
        offen = [s for s in self.spuren if nr - s["zuletzt"] <= LUECKE and s["zuletzt"] >= self.ab]
        for box, score in sorted(funde, key=lambda f: -f[1]):
            beste, wert = None, self.schwelle
            for s in offen:
                letzte = s["bilder"][s["zuletzt"]]
                w = max(bild.iou(box, letzte), 0.5 * bild.anteil_in(box, bild.erweitern(letzte, 0.6, 10**5, 10**5)))
                if w > wert:
                    beste, wert = s, w
            if beste is None:
                beste = {"bilder": {}, "zuletzt": nr, "score": 0.0}
                self.spuren.append(beste)
                offen.append(beste)
            beste["bilder"][nr] = tuple(box)
            beste["zuletzt"] = nr
            beste["score"] = max(beste["score"], score)
            offen.remove(beste)


def _luecken_fuellen(bilder: dict[int, tuple]) -> dict[int, tuple]:
    if not bilder:
        return bilder
    nrn = sorted(bilder)
    out = dict(bilder)
    for a, b in zip(nrn, nrn[1:]):
        if 1 < b - a <= LUECKE + 1:
            for k in range(a + 1, b):
                t = (k - a) / (b - a)
                out[k] = tuple(bilder[a][j] * (1 - t) + bilder[b][j] * t for j in range(4))
    return out


def _ausdehnen(bilder: dict[int, tuple], n: int, gesamt: int = 10**9, schnitte: list | None = None) -> dict[int, tuple]:
    """Eine Spur n Einzelbilder vor ihrem ersten und nach ihrem letzten Fund weiterführen, ebenso über Lücken bis 2n.
    Kleine Gesichter und Kennzeichen werden nicht in jedem Einzelbild erkannt; ohne Nachlauf blieben sie in den
    Bildern dazwischen sichtbar, und die Gegenprobe fände sie dort. Über einen Schnitt hinweg läuft nichts nach."""
    if not bilder:
        return bilder
    out = dict(bilder)
    nrn = sorted(bilder)
    for f in nrn:
        for k in range(max(0, f - n), min(gesamt, f + n + 1)):
            if k not in out and not any(min(f, k) < c <= max(f, k) for c in schnitte or ()):
                out[k] = bilder[f]
    return out


def analysieren(pfad, ordner: Path, fortschritt=lambda anteil, text: None) -> dict:
    """Liefert Stellen (eine je Spur) und schreibt die Bilddaten der Spuren nach `ordner/spuren.json`."""
    i = info(pfad)
    cap = cv2.VideoCapture(str(pfad))
    seg = modelle.yolo_seg_neu()
    personen: dict[int, dict] = {}
    gesichter_frei = Verfolger()
    schilder = Verfolger(0.1)
    nr = 0
    gesamt = max(1, i["bilder"])
    vorher, versatz, schnitte = None, 0, []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        m = merkmal(frame)
        if vorher is not None and ist_schnitt(vorher, m):
            # Schnitt: Personen, Gesichter und Kennzeichen danach sind neue Spuren mit neuen Karten. Sonst ginge eine
            # Entscheidung („sichtbar lassen“) auf jemanden über, der zufällig an derselben Stelle der nächsten Szene steht.
            schnitte.append(nr)
            seg = modelle.yolo_seg_neu()
            versatz += 100_000
            gesichter_frei.schnitt(nr)
            schilder.schnitt(nr)
        vorher = m
        r = seg.track(frame, persist=True, tracker="bytetrack.yaml", classes=[0], conf=0.3, verbose=False)[0]
        aktuell = []
        if r.boxes is not None and r.boxes.id is not None:
            polys = r.masks.xy if r.masks is not None else [None] * len(r.boxes)
            for box, tid, poly in zip(r.boxes.xyxy.tolist(), [t + versatz for t in r.boxes.id.int().tolist()], polys):
                p = personen.setdefault(tid, {"boxen": {}, "koepfe": {}, "umrisse": {}, "gesichter": {}})
                p["boxen"][nr] = tuple(box)
                if poly is not None and len(poly) >= 3:
                    p["umrisse"][nr] = bild.vereinfachen(poly, 40)
                aktuell.append((tid, tuple(box)))
        for k in bild.koepfe(frame):
            ziel = max(aktuell, key=lambda a: bild.iou(a[1], k["box"]), default=None)
            if ziel and bild.iou(ziel[1], k["box"]) > 0.45 and k["kopf"]:
                personen[ziel[0]]["koepfe"][nr] = k["kopf"]
        frei = []
        for box, s in bild.gesichter(frame, 0.5):
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            traeger = [a for a in aktuell if a[1][0] <= cx <= a[1][2] and a[1][1] <= cy <= a[1][1] + 0.6 * (a[1][3] - a[1][1])]
            if traeger:
                tid = min(traeger, key=lambda a: a[1][3] - a[1][1])[0]
                personen[tid]["gesichter"][nr] = (box, s)
            else:
                frei.append((box, s))
        gesichter_frei.schritt(nr, frei)
        schilder.schritt(nr, bild.kennzeichen_beide(frame))
        nr += 1
        if nr % 5 == 0:
            fortschritt(min(0.95, nr / gesamt), f"Einzelbild {nr} von {gesamt}")
    cap.release()
    i["bilder"] = nr
    i["schnitte"] = schnitte

    # Gesichter ohne Person, die meist innerhalb einer verfolgten Person liegen, gehören zu ihr.
    uebrig = []
    for s in gesichter_frei.spuren:
        stimmen: dict[int, int] = {}
        for f, box in s["bilder"].items():
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            for tid, p in personen.items():
                b = p["boxen"].get(f)
                if b and b[0] - 10 <= cx <= b[2] + 10 and b[1] - 0.15 * (b[3] - b[1]) <= cy <= b[1] + 0.5 * (b[3] - b[1]):
                    stimmen[tid] = stimmen.get(tid, 0) + 1
        if stimmen and max(stimmen.values()) >= 0.5 * len(s["bilder"]):
            tid = max(stimmen, key=stimmen.get)
            for f, box in s["bilder"].items():
                personen[tid]["gesichter"].setdefault(f, (box, s["score"]))
                bw, bh = box[2] - box[0], box[3] - box[1]
                personen[tid]["boxen"].setdefault(f, (box[0] - bw, box[1] - 0.3 * bh, box[2] + bw, box[3] + 5.5 * bh))
        else:
            uebrig.append(s)
    # Alle übrigen Gesichter bleiben Vorschläge, auch kurze und unsichere: Was die Gegenprobe später findet,
    # soll der Mensch vorher gesehen haben. Kurze Spuren landen in der Oberfläche unter „Hintergrund“.
    gesichter_frei.spuren = uebrig

    spuren: dict[str, dict] = {}
    stellen: list[dict] = []
    for tid, p in sorted(personen.items()):
        if len(p["boxen"]) < MIN_BILDER and not p["gesichter"]:
            continue
        boxen = _luecken_fuellen(p["boxen"])
        koepfe = {}
        for f, box in boxen.items():
            teile = []
            if f in p["gesichter"]:
                teile.append(bild.erweitern(p["gesichter"][f][0], 0.35, i["breite"], i["hoehe"], oben=0.15))
            if f in p["koepfe"]:
                teile.append(p["koepfe"][f])
            if teile:
                a = np.array(teile)
                koepfe[f] = (a[:, 0].min(), a[:, 1].min(), a[:, 2].max(), a[:, 3].max())
        koepfe = _luecken_fuellen(koepfe)
        for f, box in boxen.items():
            if f not in koepfe:
                k = bild.kopf_aus_punkten(None, box)
                if k:
                    koepfe[f] = k
            hoehe = box[3] - box[1]
            if hoehe < 0.2 * i["hoehe"]:
                # kleine Personen: Kopfpunkte sind unsicher, darum das ganze obere Drittel der Person, etwas breiter
                b = (box[0] - 0.2 * (box[2] - box[0]), box[1] - 0.06 * hoehe, box[2] + 0.2 * (box[2] - box[0]),
                     box[1] + 0.32 * hoehe)
                k = koepfe.get(f)
                koepfe[f] = b if k is None else (min(k[0], b[0]), min(k[1], b[1]), max(k[2], b[2]), max(k[3], b[3]))
        koepfe = _ausdehnen(koepfe, 4, i["bilder"], schnitte)
        sid = f"p{tid}"
        spuren[sid] = {"art": "person", "boxen": _runden(boxen), "koepfe": _runden(koepfe),
                       "umrisse": {str(k): v for k, v in p["umrisse"].items()}}
        gesicht_anteil = len(p["gesichter"]) / max(1, len(p["boxen"]))
        st = _spur_stelle(sid, "person", boxen, i, "Person verfolgt über "
                          f"{len(boxen)} Einzelbilder" + (", Gesicht erkannt" if p["gesichter"] else ""),
                          "YOLO26-seg + ByteTrack" + (" · YuNet" if p["gesichter"] else ""),
                          max([s for _, s in p["gesichter"].values()] or [0.0]), gesicht_anteil)
        st["zeit"]["hintergrund"] = max(b[3] - b[1] for b in boxen.values()) < 0.14 * i["hoehe"]
        stellen.append(st)
    for n, s in enumerate(gesichter_frei.spuren):
        boxen = _ausdehnen(_luecken_fuellen({f: bild.erweitern(b, 0.35, i["breite"], i["hoehe"], oben=0.15)
                                             for f, b in s["bilder"].items()}), NACHLAUF, i["bilder"], schnitte)
        sid = f"g{n}"
        spuren[sid] = {"art": "gesicht", "boxen": _runden(boxen)}
        stellen.append(_spur_stelle(sid, "gesicht", boxen, i, "Gesicht ohne erkannte Person (z. B. Plakat, nah)",
                                    "YuNet", s["score"], 1.0))
    for n, s in enumerate(schilder.spuren):
        boxen = _ausdehnen(_luecken_fuellen({f: bild.erweitern(b, 0.15, i["breite"], i["hoehe"])
                                             for f, b in s["bilder"].items()}), NACHLAUF, i["bilder"], schnitte)
        sid = f"k{n}"
        spuren[sid] = {"art": "kennzeichen", "boxen": _runden(boxen)}
        stellen.append(_spur_stelle(sid, "kennzeichen", boxen, i, "Kfz-Kennzeichen, verfolgt",
                                    "YOLO26 · YOLOv9 (Kennzeichen)", s["score"], 1.0))
    for st in stellen:
        st["zeit"]["kurz"] = st["zeit"]["bis"] - st["zeit"]["von"] < 0.5
    (ordner / "spuren.json").write_text(json.dumps(spuren))
    fortschritt(0.96, "Vorschaubilder")
    miniaturen(pfad, ordner, spuren)
    fortschritt(0.98, "Vorschau für den Browser")
    vorschau_webm(pfad, ordner / "vorschau.webm")
    fortschritt(1.0, "fertig")
    return {"seiten": [{"breite": i["breite"], "hoehe": i["hoehe"], "geprueft": False}], "stellen": stellen,
            "metadaten": metadaten_inventar(i), "video": i}


def _runden(d: dict) -> dict:
    return {str(k): [round(float(v), 1) for v in b] for k, b in sorted(d.items())}


def _spur_stelle(sid, kategorie, boxen, i, grund, quelle, sicherheit, gesicht_anteil) -> dict:
    nrn = sorted(boxen)
    groesste = max(nrn, key=lambda f: (boxen[f][2] - boxen[f][0]) * (boxen[f][3] - boxen[f][1]))
    return {"spur": sid, "kategorie": kategorie, "grund": grund, "quelle": quelle, "sicherheit": round(float(sicherheit), 3),
            "seite": 0, "rechtecke": [], "text": None, "modus": "gesicht" if kategorie == "person" else None,
            "zeit": {"von": round(nrn[0] / i["fps"], 2), "bis": round(nrn[-1] / i["fps"], 2), "bilder": len(nrn),
                     "gesicht_anteil": round(gesicht_anteil, 2), "bild_gross": groesste}}


def miniaturen(pfad, ordner: Path, spuren: dict) -> None:
    """Je Spur ein Ausschnitt aus dem Einzelbild, in dem sie am größten ist (nur für die Oberfläche, lokal)."""
    ziel = {}
    for sid, s in spuren.items():
        boxen = s["boxen"]
        f = max(boxen, key=lambda k: (boxen[k][2] - boxen[k][0]) * (boxen[k][3] - boxen[k][1]))
        ziel.setdefault(int(f), []).append((sid, boxen[f]))
    cap = cv2.VideoCapture(str(pfad))
    nr = 0
    while ziel:
        ok, frame = cap.read()
        if not ok:
            break
        for sid, b in ziel.pop(nr, []):
            h, w = frame.shape[:2]
            x0, y0, x1, y1 = bild.erweitern(tuple(b), 0.25, w, h)
            aus = frame[int(y0):int(y1), int(x0):int(x1)]
            if aus.size:
                hoehe = 240
                aus = cv2.resize(aus, (max(1, int(aus.shape[1] * hoehe / aus.shape[0])), hoehe))
                cv2.imwrite(str(ordner / f"spur-{sid}.jpg"), aus, [cv2.IMWRITE_JPEG_QUALITY, 85])
        nr += 1
    cap.release()


def spuren_aus_resten(reste: list[dict], spuren: dict, fps: float, gesamt: int, praefix: str = "r") -> list[dict]:
    """Reste der Gegenprobe werden neue Spuren (in `spuren` eingetragen) und neue, offene Stellen."""
    je_bild: dict[int, list] = {}
    for r in reste:
        if r.get("bild") is not None and r.get("rechteck"):
            je_bild.setdefault(r["bild"], []).append((tuple(r["rechteck"]), 1.0))
    verf = Verfolger(0.1)
    for nr in sorted(je_bild):
        verf.schritt(nr, je_bild[nr])
    neu = []
    for n, sp in enumerate(verf.spuren):
        sid = f"{praefix}{len(spuren)}x{n}"
        boxen = _ausdehnen(_luecken_fuellen({k: bild.erweitern(b, 0.3, 10**5, 10**5) for k, b in sp["bilder"].items()}),
                           NACHLAUF, gesamt)
        spuren[sid] = {"art": "gesicht", "boxen": _runden(boxen)}
        nrn = sorted(boxen)
        neu.append({"spur": sid, "kategorie": "gesicht", "grund": "Rest aus der Gegenprobe", "quelle": "Gegenprobe",
                    "sicherheit": 1.0, "seite": 0, "rechtecke": [], "text": None, "modus": None,
                    "zeit": {"von": round(nrn[0] / fps, 2), "bis": round(nrn[-1] / fps, 2), "bilder": len(nrn),
                             "gesicht_anteil": 1.0, "bild_gross": nrn[0], "kurz": True}})
    return neu


def fuellungen(spuren: dict, stellen: list[dict], nr: int) -> list:
    """Was in Einzelbild `nr` deckend überschrieben wird: Rechtecke (x0, y0, x1, y1) und Umrisse (Polygone)."""
    out = []
    k = str(nr)
    for s in stellen:
        sp = spuren.get(s.get("spur") or "")
        if not sp:
            continue
        if sp["art"] == "person":
            if s.get("modus") == "person":
                if k in sp.get("umrisse", {}):
                    out.append(("umriss", sp["umrisse"][k]))
                elif k in sp["boxen"]:
                    out.append(("rechteck", sp["boxen"][k]))
            if k in sp.get("koepfe", {}):
                out.append(("rechteck", bild.erweitern(tuple(sp["koepfe"][k]), 0.15, 10**5, 10**5)))
        elif k in sp["boxen"]:
            out.append(("rechteck", sp["boxen"][k]))
    return out


def zeichnen(frame: np.ndarray, flaechen: list) -> None:
    for art, f in flaechen:
        if art == "umriss":
            pts = np.array(f, np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(frame, [pts], FUELLUNG_FOTO[::-1])
            cv2.polylines(frame, [pts], True, FUELLUNG_FOTO[::-1], 9)
        else:
            x0, y0, x1, y1 = (int(round(v)) for v in f)
            gefuelltes_rechteck(frame, (x0, y0, x1, y1), FUELLUNG_FOTO[::-1], int(min(x1 - x0, y1 - y0) * 0.18))


def schwaerzen(eingang, ausgang, stellen: list[dict], spuren: dict, auslassen=None,
               fortschritt=lambda a, t: None) -> dict:
    """Jedes Einzelbild deckend bearbeiten und neu kodieren (H.264), ohne Ton und ohne Metadaten.

    `auslassen` (Menge von Einzelbild-Nummern) ist nur für den Kontrollversuch der Messung."""
    i = info(eingang)
    cap = cv2.VideoCapture(str(eingang))
    ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s",
                           f"{i['breite']}x{i['hoehe']}", "-r", str(i["fps"]), "-i", "-", "-an", "-sn", "-dn",
                           "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
                           "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
                           "-movflags", "+faststart", str(ausgang)], stdin=subprocess.PIPE)
    nr = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if not auslassen or nr not in auslassen:
            zeichnen(frame, fuellungen(spuren, stellen, nr))
        ff.stdin.write(frame.tobytes())
        nr += 1
        if nr % 25 == 0:
            fortschritt(nr / max(1, i["bilder"]), f"Einzelbild {nr}")
    cap.release()
    ff.stdin.close()
    if ff.wait() != 0:
        raise RuntimeError("ffmpeg konnte das Video nicht schreiben")
    return {"bilder": nr}


def vorschau_webm(pfad, ziel) -> None:
    """Vorschau für die Oberfläche als WebM (VP9), weil nicht jeder Browser H.264 abspielt; ohne Ton, 720 Zeilen."""
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(pfad), "-an", "-sn", "-map_metadata", "-1",
                    "-vf", "scale=-2:720", "-c:v", "libvpx-vp9", "-deadline", "realtime", "-cpu-used", "8",
                    "-row-mt", "1", "-b:v", "0", "-crf", "40", str(ziel)], check=True)


def standbild(pfad, sekunde: float, max_breite: int = 1280) -> bytes:
    cap = cv2.VideoCapture(str(pfad))
    cap.set(cv2.CAP_PROP_POS_MSEC, sekunde * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return b""
    if frame.shape[1] > max_breite:
        frame = cv2.resize(frame, (max_breite, int(frame.shape[0] * max_breite / frame.shape[1])))
    return cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes()
