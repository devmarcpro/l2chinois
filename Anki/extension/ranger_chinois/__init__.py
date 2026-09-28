# -*- coding: utf-8 -*-
"""Ranger mon chinois : range les cartes du paquet « Chinois » dans l'ordre du manuel de la fac.

Un import Anki met à jour le texte des notes déjà présentes, mais ne les change ni de paquet ni de place dans
la file des nouvelles cartes. Ce module lit RANGEMENT.tsv (dossier Anki/corrige du coffre : recto de la note,
paquet, rang) et, pour chaque note du paquet Chinois :
- déplace ses cartes dans le bon sous-paquet (leçon du manuel, « Après le manuel », « À supprimer ») ;
- donne à ses cartes nouvelles leur rang dans l'ordre d'apprentissage.
Les paquets vides qui restent sont supprimés. Tout s'annule en une fois (Édition > Annuler).

Menu Outils :
- « Chinois : tout mettre en place ou à jour » : sauvegarde, types « Chinois (phrase) » et « Chinois (grammaire) »,
  notes d'écoute sur le bon type, import des sept fichiers, rangement, réglages, suppression du paquet
  « 9 · À supprimer » ; à relancer pour chaque nouvelle version des fichiers ;
- « Chinois : importer les fichiers et ranger » : la même chose sans sauvegarde, réglages ni suppression ;
- « Ranger mon chinois (ordre du manuel) » : à relancer après chaque import fait à la main ;
- « Chinois : appliquer les réglages conseillés » : groupe d'options « Chinois – manuel » (nouvelles cartes
  prises leçon par leçon dans l'ordre, mêlées aux révisions, cartes sœurs enterrées) ;
- « Chinois : ajouter l'audio (Google Traduction) » : l'audio de chaque note qui n'en a pas, lu par la voix Google
  Traduction (chinois) d'HyperTTS depuis le champ « Texte audio » ; s'arrête avec Échap, reprend où il en était ;
- « Chinois : refaire l'audio d'une catégorie » : mots, phrases, réponses d'exercices, grammaire, dialogues, textes ou
  caractères (étiquettes tts::…) ; refait chaque audio qui manque ou n'est pas celui du texte actuel (ancien audio
  HyperTTS, texte corrigé depuis), l'ancien restant en place jusqu'au remplacement ;
- « Chinois : notes sans audio (HyperTTS) » : le navigateur sur les notes à doter d'un audio (champ « Texte audio »
  rempli, « Ajouter le verso » vide), pour le faire à la main avec HyperTTS.
"""
import os
from collections import defaultdict

from aqt import mw
from aqt.operations import CollectionOp
from aqt.qt import QAction, QFileDialog
from aqt.utils import askUser, showInfo, showWarning

from .coeur import (GROUPE, NOUVELLES, RACINE, RECHERCHE_SANS_AUDIO, REVISIONS, importer, lire_rangement,
                    mettre_en_place, preparer_types, ranger, reglages)


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
                   f"Limites du jour ({NOUVELLES} nouvelles cartes et {REVISIONS} révisions à la création) : "
                   "elles se règlent ensuite dans les options du paquet Chinois."):
        return
    bilan = defaultdict(int)

    def fini(_):
        showInfo(f"Groupe « {GROUPE} » {'créé et ' if bilan['cree'] else ''}appliqué à {bilan['paquets']} paquets.\n"
                 f"Par jour : {bilan['par_jour']} nouvelles cartes et {bilan['revisions']} révisions "
                 "(à changer dans les options du paquet Chinois).",
                 title="Ranger mon chinois")

    CollectionOp(parent=mw, op=lambda col: reglages(col, bilan)).success(fini).run_in_background()


