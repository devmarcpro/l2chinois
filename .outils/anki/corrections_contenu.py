# -*- coding: utf-8 -*-
"""Corrections de contenu (fautes de chinois, contresens, pinyin, étiquettes), relues une à une.

Elles sont décrites dans corrections_contenu.json (produit par construire_corrections.py à partir des relectures) ;
chaque entrée vise une note par l'empreinte de son recto d'origine :
  {"paquet", "cle", "apercu", "champ": "RECTO|VERSO|ETIQUETTES", "ancien", "nouveau", "probleme"}
  {..., "pinyin": {"mot", "caractere", "lecture_juste"}}      lecture imposée dans cette note
  {..., "refaire": {"recto", "verso"}}                        carte réécrite (HTML)
  {..., "niveau": 4}                                          niveau utilisé pour le rangement
  {..., "doublon": "titre de la carte conservée"}             carte en double : marquée à supprimer
"mots" (en tête du fichier) : lectures de mots valables partout, ajoutées au dictionnaire de pinyin.

Quand le recto d'une note change, Anki ne peut plus la reconnaître : la note corrigée est ajoutée comme nouvelle carte,
et l'ancienne est gardée avec l'étiquette a_supprimer et un verso qui dit qu'elle est remplacée.
"""
import hashlib
import html
import json
import re
from pathlib import Path

from pypinyin import load_phrases_dict

from pinyin_correct import CJK, ton

FICHIER = Path(__file__).with_name("corrections_contenu.json")
UNITE = re.compile(r"<ruby>(.)<rt[^>]*>[^<]*</rt></ruby>|<[^>]+>|&[#\w]+;|.", re.S)
RUBY = re.compile(r'<ruby>(.)<rt class="t\d">([^<]*)</rt></ruby>')
BLOC = re.compile(r'(?:<ruby>.<rt class="t\d">[^<]*</rt></ruby>|[，。！？、；：,.!?“”"‘’《》（）()…—·\s])+')
SPAN = re.compile(r'<span class="t\d">([^<]+)</span>')
PINYIN_CROCHETS = re.compile(r"\s*\[[A-Za-zǜ-ͯāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹ'’ ,.?!…\-]*\]")
REMPLACEE = ("<b>Carte remplacée.</b><br><br>Une faute dans l'énoncé a été corrigée : la version juste est une nouvelle carte du même paquet. "
             "Celle-ci peut être supprimée (dans le navigateur d'Anki : <i>tag:a_supprimer</i>).")
DOUBLON = ("<b>Carte en double.</b><br><br>Le même point est traité par la fiche « {} ». "
           "Celle-ci peut être supprimée (dans le navigateur d'Anki : <i>tag:a_supprimer</i>).")


def cle(recto: str) -> str:
    return hashlib.sha1(recto.encode("utf-8")).hexdigest()[:16]


def charger():
    if not FICHIER.exists():
        return {}, {}
    donnees = json.loads(FICHIER.read_text(encoding="utf-8"))
    mots = {m: [[s] for s in l.split()] for m, l in donnees.get("mots", {}).items()}
    if mots:
        load_phrases_dict(mots)
    par_note = {}
    for e in donnees.get("corrections", []):
        par_note.setdefault((e["paquet"], e["cle"]), []).append(e)
    return par_note, donnees.get("mots", {})


PAR_NOTE, MOTS = charger()
NIVEAUX = {}      # (paquet, recto) -> niveau de rangement imposé
bilan = {"appliquées": 0, "cartes remplacées": 0, "échecs": []}


# ------------------------------------------------------------------ remplacement de texte dans un champ HTML
def _norme(c: str) -> str:
    return " " if c.isspace() or c == "\xa0" else {"’": "'", "‘": "'"}.get(c, c)


def _plan(champ: str):
    """Texte lisible du champ et, pour chacun de ses caractères, sa place dans le HTML : (début, fin, est_ruby)."""
    texte, places = [], []
    for m in UNITE.finditer(champ):
        s = m.group(0)
        if m.group(1):
            c, rb = m.group(1), True
        elif s.startswith("<") and len(s) > 1:
            if not re.match(r"<br|</div|</p|</li", s):
                continue
            c, rb = " ", False
        else:
            c, rb = _norme(html.unescape(s)), False
        if c == " " and (not texte or texte[-1] == " "):
            continue
        for x in c:  # une entité peut donner plusieurs caractères
            texte.append(x)
            places.append((m.start(), m.end(), rb))
    return "".join(texte), places


