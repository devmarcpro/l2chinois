(function () {
  "use strict";
  var racine = document.body.dataset.racine || ".";
  var bouton = document.getElementById("bouton-menu");
  var champ = document.getElementById("recherche");
  var panneau = document.getElementById("resultats");

  // ---- menu des cours
  function fermerMenu() {
    document.body.classList.remove("menu-ouvert");
    bouton.setAttribute("aria-expanded", "false");
  }
  bouton.addEventListener("click", function (ev) {
    ev.stopPropagation();
    var ouvert = document.body.classList.toggle("menu-ouvert");
    bouton.setAttribute("aria-expanded", String(ouvert));
  });
  document.addEventListener("click", function (ev) {
    if (!ev.target.closest("#menu")) fermerMenu();
    if (!ev.target.closest("#resultats") && ev.target !== champ) panneau.hidden = true;
  });
  document.addEventListener("keydown", function (ev) {
    if (ev.key === "Escape") { fermerMenu(); panneau.hidden = true; champ.blur(); }
  });

  // ---- recherche : sans accents ni tons, donc « zhanguo » trouve « Zhànguó »
  var index = null, chargement = false;

  function simplifier(car) {
    return car.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  }
  function preparer(entree) {
    var brut = entree.t + " · " + entree.x, norme = "", positions = [];
    for (var i = 0; i < brut.length; i++) {
      var s = simplifier(brut[i]);
      for (var j = 0; j < s.length; j++) { norme += s[j]; positions.push(i); }
    }
    entree.brut = brut; entree.norme = norme; entree.positions = positions;
  }
  function charger(suite) {
    if (index) return suite();
    if (chargement) return;
    chargement = true;
    var s = document.createElement("script");
    s.src = racine + "/assets/index-recherche.js";
    s.onload = function () { index = window.INDEX_RECHERCHE || []; index.forEach(preparer); suite(); };
    document.head.appendChild(s);
  }
  function echapper(t) {
    return t.replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function extrait(entree, pos, longueur) {
    var debut = entree.positions[pos], fin = entree.positions[Math.min(pos + longueur, entree.positions.length) - 1] + 1;
    var a = Math.max(0, debut - 40), b = Math.min(entree.brut.length, fin + 70);
    return (a > 0 ? "…" : "") + echapper(entree.brut.slice(a, debut)) + "<mark>" + echapper(entree.brut.slice(debut, fin)) + "</mark>" + echapper(entree.brut.slice(fin, b)) + (b < entree.brut.length ? "…" : "");
  }
  function chercher() {
    var mots = simplifier(champ.value.trim()).split(/\s+/).filter(Boolean);
    if (!mots.length) { panneau.hidden = true; return; }
    var trouves = [];
    index.forEach(function (entree) {
      var premier = -1, dansTitre = true, titre = simplifier(entree.t);
      for (var k = 0; k < mots.length; k++) {
        var p = entree.norme.indexOf(mots[k]);
        if (p < 0) return;
        if (k === 0) premier = p;
        if (titre.indexOf(mots[k]) < 0) dansTitre = false;
      }
      trouves.push({ entree: entree, pos: premier, score: dansTitre ? 0 : 1 });
    });
    trouves.sort(function (a, b) { return a.score - b.score; });
    panneau.innerHTML = trouves.length ? trouves.slice(0, 40).map(function (r) {
      return '<a href="' + racine + "/" + r.entree.u + '"><span class="titre">' + echapper(r.entree.t) + "</span>" +
        (r.entree.c ? '<span class="cours">' + echapper(r.entree.c) + "</span>" : "") +
        '<span class="extrait">' + extrait(r.entree, r.pos, mots[0].length) + "</span></a>";
    }).join("") : '<p class="vide">Aucun résultat.</p>';
    panneau.hidden = false;
  }
  champ.addEventListener("focus", function () { charger(function () { if (champ.value) chercher(); }); });
  champ.addEventListener("input", function () { charger(chercher); });

  // ---- lecture hors connexion
  if ("serviceWorker" in navigator && location.protocol === "https:") {
    navigator.serviceWorker.register(racine + "/sw.js").catch(function () {});
  }
})();
