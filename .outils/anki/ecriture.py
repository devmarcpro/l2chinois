# -*- coding: utf-8 -*-
"""Paquet Écriture : écrire de mémoire les 1 200 caractères de la liste officielle d'écriture manuscrite du HSK 3.0
(手写汉字表 : 300 pour les niveaux 1-3, 400 pour 4-6, 500 pour 7-9).

Recto : la lecture du caractère, son sens quand il est un mot à lui seul, et des mots de la liste officielle où il
est remplacé par ＿ (avec leur pinyin et leur sens) ; verso : le caractère, sa forme traditionnelle, le nombre de
traits, la clé et les mots complets. Lectures, sens et formes traditionnelles viennent des cartes du paquet
Vocabulaire (déjà relues) ; traits et clé : base Unihan (donnees_hsk/caracteres.json, construit à partir des listes
officielles de github.com/krmanik/HSK-3.0 et d'Unihan).
"""
import html
import json
import re
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees_hsk"
BANDES = {1: "1-3", 2: "4-6", 3: "7-9"}
SOUS_PAQUETS = {"1-3": "1 · HSK 1-3", "4-6": "2 · HSK 4-6", "7-9": "3 · HSK 7-9"}
TROU = "＿"
SPAN = re.compile(r'<span class="t(\d)">([^<]+)</span>')


