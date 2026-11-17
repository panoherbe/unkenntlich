// Hell oder dunkel vor dem ersten Zeichnen setzen: gespeicherte Wahl, sonst die Einstellung des Systems.
(function () {
  var wahl = null;
  try { wahl = localStorage.getItem("unkenntlich-schema"); } catch (e) { /* privat oder gesperrt */ }
  if (wahl !== "hell" && wahl !== "dunkel") {
    wahl = window.matchMedia && matchMedia("(prefers-color-scheme: dark)").matches ? "dunkel" : "hell";
  }
  document.documentElement.setAttribute("data-schema", wahl);
})();