def lancer_mise_en_place():
    chemin = _fichier()
    if not chemin:
        return
    dossier = os.path.dirname(chemin)
    if not askUser("Tout mettre en place dans le paquet « Chinois » ?\n\n"
                   "1. sauvegarde complète de la collection (Fichier > Revenir à une sauvegarde pour revenir en arrière) ;\n"
                   "2. types « Chinois (phrase) » (lecture, thème, dictée) et « Chinois (grammaire) » (comprendre, "
                   "utiliser) ; phrases déjà importées passées au premier ;\n"
                   "3. notes d'écoute sur le type d'écoute, qui joue l'audio HyperTTS ;\n"
                   "4. import des sept fichiers du dossier " + dossier + " (et des cartes privées du manuel, "
                   "dossier Anki/prive, s'il existe) ;\n"
                   "5. rangement dans l'ordre du manuel et réglages conseillés (FSRS activé s'il ne l'est pas) ;\n"
                   "6. suppression du paquet « 9 · À supprimer » ;\n"
                   "7. champ « Texte audio », audio au verso des exercices, ménage des audios en double ou lus "
                   "sur le recto ;\n"
                   "8. rappel actif : choix des exercices cachés derrière un bouton, questions des textes au recto.\n\n"
                   "La progression des cartes déjà révisées est gardée. Le changement de type de note demande, à la "
                   "prochaine synchronisation, de choisir « Envoyer vers AnkiWeb » (synchronisez d'abord votre "
                   "téléphone si vous y avez révisé depuis la dernière synchronisation de l'ordinateur)."):
        return
    journal = []

    def op(col):
        col.create_backup(backup_folder=mw.pm.backupFolder(), force=True, wait_for_completion=True)
        journal.append("Sauvegarde faite.")
        return mettre_en_place(col, dossier, journal)

    def fini(_):
        showInfo("\n".join(journal), title="Ranger mon chinois")
        lancer_audio()  # l'audio des notes qui n'en ont pas encore (demande confirmation)

    CollectionOp(parent=mw, op=op).success(fini).run_in_background()


def lancer_import():
    chemin = _fichier()
    if not chemin:
        return
    dossier = os.path.dirname(chemin)
    journal = []

    def op(col):
        preparer_types(col, dossier, journal)
        importer(col, dossier, journal)
        bilan = defaultdict(int)
        changes = ranger(col, lire_rangement(chemin), bilan)
        journal.append(f"Rangement : {bilan['deplacees']} cartes déplacées, {bilan['placees']} cartes nouvelles remises "
                       f"dans l'ordre, {bilan['vides']} paquets vides supprimés.")
        return changes

    CollectionOp(parent=mw, op=op).success(lambda _: showInfo("\n".join(journal), title="Ranger mon chinois")).run_in_background()


def lancer_refaire_audio():
    """Refaire l'audio d'une catégorie (étiquette tts::…) : chaque note dont l'audio manque ou n'est pas celui de son
    texte actuel (ancien audio HyperTTS, texte corrigé depuis) reçoit le nouvel audio, qui remplace l'ancien."""
    from aqt.qt import QInputDialog
    from .audio_auto import CATEGORIES, etat_categories
    etat = etat_categories(mw.col)
    choix, cles = [], []
    for tag, libelle in CATEGORIES:
        total, a_jour, a_refaire = etat[tag]
        if total:
            choix.append(f"{libelle} : {a_refaire} à refaire sur {total}")
            cles.append(tag)
    choix.append(f"Toutes les catégories : {sum(e[2] for e in etat.values())} à refaire sur {sum(e[0] for e in etat.values())}")
    cles.append(None)
    texte, ok = QInputDialog.getItem(
        mw, "Chinois : refaire l'audio", "Catégorie à refaire (l'audio actuel reste en place jusqu'à son remplacement) :",
        choix, 0, False)
    if ok and texte:
        lancer_audio(categorie=cles[choix.index(texte)], refaire=True)


