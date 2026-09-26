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
SYLLABE = re.compile(r"(?:zh|ch|sh|[bpmfdtnlgkhjqxrzcsyw])?(?:iang|iong|uang|ueng|ang|eng|ong|ian|iao|uai|uan|üan|üe|ue|ai|ei|ao|ou|an|en|ia|ie|iu|in|ua|uo|ui|un|ün|er|a|o|e|i|u|ü)(?:ng|n|r)?", re.I)


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


# niveau écrit sur les cartes d'écoute qui n'ont pas de niveau HSK : repéré d'après la difficulté mesurée des textes
# (les 初级 se lisent comme les textes marqués HSK 2, les 高级 un cran au-dessus des HSK 4)
LIBELLE_HSK = {"初中级": 3, "中高级": 5, "初级": 2, "中级": 4, "高级": 5}


def niveau_carte(paquet: str, r) -> int:
    """Niveau HSK qui range la note dans son sous-paquet. Vocabulaire, phrases, exercices : niveau HSK 3.0 officiel
    (étiquette HSK3.0::n) ; grammaire, lecture, écoute : niveau écrit sur la carte (le premier d'une fourchette)."""
    if paquet in ("Vocabulaire", "Phrases", "Exercices"):
        return niveau_hsk(r[3])
    from corrections_contenu import NIVEAUX
    if (paquet, r[0]) in NIVEAUX:
        return int(NIVEAUX[(paquet, r[0])])
    t = html.unescape(re.sub(r"<rt[^>]*>[^<]*</rt>|<[^>]+>", " ", r[0]))[:300]
    m = re.search(r"HSK ?(\d)", t)
    if m:
        return int(m.group(1))
    return next((v for k, v in LIBELLE_HSK.items() if k in t), None)


def sous_paquet(paquet: str, r) -> str:
    """Nom du sous-paquet d'après le niveau HSK de la note."""
    niv = niveau_carte(paquet, r)
    return f"Chinois::{paquet}::" + (SOUS_PAQUETS[niv] if niv else "8 · Hors HSK")


def ecrire(nom, rangs, paquet):
    SORTIE.mkdir(exist_ok=True)
    with open(SORTIE / nom, "w", encoding="utf-8", newline="") as f:
        f.write("#separator:tab\n#html:true\n#tags column:4\n#deck column:5\n")
        rangs = [r[:4] + [sous_paquet(paquet, r)] for r in rangs]
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


TRAD_CARTE = {("Vocabulaire", "卷"): "捲"}  # caractère seul à plusieurs formes : celle du sens de la carte (卷 = 内卷)


def corriger_trad(recto: str, verso: str, paquet: str) -> str:
    """Refait la forme traditionnelle à partir du recto, si l'ancienne correspondait bien au recto."""
    simple = html.unescape(re.sub(r"<[^>]+>", "", recto)).strip()
    if (paquet, simple) in TRAD_CARTE:
        stats[(paquet, "forme traditionnelle imposée (caractère à plusieurs formes)")] += 1
        return TRAD.sub(lambda m: m.group(1) + TRAD_CARTE[(paquet, simple)] + m.group(3), verso, count=1)

    def sub(m):
        if CJK.findall(VERS_SIMP.convert(m.group(2))) != CJK.findall(VERS_SIMP.convert(simple)):
            return m.group(0)
        neuf = vers_trad(simple)
        if neuf != m.group(2):
            stats[(paquet, "forme traditionnelle normalisée")] += 1
        return m.group(1) + neuf + m.group(3)
    if "hanzi-trad" not in verso:  # défaut du générateur d'origine : la ligne manque carrément, on l'ajoute
        stats[(paquet, "ligne de forme traditionnelle ajoutée (absente)")] += 1
        return f'<span class="hanzi-trad">{vers_trad(simple)}</span><br>' + verso
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


LATIN_OU_NOMBRE = re.compile(r"[A-Za-z0-9][A-Za-z0-9%+.\-]*")


