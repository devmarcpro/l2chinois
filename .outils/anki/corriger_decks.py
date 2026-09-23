# -*- coding: utf-8 -*-
"""Corrige les paquets Anki exportés (dossier Anki/) et écrit le résultat dans Anki/corrige/.

    python .outils/anki/corriger_decks.py

- pinyin des exemples (caractères à plusieurs lectures, accents manquants, tons neutres, sandhi de 一 et 不) ;
- exercices de ton : doublons fusionnés, caractères polyphones expliqués, erreurs corrigées ;
- contenu ajouté (voir contenu_cours.py) ;
- notes rangées du plus facile au plus difficile.
Les fichiers d'origine ne sont jamais modifiés. Le premier champ des notes existantes n'est pas touché,
pour qu'Anki mette les notes à jour au lieu d'en créer de nouvelles.
"""
import csv
import html
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pinyin_correct import CJK, avec_ton, base, corriger, ton  # noqa: E402

csv.field_size_limit(10**8)
from opencc import OpenCC  # noqa: E402

VERS_TRAD = OpenCC("s2tw")   # formes traditionnelles standard (吃, 為, 裡) au lieu des variantes rares 喫, 爲, 裏
VERS_SIMP = OpenCC("t2s")
# ce qu'OpenCC rend mal, corrigé après conversion (à gauche : ce qu'il produit)
TRAD_FIXES = [(re.compile(a), b) for a, b in [
    (r"彆(?!扭)", "別"), (r"幹燥", "乾燥"), (r"干旱", "乾旱"), (r"干杯", "乾杯"), (r"干脆", "乾脆"), (r"餅干", "餅乾"), (r"干糧", "乾糧"),
    (r"曬干", "曬乾"), (r"干貨", "乾貨"), (r"干涸", "乾涸"), (r"風干", "風乾"), (r"干煸", "乾煸"), (r"干香菇", "乾香菇"), (r"干果", "乾果"),
    (r"干枯", "乾枯"), (r"干洗", "乾洗"), (r"干癟", "乾癟"), (r"干爽", "乾爽"), (r"干濕", "乾濕"), (r"干電池", "乾電池"), (r"干媽", "乾媽"),
    (r"干爹", "乾爹"), (r"擦干", "擦乾"), (r"烘干", "烘乾"), (r"吹干", "吹乾"), (r"晾干", "晾乾"), (r"干笑", "乾笑"), (r"干嘔", "乾嘔"),
    (r"遊(?=[得了過到完出回向上幾一兩三四五六七八九十百千半])", "游"), (r"(?<=[能會去學想教])遊(?!覽|行|戲|客|樂|玩|說|記)", "游"),
    (r"(?<=[一二三四五六七八九十百千萬兩幾每這那哪半])只(?![有是要好能會想需不])", "隻"),
    (r"(?<=[寫說講註標表證查發闡聲申辨言指])明瞭", "明了"), (r"脩", "修"),
    (r"姜(?=[醋湯片末絲茶糖母汁])", "薑"), (r"(?<=[生老嫩鮮])姜", "薑"),
    (r"面包", "麵包"), (r"面粉", "麵粉"), (r"面食", "麵食"), (r"面團", "麵團"), (r"拉面", "拉麵"), (r"方便面", "方便麵"), (r"泡面", "泡麵"),
    (r"炒面", "炒麵"), (r"面館", "麵館"), (r"掛面", "掛麵"), (r"湯面", "湯麵"), (r"涼面", "涼麵"), (r"刀削面", "刀削麵"), (r"面點", "麵點"),
]]


def vers_trad(simple: str) -> str:
    """Forme traditionnelle (norme de Taïwan), avec les corrections de TRAD_FIXES."""
    t = VERS_TRAD.convert(simple)
    for motif, rempl in TRAD_FIXES:
        t = motif.sub(rempl, t)
    return t


# syllabe de pinyin (avec ou sans accent), pour découper « fánchou » en « fán chou »
SYLLABE = re.compile(r"(?:zh|ch|sh|[bpmfdtnlgkhjqxrzcsyw])?(?:iang|iong|uang|ueng|ang|eng|ong|ian|iao|uai|uan|üan|üe|ai|ei|ao|ou|an|en|ia|ie|iu|in|ua|uo|ui|un|ün|er|a|o|e|i|u|ü)(?:ng|n|r)?", re.I)


