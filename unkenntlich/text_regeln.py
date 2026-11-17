"""Feste Regeln für deutsche Angaben: IBAN und Steuer-ID mit Prüfziffer, Telefon, E-Mail, Geburtsdatum,
Aktenzeichen und Kundennummern, Kfz-Kennzeichen, Straße mit Hausnummer und Postleitzahl mit Ort.

Jeder Fund ist ein `Fund(start, ende, kategorie, grund)` mit Zeichenpositionen im übergebenen Text.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class Fund:
    start: int
    ende: int
    kategorie: str
    grund: str
    quelle: str = "Regel"
    sicherheit: float = 1.0


# --- Prüfziffern -------------------------------------------------------------------------------------------------

def iban_gueltig(roh: str) -> bool:
    s = re.sub(r"\s", "", roh).upper()
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{10,30}", s):
        return False
    if s.startswith("DE") and len(s) != 22:
        return False
    zahl = "".join(str(int(c, 36)) for c in s[4:] + s[:4])
    return int(zahl) % 97 == 1


def steuer_id_gueltig(roh: str) -> bool:
    """Steuerliche Identifikationsnummer: 11 Ziffern, erste nicht 0, Prüfziffer nach ISO 7064 MOD 11,10;
    in den ersten zehn Ziffern kommt genau eine Ziffer zwei- oder dreimal vor."""
    s = re.sub(r"\D", "", roh)
    if len(s) != 11 or s[0] == "0":
        return False
    zehn = s[:10]
    haeufig = [zehn.count(z) for z in set(zehn)]
    if not (sorted(haeufig, reverse=True)[0] in (2, 3) and sum(1 for h in haeufig if h > 1) == 1):
        return False
    produkt = 10
    for z in zehn:
        summe = (int(z) + produkt) % 10 or 10
        produkt = (summe * 2) % 11
    pruef = (11 - produkt) % 10
    return pruef == int(s[10])


# --- Muster -----------------------------------------------------------------------------------------------------

IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[  ]?[A-Z0-9]{4}){3,7}(?:[  ]?[A-Z0-9]{1,3})?\b")
EMAIL = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
TELEFON = re.compile(
    r"(?<![\w/])(?:\+49[\s ]?(?:\(0\)[\s ]?)?|0049[\s ]?|\(0\d{2,5}\)[\s ]?|0\d{2,5}[\s ]*[/\-][\s ]*|0\d{2,5}[\s ])"
    r"\d[\d\s \-/]{3,14}\d(?!\d|\.\d)")
TELEFON_HINWEIS = re.compile(r"(?:Tel(?:efon)?|Fon|Mobil|Handy|Fax|Durchwahl|Rufnummer)\.?\s*:?\s*$", re.I)
STEUER_ID = re.compile(r"(?<!\d)(\d{2}[  ]?\d{3}[  ]?\d{3}[  ]?\d{3})(?!\d)")
DATUM = re.compile(r"(?<!\d)(\d{1,2})\.\s?(\d{1,2})\.\s?(\d{4})(?!\d)")
GEBURT_HINWEIS = re.compile(r"(?:geb(?:oren)?\.?(?:\s+am)?|Geburtsdatum|Geburtstag|geb\.-?Datum)\s*:?\s*$", re.I)
AKTENZEICHEN = re.compile(
    r"(?P<wort>Aktenzeichen|Az\.|Geschäftszeichen|Unser Zeichen|Ihr Zeichen|[A-ZÄÖÜ][a-zäöüß]*nummer|"
    r"[A-ZÄÖÜ][a-zäöüß]*-Nr\.)[ \u00a0]*:?\s*"
    r"(?P<wert>[A-Z0-9][A-Za-z0-9./\-]*(?:[ \u00a0][A-Za-z0-9./\-]*\d[A-Za-z0-9./\-]*){0,3})")
KENNZEICHEN = re.compile(r"\b([A-ZÄÖÜ]{1,3})[\-\s ]([A-Z]{1,2})[\s ]?(\d{1,4})([EH]?)\b")
KENNZEICHEN_HINWEIS = re.compile(r"(?:Kennzeichen|amtl\.? Kennzeichen|Kfz)\s*:?\s*$", re.I)
STRASSE = re.compile(
    r"\b(?:[A-ZÄÖÜ][a-zäöüß]+[\- ]){0,2}[A-ZÄÖÜ][a-zäöüß\-]*(?:straße|strasse|str\.|weg|allee|platz|gasse|ring|damm|"
    r"ufer|chaussee|steig|pfad|stieg|markt|hof|berg|wall)[ \u00a0]+\d{1,4}(?:[ ]?[a-zA-Z]\b(?!-))?(?:[ ]?[\-/][ ]?\d{1,4}[a-z]?)?")
ANREDE = re.compile(r"\b(?:Frau|Herrn?)[ \u00a0]+(?:(?:Dr|Prof)\.[ \u00a0]+)*"
                    r"([A-ZÄÖÜ][a-zäöüßıçğşé]+(?:[\- ][A-ZÄÖÜ][a-zäöüßıçğşé]+)?)")
IBAN_DAVOR = re.compile(r"[A-Z]{2}\d{2}(?:[ \u00a0]?[A-Z0-9]{2,4})+[ \u00a0]?$")
PLZ_ORT = re.compile(r"(?<!\d)(\d{5})[  ]+([A-ZÄÖÜ][a-zäöüß]+(?:[\- ][A-ZÄÖÜ]?[a-zäöüß]+)*(?: (?:am|an der|im|bei) [A-ZÄÖÜ][a-zäöüß]+)?)")


def _vorher(text: str, start: int, n: int = 40) -> str:
    """Text der Zeile vor `start` (höchstens n Zeichen)."""
    anfang = max(0, start - n)
    stueck = text[anfang:start]
    return stueck.split("\n")[-1]


def finde(text: str) -> list[Fund]:
    funde: list[Fund] = []
    for m in IBAN.finditer(text):
        if iban_gueltig(m.group(0)):
            funde.append(Fund(m.start(), m.end(), "iban", "IBAN mit gültiger Prüfziffer"))
    for m in EMAIL.finditer(text):
        funde.append(Fund(m.start(), m.end(), "email", "E-Mail-Adresse"))
    for m in TELEFON.finditer(text):
        ziffern = re.sub(r"\D", "", m.group(0))
        if IBAN_DAVOR.search(text[max(0, m.start() - 40):m.start()]):
            continue  # Ziffernblöcke einer IBAN, keine Telefonnummer
        if 6 <= len(ziffern) <= 15:
            hinweis = bool(TELEFON_HINWEIS.search(_vorher(text, m.start())))
            funde.append(Fund(m.start(), m.end(), "telefon",
                              "Telefonnummer" + (" (nach „Tel.“)" if hinweis else " (deutsches Rufnummernformat)")))
    for m in STEUER_ID.finditer(text):
        if steuer_id_gueltig(m.group(1)):
            funde.append(Fund(m.start(1), m.end(1), "steuer_id", "Steuer-ID mit gültiger Prüfziffer"))
    for m in DATUM.finditer(text):
        if GEBURT_HINWEIS.search(_vorher(text, m.start())):
            funde.append(Fund(m.start(), m.end(), "geburtsdatum", "Datum nach „geboren“ bzw. „Geburtsdatum“"))
    for m in AKTENZEICHEN.finditer(text):
        wert = m.group("wert").rstrip(" .,;")
        if any(c.isdigit() for c in wert) and len(wert) >= 4:
            start = m.start("wert")
            funde.append(Fund(start, start + len(wert), "aktenzeichen", f"Nummer nach „{m.group('wort')}“"))
    for m in KENNZEICHEN.finditer(text):
        hinweis = KENNZEICHEN_HINWEIS.search(_vorher(text, m.start()))
        if hinweis or "-" in m.group(0):
            funde.append(Fund(m.start(), m.end(), "kennzeichen", "Kfz-Kennzeichen (deutsches Format)"))
    for m in STRASSE.finditer(text):
        funde.append(Fund(m.start(), m.end(), "anschrift", "Straße mit Hausnummer"))
    for m in ANREDE.finditer(text):
        funde.append(Fund(m.start(1), m.end(1), "name", "Name nach „Frau“ bzw. „Herr“"))
    for m in PLZ_ORT.finditer(text):
        funde.append(Fund(m.start(), m.end(), "anschrift", "Postleitzahl mit Ort"))
    return funde