def ligne_pinyin_mixte(recto_nu: str, segment: str) -> str:
    """Refait la ligne de pinyin d'une phrase qui contient des mots latins ou des nombres (offer, B站, 4K, 1978) :
    le générateur d'origine en perdait ou en coupait une partie, et la ligne n'était pas relue (les syllabes ne
    s'alignaient plus sur les caractères). Chaque mot latin ou nombre devient une syllabe à part, sans ton."""
    from contenu_cours import lire_phrase
    it = iter(lire_phrase(recto_nu))
    morceaux, i = [], 0
    while i < len(recto_nu):
        c = recto_nu[i]
        m = LATIN_OU_NOMBRE.match(recto_nu, i)
        if CJK.match(c):
            morceaux.append(("syl", next(it)))
            i += 1
        elif m:
            morceaux.append(("latin", m.group(0)))
            i = m.end()
        else:
            if not c.isspace():
                morceaux.append(("ponct", c))
            i += 1
    sortie = ""
    for genre, t in morceaux:
        if genre == "ponct":
            sortie += t
            continue
        balise = f'<span class="t{ton(t)}">{t}</span>' if genre == "syl" else f'<span class="t0">{t}</span>'
        sortie += ("" if not sortie or sortie[-1] in "，。！？、；：“”《》（）\"" else " ") + balise
    premier = SPAN.search(segment)
    if premier and premier.group(2)[:1].isupper():  # la phrase commençait par une majuscule : on la garde
        sortie = SPAN.sub(lambda s: f'<span class="t{s.group(1)}">{s.group(2)[:1].upper() + s.group(2)[1:]}</span>', sortie, count=1)
    return sortie


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


RUBY_MULTI = re.compile(r'<ruby>([^<]{2,})<rt class="t(\d)">([^<]*)</rt></ruby>')


def corriger_ruby_multi(champ: str, paquet: str) -> str:
    """Défaut du générateur d'origine (Vocabulaire) : un <ruby> a parfois une base de 2 caractères ou plus
    (ponctuation + hanzi collés, ou un nombre) pour une seule lecture, ex. <ruby>，最<rt>zuì</rt></ruby>.
    Ce ruby mal formé n'est reconnu par aucune des règles qui attendent un seul caractère par <ruby>, et une
    correction de texte peut y introduire un second <ruby> imbriqué et casser le HTML. On la répare en amont :
    la lecture ne concerne que le DERNIER caractère de la base, le reste (souvent de la ponctuation) sort du ruby."""
    def sub(m):
        base, classe, lecture = m.group(1), m.group(2), m.group(3)
        stats[(paquet, "ruby à base multiple réparé")] += 1
        if not lecture:  # aucune lecture associée (souvent un nombre) : pas de ruby du tout
            return base
        return base[:-1] + f'<ruby>{base[-1]}<rt class="t{classe}">{lecture}</rt></ruby>'
    return RUBY_MULTI.sub(sub, champ)


RUBY_SANS_CLASSE = re.compile(r'<ruby>(.)<rt>([^<]*)</rt></ruby>')


def corriger_ruby_sans_classe(champ: str, paquet: str) -> str:
    """Défaut du générateur d'origine (200 notes de Vocabulaire) : le <rt> n'a pas d'attribut class="tN" du tout,
    donc la syllabe ne s'affiche dans aucune des couleurs de ton. On calcule le ton à partir de l'accent."""
    def sub(m):
        car, lecture = m.group(1), m.group(2)
        stats[(paquet, "rt sans classe de ton réparé")] += 1
        return f'<ruby>{car}<rt class="t{ton(lecture)}">{lecture}</rt></ruby>'
    return RUBY_SANS_CLASSE.sub(sub, champ)


RUBY_UN = re.compile(r'<ruby>(.)<rt class="t\d">([^<]*)</rt></ruby>')
SEPARATEUR_TRADUCTION = re.compile(r" - |\s{2,}(?=[A-Za-zÀ-ÿ\"«(])")


