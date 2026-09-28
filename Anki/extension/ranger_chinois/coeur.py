# -*- coding: utf-8 -*-
"""Cœur de « Ranger mon chinois », sans interface (testable hors d'Anki)."""
import csv
from collections import defaultdict

RACINE = "Chinois"
GROUPE = "Chinois – manuel"
NOUVELLES, REVISIONS = 150, 300  # limites du jour à la création du groupe (environ 2 h d'Anki par jour)


def _prive(chemin_corrige):
    """Dossier Anki/prive, voisin de Anki/corrige : cartes tirées du manuel, gardées hors du dépôt public."""
    import os
    return os.path.join(os.path.dirname(os.path.abspath(chemin_corrige)), "prive")


def lire_rangement(chemin):
    """RANGEMENT.tsv, plus celui du dossier privé s'il existe."""
    import os
    plan = {}
    prive = os.path.join(_prive(os.path.dirname(os.path.abspath(chemin))), "RANGEMENT.tsv")
    for c in (chemin, prive):
        if not os.path.exists(c):
            continue
        with open(c, encoding="utf-8", newline="") as f:
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
        conf["new"]["perDay"], conf["rev"]["perDay"] = NOUVELLES, REVISIONS
        bilan["cree"] = 1
    elif (conf["new"]["perDay"], conf["rev"]["perDay"]) == (30, 9999):  # anciennes limites du module, jamais retouchées
        conf["new"]["perDay"], conf["rev"]["perDay"] = NOUVELLES, REVISIONS
    conf["newGatherPriority"] = 0  # collecte des nouvelles cartes : par paquet (leçon après leçon)
    conf["newSortOrder"] = 1  # tri : ordre de collecte (l'ordre d'apprentissage calculé)
    conf["newMix"] = 0  # nouvelles cartes mêlées aux révisions
    conf["interdayLearningMix"] = 0
    if not conf.get("desiredRetention"):
        conf["desiredRetention"] = 0.9  # FSRS : 90 % de chances de se souvenir le jour de la révision
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
    bilan["revisions"] = conf["rev"]["perDay"]
    from anki.collection import OpChanges
    return OpChanges(deck_config=True, deck=True)  # réglages : non annulables, modifiables dans les options


# ---------------------------------------------------------------- mise en place complète (et mises à jour)
FICHIERS = ("Vocabulaire", "Phrases", "Exercices", "Grammaire", "Lecture", "Ecoute", "Ecriture")
TYPES = {  # type de note de chaque fichier : le premier nom qui existe dans la collection
    "Phrases": ("Chinois (phrase)",),
    "Ecoute": ("Chinois Audio", "Chinois (ecoute)"),
    "Ecriture": ("Chinois ecriture", "Chinois (ecriture)"),
    "Exercices": ("Chinois Texte", "Chinois (texte)"),
    "Grammaire": ("Chinois (grammaire)",),
    "Lecture": ("Chinois Texte", "Chinois (texte)"),
}


def _type(col, noms):
    for nom in noms:
        m = col.models.by_name(nom)
        if m:
            return m
    return None


def _lire_fichier(chemin):
    """En-têtes et lignes d'un fichier d'import."""
    with open(chemin, encoding="utf-8", newline="") as f:
        lignes = f.read().splitlines()
    entetes = [l for l in lignes if l.startswith("#")]
    rangs = list(csv.reader([l for l in lignes if l and not l.startswith("#")], delimiter="\t", quotechar='"'))
    return entetes, rangs


def _type_existant(col, rectos):
    """Le type des notes de la collection qui ont déjà ces rectos (le plus fréquent), ou None."""
    from collections import Counter
    c = Counter(mid for mid, flds in col.db.execute("select mid, flds from notes") if flds.split("\x1f", 1)[0] in rectos)
    return col.models.get(c.most_common(1)[0][0]) if c else None


def _blocs(dossier):
    """Blocs de TYPES_DE_NOTES.txt : {(type, titre): texte}."""
    import os
    import re
    blocs, courant = {}, None
    with open(os.path.join(dossier, "TYPES_DE_NOTES.txt"), encoding="utf-8") as f:
        for ligne in f.read().splitlines():
            m = re.match(r'^########## "(.+?)" : (.+?) ##########$', ligne)
            if m:
                courant = (m.group(1), m.group(2).split(" (")[0])
                blocs[courant] = []
            elif courant:
                blocs[courant].append(ligne)
    return {k: "\n".join(v).strip("\n") + "\n" for k, v in blocs.items()}