def decouper_syllabes(s: str):
    """'fánchou' -> ['fán', 'chou'] (on découpe sur la forme sans accent, puis on recopie les accents)."""
    nue = base(s).replace("'", "")
    morceaux, pos, res = [], 0, []
    for m in SYLLABE.finditer(nue):
        if m.start() != pos:
            return None
        morceaux.append(m.end() - m.start())
        pos = m.end()
    if pos != len(nue):
        return None
    lettres = [c for c in s if c not in "'’ "]
    k = 0
    for n in morceaux:
        # une syllabe accentuée a le même nombre de caractères (NFC) que sa forme nue
        res.append("".join(lettres[k:k + n]))
        k += n
    return res if k == len(lettres) else None
TRAD = re.compile(r'(<span class="hanzi-trad">)([^<]*)(</span>)')
VAULT = Path(__file__).resolve().parents[2]
SOURCE = VAULT / "Anki"
SORTIE = SOURCE / "corrige"

RUBY = re.compile(r'<ruby>(.)<rt class="t(\d)">([^<]*)</rt></ruby>')
BLOC = re.compile(r'(?:<ruby>.<rt class="t\d">[^<]*</rt></ruby>|[，。！？、；：,.!?“”"‘’《》（）()…—·\s])+')
SPAN = re.compile(r'<span class="t(\d)">([^<]+)</span>')
PARTICULES = set("的了着过吗呢吧啊呀嘛么们子个地得儿")

stats = Counter()
exemples_de_changements = {}


def lire(nom):
    brut = (SOURCE / nom).read_text(encoding="utf-8-sig")
    rangs = []
    for ligne in brut.splitlines():
        if not ligne.strip() or ligne.startswith("#"):
            continue
        if '""' in ligne or '"' not in ligne:
            rangs.append(next(csv.reader([ligne], delimiter="\t", quotechar='"')))
        else:  # ligne écrite sans doubler les guillemets : on coupe aux tabulations
            rangs.append([c[1:-1] if len(c) > 1 and c[0] == '"' and c[-1] == '"' else c for c in ligne.split("\t")])
    for r in rangs:
        r += [""] * (4 - len(r))
    return rangs


SOUS_PAQUETS = {1: "1 · HSK 1", 2: "2 · HSK 2", 3: "3 · HSK 3", 4: "4 · HSK 4", 5: "5 · HSK 5", 6: "6 · HSK 6",
                7: "7 · HSK 7-9", 8: "7 · HSK 7-9", 9: "7 · HSK 7-9"}


def sous_paquet(etiquettes: str) -> str:
    """Nom du sous-paquet de vocabulaire d'après le niveau HSK de la note."""
    niv = niveau_hsk(etiquettes)
    if niv:
        return "Chinois::Vocabulaire::" + SOUS_PAQUETS[niv]
    if "cours_L2" in etiquettes.split():
        return "Chinois::Vocabulaire::0 · Cours L2"
    return "Chinois::Vocabulaire::8 · Hors HSK"


def ecrire(nom, rangs, paquet=None):
    SORTIE.mkdir(exist_ok=True)
    with open(SORTIE / nom, "w", encoding="utf-8", newline="") as f:
        f.write("#separator:tab\n#html:true\n#tags column:4\n")
        if paquet == "Vocabulaire":
            f.write("#deck column:5\n")
            rangs = [r[:4] + [sous_paquet(r[3])] for r in rangs]
        csv.writer(f, delimiter="\t", quotechar='"', quoting=csv.QUOTE_MINIMAL, lineterminator="\n").writerows(rangs)


def noter(journal, texte, paquet):
    for _k, car, avant, apres, raison in journal:
        famille = re.sub(r"\(.*?\)|mot .*", lambda m: "mot à lecture particulière" if m.group(0).startswith("mot") else "", raison).strip()
        stats[(paquet, famille)] += 1
        exemples_de_changements.setdefault(famille, [])
        if len(exemples_de_changements[famille]) < 3000:
            exemples_de_changements[famille].append((car, avant, apres, raison, texte[:26]))