def reparer_exemples_interrompus(verso: str, paquet: str) -> str:
    """Défaut du générateur d'origine (Vocabulaire) : dans une phrase d'exemple, l'annotation pinyin s'arrête souvent
    à la première virgule (坏(huài)了(le)，水管漏水不得了…), un caractère se retrouve parfois dans l'annotation de la
    virgule (<ruby>，<rt>,也</rt></ruby>) et le tiret avant la traduction manque. On réannote toute la phrase."""
    from contenu_cours import ruby

    def une_ligne(ligne):
        m = SEPARATEUR_TRADUCTION.search(ligne)
        chinois, suite = (ligne[:m.start()], " - " + ligne[m.end():]) if m else (ligne, "")
        if "<ruby>" not in chinois:
            return ligne
        perdu = any(CJK.search(l) for _, l in RUBY_UN.findall(chinois))
        if not perdu and not re.search(r"</ruby>[^A-Za-z<]*[一-鿿]{2,}", re.sub(r"</ruby><ruby>", "", chinois)):
            return ligne
        texte = RUBY_UN.sub(lambda r: r.group(1) + "".join(CJK.findall(r.group(2))), chinois)
        stats[(paquet, "phrase d'exemple réannotée (annotation interrompue)")] += 1
        return ruby(texte) + suite

    def un_bloc(b):
        return b.group(1) + "<br>".join(une_ligne(l) for l in b.group(2).split("<br>")) + b.group(3)
    return re.sub(r"(<b>Exemple :</b>)(.*?)(</div>)", un_bloc, verso)


def traiter_note(paquet: str, r):
    recto, verso = r[0], r[1]
    if paquet == "Vocabulaire":
        recto, verso = corriger_ruby_multi(recto, paquet), corriger_ruby_multi(verso, paquet)
        recto, verso = corriger_ruby_sans_classe(recto, paquet), corriger_ruby_sans_classe(verso, paquet)
        verso = reparer_exemples_interrompus(verso, paquet)
    if paquet in ("Phrases", "Vocabulaire"):
        verso = corriger_trad(recto, verso, paquet)
    if paquet in ("Phrases", "Vocabulaire"):
        bornes = segment_pinyin(verso.split('<div class="exemple-bloc"')[0])
        if bornes:
            d, f = bornes
            recto_nu = html.unescape(re.sub(r"<[^>]+>", "", recto))
            segment = corriger_mots_latins_casses(corriger_nombres_tronques(verso[d:f], recto_nu, paquet), paquet)
            if paquet == "Vocabulaire" and "..." in segment:  # structures (连…也…) : « lián... yě... » -> « lián… yě… »
                segment = segment.replace("...", "…")
                stats[(paquet, "points de suspension normalisés dans le pinyin")] += 1
            if (paquet == "Phrases" and LATIN_OU_NOMBRE.search(recto_nu)
                    and len(SPAN.findall(segment)) != len(CJK.findall(recto_nu))):
                # refaite entièrement (lectures déjà relues) : corriger_spans découperait « emo » en « e mo »
                segment = ligne_pinyin_mixte(recto_nu, segment)
                stats[(paquet, "ligne de pinyin refaite (mots latins ou nombres)")] += 1
            else:
                segment = corriger_spans(segment, recto_nu, paquet + " (entrée)")
            verso = verso[:d] + segment + verso[f:]
            if paquet == "Phrases":  # mise en page : la phrase simplifiée répétée, ou une ligne vide, avant la traduction
                apres = verso[d + len(segment):]
                m = re.match(r"<br>(?:" + re.escape(html.escape(recto_nu, quote=False)) + "|" + re.escape(recto_nu) + r")?(?=<br>[^<])", apres)
                if m and m.end() > 0 and (apres[4:m.end()] or apres[m.end():m.end() + 8] != "<br><br>"):
                    verso = verso[:d + len(segment)] + apres[m.end():]
                    stats[(paquet, "ligne en trop avant la traduction retirée")] += 1
    if paquet == "Grammaire":
        def exemple(m):
            phrase, pinyin = m.group(2).strip(), m.group(4)
            # pas de span du tout (ligne en texte brut, parfois fausse), ou des spans en nombre différent des
            # caractères de la phrase (pinyin tronqué, terminé par « … » au lieu d'aller jusqu'au bout) : refait
            if not SPAN.search(pinyin) or len(SPAN.findall(pinyin)) != len(CJK.findall(phrase)):
                from contenu_cours import spans_par_mot
                stats[(paquet, "ligne de pinyin refaite")] += 1
                return m.group(1) + m.group(2) + m.group(3) + spans_par_mot(phrase) + m.group(5)
            return m.group(1) + m.group(2) + m.group(3) + corriger_spans(pinyin, phrase, paquet) + m.group(5)
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
    """Niveau HSK 3.0 officiel des mots et des caractères (un caractère prend le niveau du plus facile de ses mots)."""

    def __init__(self):
        self.mot, self.car = dict(hsk30()), {}
        for mot, niveau in self.mot.items():
            for c in mot:
                self.car[c] = min(niveau, self.car.get(c, 99))

    def officiel(self, texte: str) -> int:
        """Niveau HSK 3.0 où l'on connaît tous les mots de la phrase (7 = 7-9). Noms propres et nombres ignorés ;
        un mot absent de la liste prend le niveau de son caractère le plus difficile."""
        import jieba.posseg as pseg
        niveaux = []
        for mot, nature in pseg.cut("".join(c for c in texte if CJK.match(c) or c in "，。！？、；：")):
            if not CJK.search(mot) or nature in ("nr", "nrfg", "nrt", "ns", "nt", "nz", "m"):
                continue
            n = self.mot.get(mot) or self.mot.get(mot + "儿")
            niveaux.append(n or max(self.car.get(c, 7) for c in mot if CJK.match(c)))
        return max(niveaux, default=1)

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


