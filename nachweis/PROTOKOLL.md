# Messprotokoll

Messlauf vom 18.11.2026, 19:01 Uhr (deutsche Zeit), Unkenntlich 0.2.0. Erzeugt von [`messung/messen.py`](../messung/messen.py) über `compose.nachweis.yaml`; Rohdaten in [`messwerte.json`](messwerte.json), Bilder in [`bilder/`](bilder/).

**Rechner:** 11th Gen Intel(R) Core(TM) i7-11700B @ 3.20GHz, 16 Threads; 8 Rechenfäden; Grafikkarte: keine genutzt (nur CPU); Netz: ohne (network_mode: none). Tesseract 5.5.0. Gesamtdauer des Laufs 3,9 min.

**Was simuliert ist:** Alle zwölf Schreiben sind erfunden (Personen, Anschriften, Nummern, Unterschriften, Stempel; erzeugt von [`pruefsatz/erzeugen.py`](../pruefsatz/erzeugen.py), Scans mit simuliertem Rauschen). Fotos und Video sind mit offenen Modellen erzeugt: keine echten Personen, keine echten Kennzeichen ([`pruefsatz/QUELLEN.md`](../pruefsatz/QUELLEN.md)). Ihre Metadaten (Kamera, GPS, Urheber) und die Tonspur (Testton und Rauschen) sind eingesetzt und erfunden. Der Mensch, der die Vorschläge bestätigt, ist ein Skript (Regeln oben in `messen.py`).

## Ergebnis auf einen Blick

| Was | Ergebnis |
|---|---|
| Eingesetzte Angaben in 12 Schreiben (simuliert), vor jeder Bestätigung vorgeschlagen | Angaben im Text: **215 von 215 (100,0 %)**; mit Unterschriften und Stempeln: **231 von 235 (98,3 %)**; auf 16 Seiten |
| Vorschläge ohne eingesetzte Angabe (z. B. Anschrift und Zentrale der Behörde, die der Mensch sichtbar lässt) | 59, also 3,7 je Seite |
| Gegenprobe nach dem Unkenntlichmachen, 12 Schreiben | erste Gegenprobe: 1 Rest in 1 Datei (Export gesperrt); Reste übernommen und bestätigt, danach **0 Reste** |
| Zweite, unabhängige Prüfung: eingesetzte Angaben im Textauszug und in neuer Texterkennung des Ergebnisses gesucht | 0 von 148 noch lesbar |
| Kontrollversuch „nur schwarz übermalt“ (typischer Fehler), 10 PDFs | Gegenprobe sperrt in 10 von 10; Inhalt unter den Kästen gefunden in 10 von 10 (Text in der Textschicht in 8, Bildpunkte unter den Flächen in 10) |
| Fotos (4, erzeugt): Gegenprobe | erste Gegenprobe 1 Rest, übernommen und bestätigt, danach **0 Reste**; kein Fund verworfen; Metadaten danach: keine |
| Video (10,1 s, 1024 × 560, 243 Einzelbilder, erzeugt): Spuren | 20 Personen, 2 Personen im Hintergrund, 4 Gesichter ohne erkannte Person (oft sehr kurz), 3 Kennzeichen |
| Video: Gegenprobe über 243 von 243 Einzelbildern | **0 Reste**; in der ersten Gegenprobe kein Fund verworfen; Ton danach: entfernt; Metadaten danach: keine |
| Kontrollversuch Video: jedes zehnte Einzelbild unbearbeitet (24 Bilder) | Gegenprobe meldet Reste in 24 Bildern, davon 24 ausgelassene; Export gesperrt: ja |

## Laufzeiten auf der CPU

| Was | Dauer |
|---|---|
| Erkennen, digitales PDF | 0,6 s je Seite |
| Erkennen, Scan oder Foto eines Schreibens (mit Texterkennung) | 2,4–6,3 s je Seite |
| Gegenprobe, Schreiben | 1,3–2,4 s je Seite |
| Erkennen, Foto (1536 × 1024 px) | 0,6–0,7 s |
| Erkennen, Video (1024 × 560) | 49 s für 10,1 s Video, also 4,8 s je Videosekunde |
| Unkenntlich machen, Video | 2 s |
| Gegenprobe, Video | 28 s, also 2,8 s je Videosekunde |

Die Modelle werden beim ersten Aufruf geladen; die erste Datei eines Laufs ist deshalb einige Sekunden langsamer.

## Schreiben: Erkennung je Kategorie (simuliert)

Eine Angabe zählt als erkannt, wenn Vorschläge mindestens 60 % ihrer Fläche abdecken (bei Scans ist die Wahrheit das Rechteck der gedrehten Zeile und damit etwas größer als die Zeile selbst).

