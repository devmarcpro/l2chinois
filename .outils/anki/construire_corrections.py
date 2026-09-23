# -*- coding: utf-8 -*-
"""Transforme les signalements de relecture (JSON par tranche, identifiants E0012/V0345…) en corrections_contenu.json.

    python .outils/anki/construire_corrections.py <dossier revue>

Le dossier contient index.json (identifiant -> paquet, recto d'origine) et resultats/*.json (signalements).
Chaque signalement a été relu ; ceux de la liste A_ECARTER ne sont pas repris.
"""
import html
import json
import re
import sys
from pathlib import Path

from corrections_contenu import FICHIER, cle

# signalements écartés : (identifiant, extrait « ancien ») ou identifiant seul
A_ECARTER = {
    ("P0015", None), ("P0191", None), ("P0202", None),    # 精神 jīngshén : les deux lectures existent
    ("P0089", None), ("P0304", None),                     # 知 = 智 dans un texte classique : on garde la lecture du caractère
    ("V0445", None), ("V0535", None),                     # 儿 transcrit « ér » : convention du paquet
    ("V0688", "切"),                                       # carte du caractère seul : les deux lectures sont données
    ("G0038", "是…的 (确认información pasada)"),          # carte en double : remplacée par le doublon
    ("E0233", None), ("E0155", "3e ton (shǐng)"),          # déjà corrigé par corriger_decks (颇, 省)
    ("P0074", None), ("P0179", None), ("P0238", None), ("P0442", None),  # variantes traditionnelles : au choix, on ne touche pas
}
LETTRES = {"E": "Exercices", "G": "Grammaire", "L": "Lecture", "C": "Ecoute", "P": "Phrases", "V": "Vocabulaire"}
BRACKET_SEUL = re.compile(r"^\[([^\]]+)\]$")


def html_exercice(recto: str, verso: str):
    """Texte brut d'une carte réécrite (lignes séparées par \\n) -> HTML du paquet Exercices."""
    lignes_r = [l.strip() for l in recto.split("\n") if l.strip()]
    recto_html = "<br><br>".join(html.escape(l, quote=False) for l in lignes_r)
    lignes_v = [l.strip() for l in verso.split("\n") if l.strip()]
    sortie, corps, expl = [], [], None
    for l in lignes_v:
        if re.match(r"(Réponse|Phrase correcte|Ordre correct)\s*:", l):
            titre, _, reste = l.partition(":")
            reste = reste.strip()
            sortie.append(f"<b>{titre.strip()} : {html.escape(reste, quote=False)}</b>" if reste else f"<b>{titre.strip()} :</b>")
        elif re.match(r"(Explication|Traduction)\s*:", l):
            titre, _, reste = l.partition(":")
            expl = f'<div class="exemple-bloc"><b>{titre.strip()} :</b> {html.escape(reste.strip(), quote=False)}</div>'
        else:
            l = html.escape(l, quote=False)
            l = re.sub(r"\[ ([^\]]+) \]", r"<b>[ \1 ]</b>", l)  # réponse dans la phrase reconstituée
            corps.append(l)
    if sortie and sortie[0].startswith("<b>Phrase correcte") or sortie and sortie[0].startswith("<b>Ordre correct"):
        verso_html = sortie[0] + "<br>" + "<br>".join(corps)
    else:
        verso_html = "<br><br>".join(sortie + corps)
    if expl:
        verso_html += "<br><br>" + expl
    return recto_html, verso_html