def _changer_type(col, recherche, ancien, nouveau):
    nids = list(col.find_notes(f'{recherche} note:"{ancien["name"]}"'))
    if nids:
        req = col.models.change_notetype_info(old_notetype_id=ancien["id"], new_notetype_id=nouveau["id"]).input
        req.note_ids.extend(nids)
        col.models.change_notetype_of_notes(req)
    return len(nids)


def preparer_types(col, dossier, journal):
    """Type « Chinois (phrase) » (trois cartes) et phrases déjà importées passées à ce type ; notes d'écoute sur
    le type d'écoute, dont le recto joue l'audio HyperTTS du champ « Ajouter le verso »."""
    texte = _type(col, TYPES["Exercices"])
    if texte is None:
        raise Exception("Type « Chinois Texte » (ou « Chinois (texte) ») introuvable : le créer d'abord (TYPES_DE_NOTES.txt).")
    phrase = col.models.by_name("Chinois (phrase)")
    if phrase is None:
        b = _blocs(dossier)
        p = lambda titre: b[("Chinois (phrase)", titre)]
        phrase = col.models.copy(texte, add=False)
        phrase["name"] = "Chinois (phrase)"
        phrase["css"] = p("STYLE")
        phrase["tmpls"][0]["name"] = "Lecture"
        phrase["tmpls"][0]["qfmt"] = p("CARTE 1 LECTURE, MODELE DU RECTO")
        phrase["tmpls"][0]["afmt"] = p("CARTE 1 LECTURE, MODELE DU VERSO")
        for nom, carte in (("Theme", "CARTE 2 THEME"), ("Dictee", "CARTE 3 DICTEE")):
            t = col.models.new_template(nom)
            t["qfmt"] = p(carte + ", MODELE DU RECTO")
            t["afmt"] = p(carte + ", MODELE DU VERSO")
            col.models.add_template(phrase, t)
        col.models.add(phrase)
        phrase = col.models.by_name("Chinois (phrase)")
        journal.append("Type « Chinois (phrase) » créé (cartes Lecture, Theme, Dictee).")
    if col.models.by_name("Chinois (grammaire)") is None:
        b = _blocs(dossier)
        g = lambda titre: b[("Chinois (grammaire)", titre)]
        gram = col.models.copy(texte, add=False)
        gram["name"] = "Chinois (grammaire)"
        gram["css"] = g("STYLE")
        gram["tmpls"][0]["name"] = "Comprendre"
        gram["tmpls"][0]["qfmt"] = g("CARTE 1 COMPRENDRE, MODELE DU RECTO")
        gram["tmpls"][0]["afmt"] = g("CARTE 1 COMPRENDRE, MODELE DU VERSO")
        t = col.models.new_template("Utiliser")
        t["qfmt"] = g("CARTE 2 UTILISER, MODELE DU RECTO")
        t["afmt"] = g("CARTE 2 UTILISER, MODELE DU VERSO")
        col.models.add_template(gram, t)
        col.models.add(gram)
        journal.append("Type « Chinois (grammaire) » créé (cartes Comprendre, Utiliser).")
    n = _changer_type(col, '"deck:Chinois::Phrases"', texte, phrase)
    if n:
        journal.append(f"{n} phrases passées au type « Chinois (phrase) » (progression gardée).")
    audio = _type(col, TYPES["Ecoute"])
    if audio:
        for nom in ("Chinois ecriture", "Chinois (ecriture)", "Chinois Texte", "Chinois (texte)"):
            ancien = col.models.by_name(nom)
            if ancien and ancien["id"] != audio["id"]:
                n = _changer_type(col, '"deck:Chinois::Ecoute"', ancien, audio)
                if n:
                    journal.append(f"{n} notes d'écoute passées du type « {nom} » au type « {audio['name']} ».")
        q = audio["tmpls"][0]["qfmt"]
        if "{{tts zh_CN:Recto}}" in q and "{{Ajouter le verso}}" not in q:
            audio["tmpls"][0]["qfmt"] = q.replace("{{tts zh_CN:Recto}}", "{{Ajouter le verso}}")
            col.models.update_dict(audio)
            journal.append(f"Recto de « {audio['name']} » : l'audio HyperTTS (champ « Ajouter le verso ») remplace la synthèse vocale.")
    preparer_audio(col, journal)
    preparer_rappel(col, journal)
    preparer_consignes(col, journal)


