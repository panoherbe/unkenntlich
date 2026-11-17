"""Lädt die freien Modelle einmalig beim Bauen des Images und prüft jede Datei per SHA-256.

    python werkzeuge/modelle_laden.py /modelle

Danach läuft Unkenntlich ohne Internet. Jede Quelle ist auf eine feste Version (Commit oder Release) gesetzt;
Lizenzen stehen in der README unter „Modelle und Lizenzen“.
"""
from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

HF_GLINER = "https://huggingface.co/fastino/gliner2-privacy-filter-PII-multi/resolve/1cb4166094dc58fa8d836429f060d6c95f62b495"

DATEIEN: list[tuple[str, str, str]] = [
    # (Ziel, Quelle, SHA-256)
    ("yolo26s-seg.pt", "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26s-seg.pt",
     "3da1d83e31caec96f9300eb4064f4f62882c133c7c264d63dfe61a7c197837a4"),
    ("yolo26n-pose.pt", "https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n-pose.pt",
     "eb3bb8268828aeaf515cec23a4bfafd793944a86fe9af94ba7823609c14522a9"),
    ("yolo26n-kennzeichen.pt",
     "https://huggingface.co/ishaqinu/yolo26n-license-plate-detection/resolve/"
     "b9162ec575eae48a1c3c3d42cd24e87fea83214b/alpr_26n.pt",
     "5eb8014b7180e90bb21abc35c912fa08d3596a80191e80a7559603c8161ef62c"),
    ("yolo-v9-s-608-kennzeichen.onnx",
     "https://github.com/ankandrew/open-image-models/releases/download/assets/yolo-v9-s-608-license-plates-end2end.onnx",
     "2b878b38d9aa07b6ddc3ea75c4ffcb39869bc5c218e0a14002f60ab2f7b0be9a"),
    ("face_detection_yunet_2026may.onnx",
     "https://media.githubusercontent.com/media/opencv/opencv_zoo/26cc381e4d2594bb9f47a26eb8fd96c94a13660d/"
     "models/face_detection_yunet/face_detection_yunet_2026may.onnx",
     "ebafce4e3c118d6554634be5c27ab333b4c047a9a8c3faf1d7cf93101c22f0f0"),
    ("rfdetr-stempel-unterschrift.pth",
     "https://huggingface.co/bluecopa/rf-detr-stamp-signature-detector/resolve/"
     "c59fd4f451b254501700a56c7769f1a3d788c753/checkpoint_best_ema.pth",
     "3a831ae093be64a01a4d9c635dc6071ad7c43c3e95c3da0b33a17351df1e7909"),
    ("tessdata/deu.traineddata",
     "https://github.com/tesseract-ocr/tessdata_best/raw/e12c65a915945e4c28e237a9b52bc4a8f39a0cec/deu.traineddata",
     "8407331d6aa0229dc927685c01a7938fc5a641d1a9524f74838cdac599f0d06e"),
    ("gliner2-pii/config.json", f"{HF_GLINER}/config.json",
     "164f17362bcf9d114067d3465e7374bfdd79ce6b605acb745de5a49dabb9595c"),
    ("gliner2-pii/encoder_config/config.json", f"{HF_GLINER}/encoder_config/config.json",
     "f27dd63cc43a248d2566f0b6ad7a115db353676ce0561dcbca45bac766464c1a"),
    ("gliner2-pii/tokenizer.json", f"{HF_GLINER}/tokenizer.json",
     "f6df10ec83bea993035b2dd7c39345a3d4fcf23421c2adb6cb4ffc1e6d1bc4b5"),
    ("gliner2-pii/tokenizer_config.json", f"{HF_GLINER}/tokenizer_config.json",
     "233beed1f1095cccfc7907cde31a8d90a0c6aa4fdfaf6493f8e55fd162e81ae6"),
    ("gliner2-pii/model.safetensors", f"{HF_GLINER}/model.safetensors",
     "0280f6f39f6012da50b6640bad438d9b7e763a1b0102094115d1b710c4dd79b6"),
]


def sha256(pfad: Path) -> str:
    h = hashlib.sha256()
    with pfad.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def laden(ziel: Path) -> int:
    fehler = 0
    for name, url, soll in DATEIEN:
        pfad = ziel / name
        pfad.parent.mkdir(parents=True, exist_ok=True)
        if not pfad.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "unkenntlich-modelle/0.1"})
            with urllib.request.urlopen(req, timeout=600) as antwort, pfad.open("wb") as f:
                while block := antwort.read(1 << 20):
                    f.write(block)
        ist = sha256(pfad)
        if not soll or ist != soll:
            print(f"FALSCHE PRÜFSUMME {name}: {ist} statt {soll}", file=sys.stderr)
            fehler += 1
        else:
            print(f"ok {name} {pfad.stat().st_size} Byte sha256={ist}")
    return fehler


if __name__ == "__main__":
    sys.exit(1 if laden(Path(sys.argv[1] if len(sys.argv) > 1 else "/modelle")) else 0)
