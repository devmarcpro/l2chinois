# -*- coding: utf-8 -*-
"""儿 dans le pinyin : syllabe pleine « ér » quand 儿 est un mot ou le début / la fin d'un mot où il garde son sens
(儿子, 儿童, 女儿, 婴儿, 托儿所…), sinon suffixe de rétroflexion collé à la syllabe précédente : « r » au ton
neutre (一点儿 yìdiǎnr, 哪儿 nǎr, 一会儿 yíhuìr), comme l'écrit l'orthographe officielle du pinyin.

Le générateur d'origine et les rédacteurs mélangeaient les deux (« yī diǎn ér », « nǎ r », « huì er »).
Ne touche que les versos : rubis <ruby>儿<rt>…</rt></ruby> et lignes de <span class="tN"> alignées sur la phrase
chinoise qui les précède (la ligne n'est corrigée que si elle compte autant de syllabes que la phrase de caractères).
"""
import html
import re

from opencc import OpenCC

VERS_SIMP = OpenCC("t2s")
CJK = re.compile(r"[㐀-鿿]")
DEBUT = set("儿子 儿童 儿女 儿科 儿媳 儿戏 儿时 儿孙 儿歌 儿化 儿郎 儿马".split())
FIN = set("女儿 婴儿 幼儿 孤儿 少儿 胎儿 健儿 宠儿 男儿 孙儿 患儿 育儿 弃儿 侄儿 乳儿 小儿 托儿 生儿 血儿 犬儿".split())
LECTURES_ER = {"ér", "er", "r", "ēr", "ěr", "èr"}
RUBY = re.compile(r'<ruby>([儿兒])<rt class="t\d">([^<]*)</rt></ruby>')
TOUT_RUBY = re.compile(r'<ruby>(.)<rt class="t\d">[^<]*</rt></ruby>')
SPAN = re.compile(r'<span class="t(\d)">([^<]*)</span>')


def plein(contexte: str, i: int) -> bool:
    """儿 en position i de `contexte` (caractères simplifiés) se lit-il ér (et non r) ?"""
    avant = contexte[i - 1] if i > 0 else ""
    if not avant or not CJK.match(avant):
        return True
    return contexte[i:i + 2] in DEBUT or contexte[i - 1:i + 1] in FIN


def _rubis(champ: str) -> str:
    rubis = list(TOUT_RUBY.finditer(champ))
    contexte = VERS_SIMP.convert("".join(m.group(1) for m in rubis))
    # un rubis séparé du précédent par autre chose qu'un rubis commence un nouveau groupe
    colle = [i > 0 and rubis[i - 1].end() == m.start() for i, m in enumerate(rubis)]
    for i in reversed(range(len(rubis))):
        m = rubis[i]
        r = RUBY.fullmatch(m.group(0))
        if not r or r.group(2) not in LECTURES_ER:
            continue
        debut, fin = i, i + 1
        while debut > 0 and colle[debut]:
            debut -= 1
        while fin < len(rubis) and colle[fin]:
            fin += 1
        lecture = ("ér", "2") if plein(contexte[debut:fin], i - debut) else ("r", "0")
        nouveau = f'<ruby>{r.group(1)}<rt class="t{lecture[1]}">{lecture[0]}</rt></ruby>'
        champ = champ[:m.start()] + nouveau + champ[m.end():]
    return champ


def _lignes(champ: str, recto: str) -> str:
    """Suites de <span class="tN"> (une syllabe chacune) alignées sur les caractères chinois qui les précèdent."""
    suites = list(re.finditer(r'(?:<span class="t\d">[^<]*</span>(?:[ 　，。！？、；：,.!?“”"‘’《》（）()…—·]|&[#\w]+;)*)+', champ))
    for s in reversed(suites):
        spans = list(SPAN.finditer(s.group(0)))
        if not any(sp.group(2) in LECTURES_ER for sp in spans):
            continue
        avant = re.sub(r"<[^>]+>", "", champ[:s.start()])
        cars = CJK.findall(html.unescape(avant))
        if len(cars) < len(spans):
            cars = CJK.findall(recto) if len(CJK.findall(recto)) == len(spans) else cars
        cars = cars[-len(spans):] if len(cars) >= len(spans) else []
        if len(cars) != len(spans):
            continue
        contexte = VERS_SIMP.convert("".join(cars))
        texte = s.group(0)
        for k in reversed(range(len(spans))):
            sp = spans[k]
            if contexte[k] != "儿" or sp.group(2) not in LECTURES_ER:
                continue
            if plein(contexte, k):
                nouveau = '<span class="t2">ér</span>'
            else:
                nouveau = '<span class="t0">r</span>'
            debut, fin = sp.start(), sp.end()
            # « r » se colle à la syllabe précédente : on retire l'espace qui l'en séparait
            if nouveau.endswith(">r</span>") and texte[:debut].endswith(" ") and k > 0 and spans[k - 1].end() == debut - 1:
                debut -= 1
            texte = texte[:debut] + nouveau + texte[fin:]
        champ = champ[:s.start()] + texte + champ[s.end():]
    return champ


def normaliser(paquets, stats=None, exclus=("Ecriture",)):
    """Corrige le pinyin de 儿 dans les versos. Renvoie le nombre de notes modifiées."""
    n = 0
    for nom, rangs in paquets.items():
        if nom in exclus:
            continue
        for r in rangs:
            if "a_supprimer" in r[3].split() or ("儿" not in r[1] and "兒" not in r[1]):
                continue
            recto = VERS_SIMP.convert(html.unescape(re.sub(r"<[^>]+>", "", r[0])))
            nouveau = _lignes(_rubis(r[1]), recto)
            if nouveau != r[1]:
                r[1] = nouveau
                n += 1
                if stats is not None:
                    stats[(nom, "儿 : ér (mot) / r (suffixe) uniformisé")] += 1
    return n
