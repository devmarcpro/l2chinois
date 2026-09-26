# -*- coding: utf-8 -*-
"""Exercices et textes rangés par leçon du manuel de la fac (Méthode de chinois, Inalco), sur le modèle de ses
exercices écrits. Contenu original : rien n'est recopié du manuel.

- donnees_hsk/manuel_contenu.json (rédigé leçon par leçon, avec le seul vocabulaire des leçons déjà vues) :
  placer un mot (A, B, C, D), récrire du pinyin en caractères, choisir entre des formes proches (Ø = rien),
  trouver la question d'une réponse, réunir deux phrases, un texte de lecture et un dialogue d'écoute par leçon ;
- calculés ici : écrire les nombres en caractères (l'heure, les prix, les grands nombres, fractions et
  pourcentages) et « des caractères aux mots » (les mots déjà vus qui contiennent un caractère de la leçon).
Chaque note porte l'étiquette manuel::<leçon>, qui la range dans sa leçon (manuel.py).
"""
import json
import re
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees_hsk"
CHIFFRES = "零一二三四五六七八九"


def _t(s: str) -> str:
    import html
    return html.escape(s, quote=False)


def _libelle(lecon: str) -> str:
    return ("1er niveau" if lecon.startswith("P1") else "2e niveau") + " · " + lecon[3:]


def _etiquettes(lecon, genre):
    return f"{genre} manuel::{lecon} deck_v2 ajout_2026"


# ------------------------------------------------------------------ nombres en caractères
def _quatre(n: int, debut: bool) -> str:
    """0 < n < 10000, écrit en caractères (二 ; 两 est choisi par nombre())."""
    s, zero = "", False
    for valeur, unite in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        c = n // valeur % 10
        if c == 0:
            zero = bool(s)
            continue
        if zero:
            s += "零"
            zero = False
        if not (unite == "十" and c == 1 and not s and debut):  # 十二 et non 一十二 en tête de nombre
            s += CHIFFRES[c]
        s += unite
    return s


def nombre(n: int) -> str:
    """Nombre entier en caractères : 24758000 -> 两千四百七十五万八千, 320050000 -> 三亿两千零五万."""
    if n == 0:
        return "零"
    groupes = []
    while n:
        groupes.append(n % 10000)
        n //= 10000
    s, zero = "", False
    for i in range(len(groupes) - 1, -1, -1):
        g = groupes[i]
        if g == 0:
            zero = bool(s)  # un groupe vide entre deux groupes : 一亿零五
            continue
        if s and (zero or g < 1000):  # 六十七万零八十
            s += "零"
        s += _quatre(g, debut=not s) + ["", "万", "亿", "万亿"][i]
        zero = False
    # 两 devant 千, 万, 亿 en tête (两千, 两万) ; 二 ailleurs (二十, 十二)
    s = re.sub(r"(^|[亿万零])二(?=[千万亿])", r"\1两", s)
    s = re.sub(r"^二(?=百)", "两", s)
    return s


def decimal(texte: str) -> str:
    """« 50,2 » -> 五十点二."""
    entier, _, dec = texte.partition(",")
    return nombre(int(entier)).replace("两", "二") + ("点" + "".join(CHIFFRES[int(c)] for c in dec) if dec else "")


