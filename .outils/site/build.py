# -*- coding: utf-8 -*-
"""Génère un site statique (pensé pour le téléphone) à partir du coffre Obsidian.

    python .outils/site/build.py                  -> écrit le site dans .site/
    python .outils/site/build.py --sortie _site   -> autre dossier (utilisé par GitHub Actions)

Ne modifie jamais les notes. Dépendances : voir requirements.txt.
"""
import argparse
import hashlib
import html
import json
import os
import re
import shutil
import unicodedata
from datetime import date
from pathlib import Path

import yaml
from markdown_it import MarkdownIt
from mdit_py_plugins.anchors import anchors_plugin
from mdit_py_plugins.tasklists import tasklists_plugin

ICI = Path(__file__).resolve().parent
VAULT = ICI.parents[1]

TITRE_SITE = "Chinois L2"
ACCUEIL = "Accueil"
# Dossiers du coffre qui ne sont pas publiés
EXCLUS = {"Modèles", "_Archive (ancienne organisation)", "Pièces jointes"}
# Le site est public : on retire les adresses e-mail (enseignants) des pages
MASQUER_EMAILS = True
MARQUEUR = ".genere-par-build"
URL_VOCABULAIRE = "vocabulaire.html"
COULEUR_THEME = "#b3261e"

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
TYPES = {"seance": "Séance", "support": "Support", "lecture": "Fiche de lecture", "cours": "Cours"}
IMAGES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}

RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
RE_EMAIL_PARENTHESES = re.compile(r"\s*\(\s*" + RE_EMAIL.pattern + r"\s*\)")
RE_TD_CHINOIS = re.compile(r"<td>([⺀-鿿豈-﫿＀-￯\s·/…]{1,16})</td>")
RE_LIEN = re.compile(r"(!?)\[\[([^\]|#\\]+)(#[^\]|\\]*)?(?:\\?\|([^\]]+))?\]\]")
RE_BASE_EMBED = re.compile(r"^!\[\[[^\]]*\.base(?:#([^\]]+))?\]\]\s*$")
RE_CALLOUT = re.compile(r"^>\s*\[!(\w+)\]([+-]?)\s*(.*)$")
RE_SURLIGNE = re.compile(r"==(?=\S)(.+?)(?<=\S)==")
RE_FENCE = re.compile(r"^\s*(```|~~~)")

md = (
    MarkdownIt("commonmark", {"breaks": True, "html": True})
    .enable(["table", "strikethrough"])
    .use(tasklists_plugin)
    .use(anchors_plugin, min_level=2, max_level=3)
)


# ------------------------------------------------------------------ utilitaires
def slug(texte: str) -> str:
    n = unicodedata.normalize("NFKD", texte)
    n = "".join(c for c in n if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", n).strip("-").lower()
    if not s or any(ord(c) >= 0x2E80 for c in texte):  # caractères chinois perdus : on garde l'unicité
        s = (s + "-" if s else "") + hashlib.sha1(texte.encode("utf-8")).hexdigest()[:6]
    return s


def rel(cible: str, page: str) -> str:
    """Chemin relatif de la page `page` vers `cible` (tous deux relatifs à la racine du site)."""
    return os.path.relpath(cible, os.path.dirname(page) or ".").replace(os.sep, "/")


def e(texte) -> str:
    return html.escape(str(texte), quote=True)


def date_fr(d) -> str:
    return f"{JOURS[d.weekday()]} {d:%d/%m/%Y}" if isinstance(d, date) else str(d or "")


def texte_brut(fragment_html: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment_html))).strip()


class Note:
    def __init__(self, chemin: Path):
        self.chemin = chemin
        self.rel = chemin.relative_to(VAULT)
        self.stem = chemin.stem
        brut = chemin.read_text(encoding="utf-8")
        self.fm, self.corps = {}, brut
        if brut.startswith("---\n") and "\n---\n" in brut[4:]:
            entete, self.corps = brut[4:].split("\n---\n", 1)
            self.fm = yaml.safe_load(entete) or {}
        if MASQUER_EMAILS:
            self.corps = RE_EMAIL_PARENTHESES.sub("", self.corps)
            self.corps = RE_EMAIL.sub("(adresse sur IRIS)", self.corps)
        self.type = self.fm.get("type") or "note"
        self.dossier = self.rel.parent
        self.url = ""
        self.html = ""
        self.sommaire = []
        self.scripts = []

    @property
    def titre(self) -> str:
        return TITRE_SITE if self.stem == ACCUEIL and self.dossier == Path(".") else self.stem

    @property
    def date(self):
        d = self.fm.get("date")
        return d if isinstance(d, date) else None