_HSK30 = {}


def hsk30() -> dict:
    """Liste officielle HSK 3.0 : mot -> niveau (7 = niveaux 7-9)."""
    if not _HSK30:
        import json
        _HSK30.update(json.loads((Path(__file__).parent / "hsk30.json").read_text(encoding="utf-8"))["niveaux"])
    return _HSK30


MARQUEURS_STRUCTURE = re.compile(r"…|\.\.\.|。。。|\+|/|／")
ETIQUETTE_HORS = "HSK3.0::hors_liste"
ANCIENNE_ETIQUETTE = re.compile(r"HSK\d|HSK7-9|hors_HSK|HSK3\.0::\S+")


def niveau_officiel(entree: str):
    """Niveau HSK 3.0 d'une entrée du paquet de vocabulaire, ou None si elle n'est pas dans la liste.
    Une structure (太。。。了, V + 一下, 疼 / 痛) prend le niveau le plus élevé de ses mots, s'ils y sont tous."""
    niveaux = hsk30()

    def un(mot):
        for v in (mot, mot + "儿", mot[:-1] if mot.endswith("儿") and len(mot) > 1 else ""):
            if v in niveaux:
                return niveaux[v]
        return None

    entree = html.unescape(re.sub(r"<[^>]+>", "", entree)).strip()
    entree = re.sub(r"\s*[（(][^（）()]*[）)]$", "", entree)  # annotation finale : 束（量词）, 认认真真 (AABB)
    n = un(entree)
    if n or not MARQUEURS_STRUCTURE.search(entree):
        return n
    def morceau(m):  # mots-outils collés (不是, 的时候) : on découpe en mots, puis en caractères
        n = un(m)
        if n is None and len(m) > 1:
            import jieba
            parties = [un(p) or (max(un(c) for c in p) if all(un(c) for c in p) else None) for p in jieba.lcut(m)]
            n = max(parties) if all(parties) else None
        return n
    morceaux = [morceau(m) for m in re.findall(r"[一-鿿]+", entree)]
    return max(morceaux) if morceaux and all(morceaux) else None


