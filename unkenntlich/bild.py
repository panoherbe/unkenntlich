"""Erkenner für Bilder: Gesichter, Köpfe, Personen, Kfz-Kennzeichen, Unterschriften und Stempel.

Alle Funktionen nehmen ein Bild als numpy-Array (BGR wie OpenCV, außer wo RGB steht) und geben Rechtecke in
Pixeln zurück: (x0, y0, x1, y1).
"""
from __future__ import annotations

import cv2
import numpy as np

from . import modelle

Box = tuple[float, float, float, float]


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    schnitt = ix * iy
    if schnitt <= 0:
        return 0.0
    fa = (a[2] - a[0]) * (a[3] - a[1])
    fb = (b[2] - b[0]) * (b[3] - b[1])
    return schnitt / max(1e-9, fa + fb - schnitt)


def anteil_in(a: Box, b: Box) -> float:
    """Anteil der Fläche von a, der in b liegt."""
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    fa = max(1e-9, (a[2] - a[0]) * (a[3] - a[1]))
    return ix * iy / fa


def erweitern(b: Box, faktor: float, breite: int, hoehe: int, oben: float = 0.0) -> Box:
    w, h = b[2] - b[0], b[3] - b[1]
    dx, dy = w * faktor / 2, h * faktor / 2
    return (max(0.0, b[0] - dx), max(0.0, b[1] - dy - h * oben), min(float(breite), b[2] + dx),
            min(float(hoehe), b[3] + dy))


def nms(boxen: list[tuple[Box, float]], schwelle: float = 0.4) -> list[tuple[Box, float]]:
    boxen = sorted(boxen, key=lambda x: -x[1])
    behalten: list[tuple[Box, float]] = []
    for b, s in boxen:
        if all(iou(b, k) < schwelle and anteil_in(b, k) < 0.7 for k, _ in behalten):
            behalten.append((b, s))
    return behalten


# --- Gesichter (YuNet) ------------------------------------------------------------------------------------------

def gesichter(bild: np.ndarray, schwelle: float = 0.6) -> list[tuple[Box, float]]:
    """YuNet auf voller Auflösung (Gesichter ab etwa 10 px) und verkleinert (große Gesichter über 300 px)."""
    h, w = bild.shape[:2]
    funde: list[tuple[Box, float]] = []
    maassstaebe = [1.0] if max(h, w) <= 2400 else [2400 / max(h, w)]
    maassstaebe += [m * 0.4 for m in maassstaebe[:1]]
    for m in maassstaebe:
        b = bild if m == 1.0 else cv2.resize(bild, (int(w * m), int(h * m)), interpolation=cv2.INTER_AREA)
        det = modelle.yunet(b.shape[1], b.shape[0], schwelle)
        _, f = det.detect(b)
        if f is None:
            continue
        for zeile in f:
            x, y, bw, bh, s = zeile[0], zeile[1], zeile[2], zeile[3], zeile[-1]
            funde.append(((x / m, y / m, (x + bw) / m, (y + bh) / m), float(s)))
    return nms(funde, 0.3)


# --- Personen und Köpfe (YOLO26) --------------------------------------------------------------------------------

def personen(bild: np.ndarray, schwelle: float = 0.35) -> list[dict]:
    """Personen mit Umriss (Polygon in Pixeln)."""
    r = modelle.yolo_seg()(bild, classes=[0], conf=schwelle, verbose=False, retina_masks=False)[0]
    out = []
    if r.boxes is None:
        return out
    polys = r.masks.xy if r.masks is not None else [None] * len(r.boxes)
    for box, conf, poly in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), polys):
        out.append({"box": tuple(box), "score": float(conf),
                    "umriss": vereinfachen(poly) if poly is not None and len(poly) >= 3 else None})
    return out


def vereinfachen(poly, max_punkte: int = 48) -> list[list[float]]:
    p = np.asarray(poly, dtype=np.float32)
    if len(p) > max_punkte:
        eps = 1.0
        while True:
            q = cv2.approxPolyDP(p.reshape(-1, 1, 2), eps, True).reshape(-1, 2)
            if len(q) <= max_punkte or eps > 50:
                p = q
                break
            eps *= 1.6
    return [[round(float(x), 1), round(float(y), 1)] for x, y in p]


def kopf_aus_punkten(punkte: np.ndarray, person: Box) -> Box | None:
    """Kopfbereich aus Nase, Augen und Ohren (COCO-Punkte 0–4); ohne diese der obere Teil der Person."""
    sicher = punkte[:5][punkte[:5, 2] > 0.35] if punkte is not None else np.empty((0, 3))
    ph = person[3] - person[1]
    pw = person[2] - person[0]
    if len(sicher) >= 2:
        cx, cy = float(sicher[:, 0].mean()), float(sicher[:, 1].mean())
        spanne = float(max(sicher[:, 0].max() - sicher[:, 0].min(), sicher[:, 1].max() - sicher[:, 1].min()))
        groesse = max(spanne * 2.2, ph / 7.0, 8.0)
        groesse = min(groesse, max(pw, 8.0) * 1.1)
        return (cx - groesse / 2, cy - groesse * 0.62, cx + groesse / 2, cy + groesse * 0.55)
    if ph > 1.6 * pw:  # aufrecht: Kopf im oberen Siebtel
        groesse = ph / 6.5
        cx = (person[0] + person[2]) / 2
        return (cx - groesse * 0.6, person[1], cx + groesse * 0.6, person[1] + groesse * 1.15)
    return None


