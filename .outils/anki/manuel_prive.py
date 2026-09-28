# -*- coding: utf-8 -*-
"""Cartes tirées du manuel de la fac (Méthode de chinois, Inalco), gardées HORS du dépôt public (droits d'auteur).

Entrée : Anki/prive/manuel/<leçon>.json, transcription de chaque leçon (vocabulaire, caractères, textes et
dialogues, grammaire, lexicologie, expressions, exercices avec leurs réponses), faite page par page d'après les
PDF de l'utilisateur. Sortie, dans Anki/prive (ignoré par git) :
- Chinois__Manuel_Textes.txt : les textes de la partie écrite (lecture : texte ; verso : pinyin, traduction) ;
- Chinois__Manuel_Ecoute.txt : les dialogues de la partie orale (écoute, comme le paquet Écoute) ;
- Chinois__Manuel_Grammaire.txt : les exemples de grammaire, de lexicologie et d'expressions (phrase à
  comprendre ; verso : pinyin, traduction, point du manuel) ;
- Chinois__Manuel_Exercices.txt : les exercices du manuel qui ont une réponse (corrigé ou réponse déduite) ;
- RANGEMENT.tsv : paquet (la leçon) et rang de chaque note, que le module « Ranger mon chinois » lit en plus du
  RANGEMENT.tsv public. Les rangs reprennent ceux des cartes publiques de la leçon (exemples au milieu, exercices
  ensuite, textes et dialogues à la fin), pour ne rien changer aux fichiers publics.
Une note dont le recto disparaît (transcription corrigée) reste dans le fichier avec l'étiquette a_supprimer.

python manuel_prive.py   (après corriger_decks.py, qui écrit le RANGEMENT.tsv public)
"""
import csv
import html
import json
import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
PRIVE = RACINE / "Anki" / "prive"
PUBLIC = RACINE / "Anki" / "corrige"
CJK = re.compile(r"[一-鿿]")
EN_TETE = "#separator:tab\n#html:true\n#tags column:3\n#deck column:4\n"
A_SUPPRIMER = "Chinois::9 · À supprimer"


def _t(s) -> str:
    return html.escape(re.sub(r"\s*\[\d{3}\]", "", str(s or "")), quote=False)  # sans les numéros de piste [047]


def _lignes(x):
    if isinstance(x, list):
        return [str(l) for l in x if str(l).strip()]
    return [l for l in str(x or "").split("\n") if l.strip()]


def _pinyin(zh: str) -> str:
    from contenu_cours import spans_par_mot
    if not CJK.search(zh):
        return ""
    p = spans_par_mot(zh)
    if "儿" in zh:  # 儿 : ér quand c'est un mot (儿子), r collé pour le suffixe (一下儿 yíxiàr), comme dans les paquets publics
        from erhua import _lignes
        p = _lignes(p, zh)
    return re.sub(r"\s*\)", ")", re.sub(r"\(\s*", " (", p)).strip()  # « nǐ (de) lǎoshī »


# numéro du livre en tête d'un énoncé ou d'un exemple : « 1. », « 2、 », « 8.1.1 », « a.1. », « (7a) »
NUMERO = re.compile(r"^\s*(?:\d+(?:\.\d+)+\.?\s+|\d+[.)、]\s*|[a-z](?:\.\d+)*[.)]\s+|\(\d+[a-z]?\)\s*)")


def _zh_carte(zh: str) -> str:
    """Phrase chinoise d'un exemple, telle qu'elle va sur la carte : sans le numéro du livre ni les annotations
    entre parenthèses qui donneraient la réponse (« 派(pài : envoyer) », « （了+啊） ») ; les mots facultatifs
    entre parenthèses (« 你(的)老师 ») restent."""
    zh = NUMERO.sub("", zh)
    zh = re.sub(r"\s*[（(][^（）()]*[A-Za-zÀ-ÿāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ+:：*＊][^（）()]*[）)]", "", zh)
    return zh.strip()


def _libelle(lecon: str) -> str:
    if lecon == "P1-Lab":
        return "1er niveau · introduction"
    return ("1er niveau" if lecon.startswith("P1") else "2e niveau") + " · " + lecon[3:]


def _etiquettes(lecon, genre):
    return f"manuel_prive {genre} manuel::{lecon}"


