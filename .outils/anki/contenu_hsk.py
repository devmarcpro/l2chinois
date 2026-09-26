# -*- coding: utf-8 -*-
"""Contenu ajouté pour couvrir le programme officiel du HSK (et non les cours) :
- donnees_hsk/vocabulaire.json : mots de la liste officielle HSK 3.0 absents du paquet (sens, exemple, traduction, note) ;
- donnees_hsk/grammaire.json : une fiche par point du programme de grammaire officiel (HSK 2025), sauf ceux
  qu'une fiche existante traitait déjà ("couvert_par").
Textes rédigés puis relus ; le pinyin et la forme traditionnelle sont calculés ici.
Programme de grammaire : github.com/krmanik/HSK-3.0 (d'après le document officiel du ministère et le 新版HSK考试大纲).
"""
import html
import json
import re
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees_hsk"
ECARTS_PINYIN = []  # (mot, pinyin rédigé, pinyin calculé) : à relire


def _texte(s: str) -> str:
    return html.escape(s, quote=False)


RUBY_UN = re.compile(r'<ruby>(.)<rt class="t\d">([^<]*)</rt></ruby>')


def imposer_mot(champ: str, mot: str, lectures) -> str:
    """Donne à chaque occurrence de `mot` annotée en ruby les lectures voulues, caractère par caractère
    (宝宝 = bǎo bao : les deux 宝 n'ont pas la même lecture)."""
    from pinyin_correct import ton
    rubis = list(RUBY_UN.finditer(champ))
    cars = "".join(m.group(1) for m in rubis)
    a_changer = {}
    for d in (x.start() for x in re.finditer(re.escape(mot), cars)):
        contigus = all(rubis[d + k].end() == rubis[d + k + 1].start() for k in range(len(mot) - 1))
        if contigus:
            for k, lecture in enumerate(lectures):
                a_changer[d + k] = lecture
    for i in sorted(a_changer, reverse=True):
        m = rubis[i]
        champ = champ[:m.start()] + f'<ruby>{m.group(1)}<rt class="t{ton(a_changer[i])}">{a_changer[i]}</rt></ruby>' + champ[m.end():]
    return champ


def note_vocabulaire_hsk(e):
    """Le pinyin rédigé (relu mot par mot) prime sur le calcul automatique, qui se trompe sur les tons neutres
    de dictionnaire (困难 kùn nan) et les caractères à plusieurs lectures (大夫 dài fu, 弹 tán)."""
    from contenu_cours import lire_phrase, ruby, span
    from corriger_decks import vers_trad
    from pinyin_correct import base, ton
    mot = e["mot"]
    lectures = lire_phrase(mot)
    redige = e.get("pinyin", "").split()
    if redige and len(redige) == len(lectures):
        if any(base(a) != base(b) or ton(a) != ton(b) for a, b in zip(redige, lectures)):
            ECARTS_PINYIN.append((mot, " ".join(redige), " ".join(lectures)))
        lectures = redige
    verso = f'<span class="hanzi-trad">{vers_trad(mot)}</span><br>{"".join(span(l) for l in lectures)}<br>{_texte(e["sens"])}'
    if e.get("note"):
        verso += f'<br><br><div class="exemple-bloc"><b>Notes :</b>{imposer_mot(ruby(_texte(e["note"])), mot, lectures)}</div>'
    verso += f'<br><br><div class="exemple-bloc"><b>Exemple :</b>{imposer_mot(ruby(e["exemple"]), mot, lectures)} - {_texte(e["traduction"])}</div>'
    return [mot, verso, "", "ajout_2026 HSK_officiel"]


def ajouter_hsk(paquets):
    """Ajoute les mots et les fiches de grammaire du programme officiel. Renvoie le bilan."""
    from contenu_cours import note_grammaire
    bilan = {}
    f = DONNEES / "vocabulaire.json"
    if f.exists():
        presents = {r[0].strip() for r in paquets["Vocabulaire"]}
        neuves = [note_vocabulaire_hsk(e) for e in json.loads(f.read_text(encoding="utf-8")) if e["mot"] not in presents]
        paquets["Vocabulaire"] += neuves
        bilan["Vocabulaire : mots du HSK officiel ajoutés"] = len(neuves)
    f = DONNEES / "grammaire.json"
    if f.exists():
        titres = {re.sub(r"<[^>]+>", "", r[0]) for r in paquets["Grammaire"]}
        neuves = []
        for e in json.loads(f.read_text(encoding="utf-8")):
            if e.get("couvert_par") or not e.get("titre"):
                continue
            n = note_grammaire(f"HSK {e['niveau']}", _texte(e["titre"]), _texte(e["explication"]),
                               [(x["zh"], _texte(x["fr"])) for x in e["exemples"]], "HSK_officiel")
            if re.sub(r"<[^>]+>", "", n[0]) not in titres:
                titres.add(re.sub(r"<[^>]+>", "", n[0]))
                neuves.append(n)
        paquets["Grammaire"] += neuves
        bilan["Grammaire : points du programme officiel ajoutés"] = len(neuves)
    return bilan