def niveaux_officiels(rangs):
    """Remplace les niveaux HSK du paquet d'origine (qui ne suivent aucune liste officielle) par le niveau HSK 3.0.
    Nouvelles étiquettes HSK3.0::1 … HSK3.0::6, HSK3.0::7-9, HSK3.0::hors_liste : distinctes des anciennes HSK1…HSK9,
    pour qu'on puisse ranger les cartes même si Anki garde les anciennes étiquettes à l'import."""
    for r in rangs:
        avant = niveau_hsk(r[3])
        n = niveau_officiel(r[0])
        etiquette = ETIQUETTE_HORS if n is None else "HSK3.0::" + ("7-9" if n == 7 else str(n))
        r[3] = " ".join([etiquette] + [t for t in r[3].split() if not ANCIENNE_ETIQUETTE.fullmatch(t)])
        if n is None:
            stats[("Vocabulaire", "niveau HSK 3.0 : hors liste officielle")] += 1
        elif avant is not None and min(avant, 7) == n:
            stats[("Vocabulaire", "niveau HSK 3.0 : inchangé")] += 1
        else:
            stats[("Vocabulaire", "niveau HSK 3.0 : corrigé ou attribué")] += 1


def niveaux_phrases_exercices(paquets, lex):
    """Phrases et exercices : les niveaux d'origine (Phrases_HSK1…9) ne suivaient pas la liste officielle
    (une citation de Fan Zhongyan en HSK 1). Étiquette HSK3.0::n = niveau où l'on connaît tous les mots."""
    for nom in ("Grammaire", "Lecture", "Ecoute"):  # niveau écrit sur la carte : étiquette pour ranger les notes déjà importées
        for r in paquets[nom]:
            n = niveau_carte(nom, r)
            garde = [t for t in r[3].split() if not t.startswith("HSK::")]
            r[3] = " ".join(([f"HSK::{n}"] if n else []) + garde)
    for nom in ("Phrases", "Exercices"):
        for r in paquets[nom]:
            texte = r[0]
            if "exercice_traditionnel" in r[3].split():  # recto en caractères non simplifiés : on mesure le mot simplifié
                m = re.search(r"Réponse : ([一-鿿]+)", r[1])
                texte = m.group(1) if m else ""
            n = lex.officiel(html.unescape(re.sub(r"<[^>]+>", " ", texte)))
            etiquette = "HSK3.0::" + ("7-9" if n == 7 else str(n))
            garde = [t for t in r[3].split() if not re.fullmatch(r"Phrases_HSK\d|HSK3\.0::\S+", t)]
            r[3] = " ".join([etiquette] + garde)
            stats[(nom, f"niveau HSK 3.0 : {etiquette[8:]}")] += 1


def niveau_hsk(etiquettes: str, defaut=None):
    m = re.search(r"(?<!\S)HSK3\.0::(\d)", etiquettes)
    if m:
        return int(m.group(1))
    if ETIQUETTE_HORS in etiquettes.split():
        return defaut
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
            freq = min((FREQ[e] for e in r[3].split() if e in FREQ), default=3)
            if niv is None:  # hors liste officielle : rangé d'après le niveau de ses caractères
                return (10, lex.niveau(r[0]), freq, len(CJK.findall(r[0])), i)
            return (niv, 0, freq, len(CJK.findall(r[0])), i)
    elif paquet == "Phrases":
        def cle(ir):
            i, r = ir
            return (niveau_hsk(r[3], 9), lex.niveau(r[0]), len(CJK.findall(r[0])), i)
    elif paquet == "Exercices":
        def cle(ir):
            i, r = ir
            genre = next((e for e in r[3].split() if e.startswith("exercice")), "")
            malus = 2 if genre in ("exercice_chengyu", "exercice_registre") else 0
            niv = niveau_hsk(r[3], 9)
            if genre == "exercice_traditionnel":  # le recto est en caractères non simplifiés : niveau du mot simplifié
                m = re.search(r"Réponse : ([一-鿿]+)", r[1])
                return (niv, round(lex.niveau(m.group(1)) if m else 3), TYPES_EXO.index(genre), i)
            return (niv + malus, round(lex.niveau(texte(r)) + malus), TYPES_EXO.index(genre) if genre in TYPES_EXO else 99, i)
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