# ---------------------------------------------------------------- phrases : ce que chaque carte attend
# Une phrase a trois cartes ; sans consigne nette, on fait la même chose sur les trois (l'utilisateur, 28/09 :
# « il faut mieux préciser ce que la carte attend de moi, sinon moi je traduis c'est tout »).
CONSIGNES_VERSION = "<!-- consignes phrase v1 -->"
CONSIGNE_LECTURE = ('<div class="consigne">📖 <b>Lecture</b> : lisez la phrase à voix haute (tons compris), puis dites '
                    'ce qu\'elle veut dire. Au verso : pinyin et traduction pour vérifier.</div>')
CONSIGNES_REMPLACEES = {
    "Dites ou écrivez en chinois :": "🗣️ <b>Thème</b> : dites cette phrase en chinois, à voix haute (ou écrivez-la) :",
    "🎧 Écoutez, puis écrivez (ou répétez) la phrase": "🎧 <b>Dictée</b> : écoutez, puis écrivez la phrase en "
                                                     "caractères (réécoutez autant qu'il faut)",
}


CONSIGNES_MOT_VERSION = "<!-- consignes mot v1 -->"
STYLE_CONSIGNE = "font-size:16px;opacity:.75;margin:0 0 8px;text-align:center"
CONSIGNES_MOT = {  # carte du type de vocabulaire -> ce qu'elle attend ; seulement pour les notes du paquet Chinois
    "Carte 1": "🔤 <b>Mot</b> : prononcez-le (tons compris) et donnez son sens.",
    "Carte 2": "✍️ <b>Mot</b> : dites ce mot en chinois, puis écrivez-le en caractères.",
}


def preparer_consignes(col, journal):
    """Consigne propre à chaque carte : types « Chinois (phrase) » (Lecture, Thème, Dictée) et de vocabulaire (sens,
    puis production) ; textes et écoutes : voir RAPPEL. Modèles seulement ; une fois (repères de version)."""
    _consignes_mot(col, journal)
    m = col.models.by_name("Chinois (phrase)")
    if not m or any(CONSIGNES_VERSION in t["qfmt"] for t in m["tmpls"]):
        return
    for t in m["tmpls"]:
        for cote in ("qfmt", "afmt"):
            s = t[cote]
            for ancien, nouveau in CONSIGNES_REMPLACEES.items():
                s = s.replace(ancien, nouveau)
            if t["name"] == "Lecture":
                s = CONSIGNE_LECTURE + "\n" + s
                if cote == "qfmt":  # repère sur la seule carte Lecture (la Dictée n'existe que s'il y a un audio)
                    s = CONSIGNES_VERSION + "\n" + s
            t[cote] = s
    col.models.update_dict(m)
    journal.append("Phrases : chaque carte dit ce qu'elle attend (Lecture, Thème, Dictée).")


def _consignes_mot(col, journal):
    """Vocabulaire : « prononcez-le et donnez son sens » (carte 1), « dites-le en chinois et écrivez-le » (carte 2).
    Affiché seulement pour les notes qui ont un « Texte audio » (celles du paquet Chinois)."""
    m = col.models.by_name("Basique (carte inversée optionnelle)")  # le type du vocabulaire de l'utilisateur
    if not m or TEXTE_AUDIO not in [f["name"] for f in m["flds"]]:
        return
    if any(CONSIGNES_MOT_VERSION in t["qfmt"] for t in m["tmpls"]):
        return
    for t in m["tmpls"]:
        consigne = CONSIGNES_MOT.get(t["name"])
        if consigne:
            t["qfmt"] = (f"{CONSIGNES_MOT_VERSION}\n{{{{#{TEXTE_AUDIO}}}}}<div class=\"consigne-mot\" "
                         f"style=\"{STYLE_CONSIGNE}\">{consigne}</div>{{{{/{TEXTE_AUDIO}}}}}\n" + t["qfmt"])
    col.models.update_dict(m)
    journal.append("Vocabulaire : chaque carte dit ce qu'elle attend (sens, puis le mot en chinois).")