def cartes_nombres():
    """Exercices de nombres rangés dans les leçons qui les enseignent."""
    notes = []

    def carte(lecon, consigne, question, reponse, note=""):
        recto = f"{consigne} :<br><br><b>{_t(question)}</b>"
        verso = f"<b>{_t(reponse)}</b>" + (f'<br><br><div class="exemple-bloc">{_t(note)}</div>' if note else "")
        notes.append([recto, verso, "", _etiquettes(lecon, "exercice_nombres")])

    heures = [("7 h 00", "七点", ""), ("7 h 30", "七点半", "半 = la demie."),
              ("8 h 15", "八点一刻", "一刻 = un quart d'heure ; on dit aussi 八点十五（分）."),
              ("9 h 45", "九点三刻", "On dit aussi 九点四十五（分） ou 差一刻十点 (dix heures moins le quart)."),
              ("2 h 05", "两点零五分", "两点 (et non 二点) pour deux heures ; 零 marque le zéro des minutes."),
              ("12 h 10", "十二点十分", ""),
              ("10 h 50", "十点五十（分）", "On dit aussi 差十分十一点 (onze heures moins dix).")]
    for q, r, n in heures:
        carte("P1-L04", "Dites l'heure en chinois", q, r, n)
    carte("P1-L04", "Écrivez la date en chinois", "le 26 septembre 2026",
          "二〇二六年九月二十六日（号）", "L'année se lit chiffre par chiffre : 二〇二六年 (èr líng èr liù nián). 号 à l'oral, 日 à l'écrit.")
    carte("P1-L04", "Écrivez la date en chinois", "le 1er mai 2019", "二〇一九年五月一日（号）", "Ordre chinois : année, mois, jour.")
    prix = [("35 yuans", "三十五块（元）", "块 à l'oral, 元 à l'écrit."), ("128 yuans", "一百二十八块", "一百二十八 : on dit bien 一百 et 一十 à l'intérieur du nombre (一百一十)."),
            ("2,50 yuans", "两块五（毛）", "毛 (角 à l'écrit) = un dixième de yuan ; le dernier 毛 se sous-entend souvent."),
            ("1 500 yuans", "一千五百块", ""), ("208 yuans", "两百零八块", "零 marque le zéro des dizaines ; on dit aussi 二百零八.")]
    for q, r, n in prix:
        carte("P1-L09", "Dites ce prix en chinois", q, r, n)
    grands = [(5400, ""), (24000, "万 = dix mille : 24 000 = 2,4 万 -> 两万四千."), (670080, "67 万 + 80 : le zéro entre les deux se dit 零."),
              (9600000, "960 万."), (24758000, "2 475 万 8 000."), (320050000, "3 亿 (cent millions) + 2 005 万."),
              (1400000000, "14 亿 : la population de la Chine."), (100000, "十万 (dix fois dix mille).")]
    for n, note in grands:
        chiffres = f"{n:,}".replace(",", " ")
        carte("P2-L09", "Écrivez ce nombre en caractères", chiffres, nombre(n), note)
        carte("P2-L09", "Écrivez ce nombre en chiffres", nombre(n), chiffres, note)
    fractions = [("3/4", "四分之三"), ("1/3", "三分之一"), ("5/6", "六分之五"), ("2/5", "五分之二")]
    for q, r in fractions:
        carte("P2-L09", "Écrivez cette fraction en caractères", q, r, "分之 : le dénominateur d'abord, puis 分之, puis le numérateur.")
    pourcents = [("8 %", "百分之八"), ("50,2 %", "百分之五十点二"), ("76,43 %", "百分之七十六点四三"), ("100 %", "百分之百")]
    for q, r in pourcents:
        carte("P2-L09", "Écrivez ce pourcentage en caractères", q, r, "百分之 + nombre ; 点 = la virgule, les décimales chiffre par chiffre.")
    carte("P2-L09", "Écrivez ce nombre en caractères", "3,14", "三点一四", "点 = la virgule ; les décimales se lisent chiffre par chiffre.")
    return notes


# ------------------------------------------------------------------ des caractères aux mots
def cartes_caracteres(paquets, manuel, par_lecon=6):
    """« Trouvez des mots formés avec 代 » : pour les caractères à écrire de chaque leçon, les mots déjà vus
    (leçons précédentes ou en cours) qui les contiennent."""
    from manuel import nu
    info = {}
    for r in paquets["Vocabulaire"]:
        parties = r[1].split("<br>")
        mot = nu(r[0])
        if re.fullmatch(r"[一-鿿]{2,4}", mot) and len(parties) > 2:
            info[mot] = (parties[1], nu(parties[2])[:40])
    notes = []
    for r in paquets.get("Ecriture", []):
        m = re.search(r'class="ecriture-car"[^>]*>\s*([一-鿿])', r[1])
        if not m or "a_supprimer" in r[3].split():
            continue
        car = m.group(1)
        lecon = manuel.car.get(car)
        if lecon is None or lecon >= len(manuel.lecons):
            continue
        mots = sorted((w for w in info if car in w and manuel.voc.get(w, 10 ** 6) <= lecon), key=lambda w: manuel.voc[w])
        if len(mots) >= 3:
            notes.append((lecon, len(mots), car, mots[:6]))
    choisies, par = [], {}
    for lecon, n, car, mots in sorted(notes, key=lambda x: (x[0], -x[1])):
        if par.get(lecon, 0) < par_lecon:
            par[lecon] = par.get(lecon, 0) + 1
            lid = manuel.lecons[lecon]["id"]
            recto = f"Trouvez des mots formés avec ce caractère :<br><br>{car}"
            lignes = "<br>".join(f"<b>{w}</b> {info[w][0]} {_t(info[w][1])}" for w in mots)
            verso = f"{lignes}"
            choisies.append([recto, verso, "", _etiquettes(lid, "exercice_mots")])
    return choisies


# ------------------------------------------------------------------ exercices et textes rédigés
def _phrase(zh, tr):
    from contenu_cours import spans_par_mot
    return f"{_t(zh)}<br><small>{spans_par_mot(zh)}</small><br><i>{_t(tr)}</i>"