class PageSpeciale:
    """Page du site qui ne vient pas d'une note (ex. la page de vocabulaire)."""

    def __init__(self, url, titre, contenu, scripts=()):
        self.url, self.titre, self.stem, self.html = url, titre, titre, contenu
        self.type, self.dossier, self.fm, self.sommaire, self.date = "page", Path("__aucun__"), {}, [], None
        self.scripts = list(scripts)


# ------------------------------------------------------------------ chargement
def charger():
    notes = []
    for chemin in sorted(VAULT.rglob("*.md")):
        parties = chemin.relative_to(VAULT).parts
        if any(p.startswith(".") or p.startswith("_site") for p in parties) or parties[0] in EXCLUS:
            continue
        notes.append(Note(chemin))
    pris = set()
    for n in notes:
        if n.stem == ACCUEIL and n.dossier == Path("."):
            n.url = "index.html"
        else:
            base = "/".join([slug(p) for p in n.dossier.parts] + [slug(n.stem)])
            url, i = base + ".html", 2
            while url in pris:
                url, i = f"{base}-{i}.html", i + 1
            n.url = url
        pris.add(n.url)
    return notes


# ------------------------------------------------------------------ tableaux (équivalent des Bases d'Obsidian)
def lien(n: Note, page: Note, texte=None) -> str:
    return f'<a href="{e(rel(n.url, page.url))}">{e(texte or n.titre)}</a>'


def badge_fait(n: Note) -> str:
    return '<span class="badge ok">fait</span>' if n.fm.get("fait") is True else '<span class="badge">à compléter</span>'


def tableau_seances(seances, page: Note, avec_cours=False) -> str:
    """Liste de séances, en cartes plutôt qu'en tableau pour rester lisible sur téléphone."""
    if not seances:
        return '<p class="vide">Aucune note de séance pour l\'instant.</p>'
    items = []
    for s in sorted(seances, key=lambda s: (s.date or date.min, s.stem)):
        quand = f"{JOURS[s.date.weekday()]} {s.date:%d/%m}" if s.date else s.stem
        if s.fm.get("seance"):
            quand += f" · séance {s.fm['seance']}"
        cours = f'<span class="cours">{e(s.cours.titre)}</span>' if avec_cours and s.cours else ""
        theme = f'<span class="theme-court">{e(s.fm["theme"])}</span>' if s.fm.get("theme") else ""
        items.append(f'<li><a href="{e(rel(s.url, page.url))}"><span class="quand">{e(quand)} {badge_fait(s)}</span>{cours}{theme}</a></li>')
    return '<ul class="seances">' + "".join(items) + "</ul>"


def vue_base(nom_vue, page: Note, ctx) -> str:
    seances = ctx["seances"]
    if page.type == "cours":
        return tableau_seances([s for s in seances if s.dossier == page.dossier], page)
    if nom_vue and "compl" in nom_vue.lower():
        a_faire = [s for s in seances if s.fm.get("fait") is not True]
        if not a_faire:
            return '<p class="vide">Tout est à jour.</p>'
        return tableau_seances(a_faire, page, avec_cours=True)
    blocs = []
    for c in ctx["cours"]:
        du_cours = [s for s in seances if s.dossier == c.dossier]
        if du_cours:
            blocs.append(f"<h3>{lien(c, page)}</h3>" + tableau_seances(du_cours, page))
    return "".join(blocs) or '<p class="vide">Aucune note de séance pour l\'instant.</p>'