# ---------------------------------------------------------------- rappel actif (chercher avant de voir)
RAPPEL_VERSION = "<!-- rappel actif v2 -->"
RAPPEL = RAPPEL_VERSION + """
<div id="rc-verso" style="display:none">{{Verso}}</div>
<script>
(function () {
  // ce que la carte attend, pour les textes et les écoutes (les exercices ont déjà leur consigne)
  if (document.getElementById('rc-consigne')) return;
  var t = document.querySelector('.texte') || document.querySelector('.card') || document.body;
  var label = document.querySelector('.ecoute-label');
  var html = '';
  if (label && !/dictée/i.test(label.textContent)) {
    html = '🎧 <b>Écoute</b> : écoutez (autant de fois qu\\'il faut), puis répondez aux questions, ou dites ce que vous avez compris.';
  } else if (!label && /^\\s*📖/.test(t.textContent || '')) {
    html = '📖 <b>Lecture</b> : lisez le texte à voix haute, puis répondez aux questions, ou résumez-le en quelques phrases.';
  }
  if (!html) return;
  var d = document.createElement('div');
  d.id = 'rc-consigne';
  d.innerHTML = html;
  d.style.cssText = 'font-size:16px;opacity:.75;margin:0 0 8px;text-align:center';
  t.parentNode.insertBefore(d, t);
})();
</script>
<script>
(function () {
  // rappel actif : chercher la réponse avant de voir les choix ; les questions d'un texte sont posées au recto
  var c = document.querySelector('.texte .choix');
  if (c && !document.getElementById('rc-choix')) {
    c.style.display = 'none';
    var b = document.createElement('div');
    b.id = 'rc-choix';
    b.textContent = 'Voir les choix';
    b.style.cssText = 'display:inline-block;margin:10px 0;padding:4px 14px;border:1px solid #888;' +
      'border-radius:14px;cursor:pointer;font-size:16px;opacity:.8';
    b.onclick = function () { c.style.display = ''; b.parentNode.removeChild(b); };
    c.parentNode.insertBefore(b, c);
  }
  var v = document.getElementById('rc-verso');
  if (!v) return;
  var qs = [], re = /<b>Q :<\\/b>\\s*([\\s\\S]*?)<br>\\s*<b>R :<\\/b>/g, m;
  while ((m = re.exec(v.innerHTML))) qs.push(m[1]);
  v.parentNode.removeChild(v);
  if (!qs.length || document.getElementById('rc-questions')) return;
  var d = document.createElement('div');
  d.id = 'rc-questions';
  d.style.cssText = 'text-align:left;margin-top:14px;font-size:22px;line-height:1.7';
  d.innerHTML = '<b>Questions</b> (répondez avant de retourner la carte) :<br>' +
    qs.map(function (q, i) { return (i + 1) + '. ' + q; }).join('<br>');
  (document.querySelector('.texte') || document.body).appendChild(d);
})();
</script>
<!-- /rappel actif -->"""
TYPES_RAPPEL = ("Chinois Texte", "Chinois (texte)", "Chinois Audio", "Chinois (ecoute)")


def preparer_rappel(col, journal):
    """Recto des exercices : choix cachés derrière « Voir les choix » (on cherche d'abord sans aide) ; recto des
    textes de lecture et d'écoute : leurs questions (réponses au verso). Modèles seulement, sans changer les notes."""
    import re
    n = 0
    for nom in TYPES_RAPPEL:
        m = col.models.by_name(nom)
        if not m:
            continue
        t = m["tmpls"][0]
        if RAPPEL_VERSION in t["qfmt"]:
            continue
        q = re.sub(r"\n*<!-- rappel actif.*?<!-- /rappel actif -->\n*", "\n", t["qfmt"], flags=re.S)
        t["qfmt"] = q.rstrip() + "\n\n" + RAPPEL + "\n"
        col.models.update_dict(m)
        n += 1
    if n:
        journal.append(f"Rappel actif : {n} modèles de recto mis à jour (choix cachés derrière un bouton, questions "
                       "des textes au recto).")


# ---------------------------------------------------------------- audio HyperTTS : un seul audio par note, le bon texte
AUDIO = "Ajouter le verso"  # champ où HyperTTS met l'audio
TEXTE_AUDIO = "Texte audio"  # champ importé (5e colonne des fichiers) : le seul texte à lire
TYPES_CHINOIS = ("Basique (carte inversée optionnelle)", "Chinois Texte", "Chinois (texte)", "Chinois Audio",
                 "Chinois (ecoute)", "Chinois ecriture", "Chinois (ecriture)", "Chinois (phrase)", "Chinois (grammaire)")
# types dont l'audio doit passer au verso (au recto, il donnerait la réponse) ; l'écoute et la dictée le jouent au recto
VERSO_AUDIO = ("Chinois Texte", "Chinois (texte)", "Chinois ecriture", "Chinois (ecriture)", "Chinois (grammaire)")
# audios faits jusqu'ici en lisant le recto (consigne, titre, 男：) : effacés une fois, à refaire depuis « Texte audio »
AUDIO_A_REFAIRE = ("Chinois Texte", "Chinois (texte)", "Chinois Audio", "Chinois (ecoute)", "Chinois ecriture",
                   "Chinois (ecriture)", "Chinois (grammaire)")
