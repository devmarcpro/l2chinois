# -*- coding: utf-8 -*-
"""Audio automatique, voix Google Traduction (chinois zh-CN, la voix des préréglages HyperTTS).

Pour chaque note du paquet Chinois dont le champ « Texte audio » est rempli et « Ajouter le verso » vide, la voix
Google Traduction lit le texte ; le mp3 va dans le dossier des médias et la note reçoit [sound:…] dans
« Ajouter le verso ». C'est le moteur qu'HyperTTS emploie pour cette voix (la bibliothèque gTTS livrée avec HyperTTS),
appelé directement : aucune voix Windows, et un seul audio par note, jamais remplacé.

Les notes passent dans l'ordre d'étude : cartes déjà vues, puis cartes nouvelles dans l'ordre du manuel. Google
Traduction bloque une connexion qui demande trop vite (erreur 429, pour quelques heures) : on avance donc doucement,
une demande à la fois, par séances de PAR_SEANCE notes ; la séance suivante reprend où l'on en était. Si Google
bloque quand même, la séance s'arrête tout de suite en le disant. Échap arrête à tout moment. Un même texte n'est
demandé qu'une fois (le nom du fichier vient du texte), et un fichier déjà présent dans les médias n'est pas redemandé.
"""
import hashlib
import io
import os
import re
import sys
import time

from .coeur import AUDIO, RECHERCHE_SANS_AUDIO, TEXTE_AUDIO

HYPERTTS = "111623432"  # dossier d'HyperTTS dans addons21 (numéro AnkiWeb)
LANGUE, DOMAINE = "zh-CN", "com"  # voix « Chinese (Mandarin) » de Google Traduction, comme le préréglage HyperTTS
PAR_SEANCE = 600  # notes par lancement : une dizaine de minutes, de quoi rester en avance sur les révisions
PAR_LOT = 20  # notes enregistrées ensemble
PAUSE = 0.8  # secondes entre deux demandes : 4 demandes en parallèle ont fait bloquer la connexion (27/09)
ATTENTE_LIMITE = 90  # secondes d'attente, une fois, si Google limite en cours de séance


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


CATEGORIES = (  # étiquette tts:: -> ce qu'elle regroupe (voir audio.py dans .outils/anki)
    ("tts::mot", "Mots (vocabulaire)"),
    ("tts::phrase", "Phrases, dictées, exemples de grammaire du manuel"),
    ("tts::reponse", "Réponses des exercices"),
    ("tts::grammaire", "Fiches de grammaire (comprendre / utiliser)"),
    ("tts::dialogue", "Dialogues et textes d'écoute"),
    ("tts::texte", "Textes de lecture"),
    ("tts::caractere", "Caractères à écrire"),
)


def _sons(champ: str):
    return re.findall(r"\[sound:([^\]]+)\]", champ)


def etat_categories(col):
    """{étiquette: (notes avec un texte à lire, à jour, à refaire)} ; « à refaire » : pas d'audio, ou un audio qui
    n'est pas celui du texte actuel (ancien HyperTTS, texte changé depuis)."""
    etat = {t: [0, 0, 0] for t, _ in CATEGORIES}
    place = {}
    for mid, flds, tags in col.db.all("select mid, flds, tags from notes"):
        tag = next((t for t in tags.split() if t in etat), None)
        if tag is None:
            continue
        if mid not in place:
            noms = [f["name"] for f in col.models.get(mid)["flds"]]
            place[mid] = (noms.index(TEXTE_AUDIO), noms.index(AUDIO)) if TEXTE_AUDIO in noms and AUDIO in noms else None
        if not place[mid]:
            continue
        champs = flds.split("\x1f")
        texte = champs[place[mid][0]].strip()
        if not texte:
            continue
        etat[tag][0] += 1
        etat[tag][1 if _sons(champs[place[mid][1]]) == [nom_fichier(texte)] else 2] += 1
    return etat


def a_faire(col, categorie=None, refaire=False):
    """[(nid, texte à lire)] dans l'ordre d'étude : les notes sans audio, ou (refaire=True) aussi celles dont l'audio
    n'est pas celui de leur texte actuel ; seulement l'étiquette `categorie` (tts::mot…) si elle est donnée."""
    from anki.utils import ids2str
    recherche = (f'deck:Chinois -"{TEXTE_AUDIO}:" -tag:tts::aucun' if refaire else RECHERCHE_SANS_AUDIO + " -tag:tts::aucun")
    if categorie:
        recherche += f" tag:{categorie}"
    nids = col.find_notes(recherche)
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
        sons = _sons(champs[place[mid][1]])
        if texte and (not sons or (refaire and sons != [nom_fichier(texte)])):
            travail.append((nid, texte))
    travail.sort(key=lambda x: rang.get(x[0], (2, 0)))
    return travail