# ------------------------------------------------------------------ Markdown Obsidian -> Markdown standard
def remplacer_liens(ligne: str, page: Note, ctx) -> str:
    def sub(m):
        embed, cible, _ancre, alias = m.group(1), m.group(2).strip(), m.group(3), m.group(4)
        nom = cible.split("/")[-1]
        texte = (alias or nom).strip()
        ext = Path(nom).suffix.lower()
        if ext and ext != ".md":
            fichier = ctx["fichiers"].get(nom)
            if not fichier:
                return f'<span class="lien-mort">{e(texte)}</span>'
            url = "assets/pj/" + slug(Path(nom).stem) + ext
            ctx["pieces"][url] = fichier
            if embed and ext in IMAGES:
                return f'<img src="{e(rel(url, page.url))}" alt="{e(texte)}" loading="lazy">'
            return f'<a href="{e(rel(url, page.url))}">{e(texte)}</a>'
        n = ctx["par_nom"].get(nom.removesuffix(".md"))
        if n is None:
            return f'<span class="lien-mort">{e(texte)}</span>'
        return f"[{texte}]({rel(n.url, page.url)})"
    return RE_LIEN.sub(sub, ligne)


def preparer(page: Note, ctx) -> str:
    sortie, lignes, i, dans_code = [], page.corps.split("\n"), 0, False
    # la première ligne « [[Cours]] » d'une note fait doublon avec le fil d'Ariane
    premiere = next((k for k, l in enumerate(lignes) if l.strip()), None)
    if premiere is not None and page.type != "cours" and re.fullmatch(r"\[\[[^\]|]+\]\]", lignes[premiere].strip()):
        lignes[premiere] = ""
    while i < len(lignes):
        l = lignes[i]
        if RE_FENCE.match(l):
            if not dans_code and l.strip().lower() in ("```base", "~~~base"):
                i += 1
                while i < len(lignes) and not RE_FENCE.match(lignes[i]):
                    i += 1
                sortie += ["", vue_base(None, page, ctx), ""]
                i += 1
                continue
            dans_code = not dans_code
            sortie.append(l)
            i += 1
            continue
        if dans_code:
            sortie.append(l)
            i += 1
            continue
        m = RE_BASE_EMBED.match(l.strip())
        if m:
            sortie += ["", vue_base(m.group(1), page, ctx), ""]
            i += 1
            continue
        m = RE_CALLOUT.match(l)
        if m:
            genre, pli, titre = m.group(1).lower(), m.group(2), m.group(3).strip()
            corps = []
            i += 1
            while i < len(lignes) and lignes[i].startswith(">"):
                corps.append(re.sub(r"^>\s?", "", lignes[i]))
                i += 1
            titre = md.renderInline(enrichir(titre or genre.capitalize(), page, ctx))
            if pli:  # encadré repliable d'Obsidian : [!tip]- replié, [!tip]+ déplié
                ouvert = " open" if pli == "+" else ""
                sortie += ["", f'<details class="callout callout-{e(genre)}"{ouvert}><summary class="callout-title">{titre}</summary>', ""]
            else:
                sortie += ["", f'<div class="callout callout-{e(genre)}"><div class="callout-title">{titre}</div>', ""]
            sortie += [enrichir(c, page, ctx) for c in corps]
            sortie += ["", "</details>" if pli else "</div>", ""]
            continue
        sortie.append(enrichir(l, page, ctx))
        i += 1
    return "\n".join(sortie)


def enrichir(ligne: str, page: Note, ctx) -> str:
    ligne = remplacer_liens(ligne, page, ctx)
    return RE_SURLIGNE.sub(r"<mark>\1</mark>", ligne)


def rendre(page: Note, ctx):
    tokens = md.parse(preparer(page, ctx))
    sommaire = []
    for k, t in enumerate(tokens):
        if t.type == "heading_open" and t.tag in ("h2", "h3") and t.attrGet("id"):
            sommaire.append((t.tag, t.attrGet("id"), texte_brut(md.renderInline(tokens[k + 1].content))))
    h = md.renderer.render(tokens, md.options, {})
    h = h.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    h = h.replace('<div class="table-wrap"><div class="table-wrap">', '<div class="table-wrap">').replace("</table></div></div>", "</table></div>")
    h = re.sub(r'<a href="(https?://[^"]+)"', r'<a href="\1" target="_blank" rel="noopener"', h)
    # sur téléphone : les cellules en caractères chinois ne se coupent pas, les tableaux larges défilent
    h = RE_TD_CHINOIS.sub(r'<td class="zh">\1</td>', h)
    h = re.sub(r"<table>(?=\s*<thead>\s*<tr>(?:\s*<th[^>]*>.*?</th>){4,})", '<table class="large">', h, flags=re.S)
    page.html, page.sommaire = h, sommaire


