# -*- coding: utf-8 -*-
"""Fiches de grammaire transformées en cartes à questions (type de note « Chinois (grammaire) », deux cartes) :
- « Comprendre » : une phrase chinoise, la structure en gras ; que veut dire la phrase, à quoi sert la structure ?
- « Utiliser » : ce qu'il faut exprimer et une phrase française à dire en chinois, sans donner la structure.
Le champ Recto contient les deux questions, le champ Verso les deux réponses puis la fiche complète (titre,
explication, exemples) ; chaque carte n'affiche que sa partie (classes carte-comprendre / carte-utiliser du
modèle). Phrases rédigées avec le seul vocabulaire des leçons déjà vues : donnees_hsk/grammaire_cartes.json.
"""
import html
import json
import re
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees_hsk"
QUESTION = "Que veut dire cette phrase ? À quoi sert la partie en gras ?"
OUVERTURE = '<div class="exemple-bloc" style="text-align:left">'


def _t(s: str) -> str:
    return html.escape(s, quote=False)


def _gras(phrase_gras: str) -> str:
    morceaux = phrase_gras.split("**")
    return "".join(f"<b>{_t(m)}</b>" if i % 2 else _t(m) for i, m in enumerate(morceaux))


def carte(titre, niveau, ancien_verso, c):
    """(recto, verso) d'une fiche."""
    from contenu_cours import spans_par_mot
    co, ut = c["comprendre"], c["utiliser"]
    phrase = co["phrase_gras"].replace("**", "")
    etiquette = f'<div class="g-niveau">Grammaire · HSK {niveau}</div>' if niveau else '<div class="g-niveau">Grammaire</div>'
    consigne = ut["consigne"].rstrip(" .:")
    if consigne[:1].isupper() and not consigne[1:2].isupper():  # « Dites en chinois — mettez… »
        consigne = consigne[0].lower() + consigne[1:]
    recto = (etiquette
             + f'<div class="g-comprendre"><div class="g-consigne">{_t(co.get("question") or QUESTION)}</div>'
               f'<div class="g-zh">{_gras(co["phrase_gras"])}</div></div>'
             + f'<div class="g-utiliser"><div class="g-consigne">Dites en chinois — {_t(consigne)} :</div>'
               f'<div class="g-fr">« {_t(ut["francais"])} »</div></div>')
    variantes = ""
    if ut.get("variantes"):
        variantes = '<div class="g-variantes">Aussi possible : ' + " ; ".join(_t(v) for v in ut["variantes"]) + "</div>"
    fiche = ancien_verso
    if fiche.startswith(OUVERTURE):
        fiche = OUVERTURE + f'<span style="font-size:130%;color:#2980b9">{_t(titre)}</span><br><br>' + fiche[len(OUVERTURE):]
    else:
        fiche = f'<span style="font-size:130%;color:#2980b9">{_t(titre)}</span><br>' + fiche
    verso = (f'<div class="g-rep-comprendre"><div class="g-reponse">{_t(co["reponse"])}</div>'
             f'<div class="g-zh">{_gras(co["phrase_gras"])}</div><small>{spans_par_mot(phrase)}</small>'
             f'<div class="traduction">{_t(co["traduction"])}</div></div>'
             f'<div class="g-rep-utiliser"><div class="g-zh">{_t(ut["chinois"])}</div>'
             f'<small>{spans_par_mot(ut["chinois"])}</small>{variantes}</div>'
             f"<br>{fiche}")
    return recto, verso


def transformer(paquets, stats):
    """Remplace chaque fiche du paquet Grammaire qui a ses cartes rédigées. L'ancien recto disparaît :
    garder_anciens_rectos garde l'ancienne note avec l'étiquette a_supprimer."""
    f = DONNEES / "grammaire_cartes.json"
    if not f.exists():
        return {}
    from corriger_decks import niveau_carte
    from manuel import titre_fiche
    cartes = json.loads(f.read_text(encoding="utf-8"))
    n = 0
    for r in paquets["Grammaire"]:
        if "a_supprimer" in r[3].split() or 'class="g-niveau"' in r[0]:
            continue
        titre = titre_fiche(r[0])
        c = cartes.get(titre)
        if not c:
            stats[("Grammaire", "fiche sans cartes à questions (laissée telle quelle)")] += 1
            continue
        r[0], r[1] = carte(titre, niveau_carte("Grammaire", r), r[1], c)
        r[3] = " ".join([t for t in r[3].split() if t != "grammaire"] + ["grammaire", "grammaire_cartes"])
        n += 1
    return {"Grammaire : fiches transformées en deux cartes à questions (comprendre, utiliser)": n}
