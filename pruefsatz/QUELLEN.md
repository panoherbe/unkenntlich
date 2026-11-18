# Quellen und Lizenzen des Prüfsatzes

Stand 18.11.2026. Jede Datei mit Herkunft, Lizenz und was geändert wurde. **Im ganzen Prüfsatz ist keine echte Person
und kein echtes Kennzeichen zu sehen:** Die Schreiben sind erfunden, Fotos und Video sind mit offenen Modellen erzeugt.

## Schreiben (`dokumente/`): simuliert

Zwölf erfundene deutsche Schreiben, erzeugt von [`erzeugen.py`](erzeugen.py) mit festem Zufallsstartwert. Alle
Personen, Anschriften, Kennzeichen, Akten- und Kundennummern, Unterschriften und Stempel sind **erfunden**;
Ähnlichkeiten mit echten Personen wären Zufall. „Stadt Musterhausen“ und „Beispiel Logistik GmbH“ gibt es nicht.
Zwei Personen eines Schreibens tragen nie denselben Familiennamen: In Schreiben 02 hatte der Zufall Mieterin und
Vermieterin denselben Namen gegeben; seit 18.11.2026 zieht `erzeugen.py` dann mit eigenem Startwert nach (die übrigen
elf Schreiben sind inhaltlich unverändert).

