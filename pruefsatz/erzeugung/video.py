"""Erzeugt die Szenen des Testvideos mit einem offenen Videomodell: keine echten Personen, keine echten Kennzeichen.

    docker run --rm --gpus all -u "$(id -u):$(id -g)" -e HOME=/tmp -e HF_HOME=/hf -e HF_HUB_OFFLINE=1 \
        -v <modelle>:/hf -v "$PWD":/app -w /app unkenntlich-erzeugen:1 python pruefsatz/erzeugung/video.py szene-1

Eine Szene je Aufruf: Mit zwei Szenen in einem Prozess reichten 62 GB Hauptspeicher beim Dekodieren der zweiten nicht
(17.11.2026, Prozess beendet nach 22 Minuten Rechnen).

Modell: Vimoo-1.0-Lite (Vimoo-AI, Oktober 2026, Apache-2.0), Bild und Text zu Video, Ordner /hf/vimoo-1.0-lite
(`hf download Vimoo-AI/Vimoo-1.0-Lite`, dazu die Bausteine aus `modular_model_index.json`: Qwen2.5-VL-7B-Instruct als
Text-Kodierer, Glyph-ByT5 für Schrift im Bild, VAE aus Wan2.2-TI2V-5B, SigLIP für das Startbild). Jede Szene beginnt
mit einem Standbild aus bilder.py (MOSS-Image-SFT), damit Personen und erfundene Kennzeichen feststehen. Auf einer Grafikkarte mit 12 GB
werden Text-Kodierer und Videomodell blockweise ein- und ausgelagert; weniger Schritte und eine kleinere Auflösung als
die Voreinstellung (50 Schritte, 1280 × 720), damit eine Szene in Minuten statt Stunden fertig ist. Feste Startwerte;
die Ergebnisse stehen unter CC0 1.0 (pruefsatz/QUELLEN.md). metadaten.py setzt die Szenen zum Testvideo zusammen.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch

HIER = Path(__file__).resolve().parent
MODELL = Path("/hf/vimoo-1.0-lite")
ROH = HIER / "roh"
sys.path.insert(0, "/vimoo/examples")

BREITE, HOEHE, BILDER, SCHRITTE, FPS = 1024, 560, 81, 30, 24
STIL = ("Realistic documentary footage filmed with a fixed camera on a tripod at eye level, natural daylight, sharp "
        "focus, ordinary people in everyday clothes walking at a normal pace. The camera remains fixed throughout.")

SZENEN = [
    # (Datei, Startwert, Beschreibung)
    ("szene-1", 3114,
     "A pedestrian shopping street in a small German town on a bright afternoon, view along the street. Five people "
     "walk slowly towards the camera at different distances, their faces clearly visible: a couple in their forties, "
     "a young woman with a backpack, an older man with a flat cap, a teenager with headphones. On the left a white "
     "delivery van is parked at the kerb with its front facing the camera; its licence plate is a white German plate "
     "with a blue EU band and the black text \"XZ-DL 314\". Shop windows, planters and paving stones."),
    ("szene-2", 2207,
     "A small German town square with a stone fountain. Two women stop in the foreground and talk to each other, "
     "their faces turned towards the camera; behind them people cross the square from left to right and from right "
     "to left. A bronze statue of a seated man stands motionless on a pedestal in the middle ground. On the right a "
     "red hatchback is parked with its rear towards the camera; its licence plate is a white German plate with a blue "
     "EU band and the black text \"QM-AT 1907\"."),
    ("szene-3", 1907,
     "A tram stop in a German city in the late afternoon. A man in a grey coat and a woman with a pushchair wait at "
     "the stop and look towards the camera; a man with a briefcase walks past close to the camera; further back a "
     "few people walk along the pavement. A dark blue estate car is parked in the foreground on the right with its "
     "front towards the camera; its licence plate is a white German plate with a blue EU band and the black text "
     "\"YJ-RS 220\"."),
]


def laden():
    from diffusers import ClassifierFreeGuidance, ModularPipeline
    from diffusers.hooks import apply_group_offloading
    from _attention import resolve_attention_backend
    from _byt5 import require_byt5_components
    require_byt5_components(str(MODELL))
    pipe = ModularPipeline.from_pretrained(str(MODELL), workflow="i2v")
    # wie das Beispiel des Herstellers: Qwen erst in FP32 laden, das Profil rechnet es auf FP16 um
    pipe.load_components(dtype={"transformer": torch.bfloat16, "text_encoder": torch.float32,
                                "vision_encoder": torch.bfloat16, "default": torch.float32})
    pipe.vision_encoder.to(dtype=torch.float16)
    pipe.update_components(guider=ClassifierFreeGuidance.from_config(pipe.guider.config, guidance_scale=5.0,
                                                                     guidance_rescale=0.85))
    if pipe.text_encoder.dtype != torch.float16:
        pipe.text_encoder.to(dtype=torch.float16)
    pipe.transformer.set_attention_backend(resolve_attention_backend("sdpa"))
    pipe.text_encoder.config.use_cache = False
    cuda, cpu = torch.device("cuda"), torch.device("cpu")
    # Jeder große Teil liegt im Hauptspeicher und kommt erst für seinen Schritt auf die Karte: Text-Kodierer je
    # Schicht, Videomodell je Block (mit Vorausladen), Bild-Kodierer und VAE je Ebene.
    te = pipe.text_encoder
    for teil in ("norm", "rotary_emb"):
        getattr(te, teil).to(cuda)
    for modul in [te.embed_tokens, *te.layers]:
        apply_group_offloading(modul, onload_device=cuda, offload_device=cpu, offload_type="block_level",
                               num_blocks_per_group=1)
    pipe.transformer.enable_group_offload(onload_device=cuda, offload_device=cpu, offload_type="block_level",
                                          num_blocks_per_group=1, use_stream=True)
    apply_group_offloading(pipe.vae, onload_device=cuda, offload_device=cpu, offload_type="leaf_level")
    apply_group_offloading(pipe.vision_encoder, onload_device=cuda, offload_device=cpu, offload_type="block_level",
                           num_blocks_per_group=64)
    pipe.text_encoder_2.to(device=cpu, dtype=torch.float32)   # Schrift-Kodierer verlangt CPU und FP32
    return pipe


def main() -> int:
    import imageio.v2 as imageio
    import numpy as np
    ROH.mkdir(exist_ok=True)
    nur = set(sys.argv[1:])
    auswahl = [s for s in SZENEN if not nur or s[0] in nur]
    t0 = time.time()
    pipe = laden()
    print(f"geladen: {time.time() - t0:.0f} s", flush=True)
    protokoll = []
    from diffusers.utils import load_image
    for name, start, text in auswahl:
        t1 = time.time()
        startbild = load_image(str(ROH / f"{name}-start.png"))
        videos = pipe(reference_image=startbild, reference_guidance_scale=3.0, i2v_anchor_tau=0.001,
                      prompt=f"{text} {STIL}", height=HOEHE, width=BREITE, num_frames=BILDER, fps=FPS,
                      num_inference_steps=SCHRITTE, flow_shift=8.0, max_sequence_length=1400,
                      generator=torch.Generator("cpu").manual_seed(start), vae_tiling=True, output_type="pil",
                      output="videos")
        imageio.mimwrite(str(ROH / f"{name}.mp4"), np.stack([np.asarray(f) for f in videos[0]]), fps=FPS,
                         quality=9)
        protokoll.append({"datei": f"{name}.mp4", "breite": BREITE, "hoehe": HOEHE, "einzelbilder": BILDER,
                          "fps": FPS, "schritte": SCHRITTE, "cfg": 5.0, "referenz": 3.0, "startwert": start,
                          "startbild": f"{name}-start.png",
                          "beschreibung": f"{text} {STIL}", "sekunden": round(time.time() - t1, 1)})
        print(f"{name}: {time.time() - t1:.0f} s", flush=True)
    alt = json.loads((ROH / "video.json").read_text()) if (ROH / "video.json").exists() else []
    neu = {p["datei"]: p for p in alt} | {p["datei"]: p for p in protokoll}
    (ROH / "video.json").write_text(json.dumps(list(neu.values()), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
