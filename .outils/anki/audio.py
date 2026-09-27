# -*- coding: utf-8 -*-
"""Texte à faire lire par HyperTTS pour chaque note, et étiquette du genre d'audio.

Chaque fichier d'import a une 5e colonne, importée dans le champ « Texte audio » : le seul texte chinois que la
carte doit faire entendre (jamais la consigne ni le titre). HyperTTS le lit et met l'audio dans le champ
« Ajouter le verso » (réglage et recherche : LISEZMOI, AUDIO). Étiquettes :
- tts::mot        le mot (vocabulaire)                     audio au verso
- tts::phrase     la phrase (paquet Phrases)               audio au verso ; carte Dictée : au recto
- tts::dialogue   le texte d'écoute, sans titre ni 男：/女：  audio au recto (c'est l'exercice)
- tts::texte      le texte de lecture                      audio au verso
- tts::reponse    la bonne réponse d'un exercice            audio au verso (jamais au recto : elle la donnerait)
- tts::grammaire  la phrase « comprendre » puis la réponse « utiliser »   audio au verso
- tts::caractere  le caractère à écrire                    audio au verso
- tts::aucun      rien à lire
"""
import html
import re

CJK = re.compile(r"[一-鿿]")
GARDER = re.compile(r"[^一-鿿0-9０-９，。！？、；：“”‘’（）《》…\s]")
LOCUTEUR = re.compile(r"^\s*[^\s：:]{1,6}[：:]")  # 男：, 女：, 王：, A：


def _nu(s: str) -> str:
    s = re.sub(r"<rt[^>]*>.*?</rt>", "", s, flags=re.S)
    s = re.sub(r"</?(?:b|i|u|span|ruby|rb|small|big|font|strong|em)[^>]*>", "", s)  # balises dans la ligne : collées
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def _chinois(s: str, phrase=None) -> str:
    """Seulement le chinois : sans lettres (consignes, pinyin, traductions) ni trous (___)."""
    s = GARDER.sub(" ", _nu(s).replace("___", " ").replace("＿", " "))
    s = re.sub(r"(?<![一-鿿0-9０-９])[0-9０-９]+(?![一-鿿0-9０-９])", " ", s)  # numéros isolés (语 3 雨 3)
    s = re.sub(r"[（(]\s*[）)]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ，、；：")
    if phrase or (phrase is None and (re.search(r"[。！？]", s) or len(CJK.findall(s)) > 8)):  # une phrase
        return s.replace(" ", "")
    return re.sub(r"(?<=[一-鿿]) (?=[一-鿿])", "，", s).replace(" ", "")  # des mots séparés : une pause entre eux


def _segments(fragment: str):
    """Morceaux de texte d'un fragment HTML, coupés aux <br> et aux blocs."""
    for m in re.split(r"<br\s*/?>|</div>|<div[^>]*>|</p>|<p[^>]*>", fragment):
        t = _chinois(m)
        if CJK.search(t):
            yield t


def _plus_long(fragment: str) -> str:
    return max(_segments(fragment), key=lambda t: len(CJK.findall(t)), default="")


def _lignes_sans_locuteur(fragment: str) -> str:
    lignes = [LOCUTEUR.sub("", _nu(l)) for l in re.split(r"<br\s*/?>", fragment)]
    return " ".join(t for t in (_chinois(l) for l in lignes) if CJK.search(t))


def texte_audio(paquet: str, recto: str, verso: str, etiquettes: str):
    """(texte à lire, étiquette tts::…)."""
    tags = set(etiquettes.split())
    avant_bloc = verso.split('<div class="exemple-bloc"')[0]
    if paquet == "Vocabulaire":
        mot = _chinois(recto)
        if not re.search(r"。。。|…|\.\.\.", _nu(recto)) and CJK.search(mot):
            return mot, "tts::mot"
        m = re.search(r"<b>Exemple :</b>(.*?)(?: - |</div>)", verso, re.S)  # structure : on lit son exemple
        return (_chinois(m.group(1), phrase=True) if m else ""), ("tts::mot" if m else "tts::aucun")
    if paquet == "Phrases":
        return _chinois(recto), "tts::phrase"
    if paquet == "Ecoute" or "ecoute-texte" in recto:
        m = re.search(r'class="ecoute-texte">(.*?)</div>', recto, re.S)
        return (_lignes_sans_locuteur(m.group(1)) if m else ""), "tts::dialogue"
    if paquet == "Lecture" or "texte_gradue" in tags or "manuel_texte" in tags:
        corps = re.sub(r"^<div[^>]*>.*?</div>", "", recto, count=1, flags=re.S)  # sans la ligne de titre
        t = _lignes_sans_locuteur(corps)
        return t, ("tts::texte" if t else "tts::aucun")
    if paquet == "Grammaire" and 'class="g-rep-comprendre"' in verso:
        zh = [_chinois(x) for x in re.findall(r'<div class="g-zh">(.*?)</div>', verso, re.S)]
        t = "。".join(z.rstrip("。") for z in zh if z) + "。"
        return t, "tts::grammaire"
    if paquet == "Ecriture":
        m = re.search(r'class="ecriture-car"[^>]*>\s*([一-鿿])', verso)
        return (m.group(1) if m else ""), ("tts::caractere" if m else "tts::aucun")
    # exercices (et fiches de grammaire anciennes, cartes privées d'exercices ou d'exemples) : la bonne réponse
    t = _plus_long(avant_bloc)
    trou = re.search(r"[^<>]*?(?:_{2,}|＿)[^<>]*", recto)
    if len(CJK.findall(t)) <= 4 and trou and CJK.search(trou.group(0)):  # réponse d'un mot : la phrase complétée
        parties = [p for p in (_chinois(x) for x in re.split(r"_{2,}|＿+", trou.group(0))) if CJK.search(p)]
        if parties and all(p in t.replace("，", "") for p in parties):  # le verso donne déjà l'expression entière
            t = t.replace("，", "")
        else:
            phrase = _chinois(re.sub(r"_{2,}|＿+", t, _nu(trou.group(0))))
            if len(CJK.findall(phrase)) > len(CJK.findall(t)):
                t = phrase
    if not t:  # ton, pinyin d'un caractère : le caractère lui-même
        t = _plus_long(recto)
    if tags & {"exercice_chengyu", "exercice_expression"}:  # une expression : d'un seul tenant
        t = t.replace("，", "")
    return t, ("tts::reponse" if t else "tts::aucun")
