# -*- coding: utf-8 -*-
"""Rangement des paquets dans l'ordre du manuel de la fac : Méthode de chinois (Inalco), premier et deuxième niveau.

Un sous-paquet par leçon (Chinois::1 · Premier niveau::L01 · …), qui mélange tous les types de cartes dans un ordre
d'apprentissage : une carte n'arrive qu'une fois vus les mots qu'elle contient, la fiche d'un point de grammaire
avant ses exercices, les textes en fin de leçon. Ce qui dépasse le manuel (HSK 5 à 9, hors HSK) forme la suite du
parcours : « 3 · Après le manuel::S01… », des paliers de la taille d'une leçon, construits de la même façon.

Données : donnees_hsk/manuel.json
- "lecons" : les 28 leçons (sommaire de l'éditeur) ;
- "vocabulaire" : mot -> leçon. Les mots des deux manuels sont à leur première leçon d'après leurs index lexicaux
  (premier niveau : première apparition, à l'oral « py » ou à l'écrit ; deuxième niveau : index des mots et
  vocabulaire de la compréhension orale) ; les autres mots HSK 1 à 4 sont répartis par thème et par point de
  grammaire ;
- "grammaire" : titre de fiche -> leçon ou "apres" (leçon où le manuel traite le point, d'après l'index
  grammatical du premier niveau et le sommaire du deuxième ; sinon rangement par thème) ;
- "caracteres" : caractère -> leçon où le manuel le donne à écrire (tableaux des caractères nouveaux) : range
  les cartes du paquet Écriture.
Les manuels eux-mêmes (PDF) ne sont pas dans le dépôt : rien n'en est recopié ici.

Anki ne change ni le paquet ni la position (ordre des nouvelles cartes) d'une note déjà importée : le fichier
RANGEMENT.tsv (recto, paquet, rang) sert au module complémentaire « Ranger mon chinois », qui les range.
"""
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
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
        # caractère -> leçon où le manuel le donne à écrire (tableaux des caractères nouveaux)
        self.car_manuel = {c: self.index[l] for c, l in d.get("caracteres", {}).items()}
        self._cache = {}

    def paquet(self, i: int) -> str:
        l = self.lecons[i]
        niveau = "1 · Premier niveau" if l["id"].startswith("P1") else "2 · Deuxième niveau"
        return f"Chinois::{niveau}::{l['id'][3:]} · {l['titre']}"

    def lecon_mot(self, mot: str) -> int:
        from corriger_decks import hsk30
        if len(mot) == 3 and mot[1] in "没不" and mot[0] == mot[2] and mot[0] in self.voc:
            return max(self.voc[mot[0]], self.voc.get(mot[1], INF))  # 有没有, 是不是 : connus avec 有 / 是 et 没 / 不
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
    """Le texte d'une carte de lecture ou d'écoute, sans la ligne de titre et de niveau (初级, HSK 4…) ni les
    marques de locuteur des dialogues (男：/ 女：)."""
    if nom == "Ecoute":
        m = re.search(r'class="ecoute-texte">(.*?)</div>', r[0], re.S)
        if m:
            return re.sub(r"[男女][：:]", " ", nu(m.group(1)))
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
                e["titre"] = titre_fiche(r[0] if "#2980b9" in r[0] else r[1])  # cartes à questions : titre au verso
                lecon = m.gram.get(e["titre"], INF)
                e["mots"] = [w for w, _ in m.mots(re.sub(r"[（(].*?[）)]", "", e["titre"].split(" — ")[0]))]
            elif nom == "Ecriture":
                e["car"] = _caractere_ecriture(r)
                if e["car"] in m.car_manuel:  # le manuel le donne à écrire dans cette leçon
                    lecon = m.car_manuel[e["car"]]
                else:
                    lecon = m.car.get(e["car"], INF)
                    bande = re.search(r"ecriture::(\S+)", r[3])
                    bande = bande.group(1) if bande else ""
                    # sinon : liste d'écriture HSK 1-3, et HSK 4-6 au deuxième niveau seulement
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
            if voulue and {"exercice_mots", "exercice_nombres"} & set(r[3].split()):
                lecon = m.index[voulue.group(1)]  # calculés d'après les mots déjà vus / sans vocabulaire : leur leçon
            elif voulue:
                lecon = m.index[voulue.group(1)] if lecon >= INF else max(lecon, m.index[voulue.group(1)])
            groupes[("lecon", lecon) if lecon < INF else ("apres", _niveau_apres(nom, r))].append(e)

    resultat, rang = {}, 0
    blocs = [(m.paquet(i), entrelacer(ordonner(groupes.get(("lecon", i), [])))) for i in range(len(m.lecons))]
    apres = [e for n in APRES for e in groupes.get(("apres", n), [])]
    blocs += suite_du_parcours(apres, m)
    blocs.append((A_SUPPRIMER, groupes.get(("supprimer",), [])))
    for paquet, suite in blocs:
        for e in suite:
            rang += PAS_RANG
            resultat[(e["nom"], e["r"][0])] = (paquet, rang)
    return resultat, m, groupes