- **Telefonnummern** stammen aus den Bereichen, die die Bundesnetzagentur für Medien freihält und niemandem zuteilt
  („Drama Numbers“, [Mitteilung 148/2021](https://www.bundesnetzagentur.de/DE/Fachthemen/Telekommunikation/Nummerierung/_DL/mittlg148_2021.pdf)):
  030 23125 …, 069 90009 …, 040 66969 …, 0221 4710 …, 089 99998 … sowie 0171 39200 … und 0176 040690 ….
- **IBAN** haben eine gültig gerechnete Prüfziffer, damit die Regel greift; ihre Bankleitzahl beginnt mit 0 oder 9.
  Diese Bereiche sind keiner Bank zugeteilt (die erste Ziffer ist das Clearinggebiet 1 bis 8), es gibt also kein
  solches Konto.
- **Steuer-IDs** sind zufällig erzeugt und haben eine gültig gerechnete Prüfziffer. Ob eine solche Nummer jemandem
  zugeteilt ist, lässt sich nicht prüfen: Das Bundeszentralamt für Steuern veröffentlicht weder die vergebenen
  Nummern noch einen Bereich für Beispiele. Die Nummern stehen nur in erfundenen Schreiben, ohne Bezug zu einer Person.
- **E-Mail-Adressen** liegen unter `example.org` (für Beispiele reserviert, RFC 2606).
- **Kfz-Kennzeichen** beginnen mit XZ, QM oder YJ; diese Unterscheidungszeichen werden in Deutschland nicht vergeben
  (geprüft an der Liste der Unterscheidungszeichen in der deutschsprachigen Wikipedia, 17.11.2026).

Scans sind simuliert (leicht gedreht, Papierton, Rauschen, JPEG). [`dokumente/wahrheit.json`](dokumente/wahrheit.json)
nennt jede eingesetzte Angabe mit Kategorie und Position. Lizenz der erzeugten Dateien: **CC0 1.0**. Schriften darin:
IBM Plex Serif, IBM Plex Sans, Mrs Saint Delafield, Herr Von Muellerhoff, Allura (je SIL Open Font License 1.1,
Urheber und reservierte Namen in [`schriften/OFL.txt`](schriften/OFL.txt)).

## Fotos (`fotos/`): erzeugt, keine echten Personen

Vier Fotos, erzeugt mit **MOSS-Image-SFT** (OpenMOSS, Oktober 2026,
[Hugging Face](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT), Stand `f972bd4`, Lizenz Apache-2.0) über
[`erzeugung/bilder.py`](erzeugung/bilder.py): 50 Schritte, feste Startwerte, auf einer Grafikkarte mit 12 GB. Die
vollständigen Beschreibungen, Startwerte und Rechenzeiten stehen in [`erzeugung/roh/bilder.json`](erzeugung/roh/bilder.json).

| Datei | Was zu sehen ist | Startwert |
|---|---|---|
| `marktplatz.jpg` | drei Personen vor einem grünen Wagen (Kennzeichen „XZ KL 482“), eine Bronzestatue, ein roter Kleinwagen („QM AT 1907“), Passanten im Hintergrund | 4711 |
| `parkplatz.jpg` | Supermarkt-Parkplatz, zwei Personen, drei Autos mit erfundenen Kennzeichen | 1907 |
| `werkstatt.jpg` | Hof einer Werkstatt, zwei Personen, ein Auto mit erfundenem Kennzeichen | 2207 |
| `flohmarkt.jpg` | Flohmarkt mit vielen kleinen Gesichtern in verschiedenen Abständen | 1503 |

Die Personen sind vom Modell erzeugt und bilden niemanden ab; Ähnlichkeiten mit echten Personen wären Zufall. Die
Kennzeichen tragen nicht vergebene Unterscheidungszeichen (siehe oben). [`erzeugung/metadaten.py`](erzeugung/metadaten.py)
macht aus den PNG des Modells JPEG und setzt **erfundene EXIF-Angaben** ein, damit sich prüfen lässt, dass Unkenntlich
sie entfernt: Kamera „Beispielkamera / Modell X (simuliert)“, Software, Urheber „Erika Beispiel (erfunden)“,
Seriennummer „SIM-000123“, Aufnahmezeit 14.05.2026 und eine GPS-Position (Mittelpunkt Deutschlands, kein
Aufnahmeort); im Flohmarkt-Foto zusätzlich ein Kommentar. Lizenz der Fotos: **CC0 1.0**.

## Video (`video/`): erzeugt, keine echten Personen

`fussgaengerzone.mp4`: drei Szenen (Fußgängerzone mit Lieferwagen „XZ DL 314“ und Schaufensterpuppe, Platz mit
Bronzestatue, Haltestelle), erzeugt mit **Vimoo-1.0-Lite** (Vimoo-AI, Oktober 2026,
[Hugging Face](https://huggingface.co/Vimoo-AI/Vimoo-1.0-Lite), Stand `9016df4`, Lizenz Apache-2.0) über
[`erzeugung/video.py`](erzeugung/video.py). Jede Szene beginnt mit einem Standbild aus MOSS-Image-SFT (oben) und wird vom
Videomodell bewegt. Bausteine, die Vimoo-1.0-Lite dafür lädt: Qwen2.5-VL-7B-Instruct (Text, Apache-2.0), Glyph-SDXL-v2 (Schrift
im Bild; Code Apache-2.0 laut [GitHub](https://github.com/AIGText/Glyph-ByT5), die Modellseite nennt keine Lizenz),
google/byt5-small (Apache-2.0), der VAE aus Wan2.2-TI2V-5B (Apache-2.0) und SigLIP so400m (Apache-2.0). Beschreibungen,
Startwerte, Auflösung und Rechenzeiten: [`erzeugung/roh/video.json`](erzeugung/roh/video.json).

[`erzeugung/metadaten.py`](erzeugung/metadaten.py) setzt die Szenen zusammen (H.264, 24 Bilder/s) und fügt hinzu:

- eine **Tonspur aus Testton (440 Hz) und rosa Rauschen**, erzeugt mit FFmpeg; keine Aufnahme, keine Stimmen;
- **erfundene Metadaten**: Titel, Urheber „Erika Beispiel (erfunden)“, Kommentar „Metadaten simuliert“,
  Aufnahmezeit 14.05.2026, Aufnahmeort (Mittelpunkt Deutschlands).

Unkenntlich muss Ton und Metadaten entfernen. Lizenz des Videos: **CC0 1.0**.

## Rundgang und Bilder in `medien/` und `nachweis/bilder/`

Sie zeigen diese Dateien, bearbeitet: Markierungen und Abdeckungen aus Unkenntlich. Lizenz wie die gezeigten Dateien
(CC0 1.0).
