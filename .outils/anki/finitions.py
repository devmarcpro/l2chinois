# -*- coding: utf-8 -*-
"""Dernières finitions, sur toutes les notes (trouvées par l'audit d'ensemble du 27/09/2026) :
- pinyin écrit en <span class="py"> (sans couleur de ton) : passé en <span class="tN"> comme partout ailleurs ;
- annotation <ruby> posée sur plusieurs caractères ou avec une ponctuation collée : un caractère par <ruby> ;
- forme traditionnelle absente en tête d'une carte de vocabulaire ; ligne de prononciation vide ou sans couleurs ;
- guillemets droits "…" : “…” autour du chinois et du pinyin, « … » autour du français ;
- retouches relues à la main (donnees_hsk/retouches.json) : remplacements exacts dans le verso, ou note retirée
  (garder_anciens_rectos la garde alors avec a_supprimer).
Ne change un recto que pour ses guillemets droits (anciens exports) et, sur les cartes d'écriture, une parenthèse
jamais fermée : ces cartes-là n'avaient pas encore été étudiées (l'ancienne version reste avec a_supprimer)."""
import json
import re
from pathlib import Path

CJK = re.compile(r"[一-鿿]")
RUBY = re.compile(r"<ruby>([^<]*)<rt[^>]*>[^<]*</rt></ruby>")
RETOUCHES = Path(__file__).parent / "donnees_hsk" / "retouches.json"


def _spans_py(champ: str) -> str:
    from pinyin_correct import ton
    return re.sub(r'<span class="py">([^<]*)</span>',
                  lambda m: f'<span class="t{ton(m.group(1).strip())}">{m.group(1)}</span>', champ)


def _ruby_simple(champ: str) -> str:
    from contenu_cours import ruby

    def refaire(m):
        base = m.group(1)
        if len(CJK.findall(base)) <= 1 and not re.match(r"[^一-鿿]+[一-鿿]", base):
            return m.group(0)
        debut = re.match(r"[^一-鿿]*", base).group(0)  # ponctuation collée devant
        return debut + ruby(base[len(debut):])
    return RUBY.sub(refaire, champ)


def _ligne_pinyin(recto: str, verso: str) -> str:
    """Carte de vocabulaire : 2e ligne (prononciation) vide, en texte brut pour un mot mêlé de lettres latines
    (« AA制 — AA zhì », « shuān Q »), ou remplacée par la forme traditionnelle répétée : refaite, en couleurs de ton."""
    from contenu_cours import spans_par_mot
    from corriger_decks import ligne_pinyin_mixte
    parties = verso.split("<br>")
    mot = re.sub(r"<[^>]+>", "", recto).strip()
    if len(parties) < 3 or not CJK.search(mot) or not re.fullmatch(r"[一-鿿A-Za-z0-9]+", mot):
        return verso
    if "hanzi-trad" in parties[1]:  # forme traditionnelle répétée (et mal écrite) à la place de la prononciation
        del parties[1]
    ligne = parties[1]
    vide = re.fullmatch(r'\s*(?:<span class="t\d">\s*</span>)?\s*', ligne)
    brut = '<span class="t' not in ligne and re.search(r"[A-Za-z]", mot)
    if vide or brut:
        parties[1] = spans_par_mot(mot) if CJK.fullmatch(mot[0]) and not re.search(r"[A-Za-z0-9]", mot) \
            else ligne_pinyin_mixte(mot, "")
    return "<br>".join(parties)


PINYIN = re.compile(r"[āǎēěīǐíōǒóūǔúǖǘǚǜ]|<span class=\"t\d\">")
REPLIQUE = re.compile(r'^([一-鿿][^"<>]*[？。！?])\s*"([一-鿿][^"<>]*)"$')


def _fermer_parentheses(recto: str) -> str:
    """Recto d'écriture : sens d'un mot d'exemple coupé avant sa parenthèse fermante (« …taïwanais<br> »)."""
    lignes = recto.split("<br>")
    for i, l in enumerate(lignes):
        texte = re.sub(r"<[^>]+>", "", l)
        if texte.count("(") == texte.count(")") + 1:
            m = re.search(r"(</div>)*$", l)
            lignes[i] = l[:m.start()] + ")" + l[m.start():]
    return "<br>".join(lignes)


