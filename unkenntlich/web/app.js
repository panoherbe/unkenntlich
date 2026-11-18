// Unkenntlich – Oberfläche. Ohne Abhängigkeiten, ohne Build-Schritt, ohne Aufrufe nach außen.
const $ = (sel, wurzel = document) => wurzel.querySelector(sel);
const $$ = (sel, wurzel = document) => [...wurzel.querySelectorAll(sel)];
const NS = "http://www.w3.org/2000/svg";

// --- Symbole (24er-Raster, Strich) -------------------------------------------------------------------------------
const S = (pfad) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${pfad}</svg>`;
const SYMBOL = {
  dokument: S('<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5M10 13h6M10 17h6"/>'),
  foto: S('<rect x="3" y="5" width="18" height="14" rx="2.5"/><circle cx="9" cy="10" r="1.8"/><path d="M21 16l-5-5-8 8"/>'),
  video: S('<rect x="3" y="6" width="13" height="12" rx="2.5"/><path d="M16 10l5-3v10l-5-3z"/>'),
  person: S('<circle cx="12" cy="8" r="3.6"/><path d="M5 20c1.2-3.6 4-5.4 7-5.4s5.8 1.8 7 5.4"/>'),
  ort: S('<path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11z"/><circle cx="12" cy="10" r="2.3"/>'),
  kontakt: S('<path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>'),
  konto: S('<path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/>'),
  nummer: S('<path d="M9 4L7 20M17 4l-2 16M4 9h16M3.5 15h16"/>'),
  fahrzeug: S('<rect x="3" y="8" width="18" height="8" rx="2"/><path d="M7 12h2M11 12h6"/>'),
  gesicht: S('<circle cx="12" cy="12" r="8.5"/><path d="M9 10h.01M15 10h.01M8.8 14.5c1.8 1.6 4.6 1.6 6.4 0"/>'),
  hand: S('<path d="M4 18c3-1 4-6 6-6s1 4 3 4 3-6 5-6 2 3 2 3"/><path d="M4 21h16"/>'),
  eigen: S('<rect x="4" y="4" width="16" height="16" rx="2" stroke-dasharray="3 3"/>'),
  haken: S('<path d="M5 12.5l4.5 4.5L19 7.5"/>'),
  pfeil: S('<path d="M5 12h14M13 6l6 6-6 6"/>'),
  zurueck: S('<path d="M15 6l-6 6 6 6"/>'),
  vor: S('<path d="M9 6l6 6-6 6"/>'),
  schloss: S('<rect x="5" y="10" width="14" height="10" rx="2.5"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10"/>'),
  auge: S('<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="2.8"/>'),
  schild: S('<path d="M12 3l7.5 3v5.5c0 4.6-3.2 8-7.5 9.5-4.3-1.5-7.5-4.9-7.5-9.5V6z"/><path d="M8.8 12.2l2.3 2.3 4.2-4.6"/>'),
  sonne: S('<circle cx="12" cy="12" r="4"/><path d="M12 2.5v2M12 19.5v2M4.6 4.6L6 6M18 18l1.4 1.4M2.5 12h2M19.5 12h2M4.6 19.4L6 18M18 6l1.4-1.4"/>'),
  mond: S('<path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5z"/>'),
  ziehen: S('<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/>'),
  laden: S('<path d="M12 4v11M7 10l5 5 5-5M5 20h14"/>'),
  griff: S('<path d="M9 7l-5 5 5 5M15 7l5 5-5 5"/>'),
  abspielen: S('<path d="M7 5v14l12-7z"/>'),
  pause: S('<path d="M8 5v14M16 5v14"/>'),
};
const GRUPPE_FARBE = { person: "--k-person", ort: "--k-ort", kontakt: "--k-kontakt", konto: "--k-konto", nummer: "--k-nummer",
  fahrzeug: "--k-fahrzeug", gesicht: "--k-gesicht", hand: "--k-hand", eigen: "--k-eigen" };
const ART_NAME = { dokument: "Dokument", foto: "Bild", video: "Video" };
const BEGRUENDUNGEN = ["Keine Person (Behörde, Firma)", "Einwilligung liegt vor", "Kein Personenbezug", "Person des öffentlichen Lebens", "Anderer Grund"];

const z = { v: null, info: null, ansicht: "ablegen", datei: null, seite: 0, gewaehlt: null, zeichnen: false,
  filter: "personen", spuren: {}, abfrage: null, entwurf: null };

// --- Hilfen ------------------------------------------------------------------------------------------------------
function el(tag, attr = {}, ...kinder) {
  const e = document.createElement(tag);
  for (const [k, w] of Object.entries(attr)) {
    if (w === false || w === null || w === undefined) continue;
    if (k === "html") e.innerHTML = w;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), w);
    else e.setAttribute(k, w === true ? "" : w);
  }
  for (const k of kinder.flat()) if (k !== null && k !== undefined && k !== false) e.append(k instanceof Node ? k : document.createTextNode(k));
  return e;
}
const breite = (e, anteil) => { e.style.width = `${Math.round(anteil * 100)}%`; return e; };
const zahl = (x, n = 0) => Number(x).toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
const groesse = (b) => b > 1e6 ? `${zahl(b / 1e6, 1)} MB` : `${zahl(b / 1e3, 0)} KB`;
const mal = (n, eins, mehr) => `${zahl(n)} ${n === 1 ? eins : mehr}`;
const uhr = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
// Meldungen: Was die Seite ohnehin zeigt (bestätigt, Bereich gezogen), hören nur Bildschirmleser („leise“). Sichtbar
// erscheint eine Meldung über der Leiste unten, nie über Knöpfen oder Inhalt der Leiste, und verschwindet nach 4 s.
function melden(text, leise = false) {
  if (leise) {
    const l = $("#vorlesen"); l.textContent = "";
    setTimeout(() => { l.textContent = text; }, 60);
    return;
  }
  const m = $("#meldung");
  m.textContent = text; m.hidden = false;
  const leiste = $("#leiste")?.getBoundingClientRect();
  m.style.bottom = leiste && leiste.top < innerHeight ? `${Math.round(innerHeight - leiste.top + 12)}px` : "";
  clearTimeout(melden.t); melden.t = setTimeout(() => { m.hidden = true; }, 4200);
}
async function api(pfad, opt = {}) {
  const antwort = await fetch(`/api${pfad}`, opt);
  if (!antwort.ok) {
    let text = `Fehler ${antwort.status}`;
    try { text = (await antwort.json()).detail || text; } catch (e) { /* kein JSON */ }
    throw new Error(text);
  }
  return antwort.headers.get("content-type")?.includes("json") ? antwort.json() : antwort;
}
const post = (pfad, daten) => api(pfad, daten === undefined ? { method: "POST" } :
  { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(daten) });
const vid = () => z.v.id;
const katInfo = (k) => z.info?.kategorien?.[k] || { name: k, gruppe: "eigen" };
const farbe = (k) => `var(${GRUPPE_FARBE[katInfo(k).gruppe] || "--k-eigen"})`;
const dateiVon = (id) => z.v.dateien.find((d) => d.id === id);
const stellenVon = (did, seite) => z.v.stellen.filter((s) => s.datei === did && (seite === undefined || (s.seite || 0) === seite));
function speichereVorgang(id) { try { sessionStorage.setItem("unkenntlich-vorgang", id); } catch (e) { /* ohne Speicher */ } }
function geladenerVorgang() { try { return sessionStorage.getItem("unkenntlich-vorgang"); } catch (e) { return null; } }

// --- Start -------------------------------------------------------------------------------------------------------
async function start() {
  schemaKnopf();
  z.info = await api("/info");
  const merk = new URLSearchParams(location.hash.slice(1)).get("v") || geladenerVorgang();
  if (merk) { try { z.v = await api(`/vorgang/${merk}`); } catch (e) { z.v = null; } }
  if (!z.v) z.v = await post("/vorgang");
  speichereVorgang(z.v.id);
  z.ansicht = { ablegen: "ablegen", pruefen: "pruefen", gegenprobe: "gegenprobe", fertig: "fertig" }[z.v.phase] || "ablegen";
  if (z.ansicht === "pruefen" && z.v.dateien.some((d) => d.status !== "bereit")) z.ansicht = "ablegen";
  $$("#schritte button").forEach((b) => b.addEventListener("click", () => wechseln(b.dataset.schritt)));
  $("#marke").addEventListener("click", (e) => { e.preventDefault(); wechseln("ablegen"); });
  $("#loeschen").addEventListener("click", allesLoeschen);
  $("#meldung").addEventListener("click", () => { $("#meldung").hidden = true; });
  zeichnen();
  abfragenWennNoetig();
}

function schemaKnopf() {
  const k = $("#schema");
  const setzen = () => {
    const dunkel = document.documentElement.dataset.schema === "dunkel";
    k.innerHTML = dunkel ? SYMBOL.sonne : SYMBOL.mond;
    k.setAttribute("aria-pressed", String(dunkel));
    k.setAttribute("aria-label", "Dunkles Schema");
    k.title = dunkel ? "Helles Schema" : "Dunkles Schema";
  };
  k.addEventListener("click", () => {
    const neu = document.documentElement.dataset.schema === "dunkel" ? "hell" : "dunkel";
    document.documentElement.dataset.schema = neu;
    try { localStorage.setItem("unkenntlich-schema", neu); } catch (e) { /* ohne Speicher */ }
    setzen(); if (z.ansicht === "pruefen") zeichneFilm();
  });
  setzen();
}

async function allesLoeschen() {
  if (!confirm("Alle abgelegten Dateien, Ergebnisse und den Prüfbericht dieses Vorgangs von diesem Rechner löschen?")) return;
  await api(`/vorgang/${vid()}`, { method: "DELETE" });
  z.v = await post("/vorgang"); speichereVorgang(z.v.id);
  Object.assign(z, { datei: null, seite: 0, gewaehlt: null, spuren: {}, ansicht: "ablegen" });
  zeichnen(); melden("Alles gelöscht. Ein neuer, leerer Vorgang ist bereit.");
}

function erlaubt(schritt) {
  const v = z.v;
  const bereit = v.dateien.length && v.dateien.every((d) => d.status === "bereit");
  if (schritt === "ablegen") return true;
  if (schritt === "pruefen") return !!bereit;
  if (schritt === "gegenprobe") return !!v.gegenprobe || v.bereit_fuer_gegenprobe;
  if (schritt === "fertig") return v.gegenprobe?.status === "fertig" && v.gegenprobe.reste === 0;
  return false;
}

function wechseln(schritt) {
  if (!erlaubt(schritt)) return;
  $("#meldung").hidden = true;
  z.ansicht = schritt; z.gewaehlt = null; z.zeichnen = false;
  zeichnen();
  $("#inhalt").focus({ preventScroll: true });
  window.scrollTo({ top: 0 });
}

function schritteZeichnen() {
  const reihe = ["ablegen", "pruefen", "gegenprobe", "fertig"];
  const jetzt = reihe.indexOf(z.ansicht);
  $$("#schritte button").forEach((b) => {
    const i = reihe.indexOf(b.dataset.schritt);
    b.disabled = !erlaubt(b.dataset.schritt);
    if (i === jetzt) b.setAttribute("aria-current", "step"); else b.removeAttribute("aria-current");
    b.classList.toggle("erledigt", i < jetzt);
  });
}

function zeichnen() {
  schritteZeichnen();
  const main = $("#inhalt");
  main.replaceChildren();
  ({ ablegen: zeichneAblegen, pruefen: zeichnePruefen, gegenprobe: zeichneGegenprobe, fertig: zeichneFertig })[z.ansicht](main);
}

function beschaeftigt() {
  return z.v.dateien.some((d) => d.status === "wartet" || d.status === "liest") || z.v.gegenprobe?.status === "laeuft";
}
function abfragenWennNoetig() {
  if (z.abfrage || !beschaeftigt()) return;
  z.abfrage = setInterval(async () => {
    try { z.v = await api(`/vorgang/${vid()}`); } catch (e) { return; }
    if (z.ansicht === "ablegen") aktualisiereDateiliste();
    if (z.ansicht === "gegenprobe") gegenprobeAktualisieren();
    if (!beschaeftigt()) {
      clearInterval(z.abfrage); z.abfrage = null;
      if (z.ansicht === "ablegen") zeichnen();
      if (z.ansicht === "gegenprobe") zeichnen();
    }
  }, 700);
}

// --- 1 Ablegen ---------------------------------------------------------------------------------------------------
function zeichneAblegen(main) {
  const eingabe = el("input", { type: "file", id: "auswahl", class: "unsichtbar", multiple: true,
    accept: ".pdf,.jpg,.jpeg,.png,.mp4,.mov,application/pdf,image/jpeg,image/png,video/mp4,video/quicktime",
    onchange: (e) => hochladen(e.target.files) });
  const zone = el("div", { class: "zone", id: "zone" },
    el("div", { class: "pixel", "aria-hidden": "true" }, ...Array.from({ length: 12 }, () => el("i"))),
    el("div", { class: "bildchen", "aria-hidden": "true" }, el("span", { html: SYMBOL.dokument }), el("span", { html: SYMBOL.foto }), el("span", { html: SYMBOL.video })),
    el("h2", {}, "Dateien hier ablegen"),
    el("p", {}, "PDF (auch gescannt), Fotos (JPG, PNG) und kurze Videos (MP4). Nichts verlässt diesen Rechner."),
    el("div", { class: "knoepfe" },
      el("label", { class: "knopf haupt", for: "auswahl", tabindex: "0", role: "button",
        onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); eingabe.click(); } } }, "Dateien auswählen"),
      el("button", { type: "button", class: "knopf", id: "beispiele", onclick: beispiele }, "Beispiele laden")),
    eingabe);
  ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.add("ueber"); }));
  ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, (e) => { e.preventDefault(); zone.classList.remove("ueber"); }));
  zone.addEventListener("drop", (e) => hochladen(e.dataTransfer.files));

  main.append(el("section", { class: "start" },
    el("div", {},
      el("h1", {}, "Personen und ihre Daten ", el("em", {}, "unkenntlich"), " machen."),
      el("p", { class: "unterzeile" }, "Für Dokumente, Fotos und Videos. Unkenntlich schlägt jede Stelle vor, Sie entscheiden. Danach prüft eine Gegenprobe das Ergebnis, und ein Prüfbericht hält alles fest."),
      el("ul", { class: "vorteile" },
        vorteil(SYMBOL.schloss, "Bleibt auf diesem Rechner", "Ohne Internet, ohne Konto, ohne Statistik. Die Modelle laufen lokal, auch ohne Grafikkarte."),
        vorteil(SYMBOL.auge, "Sie entscheiden jede Stelle", "Namen, Anschriften, IBAN, Unterschriften, Gesichter und Kennzeichen werden vorgeschlagen, nie still entfernt."),
        vorteil(SYMBOL.schild, "Gegenprobe vor dem Export", "Text, Bilder und Metadaten werden wirklich entfernt. Findet die Gegenprobe noch etwas, bleibt der Export gesperrt."))),
    el("div", { class: "ablage" }, zone,
      el("p", { class: "hinweis-klein" }, "Beispiele: ein erfundenes Schreiben als Scan (simuliert), ein Foto und ein Video, erzeugt mit offenen Modellen: keine echten Personen, keine echten Kennzeichen."),
      el("ul", { class: "dateiliste", id: "dateiliste", "aria-label": "Abgelegte Dateien" }),
      el("div", { class: "weiter", id: "weiter" }))));
  aktualisiereDateiliste();
}
function vorteil(symbol, titel, text) {
  return el("li", {}, el("span", { class: "zeichen", html: symbol }), el("div", {}, el("b", {}, titel), el("span", {}, text)));
}
function aktualisiereDateiliste() {
  const liste = $("#dateiliste"); if (!liste) return;
  liste.replaceChildren(...z.v.dateien.map((d) => {
    const anteil = d.status === "bereit" ? 1 : d.fortschritt || 0;
    const zahlStellen = stellenVon(d.id).length;
    const zustand = d.status === "bereit" ? `${zahlStellen} Vorschläge · ${zahl(d.dauer_analyse, 1)} s`
      : d.status === "fehler" ? d.meldung : d.status === "wartet" ? "wartet …" : d.meldung;
    return el("li", {},
      el("span", { class: "art", html: SYMBOL[d.art] }),
      el("div", {}, el("div", { class: "name" }, d.name),
        el("div", { class: "zustand" }, `${ART_NAME[d.art]} · ${groesse(d.groesse)} · ${zustand}`),
        d.status !== "bereit" ? el("div", { class: "balken", role: "progressbar", "aria-label": `Erkennung ${d.name}`,
          "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(Math.round(anteil * 100)) }, breite(el("i"), anteil)) : null),
      el("span", { class: "zahl" }, d.status === "bereit" ? el("span", { class: "fertig-zeichen", html: SYMBOL.haken }) : `${Math.round(anteil * 100)} %`));
  }));
  const weiter = $("#weiter");
  const alle = z.v.dateien.length && z.v.dateien.every((d) => d.status === "bereit");
  weiter.replaceChildren(alle ? el("button", { type: "button", class: "knopf haupt", onclick: () => wechseln("pruefen"), html: `Weiter: Vorschläge prüfen ${SYMBOL.pfeil}` }) : "");
  schritteZeichnen();
}
async function hochladen(dateien) {
  if (!dateien?.length) return;
  const form = new FormData();
  for (const f of dateien) form.append("dateien", f, f.name);
  try { z.v = await api(`/vorgang/${vid()}/dateien`, { method: "POST", body: form }); } catch (e) { melden(e.message); return; }
  aktualisiereDateiliste(); abfragenWennNoetig();
}
async function beispiele() {
  $("#beispiele").disabled = true;
  try { z.v = await post(`/vorgang/${vid()}/beispiele`); } catch (e) { melden(e.message); }
  aktualisiereDateiliste(); abfragenWennNoetig();
}

// --- 2 Prüfen ----------------------------------------------------------------------------------------------------
const imExport = (d) => !d?.ausgenommen;
function aktuelleDatei() {
  if (!z.datei || !dateiVon(z.datei)) z.datei = (z.v.dateien.find((d) => imExport(d) && d.seiten.some((s) => !s.geprueft)) || z.v.dateien[0])?.id;
  return dateiVon(z.datei);
}

function zeichnePruefen(main) {
  const d = aktuelleDatei();
  if (!d) return;
  if (z.seite >= d.seiten.length) z.seite = 0;
  const reiter = el("div", { class: "reiter" }, el("h2", { id: "dateien-titel" }, "Dateien"),
    el("div", { class: "reiter-liste", role: "tablist", "aria-labelledby": "dateien-titel" }, ...z.v.dateien.map((x) => {
      const offen = imExport(x) ? x.seiten.filter((s) => !s.geprueft).length : 0;
      return el("button", { type: "button", role: "tab", "aria-selected": String(x.id === d.id), class: offen || !imExport(x) ? "" : "fertig",
        onclick: () => { z.datei = x.id; z.seite = 0; z.gewaehlt = null; z.zeichnen = false; zeichnen(); } },
        el("span", { class: "art", html: SYMBOL[x.art] }),
        el("span", {}, el("b", {}, x.name), el("small", {}, !imExport(x) ? "nicht im Export" : offen ? (x.art === "dokument" ? `${offen} von ${x.seiten.length} Seiten offen` : "noch ansehen") : "angesehen ✓")));
    })));
  const buehne = el("section", { class: "buehne", "aria-label": "Ansicht" });
  const tafel = el("aside", { class: "tafel", id: "tafel", "aria-label": "Vorschläge" });
  main.append(el("div", { class: "pruefen" }, reiter, buehne, tafel), leiste());
  if (d.art === "video") zeichneVideo(d, buehne, tafel); else zeichneSeite(d, buehne, tafel);
}

function leiste() {
  const v = z.v;
  const offenSeiten = v.dateien.filter(imExport).reduce((n, d) => n + d.seiten.filter((s) => !s.geprueft).length, 0);
  const offenStellen = v.stellen.filter((s) => s.entscheidung === "offen" && imExport(dateiVon(s.datei))).length;
  const text = v.bereit_fuer_gegenprobe ? el("p", {}, el("b", {}, "Alles angesehen. "), "Jetzt werden die Dateien unkenntlich gemacht und erneut geprüft.")
    : el("p", {}, el("b", {}, "Noch offen: "), `${offenSeiten} Seite(n) bzw. Datei(en) ansehen, ${offenStellen} Vorschläge ohne Entscheidung.`);
  return el("div", { class: "leiste", id: "leiste" }, text,
    el("button", { type: "button", class: "knopf haupt", disabled: !v.bereit_fuer_gegenprobe, onclick: gegenprobeStarten,
      html: `Gegenprobe starten ${SYMBOL.pfeil}` }));
}

async function entscheiden(aenderungen) {
  try { z.v = await post(`/vorgang/${vid()}/entscheidungen`, aenderungen); } catch (e) { melden(e.message); return; }
  const d = aktuelleDatei();
  if (d.art === "video") { tafelVideo(d); zeichneFilm(); zeichneZeitleiste(d); } else { tafelSeite(d); ueberlagerung(d); }
  $("#leiste").replaceWith(leiste()); schritteZeichnen();
}

function wahlKnopf(text, gedrueckt, klick, klasse = "") {
  return el("button", { type: "button", class: klasse, "aria-pressed": String(gedrueckt), onclick: klick }, text);
}

// Dokument oder Bild
function zeichneSeite(d, buehne, tafel) {
  const seite = d.seiten[z.seite];
  const titel = d.art === "dokument" ? `${d.name} · Seite ${z.seite + 1} von ${d.seiten.length}` : d.name;
  const zeichnenKnopf = el("button", { type: "button", class: "knopf klein schalter-zeichnen", "aria-pressed": String(z.zeichnen),
    onclick: () => { z.zeichnen = !z.zeichnen; zeichnen(); }, html: `${SYMBOL.ziehen} Bereich ziehen` });
  const blaettern = d.seiten.length > 1 ? el("div", { class: "blaettern" },
    el("button", { type: "button", class: "symbolknopf", "aria-label": "Vorige Seite", disabled: z.seite === 0, html: SYMBOL.zurueck,
      onclick: () => { z.seite--; z.gewaehlt = null; zeichnen(); } }),
    el("span", {}, `Seite ${z.seite + 1} / ${d.seiten.length}`),
    el("button", { type: "button", class: "symbolknopf", "aria-label": "Nächste Seite", disabled: z.seite >= d.seiten.length - 1, html: SYMBOL.vor,
      onclick: () => { z.seite++; z.gewaehlt = null; zeichnen(); } })) : null;
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "flaeche"); svg.setAttribute("viewBox", `0 0 ${seite.breite} ${seite.hoehe}`);
  svg.setAttribute("role", "img"); svg.setAttribute("aria-label", `${titel} mit markierten Vorschlägen`);
  const bild = document.createElementNS(NS, "image");
  bild.setAttribute("href", `/api/vorgang/${vid()}/datei/${d.id}/seite/${z.seite}`);
  bild.setAttribute("width", seite.breite); bild.setAttribute("height", seite.hoehe);
  svg.append(bild, Object.assign(document.createElementNS(NS, "g"), { id: "stellen" }));
  const ansicht = el("div", { class: `ansicht${z.zeichnen ? " zeichnen" : ""}` }, svg);
  bereichZiehen(svg, d);
  const geprueft = seite.geprueft;
  buehne.append(
    el("div", { class: "buehne-kopf" }, el("h2", {}, titel), el("div", { class: "blaettern" }, blaettern, zeichnenKnopf)),
    ansicht,
    el("div", { class: "buehne-fuss" },
      el("span", { class: "leise" }, z.zeichnen ? "Ziehen Sie mit der Maus einen Rahmen um eine Stelle, die fehlt." : "Klicken Sie auf eine Markierung, um sie in der Liste zu sehen."),
      el("button", { type: "button", class: `knopf ${geprueft ? "" : "haupt"}`, disabled: geprueft, onclick: () => seiteBestaetigen(d),
        html: geprueft ? `${SYMBOL.haken} angesehen` : `${SYMBOL.haken} ${d.art === "dokument" ? "Seite" : "Bild"} angesehen – offene Vorschläge unkenntlich` })));
  ueberlagerung(d);
  tafel.replaceChildren(); tafelSeite(d);
}

function ueberlagerung(d) {
  const g = $("#stellen"); if (!g) return;
  g.replaceChildren();
  for (const s of stellenVon(d.id, z.seite)) {
    for (const r of s.rechtecke) {
      const rect = document.createElementNS(NS, "rect");
      const [x0, y0, x1, y1] = r;
      rect.setAttribute("x", x0); rect.setAttribute("y", y0);
      rect.setAttribute("width", Math.max(1, x1 - x0)); rect.setAttribute("height", Math.max(1, y1 - y0));
      const rr = Math.min(x1 - x0, y1 - y0) * 0.18; rect.setAttribute("rx", rr); rect.setAttribute("ry", rr);
      rect.setAttribute("class", `stelle ${s.entscheidung}${z.gewaehlt === s.id ? " gewaehlt" : ""}`);
      rect.style.setProperty("--farbe", farbe(s.kategorie));
      rect.dataset.id = s.id;
      rect.addEventListener("click", () => { if (!z.zeichnen) waehlen(s.id, true); });
      const t = document.createElementNS(NS, "title"); t.textContent = `${katInfo(s.kategorie).name}: ${s.grund}`;
      rect.append(t); g.append(rect);
    }
  }
}

function waehlen(id, inListe = false) {
  z.gewaehlt = z.gewaehlt === id ? null : id;
  $$(".stelle").forEach((r) => r.classList.toggle("gewaehlt", r.dataset.id === z.gewaehlt));
  $$(".vorschlag").forEach((li) => li.classList.toggle("gewaehlt", li.dataset.id === z.gewaehlt));
  if (inListe && z.gewaehlt) $(`.vorschlag[data-id="${z.gewaehlt}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function tafelSeite(d) {
  const tafel = $("#tafel"); if (!tafel) return;
  const stellen = stellenVon(d.id, z.seite).sort((a, b) => (a.rechtecke[0]?.[1] || 0) - (b.rechtecke[0]?.[1] || 0));
  const offen = stellen.filter((s) => s.entscheidung === "offen").length;
  tafel.replaceChildren(
    el("div", { class: "tafel-kopf" }, el("h2", {}, `Vorschläge (${stellen.length})`), el("span", { class: "leise" }, offen ? `${offen} offen` : "alle entschieden")),
    el("ul", { class: "liste" }, ...stellen.map((s) => vorschlag(s))),
    metadatenBlock(d));
}