# ------------------------------------------------------------------ vocabulaire (page de révision + export Anki)
RE_SEPARATEUR = re.compile(r"^\|?\s*:?-{3,}")
COLONNES_FRANCAIS = ("Français", "Sens")
COLONNES_EXEMPLE = ("Exemple", "Mots", "Signe")


def cellules(ligne: str):
    return [c.strip() for c in re.split(r"(?<!\\)\|", ligne.strip().strip("|"))]


def texte_cellule(c: str) -> str:
    c = RE_LIEN.sub(lambda m: m.group(4) or m.group(2), c)
    c = re.sub(r"\*\([^)]*\)\*", "", c)  # mentions du type *(ajouté)*
    return re.sub(r"\s+", " ", c.replace("**", "").replace("==", "").replace("`", "").replace("*", "")).strip()


def extraire_vocabulaire(n: Note, cours):
    """Lit les tableaux de la note qui ont une colonne 汉字 (ou 字) et une colonne 拼音, ou une colonne « 汉字 · 拼音 »."""
    mots, lignes, i = [], n.corps.split("\n"), 0
    while i < len(lignes) - 1:
        if not (lignes[i].startswith("|") and RE_SEPARATEUR.match(lignes[i + 1])):
            i += 1
            continue
        entete = [texte_cellule(c) for c in cellules(lignes[i])]
        j = i + 2
        rangs = []
        while j < len(lignes) and lignes[j].startswith("|"):
            rangs.append([texte_cellule(c) for c in cellules(lignes[j])])
            j += 1
        i = j
        ih = next((k for k, c in enumerate(entete) if c in ("汉字", "字")), None)
        ip = entete.index("拼音") if "拼音" in entete else None
        ihp = entete.index("汉字 · 拼音") if "汉字 · 拼音" in entete else None
        if ihp is None and (ih is None or ip is None):
            continue
        ifr = next((k for k, c in enumerate(entete) if c.startswith(COLONNES_FRANCAIS)), None)
        iex = next((k for k, c in enumerate(entete) if c in COLONNES_EXEMPLE), None)
        for r in rangs:
            r += [""] * (len(entete) - len(r))
            if ihp is not None:
                h, _, p = r[ihp].partition(" · ")
                f, x = r[0], (r[-1] if len(r) - 1 not in (0, ihp) else "")
            else:
                h, p = r[ih], r[ip]
                f, x = (r[ifr] if ifr is not None else ""), (r[iex] if iex is not None else "")
            if h and (p or f):
                mots.append({"h": h, "p": p, "f": f, "x": x, "c": cours.titre if cours else "", "n": n.titre, "u": n.url})
    return mots


def page_vocabulaire(nb: int) -> str:
    return f"""<h1>Vocabulaire</h1>
<p class="props">{nb} mots tirés des tableaux 汉字 / 拼音 de mes notes. Les mots marqués « su » sont mémorisés sur cet appareil.</p>
<div id="vocab">
<div class="filtres">
<label>Cours <select id="v-cours"></select></label>
<label>Note <select id="v-note"></select></label>
<label>Afficher <select id="v-etat"><option value="">tous les mots</option><option value="a-revoir">pas encore sus</option></select></label>
</div>
<div class="onglets"><button type="button" id="v-mode-liste" class="actif">Liste</button><button type="button" id="v-mode-cartes">Cartes</button></div>
<p id="v-compte" class="props"></p>
<section id="v-liste">
<p class="bascules"><label><input type="checkbox" id="v-cache-pinyin"> cacher le pinyin</label> <label><input type="checkbox" id="v-cache-fr"> cacher le français</label> <span class="aide">(toucher une case pour la révéler)</span></p>
<div class="table-wrap"><table class="vocab"><thead><tr><th>汉字</th><th>拼音</th><th>Français</th><th></th></tr></thead><tbody id="v-corps"></tbody></table></div>
</section>
<section id="v-cartes" hidden>
<p><label>Sens <select id="v-sens"><option value="zh">汉字 → français</option><option value="fr">français → 汉字</option></select></label></p>
<div id="v-carte" class="carte" tabindex="0" role="button" aria-label="Carte : toucher pour voir la réponse"></div>
<div id="v-actions" class="actions" hidden><button type="button" id="v-revoir">À revoir</button><button type="button" id="v-su">Je savais</button></div>
<p><button type="button" id="v-recommencer" hidden>Recommencer</button></p>
<p id="v-progres" class="props"></p>
</section>
<p class="props"><a href="assets/vocabulaire-anki.txt" download>Télécharger pour Anki</a> (fichier texte à importer : 汉字, pinyin, français, exemple, étiquette) · <button type="button" id="v-oublier" class="lien">tout remettre à « pas encore su »</button></p>
</div>
"""