VERSION_AUDIO = 1
RECHERCHE_SANS_AUDIO = f'deck:Chinois "{AUDIO}:" -"{TEXTE_AUDIO}:"'


def preparer_audio(col, journal):
    """Champ « Texte audio » dans chaque type de note chinois (changement de structure : la synchronisation suivante
    demandera d'envoyer la collection vers AnkiWeb), audio au verso des exercices, et, une seule fois, ménage des
    anciens audios : doublons retirés, audios lus sur le recto effacés."""
    import re
    ajoutes = []
    for nom in TYPES_CHINOIS:
        m = col.models.by_name(nom)
        if not m:
            continue
        change = False
        if TEXTE_AUDIO not in [f["name"] for f in m["flds"]]:
            col.mod_schema(check=False)
            col.models.add_field(m, col.models.new_field(TEXTE_AUDIO))
            ajoutes.append(nom)
            change = True
        if nom in VERSO_AUDIO:
            for t in m["tmpls"]:
                if "{{" + AUDIO + "}}" not in t["afmt"]:
                    t["afmt"] = t["afmt"].rstrip() + "\n{{" + AUDIO + "}}\n"
                    change = True
        if change:
            col.models.update_dict(m)
    if ajoutes:
        journal.append(f"Champ « {TEXTE_AUDIO} » ajouté à {len(ajoutes)} types de notes (au prochain synchronisme : "
                       "« Envoyer vers AnkiWeb »).")
    if (col.get_config("ranger_chinois_audio", 0) or 0) >= VERSION_AUDIO:
        return
    doublons = effaces = 0
    maj = []
    for nid in col.find_notes("deck:Chinois"):
        note = col.get_note(nid)
        if AUDIO not in note:
            continue
        valeur = note[AUDIO]
        sons = re.findall(r"\[sound:[^\]]+\]", valeur)
        if not sons:
            continue
        if note.note_type()["name"] in AUDIO_A_REFAIRE:
            note[AUDIO] = ""
            effaces += 1
        elif len(sons) != len(set(sons)):
            vus, garder = set(), []
            for s in sons:
                if s not in vus:
                    vus.add(s)
                    garder.append(s)
            note[AUDIO] = " ".join(garder)
            doublons += 1
        else:
            continue
        maj.append(note)
    if maj:
        col.update_notes(maj)
    col.set_config("ranger_chinois_audio", VERSION_AUDIO)
    journal.append(f"Audio : {doublons} notes avec le même audio en double (un seul gardé), {effaces} audios faits en "
                   "lisant le recto effacés (refaits depuis « Texte audio » par « Chinois : ajouter l'audio »).")


def _textes_audio(col):
    """{nid: texte audio} des notes du paquet Chinois."""
    etat = {}
    for nid in col.find_notes("deck:Chinois"):
        note = col.get_note(nid)
        if TEXTE_AUDIO in note:
            etat[nid] = note[TEXTE_AUDIO]
    return etat


def audio_perime(col, avant, journal):
    """Après un import : une note dont le texte à lire a changé perd son ancien audio (à refaire)."""
    maj = []
    for nid, ancien in avant.items():
        if not ancien:
            continue
        note = col.get_note(nid)
        if note[TEXTE_AUDIO] != ancien and note[AUDIO]:
            note[AUDIO] = ""
            maj.append(note)
    if maj:
        col.update_notes(maj)
        journal.append(f"Audio : {len(maj)} notes dont le texte à lire a changé : ancien audio retiré (à refaire).")


