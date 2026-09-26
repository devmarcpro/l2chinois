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


TROP_COURANTS = set("的了是在有不一和也都就很")


def exercice_grammaire(e):
    """Exercice « complétez » tiré d'une fiche : la structure est remplacée par un trou, le sens français sert d'indice.
    Seulement si la réponse est sans ambiguïté : pas de fiche qui propose plusieurs mots au choix (A / B / C), et
    chaque mot à trouver apparaît une seule fois dans la phrase."""
    structure, _, sens = e["titre"].partition(" — ")
    if not sens or re.search(r" / |、|／", structure):
        return None
    mots = [m for m in re.findall(r"[一-鿿]+", re.sub(r"[（(][^）)]*[）)]", "", structure))]
    if not mots or all(m in TROP_COURANTS for m in mots):
        return None
    for x in e["exemples"]:
        zh = x["zh"]
        if all(zh.count(m) == 1 for m in mots):
            trou = zh
            for m in mots:
                trou = trou.replace(m, "___", 1)
            recto = (f"Complétez avec la bonne structure (sens : {_texte(sens)}) :<br><br>{trou}<br><br>"
                     f"<i>{_texte(x['fr'])}</i>")
            verso = (f"<b>Réponse : {' … '.join(mots)}</b><br><br>{zh}<br><br>"
                     f'<div class="exemple-bloc"><b>Explication :</b> {_texte(e["titre"])}. {_texte(e["explication"])}</div>')
            return [recto, verso, "", "exercice_structure deck_v2 ajout_2026 HSK_officiel"]
    return None


def _en_gras(phrase_trou: str, reponse: str) -> str:
    """Phrase complète avec la réponse en gras (« X/Y » pour une structure à deux trous)."""
    parties = reponse.split("/") if phrase_trou.count("___") == 2 else [reponse]
    rendu = _texte(phrase_trou)
    for p in parties:
        rendu = rendu.replace("___", f"<b>{_texte(p.strip())}</b>", 1)
    return rendu


def exercices_rediges(e):
    """Exercices rédigés pour une fiche : choix entre trois formes, phrase fautive à corriger."""
    notes = []
    for x in e["exercices"]:
        explication = f'<div class="exemple-bloc"><b>Explication :</b> {_texte(x["explication"])} ({_texte(x["titre_fiche"])})</div>'
        if x["type"] == "choix":
            recto = (f"Choisissez la bonne forme :<br><br>{_texte(x['phrase_trou'])}<br><br>"
                     f"Choix : {' / '.join(_texte(c) for c in x['choix'])}")
            verso = (f"<b>Réponse : {_texte(x['reponse'])}</b><br><br>{_en_gras(x['phrase_trou'], x['reponse'])}<br>"
                     f"<i>{_texte(x['traduction'])}</i><br><br>{explication}")
            notes.append([recto, verso, "", "exercice_structure deck_v2 ajout_2026 HSK_officiel"])
        elif x["type"] == "correction":
            recto = f"Trouvez et corrigez l'erreur dans cette phrase :<br><br>{_texte(x['phrase_fautive'])}"
            verso = (f"<b>Phrase correcte :</b><br>{_texte(x['phrase'])}<br><i>{_texte(x['traduction'])}</i><br><br>{explication}")
            notes.append([recto, verso, "", "exercice_correction deck_v2 ajout_2026 HSK_officiel"])
    return notes


def carte_theme(e):
    """Thème (français -> chinois) : la phrase française d'un exemple de la fiche, la structure à employer en indice."""
    from contenu_cours import spans_par_mot
    structure = e["titre"].partition(" — ")[0]
    x = e["exemples"][1] if len(e["exemples"]) > 1 else e["exemples"][0]
    recto = f"Traduisez en chinois (structure : {_texte(structure)}) :<br><br><i>{_texte(x['fr'])}</i>"
    verso = (f"<b>Traduction :</b><br>{x['zh']}<br><small>{spans_par_mot(x['zh'])}</small><br><br>"
             f'<div class="exemple-bloc"><b>Structure :</b> {_texte(e["titre"])}</div>')
    return [recto, verso, "", "exercice_theme deck_v2 ajout_2026 HSK_officiel"]


