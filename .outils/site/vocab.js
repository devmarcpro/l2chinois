// Page « Vocabulaire » : liste filtrable et cartes de révision.
// Les mots viennent des tableaux 汉字 / 拼音 des notes (window.VOCABULAIRE, écrit par build.py).
(function () {
  "use strict";
  var zone = document.getElementById("vocab");
  if (!zone) return;
  var racine = document.body.dataset.racine || ".";
  var tous = window.VOCABULAIRE || [];
  var CLE = "l2-vocab-sus";
  var sus = {};
  try { sus = JSON.parse(localStorage.getItem(CLE) || "{}"); } catch (err) { sus = {}; }
  function sauver() { try { localStorage.setItem(CLE, JSON.stringify(sus)); } catch (err) { /* stockage indisponible */ } }

  function el(id) { return document.getElementById(id); }
  function echapper(t) {
    return String(t || "").replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; });
  }
  function cle(m) { return m.h + "|" + m.p; }

  var selCours = el("v-cours"), selNote = el("v-note"), selEtat = el("v-etat"), selSens = el("v-sens");
  var corps = el("v-corps"), compte = el("v-compte"), carte = el("v-carte"), progres = el("v-progres");

  // ---- filtres
  function options(select, valeurs, libelleTous) {
    select.innerHTML = '<option value="">' + libelleTous + "</option>" +
      valeurs.map(function (v) { return '<option value="' + echapper(v) + '">' + echapper(v) + "</option>"; }).join("");
  }
  function uniques(liste, champ) {
    var vus = {}, res = [];
    liste.forEach(function (m) { if (m[champ] && !vus[m[champ]]) { vus[m[champ]] = 1; res.push(m[champ]); } });
    return res;
  }
  options(selCours, uniques(tous, "c"), "tous les cours");
  function majNotes() {
    var liste = tous.filter(function (m) { return !selCours.value || m.c === selCours.value; });
    options(selNote, uniques(liste, "n"), "toutes les notes");
  }
  majNotes();

  function selection() {
    var vus = {};
    return tous.filter(function (m) {
      if (selCours.value && m.c !== selCours.value) return false;
      if (selNote.value && m.n !== selNote.value) return false;
      if (selEtat.value === "a-revoir" && sus[cle(m)]) return false;
      if (vus[cle(m)]) return false; // un même mot noté dans plusieurs cours n'apparaît qu'une fois
      vus[cle(m)] = 1;
      return true;
    });
  }

  // ---- liste
  function afficherListe(mots) {
    corps.innerHTML = mots.map(function (m) {
      return '<tr class="' + (sus[cle(m)] ? "su" : "") + '"><td class="h zh">' + echapper(m.h) + '</td><td class="p">' + echapper(m.p) +
        '</td><td class="f">' + echapper(m.f) + (m.x ? '<span class="ex">' + echapper(m.x) + "</span>" : "") +
        '</td><td class="s"><a href="' + racine + "/" + m.u + '" title="' + echapper(m.n) + '">↗</a></td></tr>';
    }).join("");
  }
  corps.addEventListener("click", function (ev) {
    var td = ev.target.closest("td.p, td.f");
    if (td) td.classList.toggle("vu");
  });
  el("v-cache-pinyin").addEventListener("change", function () { zone.classList.toggle("cache-pinyin", this.checked); });
  el("v-cache-fr").addEventListener("change", function () { zone.classList.toggle("cache-fr", this.checked); });

  // ---- cartes
  var pile = [], total = 0, retournee = false;
  function melanger(t) {
    for (var i = t.length - 1; i > 0; i--) { var j = Math.floor(Math.random() * (i + 1)); var x = t[i]; t[i] = t[j]; t[j] = x; }
    return t;
  }
  function afficherCarte() {
    retournee = false;
    if (!pile.length) {
      carte.innerHTML = total ? '<p class="fin">Terminé : ' + total + " cartes vues.</p>" : '<p class="fin">Aucune carte avec ces filtres.</p>';
      progres.textContent = "";
      el("v-actions").hidden = true;
      el("v-recommencer").hidden = !total;
      return;
    }
    var m = pile[0], versFr = selSens.value === "zh";
    carte.innerHTML = '<div class="recto">' + (versFr ? '<span class="grand zh">' + echapper(m.h) + "</span>" : '<span class="moyen">' + echapper(m.f) + "</span>") + "</div>" +
      '<div class="verso" hidden>' + (versFr ? "" : '<span class="grand zh">' + echapper(m.h) + "</span>") +
      '<span class="pinyin">' + echapper(m.p) + "</span>" + (versFr ? '<span class="moyen">' + echapper(m.f) + "</span>" : "") +
      (m.x ? '<span class="ex">' + echapper(m.x) + "</span>" : "") +
      '<a class="source" href="' + racine + "/" + m.u + '">' + echapper(m.n) + "</a></div>" +
      '<p class="aide">Touche la carte pour voir la réponse</p>';
    el("v-actions").hidden = true;
    el("v-recommencer").hidden = true;
    progres.textContent = "Reste " + pile.length + " sur " + total;
  }
  function retourner() {
    if (!pile.length || retournee) return;
    retournee = true;
    carte.querySelector(".verso").hidden = false;
    carte.querySelector(".aide").hidden = true;
    el("v-actions").hidden = false;
  }
  carte.addEventListener("click", function (ev) { if (!ev.target.closest("a")) retourner(); });
  carte.addEventListener("keydown", function (ev) { if (ev.key === " " || ev.key === "Enter") { ev.preventDefault(); retourner(); } });
  el("v-su").addEventListener("click", function () {
    var m = pile.shift(); sus[cle(m)] = 1; sauver(); afficherCarte();
  });
  el("v-revoir").addEventListener("click", function () {
    var m = pile.shift(); delete sus[cle(m)]; sauver();
    pile.splice(Math.min(pile.length, 4), 0, m); // la carte revient quelques cartes plus loin
    afficherCarte();
  });
  function nouvellePile() { pile = melanger(selection().slice()); total = pile.length; afficherCarte(); }
  el("v-recommencer").addEventListener("click", nouvellePile);
  el("v-oublier").addEventListener("click", function () {
    if (window.confirm("Remettre tous les mots à « pas encore su » ?")) { sus = {}; sauver(); rafraichir(); }
  });

  // ---- modes
  var modeCartes = false;
  function rafraichir() {
    var mots = selection();
    var nbSus = mots.filter(function (m) { return sus[cle(m)]; }).length;
    compte.textContent = mots.length + " mots" + (selEtat.value === "a-revoir" ? " à revoir" : " · " + nbSus + " marqués « su »");
    if (modeCartes) nouvellePile(); else afficherListe(mots);
  }
  function mode(cartes) {
    modeCartes = cartes;
    el("v-liste").hidden = cartes;
    el("v-cartes").hidden = !cartes;
    el("v-mode-liste").classList.toggle("actif", !cartes);
    el("v-mode-cartes").classList.toggle("actif", cartes);
    rafraichir();
  }
  el("v-mode-liste").addEventListener("click", function () { mode(false); });
  el("v-mode-cartes").addEventListener("click", function () { mode(true); });
  selCours.addEventListener("change", function () { majNotes(); rafraichir(); });
  selNote.addEventListener("change", rafraichir);
  selEtat.addEventListener("change", rafraichir);
  selSens.addEventListener("change", function () { if (modeCartes) afficherCarte(); });
  mode(location.hash === "#cartes"); // vocabulaire.html#cartes ouvre directement les cartes
})();