| Kategorie | eingesetzt | vorgeschlagen | davon mit richtiger Kategorie |
|---|---:|---:|---:|
| Namen | 60 | 60 von 60 (100,0 %) | 60 |
| Anschriften | 51 | 51 von 51 (100,0 %) | 51 |
| Telefonnummern | 32 | 32 von 32 (100,0 %) | 32 |
| E-Mail-Adressen | 20 | 20 von 20 (100,0 %) | 20 |
| IBAN | 16 | 16 von 16 (100,0 %) | 16 |
| Akten-, Kunden- und Personalnummern | 16 | 16 von 16 (100,0 %) | 16 |
| Unterschriften | 12 | 12 von 12 (100,0 %) | 6 |
| Steuer-ID | 8 | 8 von 8 (100,0 %) | 8 |
| Geburtsdaten | 8 | 8 von 8 (100,0 %) | 8 |
| Stempel | 8 | 4 von 8 (50,0 %) | 0 |
| Kfz-Kennzeichen im Text | 4 | 4 von 4 (100,0 %) | 4 |

## Schreiben: je Datei

| Datei | Art | Seiten | erkannt | verpasst | Fehlvorschläge | Erkennen | Gegenprobe | Reste (erste → zuletzt) | zweite Prüfung lesbar |
|---|---|---:|---:|---|---:|---:|---:|---:|---:|
| 01-bescheid-scan-ocr.pdf | Scan mit Textschicht | 2 | 18 von 18 | – | 9 | 12,6 s | 4,0 s | 0 → 0 | 0 von 11 |
| 02-vermieterin-digital.pdf | digitales PDF | 1 | 21 von 21 | – | 0 | 0,6 s | 1,3 s | 0 → 0 | 0 von 15 |
| 03-arbeitgeber-scan.pdf | Scan (PDF, nur Bild) | 1 | 18 von 19 | Stempel | 8 | 2,9 s | 2,4 s | 0 → 0 | 0 von 11 |
| 04-bescheid-digital.pdf | digitales PDF | 2 | 21 von 21 | – | 6 | 1,1 s | 2,7 s | 0 → 0 | 0 von 11 |
| 05-vermieterin-jpg.jpg | Foto eines Schreibens (JPG) | 1 | 21 von 21 | – | 0 | 2,6 s | 2,3 s | 0 → 0 | 0 von 15 |
| 06-arbeitgeber-digital.pdf | digitales PDF | 1 | 18 von 19 | Stempel | 5 | 0,6 s | 1,7 s | 0 → 0 | 0 von 11 |
| 07-bescheid-scan.pdf | Scan (PDF, nur Bild) | 2 | 18 von 18 | – | 9 | 4,9 s | 4,3 s | 1 → 0 | 0 von 11 |
| 08-vermieterin-scan-ocr.pdf | Scan mit Textschicht | 1 | 21 von 21 | – | 0 | 2,9 s | 2,1 s | 0 → 0 | 0 von 15 |
| 09-arbeitgeber-jpg.jpg | Foto eines Schreibens (JPG) | 1 | 18 von 19 | Stempel | 8 | 2,4 s | 2,3 s | 0 → 0 | 0 von 11 |
| 10-bescheid-digital.pdf | digitales PDF | 2 | 18 von 18 | – | 9 | 1,2 s | 2,8 s | 0 → 0 | 0 von 11 |
| 11-vermieterin-digital.pdf | digitales PDF | 1 | 21 von 21 | – | 0 | 0,6 s | 1,4 s | 0 → 0 | 0 von 15 |
| 12-arbeitgeber-digital.pdf | digitales PDF | 1 | 18 von 19 | Stempel | 5 | 0,6 s | 1,6 s | 0 → 0 | 0 von 11 |

Verpasste Angaben zieht der simulierte Mensch als eigenen Bereich nach; erst danach laufen Unkenntlichmachen und Gegenprobe. Ohne diesen Schritt blieben sie lesbar: Die Gegenprobe findet nur, was ihre Erkenner erkennen. Findet die Gegenprobe etwas, übernimmt der simulierte Mensch jeden Rest als eigenen Bereich, und alles läuft noch einmal (so wie in der Oberfläche mit „Reste als Vorschläge übernehmen“). Die Gegenprobe sucht im Text jede bestätigte Angabe wörtlich (Textschicht und neue Texterkennung) und lässt die festen Regeln erneut laufen; das Sprachmodell läuft dort nicht mit, weil es nach dem Schwärzen den veränderten Satz anders liest (in einem früheren Lauf am selben Tag hielt es „Herr“ allein für einen Namen und ein Eintrittsdatum für ein Geburtsdatum).