function vorschlag(s) {
  const k = katInfo(s.kategorie);
  const li = el("li", { class: `vorschlag${z.gewaehlt === s.id ? " gewaehlt" : ""}`, "data-id": s.id },
    el("div", { class: "zeile" }, el("span", { class: "kat", html: `${SYMBOL[k.gruppe] || SYMBOL.eigen}<span>${k.name}</span>` }),
      s.neu ? el("span", { class: "leise" }, "· neu aus der Gegenprobe") : null),
    s.text ? el("div", { class: "fund" }, s.text) : null,
    el("div", { class: "grund" }, `${s.grund} · ${s.quelle}${s.sicherheit < 1 ? ` · ${zahl(s.sicherheit * 100)} %` : ""}`),
    el("div", { class: "wahl", role: "group", "aria-label": `Entscheidung für ${k.name}${s.text ? " " + s.text : ""}` },
      wahlKnopf("Unkenntlich", s.entscheidung === "unkenntlich", () => entscheiden([{ id: s.id, entscheidung: "unkenntlich" }]), "u"),
      wahlKnopf("Sichtbar lassen", s.entscheidung === "sichtbar", () => entscheiden([{ id: s.id, entscheidung: "sichtbar" }]))),
    s.entscheidung === "sichtbar" ? begruendungWahl(s) : null);
  li.style.setProperty("--farbe", farbe(s.kategorie));
  li.addEventListener("click", (e) => { if (!e.target.closest("button, select")) waehlen(s.id); });
  return li;
}