def _bloc_traduction(zh_lignes, fr_lignes, pinyin_imprime=None, propose=False):
    pin = pinyin_imprime or [_pinyin(l) for l in zh_lignes]
    corps = "<br>".join(p for p in pin if p)
    s = f'<div class="exemple-bloc" style="text-align:left"><b>Pinyin :</b><br>{corps}'
    if fr_lignes:
        s += (f"<br><br><b>Traduction{' (proposée)' if propose else ''} :</b><br><i>"
              + "<br>".join(_t(l) for l in fr_lignes) + "</i>")
    return s + "</div>"


def _tri():
    """Tri des exercices (manuel/tri_exercices.json : leçon -> indice de l'exercice -> garder / limiter / retirer) :
    seuls les items qui valent une carte (demande de l'utilisateur, 27/09/2026 : trop d'exercices, séries
    répétitives, exercices qui demandent le livre)."""
    f = PRIVE / "manuel" / "tri_exercices.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


VERBES_CONSIGNE = re.compile(
    r"\b(Traduisez|Complétez|Choisissez|Remettez|Insérez|Mettez|Remplacez|Corrigez|Réécrivez|Refaites|Transformez|"
    r"Répondez|Lisez|Écrivez|Transcrivez|Reconstruisez|Remplissez|Distinguez|Posez|Faites|Reliez|Trouvez|Dites|"
    r"Donnez|Formulez|Utilisez|Simplifiez|Cherchez|Indiquez|Observez|Relevez|Racontez|Présentez|Décrivez)\b", re.I)


def _consigne(consigne: str, enonce: str) -> str:
    """Consigne qui dit quoi faire : le livre écrit « Thème. » (traduire en chinois), met un simple titre en tête
    des révisions (« Les locatifs ») ou juste « 剩 ou 留 ? » (l'utilisateur, 28/09 : « pourquoi juste “thème.” ? »)."""
    c = consigne.strip()
    if re.fullmatch(r"Thème\s*[.:]?", c, re.I):
        return "Traduisez en chinois :"
    if re.fullmatch(r"Version\s*[.:]?", c, re.I):
        return "Traduisez en français :"
    if re.fullmatch(r"[一-鿿/ ,，、]+(?:\s+ou\s+[一-鿿/ ,，、]+)+\s*[?？:：.]?", c):  # « 剩 ou 留 ? »
        return f"Complétez avec {c.rstrip(' ?？:：.')} :"
    if not VERBES_CONSIGNE.search(c):  # un titre de révision
        titre = c.rstrip(" .:")
        traduction = re.match(r"Traduction (?:du |de la |de l'|des |d')?(.+)", titre)
        if traduction and not CJK.search(enonce):  # « Traduction du passé composé français. »
            return f"Traduisez en chinois (révision : {traduction.group(1)}) :"
        if VERBES_CONSIGNE.match(enonce.strip()):  # l'énoncé donne déjà l'instruction
            return f"Révision — {titre}"
        return f"Révision — {titre} : traduisez en chinois :" if not CJK.search(enonce) else f"Révision — {titre} :"
    return consigne


