# -*- coding: utf-8 -*-
"""Exercices retirés parce qu'ils n'apprennent rien de plus que les cartes de vocabulaire (demande de
l'utilisateur, 27/09/2026 : « trop d'exercices, certains pas très utiles ») :
- forme traditionnelle → forme simplifiée d'un mot (les cartes de vocabulaire montrent déjà le traditionnel) ;
- ton ou pinyin d'un caractère isolé (« De quel ton est ce caractère ? 郑 ») : la carte du mot le demande déjà.
Restent les exercices de ton qui ont un intérêt propre : caractère à plusieurs lectures dans un mot (« 好 (dans
你好) »), 一 et 不 selon le ton suivant, paires minimales.
Une note retirée reste dans le fichier avec a_supprimer (garder_anciens_rectos)."""
import re


def inutile(r) -> bool:
    etiquettes = set(r[3].split())
    if "exercice_traditionnel" in etiquettes:
        return True
    texte = re.sub(r"<[^>]+>", " ", r[0])
    if {"exercice_ton", "exercice_pinyin"} & etiquettes:
        m = re.search(r"(?:De quel ton est|Quel est le pinyin correct pour) ce caractère ?\s*\?\s*(\S+)\s*(\S*)", texte)
        if m and not m.group(2).startswith(("(", "（")):
            return True
    return False


def appliquer(paquets, stats):
    avant = len(paquets["Exercices"])
    paquets["Exercices"] = [r for r in paquets["Exercices"] if "a_supprimer" in r[3].split() or not inutile(r)]
    return {"Exercices retirés (traditionnel → simplifié, ton ou pinyin d'un caractère isolé)":
            avant - len(paquets["Exercices"])}