function begruendungWahl(s) {
  const id = `grund-${s.id}`;
  return el("div", {}, el("label", { class: "unsichtbar", for: id }, "Warum bleibt die Stelle sichtbar?"),
    el("select", { id, onchange: (e) => entscheiden([{ id: s.id, begruendung: e.target.value }]) },
      el("option", { value: "" }, "Grund wählen (für den Prüfbericht)"),
      ...BEGRUENDUNGEN.map((b) => el("option", { value: b, selected: s.begruendung === b }, b))));
}

function metadatenBlock(d) {
  if (!d.metadaten?.length) return el("div", { class: "metadaten" }, "Keine Metadaten gefunden.");
  return el("div", { class: "metadaten" }, el("b", {}, "Wird immer entfernt: "), `${d.metadaten.length} Metadaten-Felder`,
    el("ul", {}, ...d.metadaten.map((m) => el("li", {}, m.feld))));
}

function bereichZiehen(svg, d) {
  let start = null, rahmen = null;
  const punkt = (e) => { const p = svg.createSVGPoint(); p.x = e.clientX; p.y = e.clientY; return p.matrixTransform(svg.getScreenCTM().inverse()); };
  svg.addEventListener("pointerdown", (e) => {
    if (!z.zeichnen) return;
    start = punkt(e); svg.setPointerCapture(e.pointerId);
    rahmen = document.createElementNS(NS, "rect"); rahmen.setAttribute("class", "entwurf"); svg.append(rahmen);
  });
  svg.addEventListener("pointermove", (e) => {
    if (!start) return;
    const p = punkt(e);
    rahmen.setAttribute("x", Math.min(start.x, p.x)); rahmen.setAttribute("y", Math.min(start.y, p.y));
    rahmen.setAttribute("width", Math.abs(p.x - start.x)); rahmen.setAttribute("height", Math.abs(p.y - start.y));
  });
  svg.addEventListener("pointerup", async (e) => {
    if (!start) return;
    const p = punkt(e); const a = start; start = null; rahmen.remove();
    const r = [Math.min(a.x, p.x), Math.min(a.y, p.y), Math.max(a.x, p.x), Math.max(a.y, p.y)];
    if (r[2] - r[0] < 3 || r[3] - r[1] < 3) return;
    try { z.v = await post(`/vorgang/${vid()}/bereich`, { datei: d.id, seite: z.seite, rechteck: r }); } catch (err) { melden(err.message); return; }
    z.zeichnen = false; zeichnen(); melden("Eigener Bereich hinzugefügt: wird unkenntlich.", true);
  });
}