def _cartes_grammaire():
    """Relecture des exemples (manuel/cartes_grammaire.json : leçon -> "rubrique|indice du point" -> cartes
    {e, mode, fr, note}) : l'utilisateur trouvait « débiles ou incomplètes » les cartes faites de tous les exemples
    (« (réponse) » en guise de traduction, listes d'heures…)."""
    f = PRIVE / "manuel" / "cartes_grammaire.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def notes_lecon(d):
    """(genre de fichier, note) pour une leçon transcrite."""
    lecon = d["lecon"]
    lib = _libelle(lecon)
    out = []
    for t in d.get("textes", []):
        zh = _lignes(t.get("zh"))
        titre = t.get("titre") or t.get("id") or ""
        if not zh:  # texte long, non recopié (seulement résumé) : « relisez-le dans le livre » n'est pas une carte
            continue
        fr = _lignes(t.get("fr"))
        pin = [_t(p) for p in _lignes(t.get("pinyin"))] if len(_lignes(t.get("pinyin"))) == len(zh) else None
        texte = "<br>".join(_t(l) for l in zh)
        if t.get("partie") == "oral":
            recto = (f'<div class="ecoute-label">{lib} · manuel · {_t(titre)}</div><div class="ecoute-audio">🔊</div>'
                     f'<div class="ecoute-texte">{texte}</div>')
            verso = f'<div class="ecoute-reveal">{texte}</div><br>{_bloc_traduction(zh, fr, pin, t.get("fr_propose"))}'
            out.append(("Ecoute", [recto, verso, _etiquettes(lecon, "manuel_dialogue")]))
        else:
            recto = (f'<div style="text-align:left;font-size:20px;color:#888;margin-bottom:8px">📖 {_t(titre)} | {lib} · manuel</div>'
                     f'<div style="text-align:left;font-size:28px;line-height:1.8">{texte}</div>')
            out.append(("Textes", [recto, _bloc_traduction(zh, fr, pin, t.get("fr_propose")),
                                   _etiquettes(lecon, "manuel_texte")]))
    # exemples de grammaire, de lexicologie et d'expressions : seulement ceux retenus à la relecture
    # (manuel/cartes_grammaire.json : 2 au plus par point, traduction complète, note sur ce qu'il faut remarquer),
    # à comprendre (chinois -> français) ou à produire (français -> chinois)
    retenus = _cartes_grammaire().get(lecon, {})
    for rubrique, cle in (("grammaire", "grammaire"), ("lexicologie", "lexicologie"), ("expressions", "expressions")):
        for gi, g in enumerate(d.get(cle, [])):
            titre = " ".join(x for x in (g.get("numero", ""), g.get("titre", "")) if x).strip()
            titre = re.sub(r"\s*\[[^\]]*\]", "", titre).strip(" :")  # remarques de transcription (« [titre effacé…] »)
            if not re.search(r"[A-Za-zÀ-ÿ一-鿿]", titre):
                titre = rubrique.capitalize()
            for c in retenus.get(f"{cle}|{gi}", []):
                zh = _zh_carte(str(g["exemples"][c["e"]].get("zh", "")))
                bloc = f'<div class="exemple-bloc" style="text-align:left"><b>{_t(titre)}</b><br>{_t(c["note"])}</div>'
                if c["mode"] == "produire":
                    recto = (f'<small>Manuel · {lib} · {rubrique}</small><br><br>Dites en chinois :<br><br>'
                             f'<span style="font-size:130%">{_t(c["fr"])}</span>')
                    verso = f'<span style="font-size:130%">{_t(zh)}</span><br>{_pinyin(zh)}<br><br>{bloc}'
                else:
                    recto = (f'<small>Manuel · {lib} · {rubrique}</small><br><br>Que veut dire cette phrase ?<br><br>'
                             f'<span style="font-size:130%">{_t(zh)}</span>')
                    verso = f"{_pinyin(zh)}<br><i>{_t(c['fr'])}</i><br><br>{bloc}"
                out.append(("Grammaire", [recto, verso, _etiquettes(lecon, f"manuel_{rubrique}")]))
    tri = _tri().get(lecon, {})
    for j, x in enumerate(d.get("exercices", [])):
        if re.search(r"[ÉéE]coutez|enregistrement|entendez", str(x.get("consigne", ""))):
            continue  # exercices d'écoute : sans l'enregistrement, la carte n'a pas de sens
        decision = tri.get(str(j), {})
        if decision.get("decision") == "retirer":
            continue
        gardes = set(decision.get("garder", [])) if decision.get("decision") == "limiter" else None
        dictee = str(x.get("consigne", "")).startswith("Dictée")
        for k, it in enumerate(x.get("items", []), 1):
            rep = str(it.get("reponse", "")).strip()
            brut = str(it.get("enonce", "")).strip()
            enonce = NUMERO.sub("", brut).strip() or brut  # le numéro du livre est déjà dans le titre
            if not rep or not enonce or x.get("type") == "reponse_libre" or (gardes is not None and k not in gardes):
                continue
            if dictee:  # dictée : la phrase se fait entendre au recto (audio HyperTTS), on l'écrit en caractères
                texte = _t(rep)
                recto = (f'<div class="ecoute-label">{lib} · manuel · dictée {_t(x.get("numero", ""))}.{k} : '
                         f'écrivez la phrase en caractères</div><div class="ecoute-audio">🔊</div>'
                         f'<div class="ecoute-texte">{texte}</div>')
                verso = f'<div class="ecoute-reveal">{texte}</div><br>{_bloc_traduction([rep], [])}'
                out.append(("Ecoute", [recto, verso, _etiquettes(lecon, "manuel_dictee")]))
                continue
            quelle = "révision" if x.get("partie") == "revision" else "exercice"
            recto = (f"<small>Manuel · {lib} · {quelle} {_t(x.get('numero', ''))}.{k}</small><br><br>"
                     f"{_t(_consigne(str(x.get('consigne', '')), enonce))}<br><br>{_t(enonce)}")
            verso = f"<b>Réponse :</b> {_t(rep)}"
            if len(CJK.findall(rep)) >= 2 and not re.search(r"[A-Za-zÀ-ÿ]{3,}", rep):  # réponse en chinois
                verso += f"<br><small>{_pinyin(rep)}</small>"
            if it.get("source_reponse") == "déduit":
                verso += "<br><br><small>(réponse proposée : pas de corrigé dans le manuel)</small>"
            from audio import texte_exercice_manuel
            out.append(("Exercices", [recto, verso, _etiquettes(lecon, "manuel_exercice"),
                                      texte_exercice_manuel(enonce, rep)]))
    return out