class ArretGoogle(Exception):
    """Google Traduction ne répond plus (réseau coupé, erreur qui persiste)."""


class LimiteGoogle(Exception):
    """Google Traduction refuse : trop de demandes depuis cette connexion (erreur 429)."""


class Arret(Exception):
    """Échap."""


def _dormir(secondes, arreter, pendant=None):
    """Attend sans rester sourd à Échap ; pendant(reste) est appelé chaque seconde."""
    fin = time.monotonic() + secondes
    while (reste := fin - time.monotonic()) > 0:
        if arreter():
            raise Arret
        if pendant:
            pendant(max(1, round(reste)))
        time.sleep(min(1.0, reste))


def _demander(gtts, texte: str, arreter):
    """mp3 de la voix Google Traduction, ou None si le texte n'a rien à lire. Réessaie deux fois après une erreur
    passagère ; une limite de Google (429) remonte tout de suite."""
    for essai in range(3):
        try:
            tampon = io.BytesIO()
            gtts.gTTS(text=texte, lang=LANGUE, tld=DOMAINE, timeout=20).write_to_fp(tampon)
            return tampon.getvalue()
        except AssertionError:  # gTTS : rien à lire une fois la ponctuation retirée
            return None
        except Exception as e:
            if getattr(getattr(e, "rsp", None), "status_code", None) == 429:
                raise LimiteGoogle(str(e)) from e
            if essai == 2:
                raise ArretGoogle(str(e)) from e
            _dormir(3 * (essai + 1), arreter)


def generer(col, travail, progres, arreter, gtts, remplacer=False):
    """Ajoute l'audio des notes de `travail` [(nid, texte)], une demande à la fois ; remplacer=True : l'audio déjà
    présent est remplacé par le nouveau (refaire une catégorie), sinon il est gardé.

    progres(faits, total, message) ; arreter() -> True pour s'arrêter (Échap) ; gtts : le module (voir _gtts).
    Renvoie le bilan ; bilan["arret"] vaut "", "echap", "limite" ou le texte d'une erreur."""
    bilan = {"notes": 0, "demandes": 0, "deja": 0, "vides": 0, "arret": "", "total": len(travail)}
    fichiers = {}  # nom voulu -> nom réel dans les médias (None : rien à lire)
    en_attente = []  # notes prêtes, enregistrées par lots
    attendu = False

    def enregistrer():
        notes = []
        for nid, reel in en_attente:
            note = col.get_note(nid)
            if "[sound:" in note[AUDIO] and not remplacer:  # audio ajouté entre-temps (HyperTTS à la main) : gardé
                continue
            note[AUDIO] = f"[sound:{reel}]"
            notes.append(note)
        if notes:
            col.update_notes(notes, skip_undo_entry=True)
        bilan["notes"] += len(notes)
        en_attente.clear()

    try:
        for i, (nid, texte) in enumerate(travail):
            if arreter():
                raise Arret
            nom = nom_fichier(texte)
            if nom not in fichiers:
                if col.media.have(nom):
                    fichiers[nom] = nom
                    bilan["deja"] += 1
                else:
                    while True:
                        try:
                            son = _demander(gtts, texte, arreter)
                            break
                        except LimiteGoogle:
                            if attendu or not bilan["demandes"]:
                                raise  # déjà bloqué au départ, ou encore après une attente : inutile d'insister
                            attendu = True
                            _dormir(ATTENTE_LIMITE, arreter, lambda reste: progres(
                                i, len(travail), f"Google Traduction freine : nouvel essai dans {reste} s"))
                    bilan["demandes"] += 1
                    fichiers[nom] = col.media.write_data(nom, son) if son else None
                    time.sleep(PAUSE)
            if fichiers[nom]:
                en_attente.append((nid, fichiers[nom]))
            else:
                bilan["vides"] += 1
            if len(en_attente) >= PAR_LOT:
                enregistrer()
            progres(i + 1, len(travail), None)
    except Arret:
        bilan["arret"] = "echap"
    except LimiteGoogle:
        bilan["arret"] = "limite"
    except ArretGoogle as e:
        bilan["arret"] = f"Google Traduction ne répond plus ({e})"
    finally:
        enregistrer()
    return bilan
