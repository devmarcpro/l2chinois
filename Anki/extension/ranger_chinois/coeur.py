# -*- coding: utf-8 -*-
"""Cœur de « Ranger mon chinois », sans interface (testable hors d'Anki)."""
import csv
from collections import defaultdict

RACINE = "Chinois"
GROUPE = "Chinois – manuel"


def lire_rangement(chemin):
    plan = {}
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = (l for l in f if not l.startswith("#"))
        for r in csv.reader(lignes, delimiter="\t", quotechar='"'):
            if len(r) >= 3 and r[2].isdigit():
                plan[r[0]] = (r[1], int(r[2]))
    return plan


def ranger(col, plan, bilan):
    """Déplace les cartes et règle la position des cartes nouvelles. Renvoie les changements (annulables)."""
    from anki.utils import ids2str
    racine = col.decks.id_for_name(RACINE)
    if not racine:
        raise Exception("Aucun paquet « Chinois » dans la collection.")
    dids = col.decks.deck_and_child_ids(racine)
    lignes = col.db.all(
        f"select c.id, c.did, c.odid, c.type, c.due, n.flds from cards c join notes n on n.id = c.nid "
        f"where c.did in {ids2str(dids)} or c.odid in {ids2str(dids)}")
    pos = col.add_custom_undo_entry("Ranger mon chinois")
    a_deplacer, a_placer = defaultdict(list), {}
    inconnues, filtrees = set(), 0
    for cid, did, odid, typ, due, flds in lignes:
        recto = flds.split("\x1f", 1)[0]
        if recto not in plan:
            inconnues.add(recto)
            continue
        if odid:  # carte empruntée par un paquet filtré : on n'y touche pas
            filtrees += 1
            continue
        paquet, rang = plan[recto]
        a_deplacer[paquet].append((cid, did))
        if typ == 0 and due != rang:
            a_placer[cid] = rang
    cibles = set()
    for paquet, cartes in a_deplacer.items():
        did = col.decks.id_for_name(paquet) or col.decks.add_normal_deck_with_name(paquet).id  # annulable
        col.merge_undo_entries(pos)
        cibles.add(did)
        ids = [cid for cid, ancien in cartes if ancien != did]
        if ids:
            col.set_deck(ids, did)
            bilan["deplacees"] += len(ids)
        col.merge_undo_entries(pos)  # une seule étape d'annulation (Anki n'en garde qu'une trentaine)
    if a_placer:
        cartes = []
        for cid, rang in a_placer.items():
            c = col.get_card(cid)
            c.due = rang
            cartes.append(c)
        col.update_cards(cartes)
        bilan["placees"] = len(cartes)
    # paquets devenus vides (anciens sous-paquets par type et par niveau)
    vides = []
    for nom, did in sorted(((col.decks.name(d), d) for d in col.decks.deck_and_child_ids(racine)), key=lambda x: -len(x[0])):
        if did == racine or did in cibles or (col.decks.get(did) or {}).get("dyn"):
            continue
        if col.decks.card_count(did, include_subdecks=True) == 0:
            vides.append(did)
    if vides:
        col.decks.remove(vides)
        bilan["vides"] = len(vides)
    bilan["inconnues"] = len(inconnues)
    bilan["filtrees"] = filtrees
    bilan["exemples"] = sorted(inconnues)[:5]
    return col.merge_undo_entries(pos)


def reglages(col, bilan):
    racine = col.decks.id_for_name(RACINE)
    if not racine:
        raise Exception("Aucun paquet « Chinois » dans la collection.")
    conf = next((c for c in col.decks.all_config() if c["name"] == GROUPE), None)
    if conf is None:
        conf = col.decks.add_config(GROUPE, clone_from=col.decks.config_dict_for_deck_id(racine))
        conf["new"]["perDay"] = 30
        conf["rev"]["perDay"] = 9999
        bilan["cree"] = 1
    conf["newGatherPriority"] = 0  # collecte des nouvelles cartes : par paquet (leçon après leçon)
    conf["newSortOrder"] = 1  # tri : ordre de collecte (l'ordre d'apprentissage calculé)
    conf["newMix"] = 0  # nouvelles cartes mêlées aux révisions
    conf["interdayLearningMix"] = 0
    conf["new"]["bury"] = True  # cartes sœurs (lecture / thème / dictée d'une phrase…) pas le même jour
    conf["rev"]["bury"] = True
    conf["buryInterdayLearning"] = True
    col.decks.update_config(conf)
    for did in col.decks.deck_and_child_ids(racine):
        d = col.decks.get(did)
        if d and not d.get("dyn") and d.get("conf") != conf["id"]:
            d["conf"] = conf["id"]
            col.decks.save(d)
            bilan["paquets"] += 1
    bilan["par_jour"] = conf["new"]["perDay"]
    from anki.collection import OpChanges
    return OpChanges(deck_config=True, deck=True)  # réglages : non annulables, modifiables dans les options
