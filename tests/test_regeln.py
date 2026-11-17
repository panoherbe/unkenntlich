"""Feste Regeln: Prüfziffern, Muster, Zusammenführen. Ohne Modell, ohne Netz."""
from unkenntlich import text_regeln
from unkenntlich.text_erkennen import zusammenfuehren
from unkenntlich.text_regeln import Fund


def kategorien(text: str) -> dict[str, str]:
    return {text[f.start:f.ende]: f.kategorie for f in text_regeln.finde(text)}


def test_iban_pruefziffer():
    assert text_regeln.iban_gueltig("DE68 9001 2345 0123 4567 89")
    assert not text_regeln.iban_gueltig("DE68 9001 2345 0123 4567 88")
    assert not text_regeln.iban_gueltig("DE68 9001 2345")


def test_steuer_id_pruefziffer():
    assert text_regeln.steuer_id_gueltig("94 096 921 832")      # zufällig erzeugt, Prüfziffer gültig (kann theoretisch vergeben sein, wie im Prüfsatz)
    assert not text_regeln.steuer_id_gueltig("94 096 921 833")
    assert not text_regeln.steuer_id_gueltig("01 234 567 890")


def test_muster_im_brief():
    text = ("Sehr geehrte Frau Albers,\nIhre IBAN DE68 9001 2345 0123 4567 89 und Ihre Steuer-ID 94 096 921 832.\n"
            "Rückfragen unter 069 90009 123 oder an jana.albers@example.org. Geboren am 03.04.1981.\n"
            "Aktenzeichen: WG-123/4567-26\nLindenstraße 12\n12345 Musterhausen\nKennzeichen: XZ-AB 1234")
    k = kategorien(text)
    assert k["DE68 9001 2345 0123 4567 89"] == "iban"
    assert k["94 096 921 832"] == "steuer_id"
    assert k["069 90009 123"] == "telefon"
    assert k["jana.albers@example.org"] == "email"
    assert k["03.04.1981"] == "geburtsdatum"
    assert k["WG-123/4567-26"] == "aktenzeichen"
    assert k["Lindenstraße 12"] == "anschrift"
    assert k["12345 Musterhausen"] == "anschrift"
    assert k["XZ-AB 1234"] == "kennzeichen"
    assert k["Albers"] == "name"


def test_telefon_am_satzende_ganz():
    # Rufnummern aus dem Bereich der Bundesnetzagentur für Medien („Drama Numbers“), niemandem zugeteilt
    k = kategorien("Rückfragen unter 030 23125 417. Mobil 0171 3920047.")
    assert k == {"030 23125 417": "telefon", "0171 3920047": "telefon"}


def test_kein_telefon_in_iban_und_kein_geburtsdatum_ohne_hinweis():
    k = kategorien("Konto DE68 9001 2345 0123 4567 89. Datum: 12.11.2026")
    assert "telefon" not in k.values()
    assert "geburtsdatum" not in k.values()


def test_strasse_greift_nicht_ueber_zeilen():
    k = kategorien("Svenja Kühnel\nAm Kirchberg 77b")
    assert k == {"Am Kirchberg 77b": "anschrift"}


def test_regel_gewinnt_beim_zusammenfuehren():
    funde = [Fund(0, 10, "telefon", "Modell", quelle="GLiNER2-PII", sicherheit=0.9),
             Fund(0, 22, "iban", "IBAN mit gültiger Prüfziffer")]
    out = zusammenfuehren(funde)
    assert len(out) == 1 and out[0].kategorie == "iban" and out[0].ende == 22
    assert out[0].quelle == "Regel + GLiNER2-PII"