def fichier_anki(mots) -> str:
    lignes = ["#separator:tab", "#html:false", "#columns:汉字\tPinyin\tFrançais\tExemple\tTags", "#tags column:5"]
    vus = set()
    for m in mots:
        if (m["h"], m["p"]) in vus:
            continue
        vus.add((m["h"], m["p"]))
        etiquette = "L2::" + slug(m["c"] or "divers")
        lignes.append("\t".join(str(v).replace("\t", " ") for v in (m["h"], m["p"], m["f"], m["x"], etiquette)))
    return "\n".join(lignes) + "\n"


# ------------------------------------------------------------------ mise en page
def proprietes(page: Note, ctx) -> str:
    fm, items = page.fm, []
    if page.type == "seance":
        if page.date:
            items.append(date_fr(page.date))
        if fm.get("seance"):
            items.append(f"séance {fm['seance']}")
        items.append(badge_fait(page))
    elif page.type in ("support", "lecture"):
        items.append(TYPES[page.type])
        if fm.get("auteur"):
            items.append(e(f"{fm['auteur']}" + (f", {fm['annee']}" if fm.get("annee") else "")))
        if page.date:
            items.append(date_fr(page.date))
        if fm.get("source"):
            items.append(f'<a href="{e(fm["source"])}" target="_blank" rel="noopener">texte en ligne</a>')
    elif page.type == "cours":
        creneau = " ".join(str(x) for x in (fm.get("jour"), fm.get("heure")) if x)
        items += [e(x) for x in (fm.get("ue"), creneau, f"salle {fm['salle']}" if fm.get("salle") else "", fm.get("enseignant")) if x]
    bloc = f'<p class="props">{" · ".join(items)}</p>' if items else ""
    if page.type == "seance" and fm.get("theme"):
        bloc += f'<p class="theme">{e(fm["theme"])}</p>'
    return bloc


def fil_ariane(page: Note, ctx) -> str:
    if page.url == "index.html":
        return ""
    morceaux = [f'<a href="{e(rel("index.html", page.url))}">Accueil</a>']
    cours = ctx["cours_par_dossier"].get(page.dossier)
    if cours and cours is not page:
        morceaux.append(lien(cours, page))
    return '<nav class="fil">' + " › ".join(morceaux) + "</nav>"


def navigation_seances(page: Note, ctx) -> str:
    if page.type != "seance":
        return ""
    serie = sorted([s for s in ctx["seances"] if s.dossier == page.dossier], key=lambda s: (s.date or date.min, s.stem))
    k = serie.index(page)
    avant = lien(serie[k - 1], page, "← " + date_fr(serie[k - 1].date)) if k > 0 else "<span></span>"
    apres = lien(serie[k + 1], page, date_fr(serie[k + 1].date) + " →") if k < len(serie) - 1 else "<span></span>"
    return f'<nav class="prec-suiv">{avant}{apres}</nav>'


def autres_notes(page: Note, ctx) -> str:
    if page.type != "cours":
        return ""
    autres = [n for n in ctx["notes"] if n.dossier == page.dossier and n.type not in ("cours", "seance")]
    if not autres:
        return ""
    items = "".join(f"<li>{lien(n, page)} <span class=\"badge\">{e(TYPES.get(n.type, n.type))}</span></li>" for n in autres)
    return f'<section class="auto"><h2>Supports et lectures du dossier</h2><ul>{items}</ul></section>'


def retroliens(page: Note, ctx) -> str:
    sources = sorted(ctx["retro"].get(page.stem, set()) - {page.stem})
    sources = [ctx["par_nom"][s] for s in sources if s in ctx["par_nom"]]
    if not sources:
        return ""
    return '<section class="auto retro"><h2>Pages qui renvoient ici</h2><ul>' + "".join(f"<li>{lien(s, page)}</li>" for s in sources) + "</ul></section>"


