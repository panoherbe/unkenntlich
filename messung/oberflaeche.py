"""Oberfläche im Browser prüfen: ganzer Ablauf mit den Beispielen, axe-core in jeder Ansicht (hell und dunkel,
Rechner und Telefon), Tastatur am Vorher-Nachher-Schieber; Bilder für die README.

Die Person, die klickt, ist simuliert (dieses Skript). Ergebnis: nachweis/barrierefreiheit.json, Bildschirmfotos in nachweis/bilder/.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = os.environ.get("APP_URL", "http://app:8080")
HIER = Path(__file__).resolve().parent.parent
MEDIEN = HIER / "nachweis" / "bilder"   # Bildschirmfotos des Prüflaufs (README-Bilder kommen aus dem Rundgang)
AXE = Path("/opt/axe/axe.min.js").read_text()
REGELN = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"]
ergebnisse = []


def axe(seite, name: str) -> None:
    seite.add_script_tag(content=AXE) if not seite.evaluate("!!window.axe") else None
    r = seite.evaluate("""async (regeln) => {
        const e = await axe.run(document, { runOnly: { type: 'tag', values: regeln } });
        return { verstoesse: e.violations.map(v => ({ id: v.id, wirkung: v.impact, anzahl: v.nodes.length,
                   ziele: v.nodes.slice(0, 3).map(n => n.target.join(' ')) })), bestanden: e.passes.length,
                 offen: e.incomplete.map(v => v.id) };
    }""", REGELN)
    ergebnisse.append({"ansicht": name, **r})
    print(f"axe {name}: {sum(v['anzahl'] for v in r['verstoesse'])} Verstöße, {r['bestanden']} Regeln bestanden",
          [v["id"] for v in r["verstoesse"]], flush=True)


def beide_schemata(seite, name: str) -> None:
    for schema in ("hell", "dunkel"):
        seite.evaluate("s => document.documentElement.dataset.schema = s", schema)
        seite.wait_for_timeout(250)
        axe(seite, f"{name}-{schema}")
    seite.evaluate("document.documentElement.dataset.schema = 'hell'")


def api(seite, pfad: str):
    return seite.evaluate("async p => (await fetch('/api' + p)).json()", pfad)


def main() -> int:
    MEDIEN.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chromium", args=["--lang=de-DE"], env={**os.environ, "LANGUAGE": "de", "LANG": "de_DE.UTF-8"})
        ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="light", locale="de-DE",
                            bypass_csp=True)  # nur damit axe-core eingespielt werden kann; die App behält ihre Regeln
        s = ctx.new_page()
        fehler = []
        s.on("pageerror", lambda e: fehler.append(str(e)))
        s.goto(URL); s.wait_for_selector("#beispiele")
        beide_schemata(s, "start")
        s.screenshot(path=str(MEDIEN / "start.jpg"))
        # Telefon
        tel = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, locale="de-DE", bypass_csp=True)
        t = tel.new_page(); t.goto(URL); t.wait_for_selector("#beispiele")
        axe(t, "start-telefon-hell"); t.screenshot(path=str(MEDIEN / "telefon-start.jpg")); tel.close()

        s.click("#beispiele")
        t0 = time.time()
        s.wait_for_selector("text=Weiter: Vorschläge prüfen", timeout=30 * 60 * 1000)
        vid = s.evaluate("sessionStorage.getItem('unkenntlich-vorgang')")
        print(f"Erkennung der drei Beispiele: {time.time() - t0:.0f} s", flush=True)
        beide_schemata(s, "ablegen-fertig")
        s.click("text=Weiter: Vorschläge prüfen"); s.wait_for_selector("svg.flaeche image")
        s.wait_for_timeout(1500)
        beide_schemata(s, "pruefen-dokument")
        v = api(s, f"/vorgang/{vid}")
        # simulierter Mensch: Angaben der Behörde sichtbar lassen (Zentrale, Rathausplatz, Stadtkasse)
        for st in v["stellen"]:
            if st["datei"] == "d1" and st.get("text") and any(k in st["text"] for k in ("90009 100", "Rathausplatz", "12345 Musterhausen", "Bürgerbüro")):
                s.click(f".vorschlag[data-id='{st['id']}'] >> text=Sichtbar lassen") if s.locator(f".vorschlag[data-id='{st['id']}']").count() else None
                s.wait_for_timeout(300)
                if s.locator(f"#grund-{st['id']}").count():
                    s.select_option(f"#grund-{st['id']}", "Keine Person (Behörde, Firma)"); s.wait_for_timeout(300)
        s.screenshot(path=str(MEDIEN / "pruefen-dokument.jpg"))
        s.click("text=Seite angesehen"); s.wait_for_timeout(1200)
        if s.locator("text=Seite angesehen").count():
            s.click("text=Seite angesehen"); s.wait_for_timeout(1200)
        # Foto
        s.click("[role=tab] >> text=marktplatz.jpg"); s.wait_for_timeout(1500)
        beide_schemata(s, "pruefen-foto")
        s.screenshot(path=str(MEDIEN / "pruefen-foto.jpg"))
        s.click("text=Bild angesehen"); s.wait_for_timeout(1200)
        # Video: eine (erzeugte) Person bleibt sichtbar (Einwilligung, simuliert)
        s.click("[role=tab] >> text=fussgaengerzone.mp4"); s.wait_for_selector("#film"); s.wait_for_timeout(2500)
        karte = s.locator(".karte").first
        karte.locator("text=Sichtbar").click(); s.wait_for_timeout(500)
        sid = karte.get_attribute("data-id")
        if s.locator(f"#grund-{sid}").count():
            s.select_option(f"#grund-{sid}", "Einwilligung liegt vor"); s.wait_for_timeout(400)
        s.locator(".karte .bild").nth(1).click(); s.wait_for_timeout(1500)
        beide_schemata(s, "pruefen-video")
        s.screenshot(path=str(MEDIEN / "pruefen-video.jpg"))
        s.click("text=Video angesehen"); s.wait_for_timeout(1500)
        # Gegenprobe
        s.click("text=Gegenprobe starten"); s.wait_for_timeout(2000)
        axe(s, "gegenprobe-laeuft-hell")
        t0 = time.time()
        s.wait_for_selector(".urteil", timeout=60 * 60 * 1000)
        print(f"Gegenprobe: {time.time() - t0:.0f} s", flush=True)
        s.wait_for_timeout(1200)
        beide_schemata(s, "gegenprobe-ergebnis")
        s.screenshot(path=str(MEDIEN / "gegenprobe.jpg"))
        gp = api(s, f"/vorgang/{vid}")["gegenprobe"]
        runden = 1
        while gp["reste"] and runden < 3:
            # Reste übernehmen, angesehen bestätigen, erneut prüfen (der Ablauf, den ein Mensch dann geht)
            beide_schemata(s, f"gegenprobe-reste-{runden}")
            s.screenshot(path=str(MEDIEN / "gegenprobe-reste.jpg"))
            s.click("text=Reste als Vorschläge übernehmen"); s.wait_for_selector(".pruefen"); s.wait_for_timeout(1500)
            for tab in s.locator("[role=tab]").all():
                if "angesehen" not in tab.inner_text():
                    tab.click(); s.wait_for_timeout(1800)
                    if runden == 1:
                        beide_schemata(s, "pruefen-reste")
                    s.locator(".buehne-fuss button").first.click(); s.wait_for_timeout(1200)
            s.click("text=Gegenprobe starten"); s.wait_for_timeout(2000)
            s.wait_for_selector(".urteil", timeout=60 * 60 * 1000)
            gp = api(s, f"/vorgang/{vid}")["gegenprobe"]
            runden += 1
        s.screenshot(path=str(MEDIEN / "gegenprobe.jpg"))
        tastatur = None
        if gp["reste"] == 0:
            s.click("text=Zum Ergebnis"); s.wait_for_selector(".vergleich img"); s.wait_for_timeout(2500)
            beide_schemata(s, "fertig")
            griff = s.locator("[role=slider]").first
            griff.focus(); s.keyboard.press("ArrowLeft"); s.keyboard.press("ArrowLeft")
            tastatur = griff.get_attribute("aria-valuenow")
            s.screenshot(path=str(MEDIEN / "fertig.jpg"))
            for i, karte in enumerate(s.locator(".vergleich-karte").all()):
                karte.screenshot(path=str(MEDIEN / f"vergleich-{i + 1}.jpg"), quality=82)
        ergebnis = {"axe": "axe-core 4.14.1", "regeln": REGELN, "ansichten": ergebnisse,
                    "verstoesse_gesamt": sum(v["anzahl"] for e in ergebnisse for v in e["verstoesse"]),
                    # axe „incomplete“: Stellen, die axe nicht selbst entscheiden kann und zur Handprüfung meldet
                    "zur_handpruefung": sum(len(e["offen"]) for e in ergebnisse),
                    "zur_handpruefung_regeln": sorted({r for e in ergebnisse for r in e["offen"]}),
                    "gegenprobe_reste": gp["reste"], "schieber_tastatur_wert": tastatur, "seitenfehler": fehler,
                    "browser": b.version}
        (HIER / "nachweis" / "barrierefreiheit.json").write_text(json.dumps(ergebnis, ensure_ascii=False, indent=1))
        print("Verstöße gesamt:", ergebnis["verstoesse_gesamt"], "Seitenfehler:", fehler, flush=True)
        b.close()
    return 0 if ergebnis["verstoesse_gesamt"] == 0 and not fehler else 1


if __name__ == "__main__":
    raise SystemExit(main())