def corriger_ruby(champ: str, paquet: str) -> str:
    def un_bloc(m):
        bloc = m.group(0)
        triples = RUBY.findall(bloc)
        if not triples:
            return bloc
        texte = re.sub(r"<rt[^>]*>[^<]*</rt>|<[^>]+>", "", bloc)
        lectures = [t[2] for t in triples]
        neuf, journal = corriger(texte, lectures)
        touches = {j[0] for j in journal}
        for k, (car, classe, _l) in enumerate(triples):
            if k not in touches and not ton(neuf[k]) and classe in "1234" and car not in PARTICULES and car not in "一不":
                avec = avec_ton(neuf[k], int(classe))
                if avec != neuf[k]:
                    journal.append((k, car, neuf[k], avec, "accent manquant"))
                    neuf[k] = avec
        noter(journal, texte, paquet)
        it = iter(neuf)
        return RUBY.sub(lambda r: f'<ruby>{r.group(1)}<rt class="t{ton(n := next(it))}">{n}</rt></ruby>', bloc)
    return BLOC.sub(un_bloc, champ)


def corriger_spans(segment: str, texte: str, paquet: str, seulement_sandhi=False) -> str:
    """segment : morceau de HTML contenant une suite de <span class="tN">syllabe</span> pour la phrase `texte`."""
    spans = SPAN.findall(segment)
    if spans and len(spans) != len(CJK.findall(texte)):  # syllabes collées par mot (« fánchou ») : on les sépare
        def eclater(m):
            syl = decouper_syllabes(m.group(2))
            if not syl or len(syl) == 1:
                return m.group(0)
            return "".join(f'<span class="t{ton(x)}">{x}</span>' for x in syl)
        segment = SPAN.sub(eclater, segment)
        spans = SPAN.findall(segment)
    if not spans or len(spans) != len(CJK.findall(texte)):
        if spans:
            stats[(paquet, "suite de syllabes ignorée (longueur différente)")] += 1
        return segment
    lectures = [s[1] for s in spans]
    neuf, journal = corriger(texte, [l.lower() for l in lectures], seulement_sandhi=seulement_sandhi)
    noter(journal, texte, paquet + (" (entrée)" if seulement_sandhi else ""))
    rendu = [n.capitalize() if l[:1].isupper() else n for n, l in zip(neuf, lectures)]
    it = iter(rendu)
    return SPAN.sub(lambda s: f'<span class="t{ton(n := next(it))}">{n}</span>', segment)


def segment_pinyin(verso: str):
    """Renvoie (début, fin) du premier segment entre <br> qui contient des syllabes balisées."""
    pos = 0
    for morceau in verso.split("<br>"):
        if SPAN.search(morceau):
            return pos, pos + len(morceau)
        pos += len(morceau) + 4
    return None


def corriger_trad(recto: str, verso: str, paquet: str) -> str:
    """Refait la forme traditionnelle à partir du recto, si l'ancienne correspondait bien au recto."""
    simple = html.unescape(re.sub(r"<[^>]+>", "", recto)).strip()

    def sub(m):
        if CJK.findall(VERS_SIMP.convert(m.group(2))) != CJK.findall(VERS_SIMP.convert(simple)):
            return m.group(0)
        neuf = vers_trad(simple)
        if neuf != m.group(2):
            stats[(paquet, "forme traditionnelle normalisée")] += 1
        return m.group(1) + neuf + m.group(3)
    return TRAD.sub(sub, verso, count=1)


NOMBRE_SPAN = re.compile(r'<span class="t\d">(\d+)</span>')
MOT_LATIN_CASSE = re.compile(r'(?:<span class="t\d">[A-Za-z]+</span>[A-Za-z]*){1,}')


def corriger_nombres_tronques(segment: str, recto_nu: str, paquet: str) -> str:
    """Défaut du générateur d'origine : le dernier chiffre d'un nombre est parfois perdu dans son span
    (1972 -> <span>197</span>, 19世纪 -> <span>1</span>世纪). On complète à partir du nombre entier écrit dans le recto."""
    chiffres = re.findall(r"\d{2,}", recto_nu)

    def sub(m):
        v = m.group(1)
        if len(v) < 2:  # un span à un seul chiffre est presque toujours une lecture chiffre par chiffre voulue (985院校)
            return m.group(0)
        cible = next((c for c in chiffres if c != v and c.startswith(v) and len(c) - len(v) <= 2), None)
        if cible:
            stats[(paquet, "nombre tronqué réparé")] += 1
            return m.group(0).replace(f">{v}<", f">{cible}<")
        return m.group(0)
    return NOMBRE_SPAN.sub(sub, segment)