def _latin(c: str) -> bool:
    return c.isalpha() and not CJK.match(c)


def remplacer(champ: str, ancien: str, nouveau: str):
    """Renvoie (champ corrigé, nombre de remplacements, problème éventuel)."""
    from contenu_cours import ruby
    # les relectures citent le pinyin entre crochets (« 催促 [cuī cù] = presser ») : il n'est pas dans le texte du champ
    ancien, nouveau = PINYIN_CROCHETS.sub("", ancien), PINYIN_CROCHETS.sub("", nouveau)
    cherche = "".join(_norme(c) for c in " ".join(ancien.split()))
    lignes = [" ".join(l.split()) for l in nouveau.splitlines() if l.strip()]
    nouveau = " ".join(nouveau.split())
    if not cherche.strip():
        return champ, 0, "extrait vide une fois le pinyin retiré"
    texte, places = _plan(champ)
    # on ne remplace que la partie qui change, pour passer outre les balises (gras, retours à la ligne) du reste de l'extrait
    prefixe = 0
    while prefixe < min(len(cherche), len(nouveau)) and cherche[prefixe] == nouveau[prefixe]:
        prefixe += 1
    suffixe = 0
    while suffixe < min(len(cherche), len(nouveau)) - prefixe and cherche[-1 - suffixe] == nouveau[-1 - suffixe]:
        suffixe += 1
    trouves = []
    for m in re.finditer(re.escape(cherche), texte):
        d, f = m.start(), m.end()
        # un mot tronqué (« professeu ») ne doit pas être « corrigé » dans « professeur »
        if _latin(cherche[-1]) and f < len(texte) and _latin(texte[f]):
            continue
        if _latin(cherche[0]) and d > 0 and _latin(texte[d - 1]):
            continue
        trouves.append(d)
    if not trouves:
        return champ, 0, "extrait introuvable"
    for d in reversed(trouves):
        f, vise = d + len(cherche), cherche
        reste = texte[f:].strip()
        if len(reste) > 2 and nouveau.endswith(reste):  # « nouveau » redonne toute la suite du champ : on remplace jusqu'au bout
            f, vise = len(texte), texte[d:]
            prefixe = suffixe = 0
            while prefixe < min(len(vise), len(nouveau)) and vise[prefixe] == nouveau[prefixe]:
                prefixe += 1
            while suffixe < min(len(vise), len(nouveau)) - prefixe and vise[-1 - suffixe] == nouveau[-1 - suffixe]:
                suffixe += 1
        d0, f0 = d + prefixe, f - suffixe                          # partie qui change, dans le texte lisible
        milieu = nouveau[prefixe:len(nouveau) - suffixe]
        if f0 <= d0:                                              # pure insertion : on remplace le caractère voisin avec
            if f0 > d:
                d0, f0, milieu = f0 - 1, f0, texte[f0 - 1] + milieu
            else:
                d0, f0, milieu = d0, d0 + 1, milieu + texte[d0]
        debut, fin = places[d0][0], places[f0 - 1][1]
        morceau = champ[debut:fin]
        en_ruby = any(p[2] for p in places[d0:f0])
        if "<" in RUBY.sub("", morceau):  # balises (gras, retours à la ligne) dans la partie qui change : on remplace tout l'extrait
            debut, fin = places[d][0], places[f - 1][1]
            en_ruby = any(p[2] for p in places[d:f])
            milieu = nouveau if len(lignes) < 2 else None
        if milieu is None:
            rendu = "<br><br>".join(html.escape(l, quote=False) for l in lignes)
        else:
            rendu = ruby(milieu) if en_ruby else html.escape(milieu, quote=False)
        champ = champ[:debut] + rendu + champ[fin:]
    return champ, len(trouves), None