## Fotos (erzeugt, Metadaten simuliert)

| Datei | Größe | Vorschläge | Metadaten vorher | Erkennen | Gegenprobe | Reste (erste → zuletzt) |
|---|---|---|---|---:|---:|---:|
| marktplatz.jpg | 1536 × 1024 px | 9 Gesichter, 2 Kennzeichen | Kamerahersteller, Kameramodell, Software, Urheber (Artist), Seriennummer, GPS-Position, Aufnahmezeit | 0,7 s | 0,9 s | 0 → 0 |
| parkplatz.jpg | 1536 × 1024 px | 5 Gesichter, 3 Kennzeichen | Kamerahersteller, Kameramodell, Software, Urheber (Artist), Seriennummer, GPS-Position, Aufnahmezeit | 0,7 s | 0,8 s | 0 → 0 |
| werkstatt.jpg | 1536 × 1024 px | 3 Gesichter, 1 Kennzeichen | Kamerahersteller, Kameramodell, Software, Urheber (Artist), Seriennummer, GPS-Position, Aufnahmezeit | 0,6 s | 0,8 s | 0 → 0 |
| flohmarkt.jpg | 1536 × 1024 px | 48 Gesichter | Kamerahersteller, Kameramodell, Software, Urheber (Artist), Kommentar, Seriennummer, GPS-Position, Aufnahmezeit, Textfeld „comment“ | 0,7 s | 0,8 s | 1 → 0 |

Für die Fotos gibt es keine vollständige Wahrheit; der simulierte Mensch bestätigt jeden Vorschlag. Von Hand angesehen (Bild [`foto-ergebnis.jpg`](bilder/foto-ergebnis.jpg)): Im Marktplatz-Foto sind die Gesichter der drei Personen vorn, fünf kleine Gesichter im Hintergrund, das Gesicht der Bronzestatue und beide Kennzeichen vorgeschlagen und abgedeckt; die Statue würde ein Mensch sichtbar lassen (kein Personenbezug), der Rundgang zeigt das.

## Video (erzeugt, Metadaten und Ton simuliert)

fussgaengerzone.mp4: 10,1 s, 1024 × 560, 243 Einzelbilder, 3 Szenen (Schnitte erkannt bei Einzelbild 81, 162; danach beginnt jede Spur neu). Metadaten vorher: Urheber, Kommentar, Aufnahmezeit, Aufnahmeort (GPS), location-eng, Titel, Tonspur (kann Stimmen und Namen enthalten). Der simulierte Mensch bestätigt jede Spur (Personen: Gesicht unkenntlich). Von Hand angesehen (Stichprobe unten): Die Gesichter vorn sind abgedeckt, ebenso der Kopf der Schaufensterpuppe in der ersten Szene (ein Mensch würde ihn sichtbar lassen); die Bronzestatue der zweiten Szene wird nicht vorgeschlagen. Jedes der drei Kennzeichen ist eine eigene Spur und abgedeckt.

Eine Trefferquote für das Video ist nicht gemessen: Dafür müsste jedes Gesicht in jedem der 243 Einzelbilder von Hand markiert sein. Stattdessen: Gegenprobe über jedes Einzelbild, ein Kontrollversuch mit absichtlich ausgelassenen Bildern und eine Stichprobe zum Ansehen ([`video-ergebnis-stichprobe.jpg`](bilder/video-ergebnis-stichprobe.jpg), ein Bild je Sekunde aus dem Ergebnis).

## Grenzen dieser Messung

- Die Schreiben sind erfunden und folgen drei Vorlagen; echte Akten sind vielfältiger. Die Zahlen zeigen, dass der Ablauf funktioniert, nicht, wie gut er auf beliebigen Unterlagen ist.
- Die Gegenprobe nutzt dieselben Erkennerfamilien wie die Erkennung (plus eine zweite Meinung für Kennzeichen und Augen aus Körperpunkten). Was keiner davon erkennt, findet auch die Gegenprobe nicht; darum bleibt der Blick des Menschen auf jede Seite Pflicht.
- Gemessen nur auf der CPU (die Grafikkarte des Rechners war nicht eingebunden); andere Programme auf dem Rechner liefen weiter. Andere Rechner sind schneller oder langsamer.
- Fotos und Video sind erzeugt, nicht aufgenommen. Echte Aufnahmen haben andere Lichtverhältnisse, Unschärfe und Gedränge; die Zahlen zeigen den Ablauf, keine Trefferquote für echte Bilder.
