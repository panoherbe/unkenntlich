"""Macht aus den erzeugten Rohdateien die Testdateien des Prüfsatzes, mit erfundenen Metadaten zum Prüfen.

    docker run --rm --network none -u "$(id -u):$(id -g)" -v "$PWD":/app -w /app unkenntlich:0.2.0 \
        python pruefsatz/erzeugung/metadaten.py

Fotos: PNG aus bilder.py → JPEG in pruefsatz/fotos/ mit erfundenen EXIF-Angaben (Kamera, Urheber, Seriennummer,
Aufnahmezeit, GPS). Video: die Szenen aus video.py hintereinander → pruefsatz/video/fussgaengerzone.mp4 (H.264), mit
einer erzeugten Tonspur aus Testton und Rauschen (keine Stimmen) und erfundenen Metadaten. Alles hier ist erzeugt
oder erfunden und steht unter CC0 1.0. Unkenntlich muss diese Angaben finden und entfernen.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import piexif
from PIL import Image

HIER = Path(__file__).resolve().parent
ROH = HIER / "roh"
PRUEF = HIER.parent
FOTOS = ["marktplatz", "parkplatz", "werkstatt", "flohmarkt"]
SZENEN = ["szene-1", "szene-2", "szene-3"]
# erfunden: Mittelpunkt Deutschlands (Niederdorla), kein Aufnahmeort
GPS = ((51, 1), (9, 1), (4824, 100)), ((10, 1), (26, 1), (5172, 100))


def exif(kommentar: bool) -> bytes:
    null = {piexif.ImageIFD.Make: b"Beispielkamera", piexif.ImageIFD.Model: b"Modell X (simuliert)",
            piexif.ImageIFD.Software: b"Beispiel-Software 1.0 (simuliert)",
            piexif.ImageIFD.Artist: "Erika Beispiel (erfunden)".encode()}
    exif_ifd = {piexif.ExifIFD.DateTimeOriginal: b"2026:05:14 10:21:07", piexif.ExifIFD.BodySerialNumber: b"SIM-000123"}
    if kommentar:
        exif_ifd[piexif.ExifIFD.UserComment] = b"ASCII\0\0\0" + "Metadaten simuliert".encode()
    gps = {piexif.GPSIFD.GPSLatitudeRef: b"N", piexif.GPSIFD.GPSLatitude: GPS[0],
           piexif.GPSIFD.GPSLongitudeRef: b"E", piexif.GPSIFD.GPSLongitude: GPS[1]}
    return piexif.dump({"0th": null, "Exif": exif_ifd, "GPS": gps})


def fotos() -> None:
    ziel = PRUEF / "fotos"
    ziel.mkdir(exist_ok=True)
    for i, name in enumerate(FOTOS):
        bild = Image.open(ROH / f"{name}.png").convert("RGB")
        extra = {"comment": b"Metadaten simuliert"} if name == "flohmarkt" else {}
        bild.save(ziel / f"{name}.jpg", "JPEG", quality=92, exif=exif(i == 3), **extra)
        print(f"{name}.jpg {bild.size[0]} x {bild.size[1]}")


def video() -> None:
    ziel = PRUEF / "video"
    ziel.mkdir(exist_ok=True)
    liste = ROH / "szenen.txt"
    liste.write_text("".join(f"file '{ROH / s}.mp4'\n" for s in SZENEN))
    stumm = ROH / "stumm.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(liste), "-c:v", "libx264",
                    "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "24", "-an", "-map_metadata", "-1",
                    str(stumm)], check=True)
    dauer = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(stumm)], capture_output=True, text=True, check=True).stdout)
    # Tonspur: Testton 440 Hz und rosa Rauschen, erzeugt mit FFmpeg (keine Aufnahme, keine Stimmen)
    ton = (f"sine=frequency=440:sample_rate=48000:duration={dauer:.3f},volume=0.08[a];"
           f"anoisesrc=color=pink:amplitude=0.05:sample_rate=48000:duration={dauer:.3f}[b];[a][b]amix=inputs=2[t]")
    meta = ["-metadata", "title=Fußgängerzone (erzeugt, Metadaten simuliert)",
            "-metadata", "artist=Erika Beispiel (erfunden)", "-metadata", "comment=Metadaten simuliert",
            "-metadata", "creation_time=2026-05-14T10:21:07Z", "-metadata", "location=+51.1634+010.4477/",
            "-metadata", "location-eng=+51.1634+010.4477/"]
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(stumm), "-filter_complex", ton, "-map", "0:v",
                    "-map", "[t]", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-shortest", *meta,
                    "-movflags", "+use_metadata_tags", str(ziel / "fussgaengerzone.mp4")], check=True)
    stumm.unlink()
    liste.unlink()
    print(f"fussgaengerzone.mp4 {dauer:.2f} s")


if __name__ == "__main__":
    teile = set(sys.argv[1:]) or {"fotos", "video"}
    if "fotos" in teile:
        fotos()
    if "video" in teile:
        video()