async function seiteBestaetigen(d) {
  try { z.v = await post(`/vorgang/${vid()}/datei/${d.id}/seite/${z.seite}/geprueft`); } catch (e) { melden(e.message); return; }
  const dneu = dateiVon(d.id);
  const naechste = dneu.seiten.findIndex((s) => !s.geprueft);
  if (naechste >= 0) z.seite = naechste;
  else {
    const andere = z.v.dateien.find((x) => imExport(x) && x.seiten.some((s) => !s.geprueft));
    if (andere) { z.datei = andere.id; z.seite = andere.seiten.findIndex((s) => !s.geprueft); }
  }
  z.gewaehlt = null; zeichnen();
  melden(z.v.bereit_fuer_gegenprobe ? "Alles angesehen. Die Gegenprobe kann starten." : "Bestätigt.", true);
}

// Video
function nummern(d) {
  const zaehler = {}, out = {};
  for (const s of stellenVon(d.id).sort((a, b) => a.zeit.von - b.zeit.von)) {
    const k = s.kategorie === "kennzeichen" ? "kennzeichen" : hinten(s) ? "hintergrund" : s.kategorie;
    zaehler[k] = (zaehler[k] || 0) + 1; out[s.id] = zaehler[k];
  }
  return out;
}
const hinten = (s) => s.zeit.hintergrund || s.zeit.kurz;
const gruppeVon = (s) => s.kategorie === "kennzeichen" ? "kennzeichen" : hinten(s) ? "hintergrund" : "personen";
const kartenName = (s, nr) => s.kategorie === "kennzeichen" ? `Kennzeichen ${nr}` : hinten(s) ? `Hintergrund ${nr}` : s.kategorie === "gesicht" ? `Gesicht ${nr}` : `Person ${nr}`;

