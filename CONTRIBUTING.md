# Mitmachen bei Unkenntlich

Kurz: Rückmeldungen, Fehlerberichte, schwierige Testfälle und Verbesserungen sind willkommen. Bitte nie echte
Personendaten.

## Etwas melden

- **Fehler oder Wunsch:** ein [Issue](https://github.com/panoherbe/unkenntlich/issues) mit drei Sätzen: Was haben Sie
  gemacht, was ist passiert, was hätten Sie erwartet? Die Version (`pyproject.toml` oder die
  [Releases](https://github.com/panoherbe/unkenntlich/releases)) und das Betriebssystem helfen.
- **Testfälle:** nur erfundene oder selbst erzeugte Dateien ohne echte Personen, ohne echte Kennzeichen und ohne echte
  Akten. Beschreiben Sie, was erkannt werden sollte; so kommt der Fall in den Prüfsatz.
- **Sicherheitslücke:** bitte nicht öffentlich als Issue, sondern per Mail an kontakt@panoherbe.com.

## Selbst etwas ändern

- Starten und testen wie in der README, ohne Netz im Container:

  ```bash
  docker compose up -d --build
  docker compose run --rm test
  ```

- Ein Pull Request ändert eine Sache, die Tests laufen grün (GitHub Actions prüft jeden Pull Request, der Code ändert), und die
  Oberfläche bleibt auf Deutsch und per Tastatur bedienbar.
- Neue Modelle nur mit freier Lizenz, ohne Anmeldung zu laden und mit fester Prüfsumme in
  [`werkzeuge/modelle_laden.py`](werkzeuge/modelle_laden.py).

## Was geplant ist

Die nächsten Schritte stehen in der README unter [Fahrplan 2027](README.md#fahrplan-2027) und als Issues mit dem Label
[„Fahrplan 2027“](https://github.com/panoherbe/unkenntlich/issues?q=label%3A%22Fahrplan+2027%22). Hinweise dort sind
willkommen.

## Lizenz

Beiträge stehen unter derselben Lizenz wie das Projekt: GNU AGPL-3.0-or-later ([`LICENSE`](LICENSE)).