def _rangs_publics():
    """paquet -> [(rang, recto)] des cartes publiques, dans l'ordre."""
    par = {}
    with open(PUBLIC / "RANGEMENT.tsv", encoding="utf-8", newline="") as f:
        for r in csv.reader((l for l in f if not l.startswith("#")), delimiter="\t"):
            if len(r) >= 3 and r[2].isdigit():
                par.setdefault(r[1], []).append((int(r[2]), r[0]))
    return {k: sorted(v) for k, v in par.items()}


FAMILLE = {"Exercices": "exercice", "Grammaire": "grammaire", "Textes": "texte", "Ecoute": "texte"}
FAMILLE_PUBLIQUE = {}


def _familles_publiques():
    """recto -> famille des cartes publiques (pour ne pas mettre un exercice privé juste après un exercice)."""
    fam = {"Vocabulaire": "mot", "Phrases": "phrase", "Exercices": "exercice", "Grammaire": "grammaire",
           "Lecture": "texte", "Ecoute": "texte", "Ecriture": "ecriture"}
    out = {}
    for nom, f in fam.items():
        for r in _lire(PUBLIC / f"Chinois__{nom}.txt"):
            out[r[0]] = f
    return out


def _lire(chemin):
    if not chemin.exists():
        return []
    lignes = chemin.read_text(encoding="utf-8").splitlines()
    return list(csv.reader([l for l in lignes if l and not l.startswith("#")], delimiter="\t", quotechar='"'))


def _sous_genre(n) -> str:
    return next((t for t in n[2].split() if t.startswith("manuel_")), "")


