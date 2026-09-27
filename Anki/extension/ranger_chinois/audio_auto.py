# -*- coding: utf-8 -*-
"""Audio automatique, voix Google Traduction (chinois zh-CN, la voix des préréglages HyperTTS).

Pour chaque note du paquet Chinois dont le champ « Texte audio » est rempli et « Ajouter le verso » vide, la voix
Google Traduction lit le texte ; le mp3 va dans le dossier des médias et la note reçoit [sound:…] dans
« Ajouter le verso ». C'est le moteur qu'HyperTTS emploie pour cette voix (la bibliothèque gTTS livrée avec HyperTTS),
appelé directement : aucune voix Windows, et un seul audio par note, jamais remplacé.

Les notes passent dans l'ordre d'étude : cartes déjà vues, puis cartes nouvelles dans l'ordre du manuel. On peut
arrêter à tout moment (Échap) : la fois suivante reprend où l'on en était. Un même texte n'est demandé qu'une fois
(le nom du fichier vient du texte), et un fichier déjà présent dans les médias n'est pas redemandé.
"""
import hashlib
import io
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from .coeur import AUDIO, RECHERCHE_SANS_AUDIO, TEXTE_AUDIO

HYPERTTS = "111623432"  # dossier d'HyperTTS dans addons21 (numéro AnkiWeb)
LANGUE, DOMAINE = "zh-CN", "com"  # voix « Chinese (Mandarin) » de Google Traduction, comme le préréglage HyperTTS
PAR_LOT = 40  # notes enregistrées ensemble
EN_PARALLELE = 4  # demandes simultanées à Google Traduction
PAUSE = 0.1  # secondes entre deux demandes d'un même fil


def _gtts(mw):
    try:
        import gtts
    except ImportError:
        externe = os.path.join(mw.addonManager.addonsFolder(HYPERTTS), "external")
        if os.path.isdir(externe) and externe not in sys.path:
            sys.path.insert(0, externe)
        import gtts  # toujours introuvable : HyperTTS n'est pas installé
    return gtts


def nom_fichier(texte: str) -> str:
    h = hashlib.sha1(f"gtts|{LANGUE}|{DOMAINE}|{texte}".encode("utf-8")).hexdigest()[:24]
    return f"chinois-gtts-{h}.mp3"


def a_faire(col):
    """[(nid, texte à lire)] des notes sans audio, dans l'ordre d'étude."""
    from anki.utils import ids2str
    nids = col.find_notes(RECHERCHE_SANS_AUDIO + " -tag:tts::aucun")
    if not nids:
        return []
    rang = {}
    for nid, genre, due in col.db.all(f"select nid, type, due from cards where nid in {ids2str(nids)}"):
        cle = (0, 0) if genre != 0 else (1, due)  # déjà vue d'abord, puis nouvelle à son rang
        if nid not in rang or cle < rang[nid]:
            rang[nid] = cle
    place = {}  # type de note -> (indice de « Texte audio », indice de « Ajouter le verso »)
    travail = []
    for nid, mid, flds in col.db.all(f"select id, mid, flds from notes where id in {ids2str(nids)}"):
        if mid not in place:
            noms = [f["name"] for f in col.models.get(mid)["flds"]]
            place[mid] = (noms.index(TEXTE_AUDIO), noms.index(AUDIO)) if TEXTE_AUDIO in noms and AUDIO in noms else None
        if not place[mid]:
            continue
        champs = flds.split("\x1f")
        texte = champs[place[mid][0]].strip()
        if texte and "[sound:" not in champs[place[mid][1]]:
            travail.append((nid, texte))
    travail.sort(key=lambda x: rang.get(x[0], (2, 0)))
    return travail


class ArretGoogle(Exception):
    pass


def _demander(gtts, texte: str):
    """mp3 de la voix Google Traduction, ou None si le texte n'a rien à lire. Réessaie après un refus passager."""
    attente = 5
    for essai in range(7):
        try:
            tampon = io.BytesIO()
            gtts.gTTS(text=texte, lang=LANGUE, tld=DOMAINE, timeout=30).write_to_fp(tampon)
            time.sleep(PAUSE)
            return tampon.getvalue()
        except AssertionError:  # gTTS : rien à lire une fois la ponctuation retirée
            return None
        except Exception as e:
            reponse = getattr(e, "rsp", None)
            if getattr(reponse, "status_code", None) == 429:  # trop de demandes : Google dit combien attendre
                attente = max(attente, int(reponse.headers.get("Retry-After", 30)))
            if essai == 6:
                raise ArretGoogle(str(e)) from e
            time.sleep(attente)
            attente = min(attente * 2, 300)


def generer(col, travail, progres, arreter, gtts):
    """Ajoute l'audio, lot par lot. progres(faits, total) ; arreter() -> True pour s'arrêter ; gtts : le module
    (voir _gtts). Renvoie le bilan."""
    bilan = {"notes": 0, "demandes": 0, "deja": 0, "vides": 0, "arret": "", "total": len(travail)}
    with ThreadPoolExecutor(EN_PARALLELE) as pool:
        for debut in range(0, len(travail), PAR_LOT):
            if arreter():
                bilan["arret"] = "arrêt demandé"
                break
            lot = travail[debut:debut + PAR_LOT]
            fichiers = {}  # nom voulu -> nom réel dans les médias (None : rien à lire)
            a_demander = {}
            for _, texte in lot:
                nom = nom_fichier(texte)
                if nom in fichiers or nom in a_demander:
                    continue
                if col.media.have(nom):
                    fichiers[nom] = nom
                    bilan["deja"] += 1
                else:
                    a_demander[nom] = texte
            try:
                sons = list(pool.map(lambda t: _demander(gtts, t), a_demander.values()))
            except ArretGoogle as e:
                bilan["arret"] = f"Google Traduction ne répond plus ({e})"
                break
            for nom, son in zip(a_demander, sons):
                bilan["demandes"] += 1
                fichiers[nom] = col.media.write_data(nom, son) if son else None
            notes = []
            for nid, texte in lot:
                reel = fichiers.get(nom_fichier(texte))
                if not reel:
                    bilan["vides"] += 1
                    continue
                note = col.get_note(nid)
                if "[sound:" in note[AUDIO]:  # audio ajouté entre-temps (HyperTTS à la main) : on le garde
                    continue
                note[AUDIO] = f"[sound:{reel}]"
                notes.append(note)
            if notes:
                col.update_notes(notes, skip_undo_entry=True)
            bilan["notes"] += len(notes)
            progres(min(debut + PAR_LOT, len(travail)), len(travail))
    return bilan
