# -*- coding: utf-8 -*-
"""Ranger mon chinois : range les cartes du paquet « Chinois » dans l'ordre du manuel de la fac.

Un import Anki met à jour le texte des notes déjà présentes, mais ne les change ni de paquet ni de place dans
la file des nouvelles cartes. Ce module lit RANGEMENT.tsv (dossier Anki/corrige du coffre : recto de la note,
paquet, rang) et, pour chaque note du paquet Chinois :
- déplace ses cartes dans le bon sous-paquet (leçon du manuel, « Après le manuel », « À supprimer ») ;
- donne à ses cartes nouvelles leur rang dans l'ordre d'apprentissage.
Les paquets vides qui restent sont supprimés. Tout s'annule en une fois (Édition > Annuler).

Menu Outils :
- « Ranger mon chinois (ordre du manuel) » : à relancer après chaque import ;
- « Chinois : appliquer les réglages conseillés » : groupe d'options « Chinois – manuel » (nouvelles cartes
  prises leçon par leçon dans l'ordre, mêlées aux révisions, cartes sœurs enterrées).
"""
import os
from collections import defaultdict

from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import QAction, QFileDialog
from aqt.utils import askUser, showInfo, showWarning

from .coeur import GROUPE, RACINE, lire_rangement, ranger, reglages


def _config():
    return mw.addonManager.getConfig(__name__) or {}


def _fichier():
    conf = _config()
    chemin = conf.get("fichier", "")
    if chemin and os.path.exists(chemin):
        return chemin
    chemin, _ = QFileDialog.getOpenFileName(
        mw, "Ranger mon chinois : où est RANGEMENT.tsv ? (dossier Anki/corrige du coffre)", "",
        "RANGEMENT.tsv (RANGEMENT.tsv);;Fichiers tsv (*.tsv)")
    if chemin:
        conf["fichier"] = chemin
        mw.addonManager.writeConfig(__name__, conf)
    return chemin


def lancer_rangement():
    chemin = _fichier()
    if not chemin:
        return
    try:
        plan = lire_rangement(chemin)
    except Exception as e:
        showWarning(f"Impossible de lire {chemin} :\n{e}")
        return
    if not plan:
        showWarning(f"{chemin} ne contient aucune ligne de rangement.")
        return
    bilan = defaultdict(int)

    def fini(_):
        texte = (f"Cartes déplacées dans leur leçon : {bilan['deplacees']}\n"
                 f"Cartes nouvelles remises dans l'ordre d'apprentissage : {bilan['placees']}\n"
                 f"Paquets vides supprimés : {bilan['vides']}")
        if bilan["filtrees"]:
            texte += (f"\n\n{bilan['filtrees']} cartes sont dans un paquet filtré : videz-le (ou reconstruisez-le) "
                      "puis relancez le rangement.")
        if bilan["inconnues"]:
            texte += (f"\n\n{bilan['inconnues']} notes du paquet Chinois ne figurent pas dans RANGEMENT.tsv "
                      "(ajoutées à la main, ou fichier plus ancien que l'import) : laissées où elles sont.")
        texte += "\n\nPour tout annuler : Édition > Annuler."
        showInfo(texte, title="Ranger mon chinois")

    CollectionOp(parent=mw, op=lambda col: ranger(col, plan, bilan)).success(fini).run_in_background()


def lancer_reglages():
    if not askUser(f"Appliquer au paquet « {RACINE} » et à tous ses sous-paquets le groupe d'options « {GROUPE} » ?\n\n"
                   "- nouvelles cartes prises leçon par leçon, dans l'ordre d'apprentissage ;\n"
                   "- nouvelles cartes mêlées aux révisions ;\n"
                   "- cartes sœurs enterrées (pas le même jour).\n\n"
                   "Le nombre de nouvelles cartes par jour (30 à la création) se règle ensuite dans les options "
                   "du paquet Chinois."):
        return
    bilan = defaultdict(int)

    def fini(_):
        showInfo(f"Groupe « {GROUPE} » {'créé et ' if bilan['cree'] else ''}appliqué à {bilan['paquets']} paquets.\n"
                 f"Nouvelles cartes par jour : {bilan['par_jour']} (à changer dans les options du paquet Chinois).",
                 title="Ranger mon chinois")

    CollectionOp(parent=mw, op=lambda col: reglages(col, bilan)).success(fini).run_in_background()


def _menu():
    for titre, fonction in (("Ranger mon chinois (ordre du manuel)", lancer_rangement),
                            ("Chinois : appliquer les réglages conseillés", lancer_reglages)):
        action = QAction(titre, mw)
        action.triggered.connect(fonction)
        mw.form.menuTools.addAction(action)


_menu()