def lancer_audio(categorie=None, refaire=False):
    """Audio Google Traduction des prochaines notes (ordre d'étude) qui ont un texte à lire et pas encore d'audio ;
    refaire=True : aussi celles dont l'audio n'est pas celui de leur texte actuel (il est remplacé)."""
    from .audio_auto import CATEGORIES, PAR_SEANCE, PAUSE, a_faire, generer, _gtts
    try:
        gtts = _gtts(mw)
    except ImportError:
        showWarning("L'audio automatique emploie la voix Google Traduction d'HyperTTS : installez d'abord HyperTTS "
                    "(Outils > Modules > Obtenir des modules, code 111623432), redémarrez Anki, puis relancez.")
        return
    restant = a_faire(mw.col, categorie, refaire)
    nom = dict(CATEGORIES).get(categorie, "toutes les catégories") if refaire else ""
    if not restant:
        showInfo((f"{nom} : tous les audios sont déjà à jour." if refaire else
                  "Toutes les notes du paquet Chinois qui ont un texte à lire ont déjà leur audio."), title="Ranger mon chinois")
        return
    travail = restant[:PAR_SEANCE]
    textes = len({t for _, t in travail})
    minutes = max(1, round(textes * (PAUSE + 0.5) / 60))
    quoi = (f"Refaire l'audio de {len(travail)} notes ({nom} : {len(restant)} à refaire en tout) ?\n\n"
            "- l'audio actuel est remplacé par celui du texte actuel (champ « Texte audio ») ; il reste en place tant que "
            "le nouveau n'est pas prêt ;\n" if refaire else
            f"Ajouter l'audio des {len(travail)} prochaines notes du paquet Chinois "
            f"({len(restant)} notes n'ont pas encore d'audio) ?\n\n"
            "- un seul audio par note, placé dans « Ajouter le verso » ; les audios déjà là ne sont pas touchés ;\n")
    if not askUser(quoi +
                   "- voix Google Traduction (chinois), comme les préréglages HyperTTS, lisant le champ « Texte audio » : "
                   "le mot, la phrase, le dialogue ou la réponse, jamais la consigne ;\n"
                   "- d'abord les cartes déjà vues, puis les nouvelles dans l'ordre du manuel ;\n"
                   f"- environ {minutes} min, connexion Internet nécessaire ; Échap pour arrêter à tout moment ;\n"
                   "- Google Traduction bloque pour quelques heures une connexion qui demande trop vite : le module avance "
                   "doucement, par séances ; relancez-le chaque jour pour garder l'audio en avance sur vos révisions ;\n"
                   "- les fichiers (10 à 30 Ko par phrase) partent sur AnkiWeb à la synchronisation suivante."):
        return
    mw.progress.start(max=len(travail), label="Audio Google Traduction : première demande…", immediate=True)

    def progres(faits, total, message):
        texte = message or f"Audio Google Traduction : {faits} / {total} notes"
        mw.taskman.run_on_main(lambda: mw.progress.update(label=f"{texte}\n(Échap pour arrêter)", value=faits, max=total))

    def fini(futur):
        mw.progress.finish()
        try:
            bilan = futur.result()
        except Exception as e:
            showWarning(f"Audio : arrêt sur une erreur ({e}). Ce qui a été fait est gardé ; relancez pour continuer.")
            return
        reste = len(restant) - bilan["notes"] - bilan["vides"]
        menu = "« Chinois : refaire l'audio d'une catégorie »" if refaire else "« Chinois : ajouter l'audio »"
        texte = (f"Audio {'refait' if refaire else 'ajouté'} pour {bilan['notes']} notes ({bilan['demandes']} fichiers "
                 f"demandés à Google Traduction, {bilan['deja']} déjà présents). Encore {max(0, reste)} notes "
                 f"{'à refaire' if refaire else 'sans audio'}.")
        if bilan["vides"]:
            texte += f"\n{bilan['vides']} notes sans rien à lire (ponctuation seule) : laissées sans audio."
        if bilan["arret"] == "limite":
            texte += ("\n\nGoogle Traduction refuse les demandes pour le moment (trop de demandes récentes depuis cette "
                      f"connexion). Ce blocage dure en général de quelques heures à une journée : relancez {menu} "
                      "plus tard, la suite reprendra ici.")
        elif bilan["arret"] == "echap":
            texte += f"\n\nArrêté (Échap). Relancez {menu} pour continuer."
        elif bilan["arret"]:
            texte += f"\n\nArrêt : {bilan['arret']}. Relancez {menu} pour continuer."
        try:
            mw.reset()
        except Exception:
            pass
        showInfo(texte, title="Ranger mon chinois")

    mw.taskman.run_in_background(
        lambda: generer(mw.col, travail, progres, mw.progress.want_cancel, gtts, remplacer=refaire), fini)


def lancer_sans_audio():
    """Le navigateur sur les notes qui ont un texte à lire et pas encore d'audio : tout sélectionner, puis HyperTTS."""
    from aqt import dialogs
    dialogs.open("Browser", mw, search=(RECHERCHE_SANS_AUDIO,))


def _menu():
    for titre, fonction in (("Chinois : tout mettre en place ou à jour", lancer_mise_en_place),
                            ("Chinois : ajouter l'audio (Google Traduction)", lambda: lancer_audio()),
                            ("Chinois : refaire l'audio d'une catégorie", lancer_refaire_audio),
                            ("Chinois : notes sans audio (HyperTTS)", lancer_sans_audio),
                            ("Chinois : importer les fichiers et ranger", lancer_import),
                            ("Ranger mon chinois (ordre du manuel)", lancer_rangement),
                            ("Chinois : appliquer les réglages conseillés", lancer_reglages)):
        action = QAction(titre, mw)
        action.triggered.connect(fonction)
        mw.form.menuTools.addAction(action)


_menu()