def _libelle(n: int) -> str:
    return "HSK 7-9" if n == 7 else f"HSK {n}"


def _corps_texte(e) -> str:
    """Traduction, questions (réponses en chinois) et mots clés, comme les textes de lecture et d'écoute existants."""
    questions = "<br><br>".join(f"<b>Q :</b> {_texte(q['q'])}<br><b>R :</b> {_texte(q['r'])}" for q in e["questions"])
    mots = " · ".join(f"{_texte(m['mot'])} {_texte(m['pinyin'])} = {_texte(m['sens'])}" for m in e["mots_cles"])
    traduction = "<br>".join(_texte(l) for l in e["traduction"].split("\n"))
    return (f'<div class="exemple-bloc" style="text-align:left"><b>Traduction :</b><br><i>{traduction}</i><br><br>'
            f"<b>Questions :</b><br>{questions}<br><br><b>Mots clés :</b><br>{mots}</div>")


def note_lecture(e):
    texte = "<br>".join(_texte(l) for l in e["texte"].split("\n"))
    recto = (f'<div style="text-align:left;font-size:20px;color:#888;margin-bottom:8px">📖 {_texte(e["titre"])} | {_libelle(e["niveau"])}</div>'
             f'<div style="text-align:left;font-size:28px;line-height:1.8">{texte}</div>')
    return [recto, _corps_texte(e), "", "lecture deck_v2 ajout_2026 texte_gradue"]


def note_ecoute(e):
    texte = "<br>".join(_texte(l) for l in e["texte"].split("\n"))
    recto = (f'<div class="ecoute-label">{_libelle(e["niveau"])} · {_texte(e["titre"])}</div><div class="ecoute-audio">🔊</div>'
             f'<div class="ecoute-texte">{texte}</div>')
    verso = f'<div class="ecoute-reveal">{texte}</div><br>{_corps_texte(e)}'
    return [recto, verso, "", "ecoute deck_v2 ajout_2026 texte_gradue"]


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
        rectos = {r[0] for r in paquets["Exercices"]}
        exos = [x for x in (exercice_grammaire(e) for e in json.loads(f.read_text(encoding="utf-8"))
                            if not e.get("couvert_par") and e.get("titre")) if x and x[0] not in rectos]
        paquets["Exercices"] += exos
        bilan["Exercices : structures du programme officiel à compléter"] = len(exos)
        fiches = [e for e in json.loads(f.read_text(encoding="utf-8")) if not e.get("couvert_par") and e.get("titre")]
        rectos |= {x[0] for x in exos}
        themes = [t for t in (carte_theme(e) for e in fiches) if t[0] not in rectos]
        rectos |= {t[0] for t in themes}
        paquets["Exercices"] += themes
        bilan["Exercices : thème (français -> chinois) sur les structures"] = len(themes)
        fe = DONNEES / "exercices_grammaire.json"
        if fe.exists():
            titres_fiche = {e["id"]: e["titre"] for e in fiches}
            rediges = []
            for e in json.loads(fe.read_text(encoding="utf-8")):
                for x in e["exercices"]:
                    x["titre_fiche"] = titres_fiche.get(e["id"], "")
                for n in exercices_rediges(e):
                    if n[0] not in rectos:
                        rectos.add(n[0])
                        rediges.append(n)
            paquets["Exercices"] += rediges
            bilan["Exercices : choix et corrections sur les structures du programme officiel"] = len(rediges)
    for paquet, fichier, fabrique in (("Lecture", "lecture.json", note_lecture), ("Ecoute", "ecoute.json", note_ecoute)):
        f = DONNEES / fichier
        if f.exists():
            presents = {r[0] for r in paquets[paquet]}
            neuves = [n for n in (fabrique(e) for e in json.loads(f.read_text(encoding="utf-8"))) if n[0] not in presents]
            paquets[paquet] += neuves
            bilan[f"{paquet} : textes gradués ajoutés"] = len(neuves)
    return bilan
