"""Kategorien der Stellen, die Unkenntlich vorschlägt. Eine Liste für Erkennung, Oberfläche und Prüfbericht."""
from __future__ import annotations

# Schlüssel → (Bezeichnung, Gruppe). Die Gruppe bestimmt Farbe und Symbol in der Oberfläche.
KATEGORIEN: dict[str, tuple[str, str]] = {
    "name": ("Name", "person"),
    "anschrift": ("Anschrift", "ort"),
    "telefon": ("Telefon", "kontakt"),
    "email": ("E-Mail", "kontakt"),
    "iban": ("IBAN", "konto"),
    "steuer_id": ("Steuer-ID", "nummer"),
    "geburtsdatum": ("Geburtsdatum", "nummer"),
    "aktenzeichen": ("Aktenzeichen, Kundennummer", "nummer"),
    "kennzeichen": ("Kfz-Kennzeichen", "fahrzeug"),
    "gesicht": ("Gesicht", "gesicht"),
    "person": ("Person", "gesicht"),
    "unterschrift": ("Unterschrift", "hand"),
    "stempel": ("Stempel", "hand"),
    "eigener_bereich": ("Eigener Bereich", "eigen"),
}

TEXT_KATEGORIEN = {"name", "anschrift", "telefon", "email", "iban", "steuer_id", "geburtsdatum", "aktenzeichen",
                   "kennzeichen"}
BILD_KATEGORIEN = {"gesicht", "person", "kennzeichen", "unterschrift", "stempel"}


def bezeichnung(schluessel: str) -> str:
    return KATEGORIEN.get(schluessel, (schluessel, ""))[0]


def gruppe(schluessel: str) -> str:
    return KATEGORIEN.get(schluessel, ("", "eigen"))[1]
