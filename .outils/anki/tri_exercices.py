# -*- coding: utf-8 -*-
"""Exercices retirés parce qu'ils n'apprennent rien de plus que les cartes de vocabulaire (demande de
l'utilisateur, 27/09/2026 : « trop d'exercices, certains pas très utiles ») :
- forme traditionnelle → forme simplifiée d'un mot (les cartes de vocabulaire montrent déjà le traditionnel) ;
- ton ou pinyin d'un caractère isolé (« De quel ton est ce caractère ? 郑 ») : la carte du mot le demande déjà.
Restent les exercices de ton qui ont un intérêt propre : caractère à plusieurs lectures dans un mot (« 好 (dans
你好) »), 一 et 不 selon le ton suivant, paires minimales.
Une note retirée reste dans le fichier avec a_supprimer (garder_anciens_rectos)."""
import re


def _retires():
    """Exercices retirés à la relecture carte par carte du 28/09 (doublons, triviaux, ambigus, hors niveau) :
    donnees_hsk/exercices_retires.json (rectos)."""
    import json
    from pathlib import Path
    f = Path(__file__).parent / "donnees_hsk" / "exercices_retires.json"
    return {x["recto"] for x in json.loads(f.read_text(encoding="utf-8"))} if f.exists() else set()


RETIRES = _retires()


def inutile(r) -> bool:
    if r[0] in RETIRES:
        return True
    etiquettes = set(r[3].split())
    if "exercice_traditionnel" in etiquettes:
        return True
    texte = re.sub(r"<[^>]+>", " ", r[0])
    if {"exercice_ton", "exercice_pinyin"} & etiquettes:
        m = re.search(r"(?:De quel ton est|Quel est le pinyin correct pour) ce caractère ?\s*\?\s*(\S+)\s*(\S*)", texte)
        if m and not m.group(2).startswith(("(", "（")):
            return True
    return False


def _doublons():
    """Cartes retirées au dédoublonnage du 28/09 (même phrase ou même point travaillé par plusieurs sources dans une
    leçon : phrases, exercices, fiches, cartes du manuel) : donnees_hsk/cartes_retirees.json {paquet, recto}."""
    import json
    from pathlib import Path
    f = Path(__file__).parent / "donnees_hsk" / "cartes_retirees.json"
    return {(x["paquet"], x["recto"]) for x in json.loads(f.read_text(encoding="utf-8"))} if f.exists() else set()


DOUBLONS = _doublons()


def appliquer(paquets, stats):
    avant = len(paquets["Exercices"])
    paquets["Exercices"] = [r for r in paquets["Exercices"] if "a_supprimer" in r[3].split() or not inutile(r)]
    bilan = {"Exercices retirés (traditionnel → simplifié, ton ou pinyin d'un caractère isolé, relecture du 28/09)":
             avant - len(paquets["Exercices"])}
    for nom in ("Phrases", "Exercices", "Grammaire"):
        avant = len(paquets[nom])
        paquets[nom] = [r for r in paquets[nom] if "a_supprimer" in r[3].split() or (nom, r[0]) not in DOUBLONS]
        bilan[f"{nom} : doublons d'une autre carte de la leçon retirés"] = avant - len(paquets[nom])
    return bilan
