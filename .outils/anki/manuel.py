# -*- coding: utf-8 -*-
"""Rangement des paquets dans l'ordre du manuel de la fac : Méthode de chinois (Inalco), premier et deuxième niveau.

Un sous-paquet par leçon (Chinois::1 · Premier niveau::L01 · …), qui mélange tous les types de cartes dans un ordre
d'apprentissage : une carte n'arrive qu'une fois vus les mots qu'elle contient, la fiche d'un point de grammaire
avant ses exercices, les textes en fin de leçon. Ce qui dépasse le manuel va dans « 3 · Après le manuel », par
niveau HSK, rangé de la même façon.

Données : donnees_hsk/manuel.json
- "lecons" : les 28 leçons (sommaire de l'éditeur) ;
- "vocabulaire" : mot -> leçon (mots HSK 1 à 4 répartis par thème et par point de grammaire, mots relevés dans les
  corrigés et les textes du manuel du premier niveau à leur première leçon) ;
- "grammaire" : titre de fiche -> leçon ou "apres".

Anki ne change ni le paquet ni la position (ordre des nouvelles cartes) d'une note déjà importée : le fichier
RANGEMENT.tsv (recto, paquet, rang) sert au module complémentaire « Ranger mon chinois », qui les range.
"""
import csv
import hashlib
import html
import json
import re
from collections import defaultdict
from pathlib import Path

DONNEES = Path(__file__).parent / "donnees_hsk"
CJK = re.compile(r"[一-鿿]")
INF = 10 ** 6
APRES = {4: "1 · HSK 4", 5: "2 · HSK 5", 6: "3 · HSK 6", 7: "4 · HSK 7-9", None: "5 · Hors HSK"}
A_SUPPRIMER = "Chinois::9 · À supprimer"
NATURES_IGNOREES = ("nr", "nrfg", "nrt", "ns", "nt", "nz", "m")  # noms propres et nombres, comme Lexique.officiel