def lire_publies():
    """Les fichiers corrigés tels qu'ils ont été produits la dernière fois (ce que l'utilisateur a pu importer)."""
    publies = {}
    for p in SORTIE.glob("Chinois__*.txt"):
        lignes = [l for l in p.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]
        publies[p.name[len("Chinois__"):-4]] = [r[:4] for r in csv.reader(lignes, delimiter="\t", quotechar='"')]
    return publies


def garder_anciens_rectos(originaux, publies, paquets):
    """Anki reconnaît une note par son recto : une note dont le recto n'est plus dans le fichier resterait dans la
    collection sans rien signaler. Quelle que soit l'étape qui a changé ou retiré ce recto, on garde la note avec
    un verso qui le dit et l'étiquette a_supprimer. Cela vaut pour les notes d'origine comme pour celles de la
    dernière version produite (cartes ajoutées ou déjà corrigées une première fois)."""
    from corrections_contenu import REMPLACEE, RETIREE
    for source, verso, famille in ((originaux, REMPLACEE, "recto d'origine"), (publies, RETIREE, "recto déjà publié")):
        for nom, rangs in source.items():
            presents = {r[0] for r in paquets[nom]}
            for r in rangs:
                if r[0] not in presents:
                    presents.add(r[0])
                    etiquettes = [t for t in r[3].split() if t not in ("corrige_2026", "a_supprimer")] + ["a_supprimer"]
                    paquets[nom].append([r[0], verso, r[2], " ".join(etiquettes)])
                    stats[(nom, f"{famille} disparu : ancienne carte gardée avec a_supprimer")] += 1


# ------------------------------------------------------------------ programme principal
def main():
    from contenu_cours import ajouter_contenu

    paquets = {p.name[len("Chinois__"):-4]: lire(p.name) for p in sorted(SOURCE.glob("Chinois__*.txt"))}
    originaux = {k: [list(r) for r in v] for k, v in paquets.items()}
    publies = lire_publies()
    avant = {k: len(v) for k, v in paquets.items()}
    paquets["Exercices"] = nettoyer_exercices(paquets["Exercices"])
    import corrections_contenu as cc
    for nom, rangs in paquets.items():
        paquets[nom] = [n for r in rangs for n in cc.appliquer(nom, r[0], traiter_note(nom, r))]
        print(f"{nom} : pinyin relu, contenu corrigé", flush=True)
    for r in paquets["Vocabulaire"]:  # une correction de relecture a pu insérer du chinois sans annotation dans un exemple
        repare = reparer_exemples_interrompus(r[1], "Vocabulaire")
        if repare != r[1]:
            r[1] = corriger_ruby(repare, "Vocabulaire")
    for r in paquets["Vocabulaire"]:  # « classificateur » posé sur un nom qui n'en est pas un (la note cite juste son 量词)
        mot = r[0].strip()
        if "classificateur" in r[3].split() and len(CJK.findall(mot)) >= 2 and mot not in CLASSIFICATEURS_LONGS:
            r[3] = " ".join(t for t in r[3].split() if t != "classificateur")
            stats[("Vocabulaire", "étiquette classificateur retirée")] += 1
    for rangs in paquets.values():
        for r in rangs:
            r[3] = " ".join(r[3].split())
    ajouts = ajouter_contenu(paquets)
    garder_anciens_rectos(originaux, publies, paquets)
    niveaux_officiels(paquets["Vocabulaire"])
    lex = Lexique()
    niveaux_phrases_exercices(paquets, lex)
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