TAILLE_PALIER = 450  # notes par palier de la suite du parcours (à peu près une leçon du manuel)


def _frequences():
    """Utilité d'un mot : sa fréquence d'usage en chinois d'aujourd'hui (paquet wordfreq : sous-titres, Wikipédia,
    web… ; « pip install wordfreq »), sinon celle du dictionnaire de jieba, plus ancien."""
    cache = {}
    try:
        from wordfreq import zipf_frequency

        def f(w):
            if w not in cache:
                cache[w] = zipf_frequency(re.sub(r"[^一-鿿]", "", w), "zh")
            return cache[w]
    except ImportError:
        import math
        import jieba

        def f(w):
            if w not in cache:
                n = jieba.get_FREQ(re.sub(r"[^一-鿿]", "", w)) or 0
                cache[w] = math.log10(n) + 1 if n else 0.0
            return cache[w]
    return f
BANDES = {5: "HSK 5", 6: "HSK 6", 7: "HSK 7-9", 8: "Hors HSK"}


def suite_du_parcours(elements, m):
    """Tout ce qui dépasse le manuel (mots HSK 5 à 9 et hors HSK, et les phrases, exercices, fiches, textes et
    caractères qui les emploient) : la suite du parcours, en paliers de la taille d'une leçon, construits comme les
    leçons. Les cartes passent de la plus facile à la plus difficile (niveau HSK de leurs mots nouveaux, puis
    nombre de mots nouveaux) ; avant chacune, les mots qu'elle demande ; un mot qui ne sert à aucune carte vient
    à la fin de son niveau. Chaque palier est ensuite mélangé comme une leçon (entrelacer).
    Renvoie [(nom du sous-paquet, éléments dans l'ordre)]."""
    from corriger_decks import hsk30
    mots = {e["mot"]: e for e in elements if e["nom"] == "Vocabulaire"}
    utilite = _frequences()  # mot -> fréquence d'usage (échelle zipf : 7 = « 的 », 3 = rare, 0 = inconnu)
    import statistics
    seuils = {b: statistics.median([utilite(w) for w, n in hsk30().items() if n and max(5, min(n, 7)) == b] or [0])
              for b in (5, 6, 7)}

    def bande_mot(w):
        n = hsk30().get(w)
        if n is not None:
            return max(5, min(n, 7))
        # hors HSK : par utilité, aussi courant qu'un mot typique du HSK 5, du HSK 6, du HSK 7-9, ou rare
        f = utilite(w)
        return next((b for b in (5, 6, 7) if f >= seuils[b]), 8)

    def bande_element(e):
        if e["nom"] == "Vocabulaire":
            return bande_mot(e["mot"])
        n = _niveau_apres(e["nom"], e["r"])
        return 8 if n is None else max(5, min(n, 7))

    fiches = {e.get("titre"): e for e in elements if e["nom"] == "Grammaire"}
    cartes = [e for e in elements if e["nom"] not in ("Vocabulaire", "Ecriture")]
    ecriture = [e for e in elements if e["nom"] == "Ecriture"]
    besoin = {}
    for e in cartes:
        besoin[id(e)] = [w for w in dict.fromkeys(e["mots"]) if w in mots and w != e.get("mot")]
    cle = {}
    for e in cartes:
        bandes = sorted(bande_mot(w) for w in besoin[id(e)])
        if e["texte"]:  # un texte : niveau de 90 % de ses mots (les mots clés sont au verso), sans tirer ses mots
            b = bandes[int(len(bandes) * 0.9)] if bandes else bande_element(e)
            besoin[id(e)] = []
        else:
            b = max(bandes + [bande_element(e)])
        cle[id(e)] = (b, e["texte"])
    suite, vus, places = [], set(), set()

    def placer(e):
        if id(e) in places:
            return
        places.add(id(e))
        if e.get("fiche") in fiches:  # un exercice après la fiche de sa structure
            placer(fiches[e["fiche"]])
        for w in besoin.get(id(e), []):
            if w not in vus:
                vus.add(w)
                places.add(id(mots[w]))
                suite.append(mots[w])
        suite.append(e)

    for b in sorted(BANDES):
        debut_bande = len(suite)
        reste = [e for e in cartes if cle[id(e)] == (b, False) and id(e) not in places]
        while reste:  # à chaque pas, la carte qui demande le moins de mots nouveaux
            e = min(reste, key=lambda e: (sum(1 for w in besoin[id(e)] if w not in vus), e["i"]))
            placer(e)
            reste = [x for x in reste if id(x) not in places]
        # mots de ce niveau qui ne servent à aucune carte, et textes : répartis régulièrement dans tout le niveau
        seuls = sorted((e for w, e in mots.items() if bande_mot(w) == b and w not in vus),
                       key=lambda e: -utilite(e["mot"]))  # du plus courant au plus rare
        for e in seuls:
            vus.add(e["mot"])
            places.add(id(e))
        textes = [e for e in cartes if cle[id(e)] == (b, True) and id(e) not in places]
        for e in textes:
            places.add(id(e))
        if textes:  # un texte tous les n éléments, dans la seconde moitié du niveau
            seuls = seuls + []
            pas = max(1, (len(seuls) + len(suite) - debut_bande) // (2 * len(textes)))
            milieu = len(seuls) // 2
            for k, e in enumerate(textes):
                seuls.insert(min(len(seuls), milieu + k * (pas + 1)), e)
        bande = suite[debut_bande:]
        if seuls and bande:
            fusion, k = [], 0
            for j, e in enumerate(bande):
                fusion.append(e)
                while k < len(seuls) and (k + 1) * len(bande) <= (j + 1) * (len(seuls) + 1):
                    fusion.append(seuls[k])
                    k += 1
            fusion += seuls[k:]
            suite[debut_bande:] = fusion
        else:
            suite.extend(seuls)
    # caractères à écrire : juste après le premier mot qui les contient
    position = {}
    for k, e in enumerate(suite):
        if e["nom"] == "Vocabulaire":
            for c in e["mot"]:
                position.setdefault(c, k)
    apres_mot = defaultdict(list)
    for e in ecriture:
        apres_mot[position.get(e.get("car"), len(suite) - 1)].append(e)
    suite = [x for k, e in enumerate(suite) for x in [e] + apres_mot.get(k, [])]
    # paliers
    blocs, debut = [], 0
    while debut < len(suite):
        fin = min(len(suite), debut + TAILLE_PALIER)
        if len(suite) - fin < TAILLE_PALIER // 3:  # pas de tout petit dernier palier
            fin = len(suite)
        palier = suite[debut:fin]
        bandes = Counter(bande_mot(e["mot"]) for e in palier if e["nom"] == "Vocabulaire")
        nom = BANDES[bandes.most_common(1)[0][0]] if bandes else "révision"
        blocs.append((f"Chinois::3 · Après le manuel::S{len(blocs) + 1:02d} · {nom}", entrelacer(palier, seuil=0)))
        debut = fin
    return blocs


PAS_RANG = 10  # rangs espacés : les cartes privées tirées du manuel (manuel_prive.py) s'intercalent entre eux


def _flux(e) -> str:
    """Famille d'une carte pour le mélange : chaque famille est répartie sur toute la leçon."""
    if e["texte"]:
        return "texte"
    if e["nom"] == "Exercices":
        return "exercice"
    return {"Vocabulaire": "mot", "Grammaire": "grammaire", "Ecriture": "ecriture", "Phrases": "phrase"}.get(e["nom"], e["nom"])


def _genre(e) -> str:
    return next((t for t in e["r"][3].split() if t.startswith("exercice_")), e["nom"])


def entrelacer(suite, seuil=None):
    """Mélange les familles (mots, grammaire, phrases, exercices, écriture) sur toute la leçon, sans casser l'ordre
    d'apprentissage : une carte ne passe jamais avant les mots qu'elle emploie ni un exercice avant sa fiche, et
    deux exercices du même genre ne se suivent pas si un autre est disponible. À chaque pas, on prend la famille la
    plus en retard sur sa part de la leçon (répartition régulière), puis dans cette famille l'élément le plus tôt
    dans l'ordre d'apprentissage ; les textes gardent la fin de la leçon."""
    n = len(suite)
    if n < 3:
        return suite
    pos = {id(e): i for i, e in enumerate(suite)}
    mots = {e["mot"]: e for e in suite if e["nom"] == "Vocabulaire"}
    fiches = {e.get("titre"): e for e in suite if e["nom"] == "Grammaire"}
    deps = {}
    for e in suite:
        d = {id(mots[w]) for w in e["mots"] if w in mots and mots[w] is not e}
        if e.get("fiche") in fiches:
            d.add(id(fiches[e["fiche"]]))
        if e["nom"] == "Ecriture" and e.get("car"):
            premier = min((m for w, m in mots.items() if e["car"] in w), key=lambda m: pos[id(m)], default=None)
            if premier is not None:
                d.add(id(premier))
        deps[id(e)] = d
    familles = {}
    for e in suite:
        familles.setdefault(_flux(e), []).append(e)
    attendu = Counter(d for e in suite if e["nom"] != "Vocabulaire" for d in deps[id(e)])  # mot -> cartes qui l'attendent
    total = {f: len(l) for f, l in familles.items()}
    places = {f: 0 for f in familles}
    fait, resultat, dernier_genre = set(), [], None
    debut_textes = n // 2  # textes (lecture, écoute) : dans la seconde moitié de la leçon, répartis

    def retard(f, t):
        if f == "texte":
            return (t + 1 - debut_textes) * total[f] / (n - debut_textes) - places[f]
        return (t + 1) * total[f] / n - places[f]

    while len(resultat) < n:
        t = len(resultat)
        choix = None
        ordre = sorted(familles, key=lambda f: -retard(f, t))
        if len(resultat) >= 2 and _flux(resultat[-1]) == _flux(resultat[-2]):
            # pas trois fois de suite la même famille, tant qu'une autre n'est pas déjà en avance sur sa part
            # (sinon une famille minoritaire s'épuiserait au début et laisserait une longue fin d'une seule famille)
            f0 = _flux(resultat[-1])
            limite = -1e9 if seuil is None else seuil  # leçons : toujours ; suite du parcours (surtout des mots) : souple
            ordre = [f for f in ordre if f != f0 and retard(f, t) > limite] + [f0] + \
                    [f for f in ordre if f != f0 and retard(f, t) <= limite]
        for f in ordre:
            if f == "texte" and t < debut_textes and len(familles) > 1:
                continue
            prets = [e for e in familles[f] if id(e) not in fait and deps[id(e)] <= fait]
            if not prets:
                continue
            # un mot attendu par une carte encore à placer passe avant un mot qui ne sert à rien d'autre
            prets.sort(key=lambda e: (f == "mot" and not attendu.get(id(e)), pos[id(e)]))
            if f == "exercice" and dernier_genre:
                autre = [e for e in prets[:6] if _genre(e) != dernier_genre]
                prets = autre or prets
            choix = prets[0]
            break
        if choix is None:  # dépendance hors d'atteinte (ne devrait pas arriver) : ordre d'origine
            choix = next(e for e in suite if id(e) not in fait)
        fait.add(id(choix))
        if choix["nom"] != "Vocabulaire":
            for d in deps[id(choix)]:
                attendu[d] -= 1
        places[_flux(choix)] += 1
        if choix["nom"] == "Exercices":
            dernier_genre = _genre(choix)
        resultat.append(choix)
    return resultat


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
