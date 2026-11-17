"""Der ganze Ablauf über die Programmschnittstelle: ablegen, erkennen, ansehen, Gegenprobe, Export, löschen."""
import io
import time

import pymupdf
from fastapi.testclient import TestClient

from unkenntlich import server, vorgang


def pdf_bytes() -> bytes:
    doc = pymupdf.open()
    s = doc.new_page()
    s.insert_text((72, 100), "Sehr geehrte Frau Albers,", fontsize=12)
    s.insert_text((72, 130), "Ihre IBAN lautet DE68 9001 2345 0123 4567 89.", fontsize=12)
    s.insert_text((72, 160), "Rückfragen unter 069 90009 123.", fontsize=12)
    doc.set_metadata({"author": "Jana Albers"})
    return doc.tobytes()


def warten(c, vid, bedingung, sekunden=180):
    ende = time.time() + sekunden
    while time.time() < ende:
        v = c.get(f"/api/vorgang/{vid}").json()
        if bedingung(v):
            return v
        time.sleep(0.3)
    raise AssertionError("Zeit abgelaufen")


def test_ablauf(tmp_path, monkeypatch):
    monkeypatch.setattr(vorgang, "DATEN", tmp_path)
    with TestClient(server.app) as c:
        assert c.get("/api/gesundheit").json()["ok"]
        r = c.get("/")
        assert r.status_code == 200 and "default-src 'self'" in r.headers["content-security-policy"]
        vid = c.post("/api/vorgang").json()["id"]
        r = c.post(f"/api/vorgang/{vid}/dateien", files=[("dateien", ("brief.pdf", io.BytesIO(pdf_bytes()), "application/pdf"))])
        assert r.status_code == 200
        v = warten(c, vid, lambda v: v["dateien"][0]["status"] == "bereit")
        kats = {s["kategorie"] for s in v["stellen"]}
        assert {"iban", "telefon", "name"} <= kats, kats
        assert c.post(f"/api/vorgang/{vid}/gegenprobe").status_code == 409          # noch nicht angesehen
        assert c.get(f"/api/vorgang/{vid}/export.zip").status_code == 423           # Export gesperrt
        did = v["dateien"][0]["id"]
        assert c.get(f"/api/vorgang/{vid}/datei/{did}/seite/0").status_code == 200   # Original ansehen geht
        assert c.get(f"/api/vorgang/{vid}/datei/{did}/seite/0?ergebnis=true").status_code == 423
        assert c.get(f"/api/vorgang/{vid}/datei/{did}/video?ergebnis=true").status_code == 423
        v = c.post(f"/api/vorgang/{vid}/datei/{did}/seite/0/geprueft").json()
        assert v["bereit_fuer_gegenprobe"]
        assert c.post(f"/api/vorgang/{vid}/gegenprobe").status_code == 200
        v = warten(c, vid, lambda v: (v["gegenprobe"] or {}).get("status") == "fertig")
        assert v["gegenprobe"]["reste"] == 0, v["gegenprobe"]["ergebnisse"]
        assert c.get(f"/api/vorgang/{vid}/datei/{did}/seite/0?ergebnis=true").status_code == 200
        # Gegenprobe mit Rest: Vorschau des Ergebnisses, Video, Datei und ZIP bleiben gesperrt
        gespeichert = vorgang.laden(vid)["gegenprobe"]
        vorgang.laden(vid)["gegenprobe"] = {**gespeichert, "reste": 1}
        for pfad in (f"datei/{did}/seite/0?ergebnis=true", f"datei/{did}/video?ergebnis=true&format=webm",
                     f"ergebnis/{did}", "export.zip"):
            assert c.get(f"/api/vorgang/{vid}/{pfad}").status_code == 423, pfad
        vorgang.laden(vid)["gegenprobe"] = gespeichert
        r = c.get(f"/api/vorgang/{vid}/export.zip")
        assert r.status_code == 200 and r.content[:2] == b"PK"
        aus = pymupdf.open(stream=c.get(f"/api/vorgang/{vid}/ergebnis/{did}").content, filetype="pdf")
        assert "3704" not in aus[0].get_text() and not aus.metadata.get("author")
        assert c.get(f"/api/vorgang/{vid}/bericht.pdf").content[:4] == b"%PDF"
        assert c.delete(f"/api/vorgang/{vid}").json()["geloescht"]
        assert not (tmp_path / vid).exists()