def corriger_mots_latins_casses(segment: str, paquet: str) -> str:
    """Défaut du générateur d'origine (paquet Phrases seulement : dans Vocabulaire les spans sont TOUJOURS collés
    sans espace, donc ce repère ne s'applique pas) : un mot emprunté (cosplay, offer, App, LOL...) est parfois
    coupé en plusieurs fragments de span sans espace entre eux (<span>co</span>sp<span>la</span>y, <span>A</span>pp).
    On le refait en un seul span. On exige au moins 2 vrais span, SAUF si le fragment isolé n'est pas directement
    suivi d'un autre span (sinon <span>de</span>DNA — le 地/的 collé à un sigle sans rapport — serait confondu
    avec un mot cassé)."""
    if paquet != "Phrases":
        return segment

    def sub(m):
        bloc = m.group(0)
        if bloc.count("<span") < 2 and (bloc.endswith("</span>") or segment[m.end():m.end() + 5] == "<span"):
            return bloc  # un seul span bien formé (rien à corriger), ou collé à un autre span sans rapport (地/的 + sigle)
        mot = re.sub(r"<[^>]+>", "", bloc)
        stats[(paquet, "mot emprunté recollé")] += 1
        return f'<span class="t0">{mot}</span>'
    return MOT_LATIN_CASSE.sub(sub, segment)


def traiter_note(paquet: str, r):
    recto, verso = r[0], r[1]
    if paquet in ("Phrases", "Vocabulaire"):
        verso = corriger_trad(recto, verso, paquet)
    if paquet in ("Phrases", "Vocabulaire"):
        bornes = segment_pinyin(verso.split('<div class="exemple-bloc"')[0])
        if bornes:
            d, f = bornes
            recto_nu = html.unescape(re.sub(r"<[^>]+>", "", recto))
            segment = corriger_mots_latins_casses(corriger_nombres_tronques(verso[d:f], recto_nu, paquet), paquet)
            verso = verso[:d] + corriger_spans(segment, recto_nu, paquet + " (entrée)") + verso[f:]
    if paquet == "Grammaire":
        def exemple(m):
            if not SPAN.search(m.group(4)):  # ligne de pinyin en texte brut (non colorée, parfois fausse) : refaite
                from contenu_cours import spans_par_mot
                stats[(paquet, "ligne de pinyin refaite")] += 1
                return m.group(1) + m.group(2) + m.group(3) + spans_par_mot(m.group(2).strip()) + m.group(5)
            return m.group(1) + m.group(2) + m.group(3) + corriger_spans(m.group(4), m.group(2), paquet) + m.group(5)
        verso = re.sub(r"(•\s*)([^<]+)(<br><small>)(.*?)(</small>)", exemple, verso)
    verso = corriger_ruby(verso, paquet)
    recto = corriger_ruby(recto, paquet) if "<ruby>" in recto and paquet != "Vocabulaire" else recto
    return [recto, verso] + list(r[2:])


# ------------------------------------------------------------------ exercices de ton
def nettoyer_exercices(rangs):
    rangs = [[r[0], r[1].replace("1e ton", "1er ton"), r[2], r[3]] for r in rangs]
    groupes = {}
    for r in rangs:
        groupes.setdefault(r[0], []).append(r)
    sortie, vus = [], set()
    for r in rangs:
        if r[0] in vus:
            continue
        vus.add(r[0])
        groupe = groupes[r[0]]
        if len(groupe) == 1:
            sortie.append(r)
            continue
        reponses = [re.search(r"Réponse : ([^<]*)", g[1]).group(1).strip() if re.search(r"Réponse : ([^<]*)", g[1]) else g[1] for g in groupe]
        if len(set(reponses)) == 1:  # vrai doublon : on garde l'explication la plus complète
            stats[("Exercices", "doublon supprimé")] += len(groupe) - 1
            sortie.append(max(groupe, key=lambda g: len(g[1])))
        else:  # caractère à plusieurs lectures demandé hors contexte : une seule carte qui les donne toutes
            stats[("Exercices", "cartes contradictoires fusionnées")] += len(groupe) - 1
            lignes = []
            for g in groupe:
                rep = re.search(r"Réponse : ([^<]*)", g[1]).group(1).strip()
                expl = re.sub(r"<[^>]+>", " ", g[1].split("Explication :")[-1]).strip()
                expl = " ".join(expl.split())
                lignes.append(f"• <b>{rep}</b> — {expl}")
            verso = ("<b>Réponse : ça dépend du mot (caractère à plusieurs lectures)</b><br><br>"
                     '<div class="exemple-bloc"><b>Explication :</b><br>' + "<br>".join(lignes) + "</div>")
            sortie.append([r[0], verso, r[2], r[3] + " polyphone"])
    for r in sortie:
        m = re.search(r"<b>Réponse : ([^<]+/[^<]+)</b>", r[1])
        if m and r[0].count("___") == 2:
            a, b = m.group(1).split("/", 1)
            for forme in (f"<b>{m.group(1)}</b>", f"<b>[ {m.group(1)} ]</b>"):
                if r[1].count(forme) == 2:
                    fa, fb = forme.replace(m.group(1), a), forme.replace(m.group(1), b)
                    r[1] = r[1].replace(forme, fa, 1).replace(forme, fb, 1)
                    stats[("Exercices", "paire de liaison remise dans ses deux trous")] += 1
        if "颇" in r[0] and "3e ton (pō)" in r[1]:
            r[1] = r[1].replace("3e ton (pō)", "1er ton (pō)").replace("3e ton", "1er ton")
            stats[("Exercices", "erreur corrigée (颇)")] += 1
        if "shǐng" in r[1]:
            r[1] = r[1].replace("shǐng", "shěng")
            stats[("Exercices", "erreur corrigée (省)")] += 1
    return sortie


