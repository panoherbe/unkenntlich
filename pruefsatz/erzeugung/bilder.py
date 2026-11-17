"""Erzeugt die Testfotos des Prüfsatzes mit einem offenen Bildmodell: keine echten Personen, keine echten Kennzeichen.

    docker build -t unkenntlich-erzeugen:1 pruefsatz/erzeugung
    docker run --rm --gpus all -u "$(id -u):$(id -g)" -e HOME=/tmp -v <modelle>:/hf -v "$PWD":/app -w /app \
        unkenntlich-erzeugen:1 python pruefsatz/erzeugung/bilder.py

Modell: MOSS-Image-SFT (OpenMOSS, Oktober 2026, Apache-2.0), Ordner /hf/moss-image-sft
(`hf download OpenMOSS-Team/MOSS-Image-SFT`). Läuft auf einer Grafikkarte mit 12 GB: Der Text-Kodierer (Qwen3.5) wird
schichtweise ein- und ausgelagert, das Bildmodell liegt ganz auf der Karte. Feste Startwerte; die Ergebnisse stehen
unter CC0 1.0 (pruefsatz/QUELLEN.md). Die Kennzeichen tragen Unterscheidungszeichen, die in Deutschland nicht vergeben
sind (XZ, QM, YJ); die Gesichter gehören zu niemandem.

Das Bildmodell schreibt PNG nach pruefsatz/erzeugung/roh/; metadaten.py macht daraus die JPEGs des Prüfsatzes mit
erfundenen EXIF-Angaben.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path

import torch

HIER = Path(__file__).resolve().parent
MODELL = Path("/hf/moss-image-sft")
ROH = HIER / "roh"

STIL = ("Realistic candid photograph, natural daylight, shot on a 35 mm lens at eye level, sharp focus, true-to-life "
        "colours, ordinary people in everyday clothes, no text overlays, no watermark.")

BILDER = [
    # (Datei, Breite, Höhe, Startwert, Beschreibung)
    ("marktplatz", 1536, 1024, 4711,
     "A small German town market square on a sunny autumn afternoon. In the foreground, three adults stand together "
     "and chat beside a parked dark green vintage sedan; their faces are clearly visible and turned towards the "
     "camera at slightly different angles: a woman in her thirties with a beige trench coat, an older man with grey "
     "hair and glasses, a younger man with a dark jacket. The sedan's front licence plate is a white German plate "
     "with a blue EU band on the left, with the black letters \"XZ-KL 482\". Behind them, on a stone pedestal, "
     "a weathered bronze statue of a seated man with a book. On the right a small red hatchback is parked, its rear "
     "licence plate reads \"QM-AT 1907\". Half-timbered houses, café umbrellas and a few passers-by in the "
     "background."),
    ("parkplatz", 1536, 1024, 1907,
     "The car park in front of a German supermarket on an overcast morning. A woman pushes a shopping trolley "
     "towards the camera, her face clearly visible; a man in a blue fleece jacket loads bags into the open boot of a "
     "silver estate car. Three parked cars face the camera with white German licence plates with a blue EU band: "
     "\"YJ-RS 220\" on a black compact car, \"XZ-PE 1033\" on the silver estate car, \"QM-BU 58\" on a white van. "
     "Shopping trolleys, a row of young trees, the supermarket entrance in the background."),
    ("werkstatt", 1536, 1024, 2207,
     "The open courtyard of a small car repair workshop in a German suburb. A mechanic in dark blue overalls stands "
     "next to a raised bonnet and talks to a customer, a middle-aged woman with short hair; both faces are clearly "
     "visible in three-quarter view. The car is a red hatchback whose front licence plate is a white German plate "
     "with a blue EU band reading \"YJ-HN 4711\". Tyres stacked against a brick wall, a tool trolley, a roll-up door "
     "in the background."),
    ("flohmarkt", 1536, 1024, 1503,
     "A busy flea market in a German city street on a Saturday morning, seen from slightly above. Dozens of people "
     "browse tables with books, records, lamps and old toys; many faces are visible at different distances, some "
     "close to the camera, most further away. Stall owners sit on folding chairs. Brick buildings and trees line the "
     "street."),
    # Startbilder der drei Videoszenen (video.py bewegt sie)
    ("szene-1-start", 1280, 704, 3114,
     "A pedestrian shopping street in a German town centre on a bright afternoon, eye-level view along the street. "
     "Six people walk towards the camera at different distances, their faces visible: a couple in their forties, a "
     "young woman with a backpack, an older man with a flat cap, two teenagers. On the left a white delivery van is "
     "parked at the kerb with its front licence plate facing the camera, a white German plate with a blue EU band "
     "reading \"XZ-DL 314\". On the right a shop window with a mannequin wearing a red coat. Paving stones, "
     "planters, shop signs without readable brand names."),
    ("szene-2-start", 1280, 704, 2207,
     "A small German town square with a stone fountain on a sunny afternoon, eye-level view. In the foreground two "
     "women in their fifties stand and talk, their faces turned towards the camera; behind them four people cross the "
     "square at different distances. In the middle ground a weathered bronze statue of a seated man on a stone "
     "pedestal. On the right a red hatchback is parked with its rear towards the camera; its licence plate is a white "
     "German plate with a blue EU band reading \"QM-AT 1907\". Half-timbered houses, a bakery, café chairs, shop "
     "signs without readable brand names."),
    ("szene-3-start", 1280, 704, 1907,
     "A tram stop in a German city in the late afternoon, eye-level view. A man in a grey coat and a young woman with "
     "a pushchair wait at the stop and look towards the camera; a man with a briefcase walks past close to the "
     "camera; further back a few people walk along the pavement. In the foreground on the right a dark blue estate "
     "car is parked with its front towards the camera; its licence plate is a white German plate with a blue EU band "
     "reading \"YJ-RS 220\". Tram tracks, a glass shelter, trees, no readable brand names."),
]


def modul():
    spec = importlib.util.spec_from_file_location("pipeline_moss_image", MODELL / "pipeline_moss_image.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@torch.no_grad()
def kodieren(texte: list[str]) -> list[tuple[torch.Tensor, torch.Tensor]]:
    """Text-Kodierer (Qwen3.5) schichtweise auf der Grafikkarte; danach wieder freigeben."""
    from diffusers.hooks import apply_group_offloading
    from transformers import AutoModel, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODELL / "tokenizer")
    te = AutoModel.from_pretrained(MODELL / "text_encoder", dtype=torch.bfloat16).eval()
    # Einbettung und Normierung liegen auf der Karte, jede Sprachschicht wird erst für ihren Schritt geladen; der
    # Bildteil des Kodierers wird für Text nicht gebraucht und bleibt im Hauptspeicher.
    lm = te.language_model
    for teil in ("embed_tokens", "norm", "rotary_emb"):
        getattr(lm, teil).to("cuda")
    for schicht in lm.layers:
        apply_group_offloading(schicht, onload_device=torch.device("cuda"), offload_device=torch.device("cpu"),
                               offload_type="block_level", num_blocks_per_group=1)
    out = []
    for t in texte:
        formatiert = tok.apply_chat_template([{"role": "user", "content": t}], tokenize=False,
                                             add_generation_prompt=True, enable_thinking=True)
        eingabe = tok(formatiert, return_tensors="pt", truncation=True, max_length=4096).to("cuda")
        h = te(**eingabe, use_cache=False, return_dict=True).last_hidden_state.to("cpu")
        out.append((h, torch.ones(h.shape[:2], dtype=torch.bool)))
    del te
    torch.cuda.empty_cache()
    return out


def main() -> int:
    ROH.mkdir(exist_ok=True)
    nur = set(sys.argv[1:])
    auswahl = [b for b in BILDER if not nur or b[0] in nur]
    m = modul()
    t0 = time.time()
    embeds = kodieren([f"{b[4]} {STIL}" for b in auswahl] + [""])
    leer = embeds.pop()
    print(f"Text kodiert: {time.time() - t0:.0f} s", flush=True)
    from diffusers import AutoencoderKLFlux2
    transformer = m.MOSSImageTransformer.from_pretrained(MODELL / "transformer", torch_dtype=torch.bfloat16).eval()
    vae = AutoencoderKLFlux2.from_pretrained(MODELL / "vae", torch_dtype=torch.float32).eval()
    sched = m.MOSSImageScheduler.from_pretrained(MODELL / "scheduler")
    pipe = m.MOSSImagePipeline(transformer=transformer, scheduler=sched, vae=vae).to("cuda")
    protokoll = []
    for (name, breite, hoehe, start, text), (pe, pm) in zip(auswahl, embeds):
        t1 = time.time()
        latent = pipe(prompt_embeds=pe, prompt_attention_mask=pm, negative_prompt_embeds=leer[0],
                      negative_prompt_attention_mask=leer[1], height=hoehe, width=breite, num_inference_steps=50,
                      guidance_scale=3.0, uncond_skip_layers=[22], output_type="latent",
                      generator=torch.Generator("cpu").manual_seed(start)).images
        torch.save(latent.cpu(), ROH / f"{name}.latent.pt")
        protokoll.append({"datei": f"{name}.png", "breite": breite, "hoehe": hoehe, "startwert": start,
                          "schritte": 50, "cfg": 3.0, "beschreibung": f"{text} {STIL}",
                          "sekunden": round(time.time() - t1, 1)})
        print(f"{name}: {time.time() - t1:.0f} s", flush=True)
    # Erst danach dekodieren: Bildmodell und VAE passen nicht zugleich auf eine Karte mit 12 GB.
    pipe.transformer.to("cpu")
    torch.cuda.empty_cache()
    for name, *_ in auswahl:
        z = torch.load(ROH / f"{name}.latent.pt").to("cuda", dtype=vae.dtype)
        with torch.no_grad():
            bn, eps = vae.bn, vae.config.batch_norm_eps
            z = z * (bn.running_var + eps).sqrt().to(z).view(1, -1, 1, 1) + bn.running_mean.to(z).view(1, -1, 1, 1)
            b, c, h, w = z.shape
            z = z.reshape(b, c // 4, 2, 2, h, w).permute(0, 1, 4, 2, 5, 3).reshape(b, c // 4, 2 * h, 2 * w)
            bild = vae.decode(z, return_dict=False)[0].clamp(-1, 1)
        pipe.image_processor.postprocess(bild, output_type="pil")[0].save(ROH / f"{name}.png")
        (ROH / f"{name}.latent.pt").unlink()
    alt = json.loads((ROH / "bilder.json").read_text()) if (ROH / "bilder.json").exists() else []
    neu = {p["datei"]: p for p in alt} | {p["datei"]: p for p in protokoll}
    (ROH / "bilder.json").write_text(json.dumps(list(neu.values()), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