def main(revue: Path):
    index = json.loads((revue / "index.json").read_text(encoding="utf-8"))
    corrections, vus = [], set()
    for f in sorted((revue / "resultats").glob("*.json")):
        for e in json.loads(f.read_text(encoding="utf-8")):
            ident = e["id"]
            if (ident, None) in A_ECARTER or (ident, e.get("ancien")) in A_ECARTER:
                continue
            if ident not in index:
                print(f"  ignoré (identifiant absent de l'index) : {f.name} {ident}")
                continue
            paquet, recto = index[ident]["paquet"], index[ident]["recto"]
            base_ = {"paquet": paquet, "cle": cle(recto), "apercu": re.sub(r"<[^>]+>", "", recto)[:40], "id": ident,
                     "gravite": e.get("gravite", ""), "probleme": e.get("probleme", "")}
            if "pinyin" in e:
                p = e["pinyin"]
                lecture = p["lecture_juste"].split()[0].split("(")[0].strip()
                if not re.fullmatch(r"[a-zǜ-ͯāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]+", lecture):
                    continue
                corrections.append({**base_, "pinyin": {"mot": p.get("mot") or p["caractere"], "caractere": p["caractere"], "lecture_juste": lecture,
                                                        "phrase": p.get("phrase", "")}})
                continue
            if "refaire" in e:
                r = e["refaire"]
                if paquet == "Exercices":
                    recto_html, verso_html = html_exercice(r.get("recto", ""), r["verso"])
                    corrections.append({**base_, "refaire": {"recto": recto_html, "verso": verso_html}})
                else:
                    corrections.append({**base_, "refaire": r})
                continue
            champ = e.get("champ", "VERSO")
            ancien, nouveau = e.get("ancien", ""), e.get("nouveau", "")
            m_doublon = re.fullmatch(r"doublon de (\w\d{4})", e.get("probleme", ""))
            if m_doublon and not ancien:
                if e.get("gravite") == "erreur":
                    corrections.append({**base_, "doublon": re.sub(r"<[^>]+>", " ", index[m_doublon.group(1)]["recto"]).replace("Structure :", "").strip()})
                continue
            m_niveau = re.search(r"HSK ?(\d)(?:-(\d))?", nouveau) if champ == "RECTO" and re.search(r"HSK ?\d", ancien) and paquet in ("Lecture", "Ecoute") else None
            if m_niveau:
                niv = int(m_niveau.group(1)) + (0.5 if m_niveau.group(2) else 0)
                corrections.append({**base_, "niveau": niv})
                continue
            if champ == "VERSO":
                # correction donnée comme "[xxx]" -> "[yyy]" (juste le pinyin entre crochets) : on la convertit
                # en correction "pinyin" ciblée, sinon le pinyin entre crochets est retiré avant la recherche
                # du texte (PINYIN_CROCHETS) et l'extrait devient vide.
                ma, mn = BRACKET_SEUL.match(ancien.strip()), BRACKET_SEUL.match(nouveau.strip())
                if ma and mn:
                    cars = re.findall(r"[一-鿿]", re.sub(r"<[^>]+>", "", recto))
                    syll_a, syll_n = ma.group(1).split(), mn.group(1).split()
                    if len(syll_a) == len(syll_n) == len(cars) and cars:
                        mot = "".join(cars)
                        for car, sa, sn in zip(cars, syll_a, syll_n):
                            if sa != sn:
                                corrections.append({**base_, "pinyin": {"mot": mot, "caractere": car, "lecture_juste": sn}})
                        continue
            if not ancien and champ != "ETIQUETTES":
                continue
            entree = {**base_, "champ": champ, "ancien": ancien, "nouveau": nouveau}
            signature = (paquet, base_["cle"], champ, ancien)
            if signature in vus:
                continue
            vus.add(signature)
            corrections.append(entree)
    donnees = {"mots": {}, "corrections": corrections}
    FICHIER.write_text(json.dumps(donnees, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    from collections import Counter
    genres = Counter("pinyin" if "pinyin" in c else "refaire" if "refaire" in c else "doublon" if "doublon" in c else "niveau" if "niveau" in c else c["champ"] for c in corrections)
    print(f"{len(corrections)} corrections écrites dans {FICHIER.name} :", dict(genres))


if __name__ == "__main__":
    main(Path(sys.argv[1]))