def koepfe(bild: np.ndarray, schwelle: float = 0.35) -> list[dict]:
    r = modelle.yolo_pose()(bild, conf=schwelle, verbose=False)[0]
    out = []
    if r.boxes is None or r.keypoints is None:
        return out
    pts = r.keypoints.data.cpu().numpy()
    for box, conf, p in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist(), pts):
        kopf = kopf_aus_punkten(p, tuple(box))
        augen = [(float(x), float(y)) for x, y, c in p[1:3] if c > 0.5]
        out.append({"box": tuple(box), "score": float(conf), "kopf": kopf, "augen": augen})
    return out


# --- Kfz-Kennzeichen --------------------------------------------------------------------------------------------

def _kacheln(h: int, w: int, groesse: int = 1280, ueberlapp: int = 160):
    if max(h, w) <= 2400:
        return [(0, 0, w, h)]
    kacheln = [(0, 0, w, h)]
    schritt = groesse - ueberlapp
    for y in range(0, max(1, h - ueberlapp), schritt):
        for x in range(0, max(1, w - ueberlapp), schritt):
            kacheln.append((x, y, min(w, x + groesse), min(h, y + groesse)))
    return kacheln


def kennzeichen_beide(bild: np.ndarray, schwelle: float = 0.25) -> list[tuple[Box, float]]:
    """Vorschläge aus beiden Kennzeichen-Modellen zusammen (mehr Treffer; die Gegenprobe nutzt dieselben)."""
    return nms(kennzeichen(bild, schwelle) + kennzeichen_zweitmeinung(bild, schwelle), 0.3)


def kennzeichen(bild: np.ndarray, schwelle: float = 0.3) -> list[tuple[Box, float]]:
    """YOLO26n, feinabgestimmt auf Kennzeichen; große Bilder zusätzlich in Kacheln."""
    h, w = bild.shape[:2]
    funde = []
    for x0, y0, x1, y1 in _kacheln(h, w):
        r = modelle.yolo_kennzeichen()(bild[y0:y1, x0:x1], conf=schwelle, verbose=False)[0]
        for b, s in zip(r.boxes.xyxy.tolist(), r.boxes.conf.tolist()):
            funde.append(((b[0] + x0, b[1] + y0, b[2] + x0, b[3] + y0), float(s)))
    return nms(funde, 0.3)


def kennzeichen_zweitmeinung(bild: np.ndarray, schwelle: float = 0.3) -> list[tuple[Box, float]]:
    """YOLOv9-s aus open-image-models (ONNX), unabhängig trainiert; für die Gegenprobe."""
    sitzung = modelle.onnx_kennzeichen()
    h, w = bild.shape[:2]
    funde = []
    for x0, y0, x1, y1 in _kacheln(h, w):
        teil = bild[y0:y1, x0:x1]
        th, tw = teil.shape[:2]
        r = min(608 / th, 608 / tw)
        nw, nh = int(round(tw * r)), int(round(th * r))
        dw, dh = (608 - nw) / 2, (608 - nh) / 2
        im = cv2.resize(teil, (nw, nh), interpolation=cv2.INTER_LINEAR)
        im = cv2.copyMakeBorder(im, int(round(dh - 0.1)), int(round(dh + 0.1)), int(round(dw - 0.1)),
                                int(round(dw + 0.1)), cv2.BORDER_CONSTANT, value=(114, 114, 114))
        x = (im.transpose(2, 0, 1)[::-1] / 255.0).astype(np.float32)[None]
        aus = sitzung.run(None, {sitzung.get_inputs()[0].name: x})[0]
        for zeile in aus:
            s = float(zeile[6])
            if s < schwelle:
                continue
            bx = [(zeile[1] - dw) / r, (zeile[2] - dh) / r, (zeile[3] - dw) / r, (zeile[4] - dh) / r]
            funde.append(((bx[0] + x0, bx[1] + y0, bx[2] + x0, bx[3] + y0), s))
    return nms(funde, 0.3)


# --- Unterschriften und Stempel (RF-DETR) -----------------------------------------------------------------------

RFDETR_KLASSEN = {0: "stempel", 1: "unterschrift"}


def unterschriften_stempel(bild_rgb: np.ndarray, schwelle: float = 0.3) -> list[tuple[Box, str, float]]:
    from PIL import Image
    m = modelle.rfdetr()
    det = m.predict(Image.fromarray(bild_rgb), threshold=schwelle)
    out = []
    for box, kl, s in zip(det.xyxy.tolist(), det.class_id.tolist(), det.confidence.tolist()):
        kat = RFDETR_KLASSEN.get(int(kl))
        if kat:
            out.append((tuple(box), kat, float(s)))
    return out