def nu(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<rt[^>]*>[^<]*</rt>|<[^>]+>", " ", s))).strip()


def titre_fiche(recto: str) -> str:
    m = re.search(r'<span style="font-size:130%;color:#2980b9">(.*?)</span>', recto, re.S)
    return nu(m.group(1)) if m else nu(recto)


def _cle_melange(recto: str) -> str:
    """Départage stable et sans ordre de type : les cartes de types différents s'entremêlent."""
    return hashlib.md5(recto.encode("utf-8")).hexdigest()


class Manuel:
    def __init__(self):
        d = json.loads((DONNEES / "manuel.json").read_text(encoding="utf-8"))
        self.lecons = d["lecons"]
        self.index = {l["id"]: i for i, l in enumerate(self.lecons)}
        self.voc = {m: self.index[l] for m, l in d["vocabulaire"].items()}
        self.gram = {t: self.index.get(l, INF) for t, l in d["grammaire"].items()}
        self.car = {}
        for mot, i in self.voc.items():
            for c in CJK.findall(mot):
                self.car[c] = min(i, self.car.get(c, INF))
        self._cache = {}

    def paquet(self, i: int) -> str:
        l = self.lecons[i]
        niveau = "1 · Premier niveau" if l["id"].startswith("P1") else "2 · Deuxième niveau"
        return f"Chinois::{niveau}::{l['id'][3:]} · {l['titre']}"

    def lecon_mot(self, mot: str) -> int:
        from corriger_decks import hsk30
        for v in (mot, mot + "儿", mot[:-1] if mot.endswith("儿") and len(mot) > 1 else ""):
            if v in self.voc:
                if len(v) > 1 and hsk30().get(v) is None:  # expression du paquet (喝茶, 坐地铁) : connue dès ses caractères
                    return min(self.voc[v], max(self.car.get(c, INF) for c in CJK.findall(v)))
                return self.voc[v]
        if len(mot) == 3 and mot[1] in "没不" and mot[0] == mot[2]:  # 有没有, 是不是 : question A不A
            return max(self.lecon_mot(mot[0]), self.voc.get(mot[1], INF))
        n = hsk30().get(mot)
        if n and n >= 5 and len(mot) > 1:  # mot d'un niveau au-delà du manuel (un caractère seul : d'après ce caractère)
            return INF
        return max((self.car.get(c, INF) for c in CJK.findall(mot)), default=0)

    def mots(self, texte: str):
        """Mots du texte (noms propres et nombres exclus), avec leur leçon."""
        if texte not in self._cache:
            import jieba.posseg as pseg
            propre = "".join(c for c in texte if CJK.match(c) or c in "，。！？、；：")
            self._cache[texte] = [(m, self.lecon_mot(m)) for m, nature in pseg.cut(propre)
                                  if CJK.search(m) and nature not in NATURES_IGNOREES]
        return self._cache[texte]

    def lecon_texte(self, texte: str, tolerance: float = 0.0) -> int:
        """Leçon où l'on connaît tous les mots du texte (ou tous sauf une petite part, pour les longs textes
        dont les mots clés sont donnés au verso)."""
        niveaux = sorted(l for _, l in self.mots(texte))
        if not niveaux:
            return 0
        k = max(0, int(len(niveaux) * (1 - tolerance) + 0.999) - 1)
        return niveaux[k]


def _texte_exercice(r) -> str:
    """Le chinois d'un exercice : le recto et la réponse (avant le bloc d'explication, qui cite d'autres exemples).
    Recto en caractères traditionnels : le mot simplifié de la réponse."""
    verso = r[1].split('<div class="exemple-bloc"')[0]
    if "exercice_traditionnel" in r[3].split():
        m = re.search(r"Réponse : ([一-鿿]+)", r[1])
        return m.group(1) if m else ""
    return nu(r[0]) + " " + nu(verso)


def _niveau_apres(nom, r):
    from corriger_decks import niveau_carte
    if nom == "Ecriture":
        m = re.search(r"ecriture::(\S+)", r[3])
        return {"1-3": 4, "4-6": 5, "7-9": 7}.get(m.group(1) if m else "", None)
    n = niveau_carte(nom, r)
    return None if n is None else max(4, min(n, 7))


def _passage(nom, r) -> str:
    """Le texte d'une carte de lecture ou d'écoute, sans la ligne de titre et de niveau (初级, HSK 4…)."""
    if nom == "Ecoute":
        m = re.search(r'class="ecoute-texte">(.*?)</div>', r[0], re.S)
        if m:
            return nu(m.group(1))
    return nu(re.sub(r"^<div[^>]*>.*?</div>", "", r[0], count=1, flags=re.S))


def _caractere_ecriture(r) -> str:
    m = re.search(r'class="ecriture-car"[^>]*>\s*([一-鿿])', r[1])
    return m.group(1) if m else ""


def ranger(paquets):
    """Paquet Anki et rang (ordre des nouvelles cartes) de chaque note : {(paquet, recto): (nom du paquet, rang)}."""
    m = Manuel()
    titres = sorted(((html.escape(t, quote=False), t) for t in m.gram), key=lambda x: -len(x[0]))
    groupes = defaultdict(list)  # clé de groupe -> éléments
    for nom, rangs in paquets.items():
        for i, r in enumerate(rangs):
            e = {"nom": nom, "r": r, "i": i, "mots": [], "fiche": None, "texte": False}
            if "a_supprimer" in r[3].split():
                groupes[("supprimer",)].append(e)
                continue
            if nom == "Vocabulaire":
                e["mot"] = nu(r[0])
                lecon = m.voc.get(e["mot"], INF)
            elif nom == "Grammaire":
                e["titre"] = titre_fiche(r[0])
                lecon = m.gram.get(e["titre"], INF)
                e["mots"] = [w for w, _ in m.mots(re.sub(r"[（(].*?[）)]", "", e["titre"].split(" — ")[0]))]
            elif nom == "Ecriture":
                e["car"] = _caractere_ecriture(r)
                lecon = m.car.get(e["car"], INF)
                bande = re.search(r"ecriture::(\S+)", r[3])
                bande = bande.group(1) if bande else ""
                # à écrire dans le manuel : liste d'écriture HSK 1-3, et HSK 4-6 au deuxième niveau seulement
                if not (bande == "1-3" or (bande == "4-6" and 14 <= lecon < INF)):
                    lecon = INF
            elif nom in ("Lecture", "Ecoute"):
                texte = _passage(nom, r)
                lecon = m.lecon_texte(texte, tolerance=0.08)  # mots clés donnés au verso
                e["mots"] = [w for w, _ in m.mots(texte)]
                e["texte"] = True
            else:  # Exercices, Phrases
                texte = _texte_exercice(r) if nom == "Exercices" else nu(r[0])
                lecon = m.lecon_texte(texte, tolerance=0.05)  # une phrase longue peut garder un mot inconnu (traduit)
                e["mots"] = [w for w, _ in m.mots(texte)]
                if nom == "Exercices":
                    fiche = next((t for esc, t in titres if esc in r[1] or t in r[1]), None)
                    if fiche:
                        e["fiche"] = fiche
                        lecon = max(lecon, m.gram[fiche])
            voulue = re.search(r"(?<!\S)manuel::(P\d-L\d\d)", r[3])  # rédigé pour une leçon (contenu_manuel.py)
            if voulue:
                lecon = m.index[voulue.group(1)] if lecon >= INF else max(lecon, m.index[voulue.group(1)])
            groupes[("lecon", lecon) if lecon < INF else ("apres", _niveau_apres(nom, r))].append(e)

    ordre_groupes = [("lecon", i) for i in range(len(m.lecons))] + [("apres", n) for n in APRES] + [("supprimer",)]
    resultat, rang = {}, 0
    for g in ordre_groupes:
        if g == ("supprimer",):
            paquet = A_SUPPRIMER
        elif g[0] == "lecon":
            paquet = m.paquet(g[1])
        else:
            paquet = "Chinois::3 · Après le manuel::" + APRES[g[1]]
        for e in ordonner(groupes.get(g, []), rapide=g[0] != "lecon"):
            rang += 1
            resultat[(e["nom"], e["r"][0])] = (paquet, rang)
    return resultat, m, groupes


def ordonner(elements, rapide=False):
    """Ordre d'apprentissage dans une leçon : pour chaque point de grammaire, ses mots puis sa fiche et deux
    exercices ; ensuite, à chaque pas, l'élément qui demande le moins de mots nouveaux (précédés de ces mots, et
    chaque caractère à écrire juste après le premier mot qui le contient) ; les textes à la fin ; les mots qui ne
    servent à rien d'autre intercalés régulièrement."""
    voc = {e["mot"]: e for e in elements if e["nom"] == "Vocabulaire"}
    cars = {e["car"]: e for e in elements if e["nom"] == "Ecriture" and e.get("car")}
    fiches = [e for e in elements if e["nom"] == "Grammaire"]
    autres = [e for e in elements if e["nom"] not in ("Vocabulaire", "Grammaire", "Ecriture")]
    sans_car = [e for e in elements if e["nom"] == "Ecriture" and not e.get("car")]
    suite, vus, places = [], set(), set()

    def mot(w):
        e = voc.get(w)
        if e is None or w in vus:
            return
        vus.add(w)
        suite.append(e)
        places.add(id(e))

    def element(e):
        for w in e["mots"]:
            mot(w)
        suite.append(e)
        places.add(id(e))

    if rapide:  # après le manuel : ordre des paquets d'origine, mots juste avant leur première phrase
        for e in sorted(fiches + autres, key=lambda e: (e["texte"], _cle_melange(e["r"][0]))):
            element(e)
    else:
        lies = defaultdict(list)
        for e in autres:
            if e["fiche"]:
                lies[e["fiche"]].append(e)
        for f in fiches:
            element(f)
            for e in sorted(lies.get(f.get("titre"), []), key=lambda e: _cle_melange(e["r"][0]))[:2]:
                element(e)
        reste = [e for e in autres if id(e) not in places]
        while reste:
            meilleur = min(reste, key=lambda e: (e["texte"], sum(1 for w in set(e["mots"]) if w in voc and w not in vus),
                                                 _cle_melange(e["r"][0])))
            element(meilleur)
            reste.remove(meilleur)
    # mots qui ne servent dans aucun autre élément : intercalés régulièrement
    seuls = [e for w, e in voc.items() if w not in vus]
    seuls.sort(key=lambda e: e["i"])
    if seuls:
        pas = max(1, len(suite) // (len(seuls) + 1))
        resultat, k = [], 0
        for j, e in enumerate(suite):
            resultat.append(e)
            if (j + 1) % pas == 0 and k < len(seuls):
                resultat.append(seuls[k])
                places.add(id(seuls[k]))
                k += 1
        while k < len(seuls):
            resultat.append(seuls[k])
            places.add(id(seuls[k]))
            k += 1
        suite = resultat
    # caractères à écrire : chacun après le premier mot qui le contient, mais répartis sur toute la leçon
    # (une carte d'écriture est longue : pas dix d'affilée au début de la leçon)
    apres_mot = []
    for j, e in enumerate(suite):
        if e["nom"] == "Vocabulaire":
            for c in e["mot"]:
                ec = cars.get(c)
                if ec is not None and id(ec) not in places:
                    places.add(id(ec))
                    apres_mot.append((j, ec))
    if apres_mot:
        n, total = len(apres_mot), len(suite)
        cible = {}
        for k, (j, ec) in enumerate(apres_mot):
            cible.setdefault(max(j, (k + 1) * total // (n + 1)), []).append(ec)
        suite = [x for j, e in enumerate(suite) for x in [e] + cible.get(j, [])]
    suite += [e for e in cars.values() if id(e) not in places] + sans_car
    return suite


def ecrire_rangement(resultat, chemin):
    """RANGEMENT.tsv : recto, paquet, rang — lu par le module complémentaire « Ranger mon chinois »."""
    with open(chemin, "w", encoding="utf-8", newline="") as f:
        f.write("#Ranger mon chinois : recto de la note, paquet, rang (ordre des nouvelles cartes)\n")
        w = csv.writer(f, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        vus = set()
        for (nom, recto), (paquet, rang) in sorted(resultat.items(), key=lambda kv: kv[1][1]):
            if recto not in vus:
                vus.add(recto)
                w.writerow([recto, paquet, rang])