def importer(col, dossier, journal):
    """Importe les sept fichiers (mise à jour des notes existantes, sous-paquet lu dans le fichier), avec le type
    de note des notes déjà présentes. Les lignes « a_supprimer » ne sont pas importées : ces anciennes versions
    n'ont rien à faire dans la collection si elles n'y sont plus (le rangement range celles qui y sont encore)."""
    import glob
    import os
    import tempfile
    from anki.collection import ImportCsvRequest
    from anki.import_export_pb2 import CsvMetadata
    fichiers = [(p, p, os.path.join(dossier, f"Chinois__{p}.txt")) for p in FICHIERS]
    # cartes tirées du manuel (dossier privé, hors du dépôt public) : Chinois__Manuel_Textes.txt, _Ecoute, _Exercices…
    for chemin in sorted(glob.glob(os.path.join(_prive(dossier), "Chinois__Manuel_*.txt"))):
        genre = os.path.basename(chemin)[len("Chinois__Manuel_"):-4]
        fichiers.append((f"Manuel · {genre}", "Ecoute" if genre == "Ecoute" else "Exercices", chemin))
    avant = _textes_audio(col)
    for libelle, paquet, chemin in fichiers:
        if not os.path.exists(chemin):
            continue
        entetes, rangs = _lire_fichier(chemin)
        rangs = [r for r in rangs if len(r) > 2 and "a_supprimer" not in r[2].split()]
        nt = _type_existant(col, {r[0] for r in rangs})
        if nt is None:
            nt = col.models.by_name("Basique (carte inversée optionnelle)") if paquet == "Vocabulaire" else _type(col, TYPES[paquet])
        if nt is None:
            journal.append(f"{libelle} : type de note introuvable, fichier non importé.")
            continue
        fd, temp = tempfile.mkstemp(suffix=".txt", prefix=f"Chinois__{paquet}_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write("\n".join(entetes) + "\n")
                csv.writer(f, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(rangs)
            md = col.get_csv_metadata(path=temp, delimiter=None)
            md.global_notetype.id = nt["id"]
            # colonnes : 1 recto, 2 verso, 3 étiquettes, 4 sous-paquet, 5 texte audio ; « Ajouter le verso » (l'audio
            # HyperTTS) n'a pas de colonne : l'import n'y touche jamais
            del md.global_notetype.field_columns[:]
            md.global_notetype.field_columns.extend(
                {"Recto": 1, "Verso": 2, TEXTE_AUDIO: 5}.get(f["name"], 0) for f in nt["flds"])
            md.dupe_resolution = CsvMetadata.DupeResolution.UPDATE
            log = col.import_csv(ImportCsvRequest(path=temp, metadata=md)).log
        finally:
            os.remove(temp)
        # Anki range les notes mises à jour (repérées par leur recto) dans first_field_match, les inchangées dans duplicate
        journal.append(f"{libelle} ({nt['name']}) : {len(log.new)} nouvelles notes, "
                       f"{len(log.updated) + len(log.first_field_match)} mises à jour"
                       + (f", {len(log.conflicting)} en conflit de type" if log.conflicting else ""))
    audio_perime(col, avant, journal)
    n = len(col.find_notes(RECHERCHE_SANS_AUDIO))
    if n:
        journal.append(f"Audio à faire : {n} notes (Outils > « Chinois : ajouter l'audio (Google Traduction) »).")


def mettre_en_place(col, dossier, journal, supprimer=True):
    """Tout, la première fois et à chaque nouvelle version : types de notes, import, rangement, réglages, paquet « À supprimer » vidé."""
    import os
    preparer_types(col, dossier, journal)
    importer(col, dossier, journal)
    bilan = defaultdict(int)
    ranger(col, lire_rangement(os.path.join(dossier, "RANGEMENT.tsv")), bilan)
    journal.append(f"Rangement : {bilan['deplacees']} cartes déplacées dans leur leçon, {bilan['placees']} cartes "
                   f"nouvelles remises dans l'ordre, {bilan['vides']} paquets vides supprimés"
                   + (f", {bilan['inconnues']} notes inconnues laissées en place" if bilan["inconnues"] else "") + ".")
    b2 = defaultdict(int)
    reglages(col, b2)
    if not col.get_config("fsrs", False):  # planificateur FSRS (toute la collection), rétention 0,90
        col.set_config("fsrs", True)
        journal.append("FSRS activé pour la collection (Outils > Préférences > Révision pour le couper), "
                       "rétention souhaitée 0,90 pour le chinois.")
    journal.append(f"Réglages « {GROUPE} » appliqués à {b2['paquets']} paquets ({b2['par_jour']} nouvelles cartes et {b2['revisions']} révisions par jour).")
    did = col.decks.id_for_name(RACINE + "::9 · À supprimer")
    if supprimer and did:
        n = col.decks.card_count(did, include_subdecks=True)
        col.decks.remove([did])
        journal.append(f"Paquet « 9 · À supprimer » supprimé ({n} cartes remplacées par une version corrigée).")
    from anki.collection import OpChanges
    return OpChanges(card=True, note=True, deck=True, notetype=True, deck_config=True, study_queues=True,
                     browser_table=True, browser_sidebar=True, note_text=True)