# ------------------------------------------------------------------ lecture imposée dans une note
def imposer_lecture(champ: str, mot: str, caractere: str, lecture: str, phrase: str = ""):
    """Impose la lecture de `caractere` dans chaque occurrence de `mot` annotée en ruby (dans les blocs contenant `phrase`,
    si elle est donnée). Renvoie (champ, nombre)."""
    fait = 0
    phrase_cjk = "".join(CJK.findall(phrase))

    def un_bloc(m):
        nonlocal fait
        bloc = m.group(0)
        paires = RUBY.findall(bloc)
        hanzi = "".join(p[0] for p in paires)
        if phrase_cjk and phrase_cjk not in hanzi and hanzi not in phrase_cjk:
            return bloc
        cibles = {d + k for d in (x.start() for x in re.finditer(re.escape(mot), hanzi)) for k, c in enumerate(mot) if c == caractere}
        if not cibles:
            return bloc
        fait += len(cibles)
        it = iter(range(len(paires)))
        return RUBY.sub(lambda r: (f'<ruby>{r.group(1)}<rt class="t{ton(lecture)}">{lecture}</rt></ruby>' if next(it) in cibles else r.group(0)), bloc)
    return BLOC.sub(un_bloc, champ), fait


def imposer_lecture_spans(segment: str, texte: str, mot: str, caractere: str, lecture: str):
    """Même chose pour une suite de <span class="tN">syllabe</span> alignée sur les caractères de `texte`."""
    cars = CJK.findall(texte)
    hanzi = "".join(cars)
    if len(SPAN.findall(segment)) != len(cars):
        return segment, 0
    cibles = {d + k for d in (x.start() for x in re.finditer(re.escape(mot), hanzi)) for k, c in enumerate(mot) if c == caractere}
    it = iter(range(len(cars)))

    def un(s):
        if next(it) not in cibles:
            return s.group(0)
        neuf = lecture.capitalize() if s.group(1)[:1].isupper() else lecture
        return f'<span class="t{ton(lecture)}">{neuf}</span>'
    return SPAN.sub(un, segment), len(cibles)


def _imposer(paquet, note, e):
    p = e["pinyin"]
    mot, car, lecture = p.get("mot") or p["caractere"], p["caractere"], p["lecture_juste"]
    total = 0
    recto_nu = html.unescape(re.sub(r"<[^>]+>", "", note[0]))
    if paquet in ("Vocabulaire", "Phrases") and mot in recto_nu:  # pinyin principal de la carte
        tete, sep, reste = note[1].partition('<div class="exemple-bloc"')
        morceaux = tete.split("<br>")
        for i, morceau in enumerate(morceaux):
            if SPAN.search(morceau):
                morceaux[i], n = imposer_lecture_spans(morceau, recto_nu, mot, car, lecture)
                total += n
                break
        note[1] = "<br>".join(morceaux) + sep + reste
    if paquet == "Grammaire":
        def exemple(m):
            nonlocal total
            seg, n = imposer_lecture_spans(m.group(4), m.group(2), mot, car, lecture)
            total += n
            return m.group(1) + m.group(2) + m.group(3) + seg + m.group(5)
        note[1] = re.sub(r"(•\s*)([^<]+)(<br><small>)(.*?)(</small>)", exemple, note[1])
    phrase = p.get("phrase", "")
    note[1], n = imposer_lecture(note[1], mot, car, lecture, phrase)
    if paquet != "Vocabulaire":
        note[0], n0 = imposer_lecture(note[0], mot, car, lecture, phrase)
        n += n0
    return total + n


# ------------------------------------------------------------------ en-têtes régénérés quand le recto change
def _entete_phrase(recto_nu: str, verso: str, paquet: str) -> str:
    """Refait la ligne traditionnelle et la ligne de pinyin d'une note Phrases / Vocabulaire dont le recto a changé."""
    from contenu_cours import lire_phrase, span, spans_par_syllabe
    from corriger_decks import vers_trad
    verso = re.sub(r'(<span class="hanzi-trad">)[^<]*(</span>)', lambda m: m.group(1) + vers_trad(recto_nu) + m.group(2), verso, count=1)
    tete, sep, reste = verso.partition('<div class="exemple-bloc"')
    morceaux = tete.split("<br>")
    for i, morceau in enumerate(morceaux):
        if SPAN.search(morceau):
            morceaux[i] = spans_par_syllabe(recto_nu) if paquet == "Phrases" else "".join(span(l) for l in lire_phrase(recto_nu))
            break
    return "<br>".join(morceaux) + sep + reste


