"""Personenbezogene Angaben im Text: feste Regeln (text_regeln) plus das offene Modell GLiNER2-PII.

Das Modell findet vor allem Namen und Anschriften, die keine feste Form haben; die Regeln prüfen Nummern mit
Prüfziffer. Überlappende Funde werden zusammengeführt; die Regel gibt dann Kategorie und Grund vor.
"""
from __future__ import annotations

import re
import threading

from . import modelle
from .text_regeln import Fund, finde

# Modell-Labels → eigene Kategorie
LABELS = {
    "person": "name",
    "street_address": "anschrift",
    "postal_code": "anschrift",
    "city": "anschrift",
    "phone_number": "telefon",
    "email": "email",
    "iban": "iban",
    "date_of_birth": "geburtsdatum",
    "tax_id": "steuer_id",
}
SCHWELLE = 0.5
_sperre = threading.Lock()


def _stuecke(text: str, laenge: int = 1200) -> list[tuple[int, str]]:
    """Text in Stücke an Zeilengrenzen, damit das Modell nie abgeschnittene Zeilen sieht."""
    stuecke, start = [], 0
    while start < len(text):
        ende = min(len(text), start + laenge)
        if ende < len(text):
            umbruch = text.rfind("\n", start + laenge // 2, ende)
            if umbruch > start:
                ende = umbruch
        stuecke.append((start, text[start:ende]))
        start = ende
    return stuecke


def modell_funde(text: str) -> list[Fund]:
    if not text.strip():
        return []
    modell = modelle.gliner()
    funde: list[Fund] = []
    for versatz, stueck in _stuecke(text):
        with _sperre:
            ergebnis = modell.extract_entities(stueck, list(LABELS), threshold=SCHWELLE, include_confidence=True,
                                               include_spans=True)
        for label, werte in (ergebnis.get("entities") or {}).items():
            kategorie = LABELS.get(label)
            if not kategorie:
                continue
            for w in werte:
                s, e = w.get("start"), w.get("end")
                if s is None or e is None:
                    continue
                wert = stueck[s:e]
                if len(wert.strip()) < 2:
                    continue
                if label == "city":
                    # Ein Ort allein (z. B. im Datum „Kassel, den …“) ist keine Anschrift; nur mit Postleitzahl davor.
                    if not re.search(r"\d{5}\s+$", stueck[max(0, s - 8):s]):
                        continue
                if label == "person" and not re.search(r"[A-ZÄÖÜ][a-zäöüß]", wert):
                    continue
                ziffern = sum(c.isdigit() for c in wert)
                if (label == "iban" and ziffern < 10) or (label == "phone_number" and ziffern < 6) or \
                        (label == "tax_id" and ziffern < 8) or (label == "email" and "@" not in wert) or \
                        (label in ("date_of_birth", "postal_code") and ziffern < 4):
                    continue  # Form passt nicht zur Kategorie
                funde.append(Fund(versatz + s, versatz + e, kategorie,
                                  f"Modell erkennt {_label_de(label)}", quelle="GLiNER2-PII",
                                  sicherheit=float(w.get("confidence", 0.0))))
    return funde


def _label_de(label: str) -> str:
    return {"person": "einen Namen", "street_address": "eine Straße", "postal_code": "eine Postleitzahl",
            "city": "einen Ort", "phone_number": "eine Telefonnummer", "email": "eine E-Mail-Adresse",
            "iban": "eine Kontonummer", "date_of_birth": "ein Geburtsdatum", "tax_id": "eine Steuernummer"}[label]


def zusammenfuehren(funde: list[Fund]) -> list[Fund]:
    """Überlappende Funde vereinen. Eine Regel bestimmt Kategorie und Grund vor dem Modell; bei zwei Regeln die
    erste (frühere bzw. längere)."""
    funde = sorted(funde, key=lambda f: (f.start, -f.ende))
    ergebnis: list[Fund] = []
    for f in funde:
        if ergebnis and f.start < ergebnis[-1].ende:
            letzter = ergebnis[-1]
            regel_l, regel_f = letzter.quelle.startswith("Regel"), f.quelle.startswith("Regel")
            if letzter.kategorie != f.kategorie and not (regel_l or regel_f):
                # zwei verschiedene Modellfunde überlappen: der sicherere gewinnt
                if f.sicherheit > letzter.sicherheit:
                    letzter.kategorie, letzter.grund = f.kategorie, f.grund
            elif not regel_l and regel_f:
                letzter.kategorie, letzter.grund = f.kategorie, f.grund
            letzter.ende = max(letzter.ende, f.ende)
            teile = letzter.quelle.split(" + ")
            for q in f.quelle.split(" + "):
                if q not in teile:
                    teile.append(q)
            teile.sort(key=lambda q: q != "Regel")
            letzter.quelle = " + ".join(teile)
            letzter.sicherheit = max(letzter.sicherheit, f.sicherheit)
        else:
            ergebnis.append(Fund(f.start, f.ende, f.kategorie, f.grund, f.quelle, f.sicherheit))
    return ergebnis


def finde_alles(text: str, mit_modell: bool = True) -> list[Fund]:
    funde = finde(text)
    if mit_modell:
        funde += modell_funde(text)
    # Anschriften: Straße und PLZ/Ort in aufeinanderfolgenden Zeilen bleiben getrennte Stellen (je Zeile ein Balken).
    return zusammenfuehren(funde)
