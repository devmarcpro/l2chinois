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

Règles de lecture (28/09/2026) : ce qui est entre parenthèses (mot facultatif, variante, glose) n'est pas lu, ni une
forme fautive marquée *, ni une ligne « Aussi juste : … » ; 〇 est gardé (二〇二六年) ; deux variantes « 日文/日语 »
dans une phrase : la première ; un modèle « 是…的 » n'est pas lu à la place de la phrase ; un caractère seul l'est avec
la lecture de sa carte (sinon la synthèse prend la lecture la plus courante : 长 zhǎng, 得 de → 掌, 的) ; un exercice du
manuel fait entendre sa phrase complétée par la réponse (texte_exercice_manuel).
"""
import html
import re

CJK = re.compile(r"[一-鿿〇]")
GARDER = re.compile(r"[^一-鿿〇0-9０-９，。！？、；：“”‘’《》…\s]")  # 〇 : 二〇二六年 (sans lui : « 二二六年 »)
LOCUTEUR = re.compile(r"^\s*[^\s：:]{1,6}[：:]")  # 男：, 女：, 王：, A：
PARENTHESE = re.compile(r"[（(][^（）()]*[）)]")  # mot facultatif ou variante : 十点五十（分）, 没事（儿）, 她（他）


def _nu(s: str) -> str:
    s = re.sub(r"<rt[^>]*>.*?</rt>", "", s, flags=re.S)
    s = re.sub(r"</?(?:b|i|u|span|ruby|rb|small|big|font|strong|em)[^>]*>", "", s)  # balises dans la ligne : collées
    return html.unescape(re.sub(r"<[^>]+>", " ", s))


def _chinois(s: str, phrase=None) -> str:
    """Seulement le chinois : sans lettres (consignes, pinyin, traductions) ni trous (___). Ce qui est entre
    parenthèses (mot facultatif, variante, glose) n'est pas lu ; deux variantes « 日文/日语 » sont lues avec une pause."""
    s = re.sub(r"[*＊][^/／。！？]*[。！？]?", " ", _nu(s))  # forme fautive signalée par * : jamais lue
    s = PARENTHESE.sub(" ", s.replace("___", " ").replace("＿", " "))
    if re.search(r"[。！？]", s):  # dans une phrase, « 学日文/日语 » : la première variante seulement
        s = re.sub(r"(?<=[一-鿿])[/／][一-鿿]{1,3}(?![一-鿿])", "", s)
    s = re.sub(r"\s*[/／]\s*", "、", s)
    s = GARDER.sub(" ", s)
    s = re.sub(r"(?<![一-鿿〇0-9０-９])[0-9０-９]+(?![一-鿿〇0-9０-９])", " ", s)  # numéros isolés (语 3 雨 3)
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
            if len(mot) == 1:  # un caractère seul : lu avec la lecture de la carte (ligne de pinyin du verso)
                m = re.search(r'<span class="t\d">([^<]+)</span>', verso)
                mot = _homophone(mot, m.group(1) if m else "")
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
        if not m:
            return "", "tts::aucun"
        lecture = re.search(r'<span class="t\d">([^<]+)</span>', recto)  # la lecture donnée au recto
        return _homophone(m.group(1), lecture.group(1) if lecture else ""), "tts::caractere"
    # exercices (et fiches de grammaire anciennes, cartes privées d'exercices ou d'exemples) : la bonne réponse
    contexte = re.search(r"[（(]dans ([一-鿿]+)", _nu(recto))
    if contexte:  # lecture d'un caractère dans un mot (« 着 (dans 看着) ») : on fait entendre le mot, pas le caractère seul
        return contexte.group(1), "tts::reponse"
    # sans les lignes de variantes (« Aussi juste : … ») : on lit la réponse attendue, pas une variante plus longue
    avant_bloc = "<br>".join(l for l in re.split(r"<br\s*/?>", avant_bloc)
                             if not re.match(r"\s*(?:Aussi|Autre[s]? réponse|Variante)", _nu(l).strip()))
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
    t = _sans_modele(t)
    if "…" in t:  # la réponse n'est qu'un modèle (« 是…的 ») : on lit la phrase de l'énoncé
        autre = _sans_modele(_plus_long(recto))
        if CJK.search(autre) and "…" not in autre:
            t = autre
    if tags & {"exercice_chengyu", "exercice_expression"}:  # une expression : d'un seul tenant
        t = t.replace("，", "")
    return t, ("tts::reponse" if t else "tts::aucun")


TROU = re.compile(r"_{2,}|＿+|□|(?<=\s)_(?=\s)|(?<=[一-鿿])—(?=[一-鿿])")  # « 一个小时—到呢 » : trait = trou