def _nu(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def _mots(vocabulaire):
    """Mots du paquet Vocabulaire : recto, niveau HSK 3.0, syllabes (ton, pinyin), sens, forme traditionnelle."""
    from corriger_decks import hsk30, CJK
    officiel = hsk30()
    mots = []
    for rang, r in enumerate(vocabulaire):
        etiquettes = r[3].split()
        mot = r[0].strip()
        if "a_supprimer" in etiquettes or not re.fullmatch(r"[一-鿿]{1,4}", mot):
            continue
        lignes = r[1].split("<br>")
        if len(lignes) < 3:
            continue
        syllabes = SPAN.findall(lignes[1])
        trad = _nu(lignes[0])
        if len(syllabes) != len(mot) or len(CJK.findall(trad)) != len(mot):
            continue
        sens = _nu(lignes[2])
        if not sens:
            continue
        mots.append({"mot": mot, "niveau": officiel.get(mot) or officiel.get(mot + "儿") or 8, "syllabes": syllabes, "sens": sens,
                     "trad": trad, "rang": rang})
    return mots


def _pinyin(syllabes) -> str:
    return "".join(f'<span class="t{t}">{html.escape(p)}</span>' for t, p in syllabes)


def _masque(texte: str, car: str) -> str:
    return texte.replace(car, TROU)


def note_ecriture(car, info, seul, exemples):
    """seul : l'entrée du mot d'un seul caractère (ou None) ; exemples : mots de plusieurs caractères."""
    # lecture du caractère seul (même neutre : 的 de, 了 le), puis celles, accentuées, qu'il a dans les mots
    # (生 shēng et non le sheng de 学生) ; une lecture neutre des mots seulement s'il n'y a rien d'autre
    lectures = [seul["syllabes"][0]] if seul else []
    for neutre in (False, True):
        if (neutre and lectures) or (seul and car in "一不"):  # pas les tons de sandhi (bú, yí, yì) en tête
            break
        for m in exemples:
            t, p = m["syllabes"][m["mot"].index(car)]
            if (t == "0") == neutre and (t, p) not in lectures:
                lectures.append((t, p))
    lecture = " / ".join(_pinyin([x]) for x in lectures[:3])
    ligne_mot = lambda m, masquer: (
        f'{html.escape(_masque(m["mot"], car) if masquer else m["mot"])} {_pinyin(m["syllabes"])} — '
        f'{html.escape(_masque(m["sens"], car) if masquer else m["sens"])}')
    recto = ('<div style="font-size:18px;color:#888">✍️ Écrivez le caractère</div>'
             f'<div style="font-size:30px;margin:6px 0">{lecture}</div>')
    if seul:
        recto += f'<div style="font-size:20px">{html.escape(_masque(seul["sens"], car))}</div>'
    if exemples:
        recto += ('<div style="text-align:left;font-size:22px;margin-top:10px;line-height:1.7">'
                  + "<br>".join(ligne_mot(m, True) for m in exemples) + "</div>")
    trads = []
    for m in ([seul] if seul else []) + exemples:
        t = m["trad"][m["mot"].index(car)]
        if t != car and t not in trads:
            trads.append(t)
    details = f'{info["traits"]} trait{"s" if info["traits"] > 1 else ""} · clé {html.escape(info["cle"])}'
    if trads:
        details = f'traditionnel : {" / ".join(trads)} · ' + details
    verso = (f'<div style="font-size:96px;line-height:1.1">{car}</div>'
             f'<div style="font-size:18px;color:#666;margin-bottom:10px">{details}</div>'
             '<div style="text-align:left;font-size:22px;line-height:1.7">'
             + "<br>".join(ligne_mot(m, False) for m in ([seul] if seul else []) + exemples) + "</div>")
    bande = BANDES[info["ecriture"]]
    return [recto, verso, "", f"ecriture ecriture::{bande} HSK_officiel ajout_2026"]


def ajouter_ecriture(paquets, publies=None):
    """Crée ou complète le paquet Ecriture. Renvoie le bilan.
    Une carte déjà publiée garde son recto et son verso : de nouveaux mots au vocabulaire changeraient les mots
    d'exemple, donc le recto, et Anki y verrait une nouvelle carte (l'ancienne resterait avec a_supprimer)."""
    deja = {}
    for r in (publies or {}).get("Ecriture", []):
        m = re.search(r'font-size:96px;line-height:1.1">(.)<', r[1])
        if m and "a_supprimer" not in r[3].split():
            deja[m.group(1)] = list(r[:4])
    f = DONNEES / "caracteres.json"
    if not f.exists():
        return {}
    caracteres = {c: v for c, v in json.loads(f.read_text(encoding="utf-8")).items() if v["ecriture"]}
    mots = _mots(paquets["Vocabulaire"])
    seuls = {}
    par_car = {}
    for m in mots:
        if len(m["mot"]) == 1:
            seuls.setdefault(m["mot"], m)
        else:
            for c in set(m["mot"]):
                par_car.setdefault(c, []).append(m)
    notes, sans_mot = [], []
    for car, info in caracteres.items():
        seul = seuls.get(car)
        exemples = sorted(par_car.get(car, []), key=lambda m: (m["niveau"], len(m["mot"]), m["rang"]))
        exemples = [m for m in exemples if m["niveau"] <= 7][:3] or exemples[:2]
        if not seul and not exemples:
            sans_mot.append(car)
            continue
        premier = min([m["niveau"] for m in ([seul] if seul else []) + exemples])
        note = deja.get(car) or note_ecriture(car, info, seul, exemples)
        notes.append(((info["ecriture"], premier, info["niveau"], -len(par_car.get(car, []))), note))
    notes.sort(key=lambda x: x[0])
    rangs = paquets.setdefault("Ecriture", [])
    presents = {r[0] for r in rangs}
    neuves = []
    for _, n in notes:
        if n[0] in presents:  # même recto pour deux caractères : on ajoute le nombre de traits
            traits = re.search(r"(\d+) traits?", n[1]).group(1)
            n[0] += f'<div style="font-size:16px;color:#888">({traits} traits)</div>'
        presents.add(n[0])
        neuves.append(n)
    rangs += neuves
    bilan = {"Ecriture : caractères de la liste officielle d'écriture manuscrite": len(neuves)}
    if sans_mot:
        bilan["Ecriture : caractères sans mot d'exemple dans le paquet (en attente)"] = len(sans_mot)
    return bilan


def sous_paquet(r) -> str:
    m = re.search(r"(?<!\S)ecriture::(\S+)", r[3])
    return "Chinois::Ecriture::" + SOUS_PAQUETS.get(m.group(1) if m else "", "1 · HSK 1-3")