def _exemple_grammaire(verso: str, ancien: str, nouveau: str):
    """Remplace une phrase d'exemple d'une fiche de grammaire et refait sa ligne de pinyin."""
    from contenu_cours import spans_par_mot
    motif = re.compile(r"(•\s*)" + re.escape(ancien) + r"(<br><small>).*?(</small>)")
    if not motif.search(verso):
        return verso, 0
    return motif.sub(lambda m: m.group(1) + nouveau + m.group(2) + spans_par_mot(nouveau) + m.group(3), verso, count=1), 1


# ------------------------------------------------------------------ application à une note
def appliquer(paquet: str, recto_origine: str, note):
    """note : [recto, verso, champ 3, étiquettes] déjà passée par la correction du pinyin. Renvoie la liste des notes à écrire."""
    from corriger_decks import corriger_ruby
    entrees = PAR_NOTE.get((paquet, cle(recto_origine)))
    if not entrees:
        return [note]
    note = list(note)
    for e in entrees:
        ok, probleme = True, None
        if "niveau" in e:
            NIVEAUX[(paquet, recto_origine)] = e["niveau"]
        elif "doublon" in e:
            note[1] = DOUBLON.format(e["doublon"])
            note[3] = (note[3] + " a_supprimer").strip()
        elif "refaire" in e:
            note[0], note[1] = e["refaire"].get("recto") or note[0], e["refaire"]["verso"]
        elif "pinyin" in e:
            ok = _imposer(paquet, note, e) > 0
            probleme = "mot introuvable dans le pinyin de la note"
        elif e["champ"] == "ETIQUETTES":
            etiquettes = [t for t in note[3].split() if t != e["ancien"]]
            ok = len(etiquettes) != len(note[3].split())
            probleme = "étiquette absente"
            note[3] = " ".join(etiquettes + ([e["nouveau"]] if e.get("nouveau") and e["nouveau"] not in etiquettes else []))
        else:
            i = 0 if e["champ"] == "RECTO" else 1
            n = 0
            if paquet == "Grammaire" and i == 1 and CJK.search(e["ancien"]) and not re.search(r"[a-zA-Z]", e["ancien"]):
                note[1], n = _exemple_grammaire(note[1], e["ancien"], e["nouveau"])
            if n == 0 and paquet == "Grammaire" and i == 1 and re.fullmatch(r"[a-zǜ-ͯāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ' ,?!.…\[\]]+", e["ancien"]):
                ok, probleme = False, "ligne de pinyin : refaite avec la phrase"
            else:
                if n == 0:
                    note[i], n, probleme = remplacer(note[i], e["ancien"], e["nouveau"])
                ok = n > 0
                if ok and "<ruby>" in note[i] and CJK.search(e["nouveau"]):
                    note[i] = corriger_ruby(note[i], paquet)  # le sandhi dépend du contexte : on relit le bloc entier
        if ok:
            bilan["appliquées"] += 1
        else:
            bilan["échecs"].append((paquet, e.get("id", ""), e.get("apercu", ""), e.get("ancien", e.get("pinyin")), probleme))
    if note[0] != recto_origine and paquet in ("Phrases", "Vocabulaire"):
        note[1] = _entete_phrase(html.unescape(re.sub(r"<[^>]+>", "", note[0])).strip(), note[1], paquet)
    if (paquet, recto_origine) in NIVEAUX:
        NIVEAUX[(paquet, note[0])] = NIVEAUX[(paquet, recto_origine)]
    if note[0] == recto_origine:
        return [note]
    bilan["cartes remplacées"] += 1
    note[3] = (note[3] + " corrige_2026").strip()
    return [note, [recto_origine, REMPLACEE, "", (note[3].replace("corrige_2026", "") + " a_supprimer").strip()]]