def _entrelacer(ns):
    """Les notes d'une leçon, genres mêlés (tour à tour, chaque genre réparti sur toute la leçon)."""
    par = {}
    for genre, n in ns:
        par.setdefault(genre, []).append(n)
    total = sum(len(v) for v in par.values())
    places = {g: 0 for g in par}
    out = []
    while len(out) < total:
        t = len(out)
        g = max((g for g in par if places[g] < len(par[g])),
                key=lambda g: (t + 1) * len(par[g]) / total - places[g])
        out.append((g, par[g][places[g]]))
        places[g] += 1
    return out


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from audio import texte_audio
    from manuel import INF, Manuel, nu
    m = Manuel()
    publics_par_paquet = _rangs_publics()
    FAMILLE_PUBLIQUE.update(_familles_publiques())
    fichiers = {g: [] for g in ("Textes", "Ecoute", "Grammaire", "Exercices")}
    rangement = []
    par_lecon = {}  # leçon -> [(genre, note)] ; l'introduction (leçons a, b) passe en tête de la leçon 1
    for chemin in sorted((PRIVE / "manuel").glob("P?-L*.json"), key=lambda c: (c.stem.replace("Lab", "L00"))):
        d = json.loads(chemin.read_text(encoding="utf-8"))
        i = m.index.get("P1-L01" if d["lecon"] == "P1-Lab" else d["lecon"])
        if i is not None:
            par_lecon.setdefault(i, []).extend(notes_lecon(d))
    # dédoublonnage du 28/09 : cartes qui refaisaient une phrase ou un point déjà travaillé ailleurs dans la leçon
    f = PRIVE / "manuel" / "cartes_retirees.json"
    retirees = {x["recto"] for x in json.loads(f.read_text(encoding="utf-8"))} if f.exists() else set()
    par_lecon = {i: [(g, n) for g, n in notes if n[0] not in retirees] for i, notes in par_lecon.items()}
    for i, notes in sorted(par_lecon.items()):
        paquet = m.paquet(i)
        publics = publics_par_paquet.get(paquet) or [(0, "")]
        rang_mot = {nu(recto): rang for rang, recto in publics}
        vus, ns = set(), []
        for genre, n in notes:
            if n[0] not in vus:
                vus.add(n[0])
                ns.append((genre, n))
        autres = _entrelacer([x for x in ns if x[0] not in ("Textes", "Ecoute")])
        textes = [x for x in ns if x[0] in ("Textes", "Ecoute")]

        def pret(n):  # rang public à partir duquel la note peut venir : après les mots de la leçon qu'elle emploie
            r = 0
            for w, l in m.mots(nu(n[0]) + " " + nu(n[1])):
                if w in rang_mot:  # un mot (ou une expression) dont la carte est dans cette leçon
                    r = max(r, rang_mot[w])
            return r

        attente = [(g, n, pret(n), False) for g, n in autres] + [(g, n, pret(n), True) for g, n in textes]
        # fusion : après chaque carte publique, autant de cartes privées que la proportion le demande, prises dans
        # l'ordre (genres alternés) parmi celles dont les mots sont déjà vus ; les textes, dans la seconde moitié
        places, restant, dernier = [], list(attente), None
        total, npub = len(attente), len(publics)
        par_carte = -(-total // npub) + 1  # au plus 2 cartes privées de suite (un retard se rattrape peu à peu)
        for j, (rang_pub, recto_pub) in enumerate(publics):
            quota = min(par_carte, round((j + 1) * total / npub) - len(places))
            k = 0
            while quota > 0 and restant:
                prets = [x for x in restant if x[2] <= rang_pub and (not x[3] or j >= npub // 2)]
                if not prets:
                    break
                voisine = FAMILLE_PUBLIQUE.get(recto_pub) if k == 0 else FAMILLE[dernier]
                x = next((y for y in prets[:6] if FAMILLE[y[0]] != voisine and y[0] != dernier),
                         next((y for y in prets[:6] if FAMILLE[y[0]] != voisine), prets[0]))
                restant.remove(x)
                k += 1
                places.append((x, rang_pub + min(k, 9)))  # entre deux cartes publiques (rangs espacés de 10)
                dernier = x[0]
                quota -= 1
        dernier_rang = publics[-1][0]
        for k, x in enumerate(restant):  # ce qui reste (mots vus en toute fin de leçon) : juste après
            places.append((x, dernier_rang + 1 + min(k, 8)))
        for (genre, n, _, _), rang in places:
            if len(n) > 3:  # exercice : texte calculé à la création (énoncé complété par la réponse)
                audio = n[3]
                tts = "tts::reponse" if audio else "tts::aucun"
            else:
                audio, tts = texte_audio("Lecture" if genre == "Textes" else genre, n[0], n[1], n[2])
                if "manuel_dictee" in n[2] or genre == "Grammaire":
                    tts = "tts::phrase"
            fichiers[genre].append([n[0], n[1], n[2] + " " + tts, paquet, audio])
            rangement.append((n[0], paquet, rang))
    # rectos disparus depuis la dernière version : gardés avec a_supprimer
    for genre, ns in fichiers.items():
        presents = {n[0] for n in ns}
        for r in _lire(PRIVE / f"Chinois__Manuel_{genre}.txt"):
            if len(r) >= 3 and r[0] not in presents:
                tags = r[2] if "a_supprimer" in r[2].split() else r[2] + " a_supprimer"
                ns.append([r[0], r[1], tags, A_SUPPRIMER, ""])
                rangement.append((r[0], A_SUPPRIMER, 9999999))
                presents.add(r[0])
    PRIVE.mkdir(parents=True, exist_ok=True)
    for genre, ns in fichiers.items():
        with open(PRIVE / f"Chinois__Manuel_{genre}.txt", "w", encoding="utf-8", newline="") as f:
            f.write(EN_TETE)
            csv.writer(f, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(ns)
    with open(PRIVE / "RANGEMENT.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("#Ranger mon chinois (cartes privées du manuel) : recto, paquet, rang\n")
        csv.writer(f, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(rangement)
    for genre, ns in fichiers.items():
        print(f"{genre:10} {len(ns)} notes")


if __name__ == "__main__":
    main()