# ------------------------------------------------------------------ du plus facile au plus difficile
FREQ = {"tres_frequent(1)": 1, "frequent(2)": 2, "assez_frequent(3)": 3, "moins_frequent(4)": 4, "rare(5)": 5}
TYPES_EXO = ["exercice_ton", "exercice_pinyin", "exercice_hanzi", "exercice_caracteres", "exercice_classificateur", "exercice_negation",
             "exercice_remplir", "exercice_ordre", "exercice_antonyme", "exercice_aspect", "exercice_structure", "exercice_correction",
             "exercice_traduction", "exercice_traditionnel", "exercice_liaison", "exercice_potentiel", "exercice_directionnel", "exercice_reduplication",
             "exercice_verbe", "exercice_contexte", "exercice_expression", "exercice_registre", "exercice_chengyu"]
NIVEAU_LIBELLE = {"初级": 1.5, "初中级": 2.5, "中级": 3.5, "中高级": 4.5, "高级": 5.5}


class Lexique:
    """Niveau HSK des mots et des caractères, d'après le paquet de vocabulaire."""

    def __init__(self, voc):
        self.mot, self.car = {}, {}
        for r in voc:
            m = re.search(r"\bHSK(\d)\b", r[3])
            niveau = int(m.group(1)) if m else 7
            mot = r[0].strip()
            if CJK.fullmatch(mot[:1] or "x") and re.fullmatch(r"[一-鿿]+", mot):
                self.mot[mot] = min(niveau, self.mot.get(mot, 99))
                for c in mot:
                    self.car[c] = min(niveau, self.car.get(c, 99))

    def niveau(self, texte: str) -> float:
        """Niveau estimé d'un texte : on regarde les 15 % de mots les plus difficiles."""
        import jieba
        niveaux = []
        for mot in jieba.cut("".join(CJK.findall(texte))):
            if mot in self.mot:
                niveaux.append(self.mot[mot])
            else:
                niveaux.append(max((self.car.get(c, 7) for c in mot), default=7))
        if not niveaux:
            return 1.0
        niveaux.sort()
        queue = niveaux[int(len(niveaux) * 0.85):] or niveaux[-1:]
        return round(sum(queue) / len(queue), 2)


def niveau_hsk(etiquettes: str, defaut=None):
    m = re.search(r"HSK(\d)\b", etiquettes)
    return int(m.group(1)) if m else defaut