def _sans_parentheses(s: str) -> str:
    while True:  # « (我没(有)买到) » : de l'intérieur vers l'extérieur
        t = PARENTHESE.sub(" ", s)
        if t == s:
            return t
        s = t


def texte_exercice_manuel(enonce: str, reponse: str) -> str:
    """Ce que fait entendre une carte d'exercice du manuel : la phrase juste, en entier.
    - énoncé à trous : si la réponse donne la phrase complète, cette phrase ; sinon l'énoncé complété par les
      morceaux de la réponse, dans l'ordre (« 的 ; 得 », « 又…又… », « ∅ ; 完 ; 到 » : ∅ = rien) ;
    - sans trou : la réponse si elle est en chinois (traduction, transformation), sinon l'énoncé.
    Rien à lire (chaîne vide) plutôt qu'une phrase à trous."""
    rep = re.sub(r"\(réponse proposée[^)]*\)", " ", str(reponse))
    rep = re.sub(r"^.*?Par exemple\s*:\s*", "", rep)
    rep = _sans_parentheses(rep)
    en = _sans_parentheses(_nu(str(enonce)))
    trous = TROU.findall(en)
    tout_rep = "".join(CJK.findall(rep))
    if not trous:
        en_zh = "".join(CJK.findall(en))
        if len(tout_rep) <= 2 and len(en_zh) > len(tout_rep):  # « 了 de changement » : on lit la phrase de l'énoncé
            return _chinois(en, phrase=True)
        if tout_rep:  # « 在哪儿 — 她上午十点半在哪儿开会？ » : la partie la plus longue, la phrase
            partie = max(re.split(r"\s[—–→=:]\s|[→：]", rep), key=lambda p: len(CJK.findall(p)))
            return _sans_modele(_chinois(partie, phrase=True))
        return _chinois(en, phrase=True)
    morceaux_en = TROU.split(en)
    fixes = ["".join(CJK.findall(m)) for m in morceaux_en if CJK.search(m)]
    if fixes and all(f in tout_rep for f in fixes):  # la réponse redonne la phrase entière
        parties = re.split(r"\s[—–]\s|[:：→=]", rep)
        meilleure = max(parties, key=lambda p: (sum(f in "".join(CJK.findall(p)) for f in fixes), len(p)))
        return _sans_modele(_chinois(meilleure, phrase=True))
    pieces = ["" if r in ("∅", "Ø") else r for r in re.findall(r"[一-鿿〇]+|[∅Ø]", rep)]
    if not pieces:
        return ""
    phrase = morceaux_en[0]
    for i, suite in enumerate(morceaux_en[1:]):
        phrase += (pieces[i] if i < len(pieces) else "") + suite
    return _chinois(phrase, phrase=True)


def _sans_modele(t: str) -> str:
    """Sans les morceaux qui ne sont que des modèles ou des variantes elliptiques (« 除了…以外 », « …，没给我写过信。 »),
    s'il reste une vraie phrase à lire."""
    parties = re.findall(r"[^。！？]+[。！？]?", t)
    gardees = [p for p in parties if "…" not in p]
    return "".join(gardees) if gardees and len(gardees) < len(parties) else t


_HOMOPHONES = {}


def _homophone(car: str, lecture: str) -> str:
    """Un caractère lu seul l'est avec sa lecture la plus courante : 长 → cháng, 得 → dé. Pour une autre lecture (长
    zhǎng « grandir », 得 de particule, 行 háng), on fait lire un caractère courant qui n'a que cette lecture-là
    (掌, 的, 航) : le même son, sans ambiguïté."""
    from pypinyin import Style, pinyin
    lecture = lecture.strip().lower()
    if not lecture or not re.fullmatch(r"[a-zāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜü]+", lecture):
        return car
    if pinyin(car, style=Style.TONE)[0][0] == lecture:
        return car
    if not _HOMOPHONES:
        import json
        from pathlib import Path
        f = Path(__file__).parent / "donnees_hsk" / "caracteres.json"
        cars = list(json.loads(f.read_text(encoding="utf-8"))) if f.exists() else []
        try:
            from wordfreq import zipf_frequency
            frequence = lambda c: zipf_frequency(c, "zh")  # noqa: E731
        except ImportError:
            import jieba
            frequence = lambda c: jieba.get_FREQ(c) or 0  # noqa: E731
        candidats = {}
        for c in cars:
            if not CJK.fullmatch(c):
                continue
            lectures = pinyin(c, style=Style.TONE, heteronym=True)[0]
            # d'abord les caractères à lecture unique, puis ceux dont c'est la lecture habituelle ; les plus courants
            candidats.setdefault(lectures[0], []).append((len(lectures) > 1, -frequence(c), c))
        _HOMOPHONES.update({l: min(v)[2] for l, v in candidats.items()})
    return _HOMOPHONES.get(lecture, car)