async function zeichneVideo(d, buehne, tafel) {
  const film = el("div", { class: "film" },
    el("video", { id: "film", controls: true, muted: true, playsinline: true, preload: "auto",
      "aria-label": `Video ${d.name} mit markierten Personen und Kennzeichen` }, ...quellen(`/api/vorgang/${vid()}/datei/${d.id}/video`)),
    el("canvas", { id: "leinwand", "aria-hidden": "true" }));
  const geprueft = d.seiten[0].geprueft;
  buehne.append(
    el("div", { class: "buehne-kopf" }, el("h2", {}, `${d.name} · ${zahl(d.video.dauer, 1)} s`),
      el("span", { class: "leise" }, `${d.video.breite} × ${d.video.hoehe} · ${zahl(d.video.fps)} Bilder/s${d.video.schnitte?.length ? ` · ${d.video.schnitte.length + 1} Szenen` : ""}${d.video.ton ? " · Ton wird entfernt" : ""}`)),
    film,
    el("div", { class: "zeitleiste", id: "zeitleiste", "aria-label": "Zeitleiste: wann welche Spur zu sehen ist" }),
    el("div", { class: "buehne-fuss" },
      el("span", { class: "leise" }, "Je Person und je Kennzeichen eine Karte; eine Entscheidung gilt für alle Einzelbilder."),
      el("button", { type: "button", class: `knopf ${geprueft ? "" : "haupt"}`, disabled: geprueft, onclick: () => seiteBestaetigen(d),
        html: geprueft ? `${SYMBOL.haken} angesehen` : `${SYMBOL.haken} Video angesehen – offene Spuren unkenntlich` })));
  if (!z.spuren[d.id]) { try { z.spuren[d.id] = await api(`/vorgang/${vid()}/datei/${d.id}/spuren`); } catch (e) { z.spuren[d.id] = {}; } }
  const video = $("#film");
  const schleife = () => { zeichneFilm(); kopfzeiger(); if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(schleife); };
  video.addEventListener("loadedmetadata", () => { zeichneFilm(); kopfzeiger(); });
  video.addEventListener("seeked", () => { zeichneFilm(); kopfzeiger(); });
  video.addEventListener("timeupdate", () => { if (!video.requestVideoFrameCallback) { zeichneFilm(); kopfzeiger(); } });
  if (video.requestVideoFrameCallback) video.requestVideoFrameCallback(schleife);
  new ResizeObserver(() => zeichneFilm()).observe(video);
  tafelVideo(d); zeichneZeitleiste(d);
}

function quellen(basis) {
  return [el("source", { src: `${basis}${basis.includes("?") ? "&" : "?"}format=webm`, type: "video/webm" }),
    el("source", { src: basis, type: "video/mp4" })];
}

function inhaltRechteck(video) {
  // Spuren sind in Pixeln des Originals; die Vorschau im Browser kann kleiner sein (WebM, 720 Zeilen)
  const d = aktuelleDatei();
  const b = video.clientWidth, h = video.clientHeight, vb = d?.video?.breite || video.videoWidth || 16, vh = d?.video?.hoehe || video.videoHeight || 9;
  const m = Math.min(b / vb, h / vh);
  return { x: (b - vb * m) / 2, y: (h - vh * m) / 2, m };
}

function zeichneFilm() {
  const video = $("#film"), leinwand = $("#leinwand"); if (!video || !leinwand) return;
  const d = aktuelleDatei(); const spuren = z.spuren[d.id] || {};
  const dpr = window.devicePixelRatio || 1;
  leinwand.width = video.clientWidth * dpr; leinwand.height = video.clientHeight * dpr;
  const c = leinwand.getContext("2d"); c.setTransform(dpr, 0, 0, dpr, 0, 0); c.clearRect(0, 0, leinwand.width, leinwand.height);
  const { x, y, m } = inhaltRechteck(video);
  const nr = String(Math.round(video.currentTime * d.video.fps));
  const stil = getComputedStyle(document.documentElement);
  const decke = stil.getPropertyValue("--decke").trim() || "#1b2226";
  const rund = (r, f, strich) => {
    const [x0, y0, x1, y1] = r; const w = (x1 - x0) * m, h = (y1 - y0) * m, rr = Math.min(w, h) * 0.18;
    c.beginPath(); c.roundRect(x + x0 * m, y + y0 * m, w, h, rr);
    if (f) { c.fillStyle = f; c.fill(); }
    if (strich) { c.strokeStyle = strich.farbe; c.lineWidth = strich.breite; c.setLineDash(strich.strich || []); c.stroke(); }
  };
  for (const s of stellenVon(d.id)) {
    const sp = spuren[s.spur]; if (!sp) continue;
    const box = sp.boxen?.[nr]; if (!box) continue;
    const f = stil.getPropertyValue(GRUPPE_FARBE[katInfo(s.kategorie).gruppe]).trim();
    const gew = z.gewaehlt === s.id;
    if (s.entscheidung === "sichtbar") { rund(box, null, { farbe: "rgba(255,255,255,.75)", breite: 1.5, strich: [5, 4] }); continue; }
    if (s.kategorie === "person") {
      const kopf = sp.koepfe?.[nr];
      if (s.entscheidung === "unkenntlich" && s.modus === "person") {
        const u = sp.umrisse?.[nr];
        if (u) { c.beginPath(); u.forEach(([a, b], i) => (i ? c.lineTo(x + a * m, y + b * m) : c.moveTo(x + a * m, y + b * m))); c.closePath(); c.fillStyle = decke; c.fill(); }
        else rund(box, decke);
      } else rund(box, null, { farbe: f, breite: gew ? 3 : 1.6 });
      if (kopf && s.entscheidung === "unkenntlich") rund(kopf, decke, gew ? { farbe: f, breite: 3 } : null);
      else if (kopf) rund(kopf, null, { farbe: f, breite: gew ? 3 : 2 });
    } else if (s.entscheidung === "unkenntlich") rund(box, decke, gew ? { farbe: f, breite: 3 } : null);
    else rund(box, null, { farbe: f, breite: gew ? 3.2 : 2 });
  }
}