def guillemets(champ: str) -> str:
    """Guillemets droits "…" (reste d'anciens exports) : “…” autour du chinois et du pinyin, « … » autour du
    français. Pris par paires dans l'ordre, hors balises et hors pinyin des rubis ; un champ au nombre impair est
    laissé tel quel. Réplique d'un dialogue dont seule la réponse était entre guillemets (« 你吃饭了吗？ "还没呢" ») :
    les deux répliques entre guillemets, comme dans le pinyin et la traduction."""
    champ = REPLIQUE.sub(lambda m: f'"{m.group(1)}""{m.group(2)}"', champ)
    champ = re.sub(r'(<span class="hanzi-trad">)([^<]*)(</span>)',
                   lambda m: m.group(1) + REPLIQUE.sub(lambda r: f'"{r.group(1)}""{r.group(2)}"', m.group(2)) + m.group(3),
                   champ)
    places = []
    for m in re.finditer(r'<rt[^>]*>.*?</rt>|<[^>]+>|"', champ):
        if m.group(0) == '"':
            places.append(m.start())
    if not places or len(places) % 2:
        return champ
    neuf = {}
    for a, b in zip(places[::2], places[1::2]):
        brut = champ[a + 1:b]
        dedans = re.sub(r"<rt[^>]*>.*?</rt>|<[^>]+>", "", brut)
        if CJK.search(dedans) or PINYIN.search(brut):
            neuf[a], neuf[b] = "“", "”"
        elif re.search(r"[A-Za-zÀ-ÿ]", dedans) and dedans == dedans.strip():
            neuf[a], neuf[b] = "« ", " »"
    for pos in sorted(neuf, reverse=True):
        champ = champ[:pos] + neuf[pos] + champ[pos + 1:]
    return champ


def appliquer(paquets, stats):
    from corriger_decks import vers_trad
    n = {"py": 0, "ruby": 0, "trad": 0, "pinyin": 0, "retouche": 0, "retiree": 0, "guillemets": 0, "parenthese": 0}
    for nom, rangs in paquets.items():
        for r in rangs:
            if "a_supprimer" in r[3].split():
                continue
            v = _spans_py(r[1])
            n["py"] += v != r[1]
            w = _ruby_simple(v)
            n["ruby"] += w != v
            r[1] = w
            if nom == "Vocabulaire" and not r[1].startswith('<span class="hanzi-trad">'):
                mot = re.sub(r"<[^>]+>", "", r[0]).strip()
                r[1] = f'<span class="hanzi-trad">{vers_trad(mot)}</span><br>' + r[1]
                n["trad"] += 1
            if nom == "Vocabulaire":
                v = _ligne_pinyin(r[0], r[1])
                n["pinyin"] += v != r[1]
                r[1] = v
    if RETOUCHES.exists():
        for t in json.loads(RETOUCHES.read_text(encoding="utf-8")):
            rangs = paquets.get(t["paquet"], [])
            # recto d'origine, ou tel que les finitions ci-dessous l'ont déjà rendu dans une version publiée
            vises = {t["recto"], guillemets(t["recto"]), _fermer_parentheses(t["recto"])}
            r = next((x for x in rangs if x[0] in vises and "a_supprimer" not in x[3].split()), None)
            if r is None:
                stats[(t["paquet"], "retouche : note introuvable")] += 1
                continue
            if t.get("retirer"):
                rangs.remove(r)
                n["retiree"] += 1
                continue
            for rem in t.get("remplacements", []):
                if r[1].count(rem["ancien"]) == 1:
                    r[1] = r[1].replace(rem["ancien"], rem["nouveau"])
                    n["retouche"] += 1
                elif rem["nouveau"] not in r[1]:
                    stats[(t["paquet"], "retouche : texte à remplacer introuvable")] += 1
    # après les retouches (qui visent le recto et le texte d'origine) : guillemets, parenthèse des rectos d'écriture
    for nom, rangs in paquets.items():
        for r in rangs:
            if "a_supprimer" in r[3].split():
                continue
            for j in (0, 1):
                g = guillemets(r[j])
                n["guillemets"] += g != r[j]
                r[j] = g
            if nom == "Ecriture":
                e = _fermer_parentheses(r[0])
                n["parenthese"] += e != r[0]
                r[0] = e
    return {"Finitions : pinyin sans couleur de ton passé en couleur": n["py"],
            "Finitions : annotations pinyin mal posées refaites": n["ruby"],
            "Finitions : forme traditionnelle ajoutée": n["trad"],
            "Finitions : ligne de prononciation refaite (vide, brute ou remplacée)": n["pinyin"],
            "Finitions : retouches appliquées": n["retouche"],
            "Finitions : exercices ambigus retirés": n["retiree"],
            "Finitions : champs aux guillemets droits passés en “…” ou « … »": n["guillemets"],
            "Finitions : parenthèse fermée dans un recto d'écriture": n["parenthese"]}