def trier(paquet, rangs, lex: Lexique):
    from corrections_contenu import NIVEAUX

    def texte(r, i=0):
        return html.unescape(re.sub(r"<rt[^>]*>[^<]*</rt>|<[^>]+>", " ", r[i]))

    if paquet == "Vocabulaire":
        def cle(ir):
            i, r = ir
            niv = niveau_hsk(r[3])
            if niv is None:
                niv = lex.niveau(r[0]) if "cours_L2" in r[3] else 10
            freq = min((FREQ[e] for e in r[3].split() if e in FREQ), default=3)
            return (niv, freq, len(CJK.findall(r[0])), i)
    elif paquet == "Phrases":
        def cle(ir):
            i, r = ir
            return (niveau_hsk(r[3], 9), lex.niveau(r[0]), len(CJK.findall(r[0])), i)
    elif paquet == "Exercices":
        def cle(ir):
            i, r = ir
            genre = next((e for e in r[3].split() if e.startswith("exercice")), "")
            malus = 2 if genre in ("exercice_chengyu", "exercice_registre") else 0
            if genre == "exercice_traditionnel":  # le recto est en caractères non simplifiés : niveau du mot simplifié
                m = re.search(r"Réponse : ([一-鿿]+)", r[1])
                return (round(lex.niveau(m.group(1)) if m else 3), TYPES_EXO.index(genre), i)
            return (round(lex.niveau(texte(r)) + malus), TYPES_EXO.index(genre) if genre in TYPES_EXO else 99, i)
    else:  # Grammaire, Lecture, Ecoute : le niveau est écrit sur la carte
        def cle(ir):
            i, r = ir
            t = texte(r)[:120]
            m = re.search(r"HSK ?(\d)(?:-(\d))?", t)
            if (paquet, r[0]) in NIVEAUX:
                niv = NIVEAUX[(paquet, r[0])]
            elif m:
                niv = int(m.group(1)) + (0.5 if m.group(2) else 0)
            else:
                niv = next((v for k, v in sorted(NIVEAU_LIBELLE.items(), key=lambda kv: -len(kv[0])) if k in t), 9)
            return (niv, len(CJK.findall(texte(r))) if paquet != "Grammaire" else 0, i)
    return [r for _, r in sorted(enumerate(rangs), key=cle)]


CLASSIFICATEURS_LONGS = set("公斤 公里 公分 公顷 平方米 立方米 千克 毫米 厘米 分钟 小时 人次 架次 千米 毫升 光年".split())


# ------------------------------------------------------------------ programme principal
def main():
    from contenu_cours import ajouter_contenu

    paquets = {p.name[len("Chinois__"):-4]: lire(p.name) for p in sorted(SOURCE.glob("Chinois__*.txt"))}
    avant = {k: len(v) for k, v in paquets.items()}
    paquets["Exercices"] = nettoyer_exercices(paquets["Exercices"])
    import corrections_contenu as cc
    for nom, rangs in paquets.items():
        paquets[nom] = [n for r in rangs for n in cc.appliquer(nom, r[0], traiter_note(nom, r))]
        print(f"{nom} : pinyin relu, contenu corrigé", flush=True)
    for r in paquets["Vocabulaire"]:  # « classificateur » posé sur un nom qui n'en est pas un (la note cite juste son 量词)
        mot = r[0].strip()
        if "classificateur" in r[3].split() and len(CJK.findall(mot)) >= 2 and mot not in CLASSIFICATEURS_LONGS:
            r[3] = " ".join(t for t in r[3].split() if t != "classificateur")
            stats[("Vocabulaire", "étiquette classificateur retirée")] += 1
    for rangs in paquets.values():
        for r in rangs:
            r[3] = " ".join(r[3].split())
    ajouts = ajouter_contenu(paquets)
    lex = Lexique(paquets["Vocabulaire"])
    for nom in paquets:
        paquets[nom] = trier(nom, paquets[nom], lex)
        ecrire(f"Chinois__{nom}.txt", paquets[nom], nom)

    print("\n=== notes : avant -> après")
    for nom in paquets:
        print(f"  {nom:12} {avant[nom]:5} -> {len(paquets[nom]):5}")
    print("\n=== corrections de contenu")
    print(f"  appliquées : {cc.bilan['appliquées']}, cartes remplacées (recto changé) : {cc.bilan['cartes remplacées']}, échecs : {len(cc.bilan['échecs'])}")
    for e in cc.bilan["échecs"]:
        print("   échec :", e)
    print("\n=== contenu ajouté")
    for k, v in ajouts.items():
        print(f"  {k} : {v}")
    print("\n=== corrections par paquet et par famille")
    for (paquet, famille), n in sorted(stats.items()):
        print(f"  {paquet:22} {famille:45} {n}")
    journal = SORTIE / "journal_des_corrections.txt"
    with open(journal, "w", encoding="utf-8", newline="\n") as f:
        for famille, liste in exemples_de_changements.items():
            f.write(f"\n##### {famille} ({len(liste)} premiers cas)\n")
            for car, a, b, raison, ctx in liste:
                f.write(f"{car}\t{a} -> {b}\t{raison}\t{ctx}\n")
    print(f"\njournal détaillé : {journal}")


if __name__ == "__main__":
    main()
