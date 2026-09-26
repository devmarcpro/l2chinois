# -*- coding: utf-8 -*-
"""Accents remis dans le français des versos que le générateur d'origine avait écrit sans accents
(« etre », « tres », « annee », « a cause de »…).

donnees_hsk/accents.json : {"accents": {morceau d'origine (entre deux balises, entités décodées) : morceau corrigé},
"fautes": {...}}. Morceaux repérés automatiquement (mots dont seule la forme accentuée existe ailleurs dans les
paquets), corrigés par sous-agents : dans "accents", seuls les signes diacritiques (et œ / æ) peuvent changer, c'est
revérifié ici avant d'appliquer ; "fautes" = quelques fautes de frappe relevées au passage et relues à la main.
Les rectos ne sont jamais touchés (Anki reconnaît les notes par leur recto).
"""
import html
import json
import re
import unicodedata
from pathlib import Path

FICHIER = Path(__file__).parent / "donnees_hsk" / "accents.json"
LETTRES = re.compile(r"[A-Za-zÀ-ÿœæŒÆ]+")
MOT_OU_ENTITE = re.compile(r"&[#\w]+;|([A-Za-zÀ-ÿœæŒÆ]+)")


def sans_diacritiques(s: str) -> str:
    s = s.replace("œ", "oe").replace("Œ", "Oe").replace("æ", "ae").replace("Æ", "Ae")
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def noeuds(verso: str):
    """Morceaux de texte d'un verso, hors pinyin (<rt>, <span class="tN">) et forme traditionnelle."""
    v = re.sub(r"<rt[^>]*>[^<]*</rt>", "", verso)
    v = re.sub(r'<span class="t\d">[^<]*</span>', "", v)
    v = re.sub(r'<span class="hanzi-trad">[^<]*</span>', "", v)
    return [t for t in re.split(r"<[^>]+>", v) if re.search(r"[A-Za-z]{2}", t)]


def _corriger_brut(brut: str, corrige: str):
    """Reporte sur le texte brut (qui peut contenir des entités HTML) les mots corrigés, un à un et dans l'ordre."""
    origine = html.unescape(brut)
    if sans_diacritiques(corrige) != sans_diacritiques(origine):
        return None
    avant, apres = LETTRES.findall(origine), LETTRES.findall(corrige)
    bruts = [m.group(1) for m in MOT_OU_ENTITE.finditer(brut) if m.group(1)]
    if len(avant) != len(apres) or bruts != avant:
        return None
    suite = iter(apres)
    return MOT_OU_ENTITE.sub(lambda m: m.group(0) if m.group(1) is None else next(suite), brut)


def appliquer(paquets, stats=None):
    """Corrige les versos. Renvoie le nombre de notes modifiées."""
    if not FICHIER.exists():
        return 0
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    table, fautes = donnees["accents"], donnees.get("fautes", {})
    modifiees = 0
    for nom, rangs in paquets.items():
        for r in rangs:
            if "a_supprimer" in r[3].split():
                continue
            verso = r[1]
            # les plus longs d'abord : un petit morceau peut se retrouver à l'intérieur d'un grand (même phrase répétée)
            for brut in sorted(set(noeuds(verso)), key=len, reverse=True):
                if html.unescape(brut) in fautes and brut in verso:
                    verso = verso.replace(brut, html.escape(fautes[html.unescape(brut)], quote=False))
                    continue
                corrige = table.get(html.unescape(brut))
                if corrige is None or brut not in verso:
                    continue
                nouveau = _corriger_brut(brut, corrige)
                if nouveau and html.unescape(nouveau) in fautes:  # faute relevée sur le texte déjà réaccentué
                    nouveau = html.escape(fautes[html.unescape(nouveau)], quote=False)
                if nouveau and nouveau != brut:
                    verso = verso.replace(brut, nouveau)
            if verso != r[1]:
                r[1] = verso
                modifiees += 1
                if stats is not None:
                    stats[(nom, "accents remis dans le français")] += 1
    return modifiees