def menu(page: Note, ctx) -> str:
    items = [f'<li><a href="{e(rel("index.html", page.url))}">Accueil</a></li>',
             f'<li{" class=actif" if page.url == URL_VOCABULAIRE else ""}><a href="{e(rel(URL_VOCABULAIRE, page.url))}">Vocabulaire · 生词</a></li>']
    for c in ctx["cours"]:
        actif = ' class="actif"' if c.dossier == page.dossier else ""
        quand = f"{str(c.fm.get('jour') or '')[:3]}. {c.fm.get('heure') or ''}".strip(". ")
        items.append(f'<li{actif}><a href="{e(rel(c.url, page.url))}"><span class="quand">{e(quand)}</span>{e(c.titre)}</a></li>')
    return '<nav id="menu" aria-label="Cours"><ul>' + "".join(items) + "</ul></nav>"


def gabarit(page: Note, ctx) -> str:
    racine = rel(".", page.url)
    a_un_h1 = re.search(r"<h1[ >]", page.html) is not None
    scripts = "\n".join(f'<script src="{racine}/{s}" defer></script>' for s in page.scripts)
    raccourcis = ""
    if page.url == "index.html":
        raccourcis = (f'<p class="raccourcis"><a class="bouton" href="{URL_VOCABULAIRE}">Réviser le vocabulaire · 生词'
                      f'<span>{ctx["nb_mots"]} mots, liste et cartes</span></a></p>')
    sommaire = ""
    if len(page.sommaire) >= 5:
        liens = "".join(f'<li class="{niv}"><a href="#{e(ident)}">{e(txt)}</a></li>' for niv, ident, txt in page.sommaire)
        sommaire = f'<details class="sommaire"><summary>Sommaire</summary><ul>{liens}</ul></details>'
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="theme-color" content="{COULEUR_THEME}">
<title>{e(page.titre)} · {e(TITRE_SITE)}</title>
<link rel="manifest" href="{racine}/manifest.webmanifest">
<link rel="icon" href="{racine}/assets/icone-192.png">
<link rel="apple-touch-icon" href="{racine}/assets/icone-180.png">
<link rel="stylesheet" href="{racine}/assets/style.css">
</head>
<body data-racine="{racine}">
<header class="barre">
<button id="bouton-menu" type="button" aria-label="Ouvrir le menu des cours" aria-expanded="false">☰</button>
<a class="marque" href="{racine}/index.html">{e(TITRE_SITE)}</a>
<input id="recherche" type="search" placeholder="Rechercher : français, 汉字, pinyin" autocomplete="off" aria-label="Rechercher dans les notes">
</header>
<div id="resultats" hidden></div>
{menu(page, ctx)}
<main>
{fil_ariane(page, ctx)}
<article>
{'' if a_un_h1 else f'<h1>{e(page.titre)}</h1>'}
{raccourcis}
{proprietes(page, ctx)}
{sommaire}
{page.html}
</article>
{autres_notes(page, ctx)}
{navigation_seances(page, ctx)}
{retroliens(page, ctx)}
<footer>Généré le {date.today():%d/%m/%Y} à partir du coffre Obsidian.</footer>
</main>
<script src="{racine}/assets/app.js" defer></script>
{scripts}
</body>
</html>
"""


# ------------------------------------------------------------------ construction
def ordre_cours(c: Note):
    jour = str(c.fm.get("jour") or "")
    return (JOURS.index(jour) if jour in JOURS else 9, str(c.fm.get("heure") or ""), c.stem)


def construire(sortie: Path):
    if sortie.exists():
        if any(sortie.iterdir()) and not (sortie / MARQUEUR).exists():
            raise SystemExit(f"{sortie} existe et n'a pas été créé par ce script : je n'y touche pas.")
        shutil.rmtree(sortie)
    (sortie / "assets").mkdir(parents=True)
    (sortie / MARQUEUR).write_text("dossier généré, ne pas modifier à la main\n", encoding="utf-8")
    (sortie / ".nojekyll").write_text("", encoding="utf-8")

    notes = charger()
    par_nom = {}
    for n in notes:
        par_nom.setdefault(n.stem, n)
    cours = sorted([n for n in notes if n.type == "cours"], key=ordre_cours)
    cours_par_dossier = {c.dossier: c for c in cours}
    seances = [n for n in notes if n.type == "seance"]
    for s in seances:
        s.cours = cours_par_dossier.get(s.dossier)
    retro = {}
    for n in notes:
        for m in RE_LIEN.finditer(n.corps):
            retro.setdefault(m.group(2).strip().split("/")[-1], set()).add(n.stem)
    fichiers = {}
    for f in VAULT.rglob("*"):
        if f.is_file() and f.suffix.lower() != ".md" and not any(p.startswith(".") for p in f.relative_to(VAULT).parts):
            fichiers.setdefault(f.name, f)
    ctx = dict(notes=notes, par_nom=par_nom, cours=cours, cours_par_dossier=cours_par_dossier,
               seances=seances, retro=retro, fichiers=fichiers, pieces={})

    mots = []
    for n in notes:
        mots += extraire_vocabulaire(n, cours_par_dossier.get(n.dossier))
    ctx["nb_mots"] = len({(m["h"], m["p"]) for m in mots})

    index = []
    for n in notes:
        rendre(n, ctx)
    for n in notes:
        cible = sortie / n.url
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_text(gabarit(n, ctx), encoding="utf-8", newline="\n")
        c = cours_par_dossier.get(n.dossier)
        index.append({"t": n.titre, "u": n.url, "c": c.titre if c and c is not n else "",
                      "x": " ".join(filter(None, [str(n.fm.get("theme") or ""), texte_brut(n.html)]))})
    for url, source in ctx["pieces"].items():
        (sortie / url).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, sortie / url)

    # page de vocabulaire, export Anki, icône et manifeste (ajout à l'écran d'accueil du téléphone)
    vocabulaire = PageSpeciale(URL_VOCABULAIRE, "Vocabulaire", page_vocabulaire(ctx["nb_mots"]),
                               scripts=["assets/vocabulaire.js", "assets/vocab.js"])
    (sortie / URL_VOCABULAIRE).write_text(gabarit(vocabulaire, ctx), encoding="utf-8", newline="\n")
    (sortie / "assets" / "vocabulaire.js").write_text(
        "window.VOCABULAIRE = " + json.dumps(mots, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8", newline="\n")
    (sortie / "assets" / "vocabulaire-anki.txt").write_text(fichier_anki(mots), encoding="utf-8", newline="\n")
    manifeste = {
        "name": TITRE_SITE, "short_name": TITRE_SITE, "lang": "fr", "start_url": "./index.html", "scope": "./",
        "display": "standalone", "background_color": "#fbfaf7", "theme_color": COULEUR_THEME,
        "icons": [{"src": f"assets/icone-{t}.png", "sizes": f"{t}x{t}", "type": "image/png", "purpose": "any maskable"} for t in (192, 512)],
    }
    (sortie / "manifest.webmanifest").write_text(json.dumps(manifeste, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    for nom in ("style.css", "app.js", "vocab.js", "icone-180.png", "icone-192.png", "icone-512.png"):
        shutil.copyfile(ICI / nom, sortie / "assets" / nom)
    (sortie / "assets" / "index-recherche.js").write_text(
        "window.INDEX_RECHERCHE = " + json.dumps(index, ensure_ascii=False, separators=(",", ":")) + ";\n",
        encoding="utf-8", newline="\n")

    # service worker : le site reste lisible hors connexion une fois visité
    fichiers_site = sorted(p.relative_to(sortie).as_posix() for p in sortie.rglob("*")
                           if p.is_file() and not p.name.startswith(".") and p.name != "sw.js")
    empreinte = hashlib.sha1()
    for f in fichiers_site:
        empreinte.update((sortie / f).read_bytes())
    sw = (ICI / "sw.js").read_text(encoding="utf-8")
    sw = sw.replace("__VERSION__", empreinte.hexdigest()[:10]).replace("__FICHIERS__", json.dumps(["./"] + fichiers_site))
    (sortie / "sw.js").write_text(sw, encoding="utf-8", newline="\n")

    morts = sorted(set(re.findall(r'class="lien-mort">([^<]+)<', "".join(n.html for n in notes))))
    print(f"{len(notes) + 1} pages écrites dans {sortie} ; {ctx['nb_mots']} mots de vocabulaire")
    if morts:
        print("Liens sans cible :", ", ".join(morts))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--sortie", default=str(VAULT / ".site"))
    args = ap.parse_args()
    dossier = Path(args.sortie)
    construire(dossier if dossier.is_absolute() else (Path.cwd() / dossier))