def notes_redigees(d):
    lecon = d["lecon"]
    ex, lec, eco = [], [], []
    for x in d.get("placer", []):
        recto = f"Placez <b>{_t(x['mot'])}</b> au bon endroit :<br><br>{_t(x['phrase_lettres'])}"
        verso = (f"<b>Réponse : {_t(x['reponse'])}</b><br><br>{_phrase(x['phrase'], x['traduction'])}<br><br>"
                 f'<div class="exemple-bloc"><b>Explication :</b> {_t(x["explication"])}</div>')
        ex.append([recto, verso, "", _etiquettes(lecon, "exercice_placer")])
    for x in d.get("pinyin", []):
        recto = f"Écrivez cette phrase en caractères, puis traduisez-la :<br><br><i>{_t(x['pinyin'])}</i>"
        verso = f"<b>{_t(x['phrase'])}</b><br><i>{_t(x['traduction'])}</i>"
        ex.append([recto, verso, "", _etiquettes(lecon, "exercice_pinyin")])
    for x in d.get("choix", []):
        choix = " / ".join(_t(c) for c in x["choix"])
        recto = (f"Choisissez la bonne forme{' (Ø = rien)' if 'Ø' in x['choix'] else ''} :<br><br>"
                 f"{_t(x['phrase_trou'])}<br><br>Choix : {choix}")
        verso = (f"<b>Réponse : {_t(x['reponse'])}</b><br><br>{_phrase(x['phrase'], x['traduction'])}<br><br>"
                 f'<div class="exemple-bloc"><b>Explication :</b> {_t(x["explication"])}</div>')
        ex.append([recto, verso, "", _etiquettes(lecon, "exercice_choix")])
    for x in d.get("question", []):
        recto = f"Quelle question appelle cette réponse ?<br><br>— {_t(x['reponse'])}"
        verso = (f"<b>{_t(x['question'])}</b><br><small>{__import__('contenu_cours').spans_par_mot(x['question'])}</small><br>"
                 f"<i>{_t(x['traduction'])}</i><br><br>"
                 f'<div class="exemple-bloc"><b>Explication :</b> {_t(x["explication"])}</div>')
        ex.append([recto, verso, "", _etiquettes(lecon, "exercice_question")])
    for x in d.get("fusion", []):
        recto = (f"Faites une seule phrase avec <b>{_t(x['mot'])}</b> :<br><br>" + "<br>".join(_t(p) for p in x["phrases"]))
        verso = f"<b>Réponse :</b><br>{_phrase(x['phrase'], x['traduction'])}"
        ex.append([recto, verso, "", _etiquettes(lecon, "exercice_fusion")])
    from contenu_hsk import _corps_texte
    if d.get("lecture"):
        e = d["lecture"]
        texte = "<br>".join(_t(l) for l in e["texte"].split("\n"))
        recto = (f'<div style="text-align:left;font-size:20px;color:#888;margin-bottom:8px">📖 {_t(e["titre"])} | {_libelle(lecon)}</div>'
                 f'<div style="text-align:left;font-size:28px;line-height:1.8">{texte}</div>')
        lec.append([recto, _corps_texte(e), "", _etiquettes(lecon, "lecture") + " texte_gradue"])
    if d.get("ecoute"):
        e = d["ecoute"]
        texte = "<br>".join(_t(l) for l in e["texte"].split("\n"))
        recto = (f'<div class="ecoute-label">{_libelle(lecon)} · {_t(e["titre"])}</div><div class="ecoute-audio">🔊</div>'
                 f'<div class="ecoute-texte">{texte}</div>')
        verso = f'<div class="ecoute-reveal">{texte}</div><br>{_corps_texte(e)}'
        eco.append([recto, verso, "", _etiquettes(lecon, "ecoute") + " texte_gradue"])
    return ex, lec, eco


def _ajouter(paquets, paquet, neuves, libelle, bilan):
    presents = {r[0] for r in paquets[paquet]}
    ajout = []
    for n in neuves:
        if n[0] not in presents:
            presents.add(n[0])
            ajout.append(n)
    paquets[paquet] += ajout
    bilan[f"{paquet} : {libelle}"] = len(ajout)


def ajouter_manuel(paquets):
    """Exercices et textes rédigés, nombres (avant accents.py et erhua.py, qui les relisent aussi)."""
    bilan = {}
    f = DONNEES / "manuel_contenu.json"
    ex, lec, eco = [], [], []
    if f.exists():
        for d in json.loads(f.read_text(encoding="utf-8")):
            a, b, c = notes_redigees(d)
            ex += a
            lec += b
            eco += c
    _ajouter(paquets, "Exercices", ex, "exercices du manuel (placer, pinyin, choix, question, fusion)", bilan)
    _ajouter(paquets, "Exercices", cartes_nombres(), "nombres en caractères", bilan)
    _ajouter(paquets, "Lecture", lec, "textes par leçon du manuel", bilan)
    _ajouter(paquets, "Ecoute", eco, "dialogues par leçon du manuel", bilan)
    return bilan


def ajouter_caracteres(paquets):
    """« Des caractères aux mots » (après le paquet Écriture, dont on reprend les caractères)."""
    from manuel import Manuel
    bilan = {}
    _ajouter(paquets, "Exercices", cartes_caracteres(paquets, Manuel()), "des caractères aux mots", bilan)
    return bilan
