"""Die offenen Modelle, einmal geladen und dann wiederverwendet. Alle liegen lokal (UNKENNTLICH_MODELLE)."""
from __future__ import annotations

import os
import threading
from functools import lru_cache
from pathlib import Path

ORDNER = Path(os.environ.get("UNKENNTLICH_MODELLE", "/modelle"))
FADEN = int(os.environ.get("UNKENNTLICH_FAEDEN", "8"))
_sperre = threading.RLock()

# Für README, Prüfbericht und Messprotokoll: was genau läuft (Stand 16.11.2026).
VERZEICHNIS = [
    {"aufgabe": "Namen, Anschriften und weitere Angaben im Text", "modell": "GLiNER2-PII multi",
     "quelle": "fastino/gliner2-privacy-filter-PII-multi @1cb4166", "lizenz": "Apache-2.0"},
    {"aufgabe": "Nummern mit Prüfziffer (IBAN, Steuer-ID), Telefon, E-Mail, Kennzeichen", "modell": "feste Regeln",
     "quelle": "unkenntlich/text_regeln.py", "lizenz": "AGPL-3.0-or-later"},
    {"aufgabe": "Texterkennung in Scans und Fotos", "modell": "Tesseract 5.5 mit tessdata_best Deutsch",
     "quelle": "tesseract-ocr/tessdata_best @e12c65a", "lizenz": "Apache-2.0"},
    {"aufgabe": "Gesichter", "modell": "YuNet (2026may)", "quelle": "opencv/opencv_zoo @26cc381", "lizenz": "MIT"},
    {"aufgabe": "Personen und ihre Umrisse, Verfolgung im Video", "modell": "YOLO26s-seg mit ByteTrack",
     "quelle": "Ultralytics 8.4.215, Release v8.4.0", "lizenz": "AGPL-3.0"},
    {"aufgabe": "Kopfbereich aus Körperpunkten", "modell": "YOLO26n-pose", "quelle": "Ultralytics, Release v8.4.0",
     "lizenz": "AGPL-3.0"},
    {"aufgabe": "Kfz-Kennzeichen", "modell": "YOLO26n Kennzeichen (Feinabstimmung)",
     "quelle": "ishaqinu/yolo26n-license-plate-detection @b9162ec", "lizenz": "AGPL-3.0"},
    {"aufgabe": "Kfz-Kennzeichen, zweite Meinung in der Gegenprobe", "modell": "YOLOv9-s Kennzeichen (open-image-models)",
     "quelle": "ankandrew/open-image-models, Release assets", "lizenz": "MIT"},
    {"aufgabe": "Unterschriften und Stempel", "modell": "RF-DETR Base (Feinabstimmung)",
     "quelle": "bluecopa/rf-detr-stamp-signature-detector @c59fd4f", "lizenz": "Apache-2.0"},
]


def _torch_faeden():
    import torch
    torch.set_num_threads(FADEN)


@lru_cache(maxsize=1)
def gliner():
    with _sperre:
        _torch_faeden()
        from gliner2 import GLiNER2
        return GLiNER2.from_pretrained(str(ORDNER / "gliner2-pii"))


@lru_cache(maxsize=1)
def yolo_seg():
    with _sperre:
        _torch_faeden()
        from ultralytics import YOLO
        return YOLO(str(ORDNER / "yolo26s-seg.pt"))


def yolo_seg_neu():
    """Eigene Instanz je Video (der Verfolger merkt sich Spuren im Modell)."""
    from ultralytics import YOLO
    return YOLO(str(ORDNER / "yolo26s-seg.pt"))


@lru_cache(maxsize=1)
def yolo_pose():
    with _sperre:
        _torch_faeden()
        from ultralytics import YOLO
        return YOLO(str(ORDNER / "yolo26n-pose.pt"))


@lru_cache(maxsize=1)
def yolo_kennzeichen():
    with _sperre:
        _torch_faeden()
        from ultralytics import YOLO
        return YOLO(str(ORDNER / "yolo26n-kennzeichen.pt"))


@lru_cache(maxsize=1)
def onnx_kennzeichen():
    import onnxruntime as ort
    opt = ort.SessionOptions()
    opt.intra_op_num_threads = FADEN
    return ort.InferenceSession(str(ORDNER / "yolo-v9-s-608-kennzeichen.onnx"), opt,
                                providers=["CPUExecutionProvider"])


@lru_cache(maxsize=1)
def rfdetr():
    with _sperre:
        _torch_faeden()
        import logging
        logging.getLogger("rf-detr").setLevel(logging.ERROR)
        from rfdetr import RFDETRBase
        # Der gespeicherte Kopf hat drei Klassen; 0 = Stempel, 1 = Unterschrift (am Prüfsatz nachgesehen).
        m = RFDETRBase(pretrain_weights=str(ORDNER / "rfdetr-stempel-unterschrift.pth"), num_classes=3)
        return m


@lru_cache(maxsize=16)
def yunet(breite: int, hoehe: int, schwelle: float = 0.6):
    """Ein Erkenner je Bildgröße und Schwelle, wiederverwendet (im Video sonst einer je Einzelbild)."""
    import cv2
    return cv2.FaceDetectorYN.create(str(ORDNER / "face_detection_yunet_2026may.onnx"), "", (breite, hoehe),
                                     schwelle, 0.3, 5000)