function zeichneZeitleiste(d) {
  const ziel = $("#zeitleiste"); if (!ziel) return;
  const dauer = d.video.dauer || 1;
  const reihen = [["personen", "Personen"], ["hintergrund", "Hintergrund"], ["kennzeichen", "Kennzeichen"]];
  ziel.replaceChildren(...reihen.map(([g, name]) => {
    const st = stellenVon(d.id).filter((s) => gruppeVon(s) === g);
    const band = el("div", { class: "band", role: "presentation" });
    band.addEventListener("click", (e) => {
      if (e.target.dataset.id) return;
      const r = band.getBoundingClientRect(); $("#film").currentTime = ((e.clientX - r.left) / r.width) * dauer;
    });
    for (const s of st) {
      const i = el("i", { class: `${s.entscheidung === "unkenntlich" ? "u" : s.entscheidung === "sichtbar" ? "s" : ""}${z.gewaehlt === s.id ? " gewaehlt" : ""}`, "data-id": s.id });
      i.style.left = `${(s.zeit.von / dauer) * 100}%`; i.style.width = `${Math.max(0.6, ((s.zeit.bis - s.zeit.von) / dauer) * 100)}%`;
      i.style.setProperty("--farbe", farbe(s.kategorie));
      i.addEventListener("click", () => karteWaehlen(s));
      band.append(i);
    }
    band.append(el("span", { class: "kopfzeiger" }));
    return el("div", { class: "spur" }, el("span", {}, `${name} (${st.length})`), band);
  }));
  kopfzeiger();
}
function kopfzeiger() {
  const v = $("#film"); const d = aktuelleDatei(); if (!v || !d?.video) return;
  $$(".kopfzeiger").forEach((k) => { k.style.left = `${(v.currentTime / (d.video.dauer || 1)) * 100}%`; });
}
function karteWaehlen(s) {
  z.gewaehlt = z.gewaehlt === s.id ? null : s.id;
  const v = $("#film");
  if (z.gewaehlt && v) { v.pause(); v.currentTime = (s.zeit.bild_gross + 0.5) / aktuelleDatei().video.fps; }
  const g = gruppeVon(s); if (z.gewaehlt && g !== z.filter) z.filter = g;
  const d = aktuelleDatei(); tafelVideo(d); zeichneZeitleiste(d); zeichneFilm();
  $(`.karte[data-id="${z.gewaehlt}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
}

function tafelVideo(d) {
  const tafel = $("#tafel"); if (!tafel) return;
  const alle = stellenVon(d.id); const nr = nummern(d);
  const zaehlen = (g) => alle.filter((s) => gruppeVon(s) === g).length;
  const filter = el("div", { class: "filter", role: "group", "aria-label": "Karten filtern" },
    ...[["personen", "Personen"], ["hintergrund", "Hintergrund"], ["kennzeichen", "Kennzeichen"]].map(([g, n]) =>
      wahlKnopf(`${n} (${zaehlen(g)})`, z.filter === g, () => { z.filter = g; tafelVideo(d); })));
  const sichtbar = alle.filter((s) => gruppeVon(s) === z.filter).sort((a, b) => a.zeit.von - b.zeit.von);
  const offen = alle.filter((s) => s.entscheidung === "offen").length;
  tafel.replaceChildren(
    el("div", { class: "tafel-kopf" }, el("h2", {}, `Spuren (${alle.length})`), el("span", { class: "leise" }, offen ? `${offen} offen` : "alle entschieden")),
    filter,
    el("ul", { class: "karten" }, ...sichtbar.map((s) => karte(d, s, nr[s.id]))),
    metadatenBlock(d));
}

function karte(d, s, nr) {
  const name = kartenName(s, nr);
  const istPerson = s.kategorie === "person";
  const anteil = istPerson && s.zeit.gesicht_anteil ? ` · Gesicht in ${zahl(s.zeit.gesicht_anteil * 100)} %` : "";
  const li = el("li", { class: `karte${s.entscheidung === "unkenntlich" ? " u" : ""}${z.gewaehlt === s.id ? " gewaehlt" : ""}`, "data-id": s.id },
    el("button", { type: "button", class: "bild", "aria-label": `${uhr(s.zeit.von)}–${uhr(s.zeit.bis)}: ${name} im Video zeigen`, onclick: () => karteWaehlen(s) },
      el("img", { src: `/api/vorgang/${vid()}/datei/${d.id}/spur/${s.spur}.jpg`, alt: "", loading: "lazy" }),
      el("span", { class: "marker" }, `${uhr(s.zeit.von)}–${uhr(s.zeit.bis)}`)),
    el("div", { class: "text" }, el("b", {}, name), el("small", {}, `${zahl(s.zeit.bis - s.zeit.von, 1)} s im Bild${anteil}`)),
    istPerson
      ? el("div", { class: "wahl", role: "group", "aria-label": `Entscheidung für ${name}` },
        wahlKnopf("Gesicht", s.entscheidung === "unkenntlich" && s.modus !== "person", () => entscheiden([{ id: s.id, entscheidung: "unkenntlich", modus: "gesicht" }]), "u"),
        wahlKnopf("Ganze Person", s.entscheidung === "unkenntlich" && s.modus === "person", () => entscheiden([{ id: s.id, entscheidung: "unkenntlich", modus: "person" }]), "u"),
        wahlKnopf("Sichtbar", s.entscheidung === "sichtbar", () => entscheiden([{ id: s.id, entscheidung: "sichtbar" }])))
      : el("div", { class: "wahl", role: "group", "aria-label": `Entscheidung für ${name}` },
        wahlKnopf("Unkenntlich", s.entscheidung === "unkenntlich", () => entscheiden([{ id: s.id, entscheidung: "unkenntlich" }]), "u"),
        wahlKnopf("Sichtbar", s.entscheidung === "sichtbar", () => entscheiden([{ id: s.id, entscheidung: "sichtbar" }]))),
    s.entscheidung === "sichtbar" ? el("div", { class: "grundwahl" }, begruendungWahl(s)) : null);
  li.style.setProperty("--farbe", farbe(s.kategorie));
  return li;
}

// --- 3 Gegenprobe ------------------------------------------------------------------------------------------------
async function gegenprobeStarten() {
  try { z.v = await post(`/vorgang/${vid()}/gegenprobe`); } catch (e) { melden(e.message); return; }
  z.ansicht = "gegenprobe"; zeichnen(); abfragenWennNoetig();
}

function zeichneGegenprobe(main) {
  const g = z.v.gegenprobe;
  const karte = el("section", { class: "probe" });
  main.append(el("div", { class: "mitte" }, karte));
  if (!g) {
    karte.append(el("h1", {}, "Gegenprobe"), el("p", { class: "unterzeile" }, "Erst alle Dateien ansehen, dann startet hier die Gegenprobe."));
    return;
  }
  const vorschau = (d) => d.art === "video" ? `/api/vorgang/${vid()}/datei/${d.id}/seite/${Math.floor((d.video?.dauer || 2) / 2)}`
    : `/api/vorgang/${vid()}/datei/${d.id}/seite/0`;
  if (g.status === "laeuft" || g.status === "fehler") {
    karte.append(
      el("h1", {}, g.status === "fehler" ? "Gegenprobe abgebrochen" : "Gegenprobe läuft"),
      el("p", { class: "unterzeile" }, "Die Dateien werden unkenntlich gemacht. Dann suchen alle Erkenner erneut, auf dem Ergebnis: Text, Gesichter, Kennzeichen, Unterschriften und Metadaten."),
      el("div", { class: "scan", "aria-hidden": "true" }, ...z.v.dateien.map((d) => el("figure", {}, el("img", { src: vorschau(d), alt: "" })))),
      el("div", { class: "balken", role: "progressbar", "aria-label": "Fortschritt der Gegenprobe", "aria-valuemin": "0", "aria-valuemax": "100",
        "aria-valuenow": String(Math.round((g.fortschritt || 0) * 100)) }, breite(el("i"), g.fortschritt || 0)),
      el("p", { class: "leise", role: "status" }, g.meldung || ""));
    return;
  }
  const ok = g.reste === 0;
  const urteil = el("div", { class: `urteil${ok ? "" : " schlecht"}` });
  urteil.innerHTML = ok
    ? `<svg viewBox="0 0 66 66" aria-hidden="true"><circle class="urteil-zeichen-kreis" cx="33" cy="33" r="31" fill="var(--gut)"/><path class="urteil-zeichen-haken" d="M19 34l9 9 19-20" fill="none" stroke="var(--gut-hell)" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/></svg>`
    : `<svg viewBox="0 0 66 66" aria-hidden="true"><circle cx="33" cy="33" r="31" fill="var(--schlecht)"/><path d="M33 17v21M33 47v1" stroke="var(--schlecht-hell)" stroke-width="6" stroke-linecap="round"/></svg>`;
  urteil.append(el("div", {}, el("strong", {}, ok ? "Gegenprobe: 0 Reste" : `Gegenprobe: ${g.reste} Rest${g.reste === 1 ? "" : "e"}`),
    el("span", {}, ok ? `Nichts mehr gefunden, was unkenntlich sein sollte. Export freigegeben (${zahl(g.dauer, 1)} s).` : "Der Export bleibt gesperrt, bis jeder Rest geprüft ist.")));
  karte.append(el("h1", {}, "Gegenprobe"), urteil);
  const liste = el("ul", { class: "pruefliste" });
  for (const d of z.v.dateien) {
    if (!imExport(d)) {
      liste.append(el("li", {}, el("span", { class: "ok aus", html: SYMBOL.schloss }), el("div", {}, el("b", {}, d.name),
        el("div", { class: "leise" }, "vom Export ausgenommen: wird nicht herausgegeben; der Prüfbericht nennt die Reste"))));
      continue;
    }
    const e = g.ergebnisse[d.id]; if (!e) continue;
    liste.append(el("li", {}, el("span", { class: "ok", html: SYMBOL.haken }), el("div", {}, el("b", {}, d.name), el("div", { class: "leise" }, e.pruefungen.join(" · ")))));
  }
  karte.append(el("h2", { class: "unsichtbar" }, "Was geprüft wurde"), liste);
  if (!ok) {
    const reste = [];
    for (const d of z.v.dateien.filter(imExport)) for (const r of g.ergebnisse[d.id]?.reste || [])
      reste.push(el("li", {}, el("b", {}, `${d.name}: `), `${r.hinweis} (${r.pruefung}${r.seite != null && d.art === "dokument" ? `, Seite ${r.seite + 1}` : ""}${r.zeit != null ? `, bei ${zahl(r.zeit, 1)} s` : ""})`));
    const ohneOrt = z.v.dateien.some((d) => imExport(d) && d.art === "dokument" && (g.ergebnisse[d.id]?.reste || []).some((r) => !r.rechteck));
    // Reste trotz Übernahme: ab der zweiten Übernahme deckt Unkenntlich in Fotos und Videos großzügiger ab; bleibt dann
    // noch etwas, ist der letzte Ausweg, die Datei nicht herauszugeben (nie, den Rest zu übergehen).
    const hartnaeckig = z.v.dateien.filter((d) => imExport(d) && (d.runden || 0) >= 1 && (g.ergebnisse[d.id]?.reste || []).length);
    karte.append(el("h2", {}, "Gefundene Reste"), el("ul", { class: "reste" }, ...reste.slice(0, 40)),
      ...(ohneOrt ? [el("p", { class: "leise" }, "Reste ohne Ort (etwa Metadaten oder Anmerkungen) lassen sich nicht als Bereich markieren. Beim Übernehmen wird das betroffene Dokument deshalb im nächsten Durchlauf aus Seitenbildern neu aufgebaut, ohne Textschicht.")] : []),
      el("button", { type: "button", class: "knopf haupt", onclick: resteUebernehmen, html: `Reste als Vorschläge übernehmen ${SYMBOL.pfeil}` }),
      ...(hartnaeckig.length ? [el("div", { class: "ausweg" },
        el("h2", {}, "Reste trotz Übernahme"),
        el("p", {}, "Ab der zweiten Übernahme deckt Unkenntlich Reste in Fotos und Videos großzügiger ab: doppelt so groß, im Foto mit angrenzenden Flächen zusammengelegt, im Video länger nachgeführt. Sie können eine Datei mit Resten auch jetzt vom Export ausnehmen: Sie wird nicht herausgegeben; der Prüfbericht nennt sie mit ihren Resten."),
        el("div", { class: "knoepfe" }, ...hartnaeckig.map((d) => el("button", { type: "button", class: "knopf", onclick: () => ausnehmen(d) }, `${d.name} vom Export ausnehmen`))))] : []));
  } else {
    karte.append(el("div", { class: "weiter" }, el("button", { type: "button", class: "knopf haupt", onclick: () => wechseln("fertig"), html: `Zum Ergebnis ${SYMBOL.pfeil}` })));
  }
}
function gegenprobeAktualisieren() {
  const g = z.v.gegenprobe, balken = $(".probe .balken"), text = $(".probe [role=status]");
  if (g?.status === "laeuft" && balken && text) {
    balken.setAttribute("aria-valuenow", String(Math.round((g.fortschritt || 0) * 100)));
    breite(balken.firstElementChild, g.fortschritt || 0);
    text.textContent = g.meldung || "";
  } else zeichnen();
}

async function ausnehmen(d) {
  if (!confirm(`${d.name} vom Export ausnehmen? Die Datei wird nicht herausgegeben; der Prüfbericht nennt sie mit ihren Resten.`)) return;
  try { z.v = await post(`/vorgang/${vid()}/datei/${d.id}/ausnehmen`); } catch (e) { melden(e.message); return; }
  zeichnen(); melden(`${d.name} wird nicht herausgegeben; der Prüfbericht nennt sie.`);
}

async function resteUebernehmen() {
  try { z.v = await post(`/vorgang/${vid()}/reste`); } catch (e) { melden(e.message); return; }
  z.spuren = {}; z.datei = null; wechseln("pruefen");
  const neu = z.v.dateien.filter((d) => d.neu_aufbauen).map((d) => d.name);
  if (neu.length) melden(`Wird beim nächsten Durchlauf aus Seitenbildern neu aufgebaut: ${neu.join(", ")}.`);
}

// --- 4 Fertig ----------------------------------------------------------------------------------------------------
function zeichneFertig(main) {
  const v = z.v, g = v.gegenprobe;
  const unk = v.stellen.filter((s) => s.entscheidung === "unkenntlich").length;
  const sicht = v.stellen.filter((s) => s.entscheidung === "sichtbar").length;
  const meta = v.dateien.reduce((n, d) => n + (d.metadaten?.length || 0), 0);
  const ohne = v.dateien.filter((d) => !imExport(d)).map((d) => d.name);
  main.append(
    el("div", { class: "fertig-kopf" },
      el("div", {}, el("h1", {}, "Fertig."), el("p", {}, "Ziehen Sie den Schieber, um Original und Ergebnis zu vergleichen."),
        ohne.length ? el("p", {}, `Nicht herausgegeben: ${ohne.join(", ")} (Reste auch nach Übernahmen; im Prüfbericht vermerkt).`) : null),
      el("div", { class: "knoepfe" },
        el("a", { class: "knopf haupt", href: `/api/vorgang/${vid()}/export.zip`, download: "", html: `${SYMBOL.laden} Alles herunterladen (ZIP)` }),
        el("a", { class: "knopf", href: `/api/vorgang/${vid()}/bericht.pdf`, download: "", html: `${SYMBOL.dokument} Prüfbericht (PDF)` }),
        el("a", { class: "knopf", href: `/api/vorgang/${vid()}/bericht.html`, target: "_blank", rel: "noopener" }, "Bericht ansehen"))),
    el("div", { class: "zahlenreihe" },
      el("div", {}, el("b", {}, zahl(unk)), el("span", {}, "Stellen unkenntlich")),
      el("div", {}, el("b", {}, zahl(sicht)), el("span", {}, "bewusst sichtbar gelassen")),
      el("div", {}, el("b", {}, zahl(meta)), el("span", {}, "Metadaten-Felder entfernt")),
      el("div", {}, el("b", {}, zahl(g?.reste ?? 0)), el("span", {}, "Reste laut Gegenprobe"))),
    el("div", { class: "vergleiche" }, ...v.dateien.map((d) => vergleichKarte(d))));
}

function vergleichKarte(d) {
  if (!imExport(d)) {
    return el("section", { class: "vergleich-karte", "aria-label": `${d.name}: nicht herausgegeben` },
      el("div", { class: "oben" }, el("h2", {}, d.name), el("span", { class: "leise" }, "nicht herausgegeben")),
      el("p", { class: "leise" }, `Die Gegenprobe fand auch nach ${mal(d.ausgenommen.runden, "Übernahme", "Übernahmen")} noch ${mal(d.ausgenommen.reste.length, "Rest", "Reste")}. Die Datei ist nicht im Export; der Prüfbericht nennt sie.`));
  }
  const wurzel = el("section", { class: "vergleich-karte", "aria-label": `Vergleich ${d.name}` });
  const seiteWahl = { n: 0 };
  const bauen = () => {
    const vorher = d.art === "video"
      ? el("video", { muted: true, playsinline: true, preload: "auto", "aria-hidden": "true" }, ...quellen(`/api/vorgang/${vid()}/datei/${d.id}/video`))
      : el("img", { src: `/api/vorgang/${vid()}/datei/${d.id}/seite/${seiteWahl.n}`, alt: `Original ${d.name}` });
    const nachher = d.art === "video"
      ? el("video", { muted: true, playsinline: true, preload: "auto", "aria-label": `Ergebnis ${d.name}` }, ...quellen(`/api/vorgang/${vid()}/datei/${d.id}/video?ergebnis=true`))
      : el("img", { src: `/api/vorgang/${vid()}/datei/${d.id}/seite/${seiteWahl.n}?ergebnis=true`, alt: `Ergebnis ${d.name}, unkenntlich gemacht` });
    const griff = el("button", { type: "button", role: "slider", "aria-label": `Vorher und nachher: ${d.name}`, "aria-valuemin": "0",
      "aria-valuemax": "100", "aria-valuenow": "50", "aria-valuetext": "Hälfte Original, Hälfte Ergebnis", html: SYMBOL.griff });
    const feld = el("div", { class: "vergleich" }, nachher, el("div", { class: "vorher" }, vorher),
      el("div", { class: "griff" }, griff), el("span", { class: "etikett links" }, "Vorher"), el("span", { class: "etikett rechts" }, "Nachher"));
    schieber(feld, griff);
    const teile = [el("div", { class: "oben" }, el("h2", {}, d.name), el("div", { class: "blatt" },
      d.art === "dokument" && d.seiten.length > 1 ? d.seiten.map((_, i) => wahlKnopf(`Seite ${i + 1}`, i === seiteWahl.n, () => { seiteWahl.n = i; bauen(); }, "knopf klein")) : null,
      d.art === "video" ? videoKnopf(vorher, nachher) : null,
      el("a", { class: "knopf klein", href: `/api/vorgang/${vid()}/ergebnis/${d.id}`, download: "", html: `${SYMBOL.laden} Ergebnis` }))), feld];
    wurzel.replaceChildren(...teile);
  };
  bauen();
  return wurzel;
}

function videoKnopf(a, b) {
  const k = el("button", { type: "button", class: "knopf klein", html: `${SYMBOL.abspielen} Abspielen` });
  const sync = () => { if (Math.abs(a.currentTime - b.currentTime) > 0.08) a.currentTime = b.currentTime; };
  b.addEventListener("timeupdate", sync);
  k.addEventListener("click", () => {
    if (b.paused) { a.currentTime = b.currentTime; b.play(); a.play(); k.innerHTML = `${SYMBOL.pause} Anhalten`; }
    else { b.pause(); a.pause(); k.innerHTML = `${SYMBOL.abspielen} Abspielen`; }
  });
  b.addEventListener("ended", () => { a.pause(); k.innerHTML = `${SYMBOL.abspielen} Abspielen`; });
  return k;
}

function schieber(feld, griff) {
  const setzen = (p) => {
    p = Math.max(0, Math.min(100, p));
    feld.style.setProperty("--teil", `${p}%`);
    griff.setAttribute("aria-valuenow", String(Math.round(p)));
    griff.setAttribute("aria-valuetext", `${Math.round(p)} Prozent Original sichtbar`);
  };
  let ziehen = false;
  const bewegen = (e) => { const r = feld.getBoundingClientRect(); setzen(((e.clientX - r.left) / r.width) * 100); };
  feld.addEventListener("pointerdown", (e) => { ziehen = true; feld.setPointerCapture(e.pointerId); bewegen(e); });
  feld.addEventListener("pointermove", (e) => { if (ziehen) bewegen(e); });
  feld.addEventListener("pointerup", () => { ziehen = false; });
  griff.addEventListener("keydown", (e) => {
    const jetzt = Number(griff.getAttribute("aria-valuenow"));
    const schritt = { ArrowLeft: -5, ArrowDown: -5, ArrowRight: 5, ArrowUp: 5, PageDown: -20, PageUp: 20 }[e.key];
    if (schritt !== undefined) { e.preventDefault(); setzen(jetzt + schritt); }
    if (e.key === "Home") { e.preventDefault(); setzen(0); }
    if (e.key === "End") { e.preventDefault(); setzen(100); }
  });
  setzen(50);
}

start().catch((e) => { console.error(e); melden(`Start fehlgeschlagen: ${e.message}`); });
