# -*- coding: utf-8 -*-
"""Contenu ajouté aux paquets Anki : ce qui est vu dans les cours de L2 (leçons 10-11 du manuel, séances de septembre 2026)
et les structures de base qui manquaient au paquet de grammaire. Chaque liste va du plus simple au plus difficile.
Le pinyin est calculé automatiquement puis relu ; `FORCER` corrige une lecture au besoin.
"""
import re
import sys
from pathlib import Path

import jieba
from opencc import OpenCC
from pypinyin import Style, lazy_pinyin

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "site"))
from pinyin_correct import CJK, base, corriger, ton  # noqa: E402

VERS_TRAD = OpenCC("s2tw")
VERS_SIMP = OpenCC("t2s")
ZI_PLEIN = set("电子 分子 原子 量子 男子 女子 王子 孔子 老子 孟子 庄子 韩非子 君子 弟子 才子 诸子 棋子 妻子".split())
FORCER = {}  # phrase -> {index du caractère: lecture}
ER_PLEIN = set("女儿 婴儿 幼儿 孤儿 少儿 胎儿 小儿 儿子 儿童".split())
NEUTRES_LOCAUX = "晚上 早上 时候 朋友 学生 先生 意思 关系 多少 咳嗽 名字 太太 知道 喜欢 衣服".split()


# ------------------------------------------------------------------ pinyin et mise en forme
def lire_phrase(zh: str):
    """Lecture de chaque caractère chinois de la phrase (tons réellement prononcés)."""
    cars = CJK.findall(zh)
    lectures = [lazy_pinyin(c, style=Style.TONE)[0] for c in cars]
    for k, v in FORCER.get(zh, {}).items():  # avant la correction, pour que le sandhi de 一 / 不 en tienne compte
        lectures[k] = v
    lectures, _ = corriger(zh, lectures)
    positions = [i for i, c in enumerate(zh) if CJK.match(c)]
    pos = 0
    for mot in jieba.cut(zh):
        fin = pos + len(mot)
        if len(mot) >= 2 and (fin - 1) in positions:
            k = positions.index(fin - 1)
            if mot.endswith("子") and mot not in ZI_PLEIN:
                lectures[k] = "zi"
            elif mot.endswith("儿") and mot not in ER_PLEIN:
                lectures[k] = "r"
        pos = fin
    for mot in NEUTRES_LOCAUX:  # dernière syllabe au ton neutre, même si jieba a découpé autrement
        d = zh.find(mot)
        while d >= 0:
            k = positions.index(d + len(mot) - 1)
            lectures[k] = "".join(c for c in __import__("unicodedata").normalize("NFD", lectures[k]) if not __import__("unicodedata").combining(c))
            d = zh.find(mot, d + 1)
    for k, v in FORCER.get(zh, {}).items():
        lectures[k] = v
    return lectures


def span(l):
    return f'<span class="t{ton(l)}">{l}</span>'


def spans_par_syllabe(zh):
    """Format du paquet Phrases : une syllabe par <span>, séparées par des espaces, ponctuation collée."""
    it = iter(lire_phrase(zh))
    sortie = ""
    for c in zh:
        if CJK.match(c):
            sortie += ("" if not sortie or sortie[-1] in "，。！？、；：“”《》（）" else " ") + span(next(it))
        elif not c.isspace():
            sortie += c
    return sortie


def spans_par_mot(zh):
    """Format du paquet Grammaire : les syllabes d'un mot sont collées, les mots séparés par des espaces."""
    it = iter(lire_phrase(zh))
    morceaux = []
    for mot in jieba.cut(zh):
        if any(CJK.match(c) for c in mot):
            morceaux.append("".join(span(next(it)) if CJK.match(c) else c for c in mot))
        elif morceaux and not mot.isspace():
            morceaux[-1] += mot
        elif not mot.isspace():
            morceaux.append(mot)
    return " ".join(morceaux)


def ruby(zh):
    it = iter(lire_phrase(zh))
    return "".join(f'<ruby>{c}<rt class="t{ton(l := next(it))}">{l}</rt></ruby>' if CJK.match(c) else c for c in zh)


# ------------------------------------------------------------------ GRAMMAIRE
# (niveau, titre, explication, [(phrase, traduction)], étiquette supplémentaire)
GRAMMAIRE = [
    ("HSK 1", "的 (de) — possession et déterminant du nom",
     "Déterminant + 的 + nom : le déterminant (possesseur, adjectif, proposition) se place toujours <b>avant</b> le nom. Avec un proche ou une institution, 的 tombe souvent : 我妈妈, 我们学校.",
     [("这是我的书。", "C'est mon livre."), ("她是我妈妈。", "C'est ma mère. (proche : pas de 的)"), ("我喜欢他买的那本书。", "J'aime le livre qu'il a acheté.")], ""),
    ("HSK 1", "这 / 那 + classificateur + nom",
     "Démonstratif (ou nombre) + <b>classificateur</b> + nom. Un nom ne suit jamais directement un nombre. 个 est le classificateur général ; 本 pour les livres, 件 pour les vêtements, 只 (zhī) pour les animaux.",
     [("这个人是我的老师。", "Cette personne est mon professeur."), ("那本书很贵。", "Ce livre-là est très cher."), ("我有两只猫。", "J'ai deux chats.")], ""),
    ("HSK 1", "几 / 多少 — combien",
     "几 + classificateur + nom : petit nombre attendu (moins de dix). 多少 (+ nom) : nombre quelconque, classificateur facultatif. Le mot interrogatif reste à la place de la réponse.",
     [("你家有几口人？", "Combien êtes-vous dans ta famille ?"), ("你们班有多少学生？", "Combien d'étudiants y a-t-il dans votre classe ?"), ("这个多少钱？", "Combien ça coûte ?")], ""),
    ("HSK 1", "什么 / 谁 / 哪儿 / 怎么 — les mots interrogatifs restent en place",
     "En chinois on ne déplace pas le mot interrogatif : il occupe la place de la réponse, et on n'ajoute pas 吗.",
     [("你叫什么名字？", "Comment t'appelles-tu ?"), ("他是谁？", "Qui est-ce ?"), ("你去哪儿？", "Où vas-tu ?"), ("这个字怎么写？", "Comment s'écrit ce caractère ?")], ""),
    ("HSK 1", "想 / 要 — avoir envie de, vouloir",
     "想 + V : avoir envie de (souhait). 要 + V : vouloir, avoir décidé de (plus ferme) ; 要 + nom : vouloir quelque chose. Négation du souhait : 不想.",
     [("我想喝茶。", "J'ai envie de boire du thé."), ("我要去中国学习。", "Je vais (je veux) aller étudier en Chine."), ("我不想去。", "Je n'ai pas envie d'y aller.")], ""),
    ("HSK 1", "会 / 能 / 可以 — savoir, pouvoir",
     "会 : savoir faire (compétence apprise). 能 : pouvoir (capacité, conditions réunies). 可以 : avoir la permission, être possible.",
     [("我会说一点儿汉语。", "Je sais parler un peu chinois."), ("我今天很忙，不能去。", "Je suis très occupé aujourd'hui, je ne peux pas y aller."), ("我可以进来吗？", "Est-ce que je peux entrer ?")], ""),
    ("HSK 1", "和 / 跟 — et, avec",
     "和 relie deux <b>noms</b> (jamais deux phrases). 跟 + personne + 一起 + V : faire quelque chose avec quelqu'un ; ce groupe se place avant le verbe.",
     [("我和他都是学生。", "Lui et moi sommes tous les deux étudiants."), ("我跟朋友一起去看电影。", "Je vais voir un film avec un ami."), ("你跟谁一起去的？", "Avec qui y es-tu allé ?")], "cours_L2"),
    ("HSK 1", "太…了 — trop, tellement",
     "太 + adjectif + 了 : excès (trop) ou exclamation (tellement). Négation atténuée : 不太 + adjectif = pas très.",
     [("太贵了！", "C'est trop cher !"), ("这个菜太好吃了。", "Ce plat est vraiment délicieux."), ("我不太喜欢喝咖啡。", "Je n'aime pas trop le café.")], ""),
    ("HSK 1", "V 不 V — question par alternative",
     "Verbe (ou adjectif) affirmatif + négatif = question oui / non, sans 吗. Avec 有 : 有没有. Dans cette structure 不 se prononce au ton neutre.",
     [("你去不去？", "Tu y vas ou pas ?"), ("他是不是老师？", "Est-il professeur ?"), ("你有没有时间？", "As-tu du temps ?")], ""),
    ("HSK 2", "正在…呢 / 在 + V — action en cours",
     "正在 + V (+ 呢) : action en train de se faire à l'instant même. 在 + V : action en cours, en progression. 呢 en fin de phrase suffit à l'oral. Négation : 没(在) + V.",
     [("他正在看书呢。", "Il est en train de lire."), ("我在做饭，你等一下。", "Je suis en train de cuisiner, attends un instant."), ("我没在看电视，我在学习。", "Je ne regarde pas la télé, j'étudie.")], "cours_L2"),
    ("HSK 2", "刚 / 刚才 — venir de, à l'instant",
     "刚 (adverbe, devant le verbe) : l'action vient de se produire. 刚才 (nom de temps) : il y a un instant ; peut se placer en tête de phrase et s'employer avec une négation.",
     [("他刚吃了药。", "Il vient de prendre son médicament."), ("我刚到北京。", "Je viens d'arriver à Pékin."), ("刚才你去哪儿了？", "Où étais-tu il y a un instant ?")], "cours_L2"),
    ("HSK 2", "一边…一边… — deux actions en même temps",
     "一边 + V1 + 一边 + V2 : le même sujet fait deux <b>actions</b> simultanément. Pour deux états ou qualités, on emploie 又…又….",
     [("他喜欢一边坐车一边看书。", "Il aime lire en prenant le bus."), ("她喜欢一边弹钢琴一边唱歌。", "Elle aime chanter en jouant du piano."), ("他一边学法语一边学电脑。", "Il apprenait le français tout en apprenant l'informatique.")], "cours_L2"),
    ("HSK 2", "又…又… — à la fois… et…",
     "又 + adjectif / verbe d'état + 又 + adjectif : deux <b>qualités ou états</b> qui coexistent. À ne pas confondre avec 一边…一边… (deux actions).",
     [("这个菜又便宜又好吃。", "Ce plat est à la fois bon marché et délicieux."), ("她又聪明又漂亮。", "Elle est à la fois intelligente et jolie."), ("他又高又瘦。", "Il est grand et mince.")], "cours_L2"),
    ("HSK 2", "因为…所以… — cause et conséquence",
     "因为 + cause, 所以 + conséquence. Les deux mots peuvent s'employer ensemble (contrairement au français « parce que… donc »), ou l'un sans l'autre.",
     [("因为下雨，所以我没去。", "Comme il pleuvait, je n'y suis pas allé."), ("她找安娜，因为快要考试了。", "Elle cherche Anna parce que l'examen approche."), ("我病了，所以今天不能来。", "Je suis malade, donc je ne peux pas venir aujourd'hui.")], "cours_L2"),
    ("HSK 2", "如果…(的话)，就… — si… alors…",
     "如果 + condition (+ 的话), (sujet) + 就 + conséquence. 就 se place après le sujet de la seconde proposition.",
     [("如果明天下雨，我就不去了。", "S'il pleut demain, je n'irai pas."), ("如果你有时间的话，我们一起吃饭吧。", "Si tu as le temps, mangeons ensemble."), ("如果你不舒服，就去看医生。", "Si tu ne te sens pas bien, va voir un médecin.")], ""),
    ("HSK 2", "从…到… / 离 — de… à… ; distance",
     "从 + départ + 到 + arrivée (lieu ou temps). A + 离 + B + 远 / 近 : distance entre deux points. 从…开始 : à partir de.",
     [("我从星期一到星期五上课。", "J'ai cours du lundi au vendredi."), ("我家离学校很近。", "Ma maison est tout près de l'école."), ("他从昨天晚上开始不舒服。", "Il ne se sent pas bien depuis hier soir.")], "cours_L2"),
    ("HSK 2", "一点儿 vs 有点儿 — un peu",
     "adjectif + 一点儿 : un peu plus (comparaison, demande). 有点儿 + adjectif : un peu trop (ressenti négatif). V + 一点儿 + nom : un peu de.",
     [("请说慢一点儿。", "Parlez un peu plus lentement, s'il vous plaît."), ("今天有点儿冷。", "Il fait un peu froid aujourd'hui."), ("我想喝一点儿水。", "Je voudrais boire un peu d'eau.")], ""),
    ("HSK 2", "别 / 不要 — interdiction",
     "别 + V = 不要 + V : ne… pas ! 别…了 : arrête de… / ne… plus.",
     [("别忘了吃药。", "N'oublie pas de prendre tes médicaments."), ("不要说话。", "Ne parlez pas."), ("别看手机了，快睡觉吧。", "Arrête de regarder ton téléphone, va vite dormir.")], "cours_L2"),
    ("HSK 2", "已经…了 — déjà",
     "已经 + V / adjectif + 了 : l'action est déjà accomplie, l'état est déjà atteint.",
     [("他已经走了。", "Il est déjà parti."), ("我已经吃饭了。", "J'ai déjà mangé."), ("现在已经十二点了。", "Il est déjà midi.")], ""),
    ("HSK 2", "就 vs 才 — plus tôt / plus tard que prévu",
     "moment + 就 + V (+ 了) : plus tôt, plus vite ou plus facilement que prévu. moment + 才 + V (sans 了) : plus tard ou plus difficilement que prévu.",
     [("他六点就起床了。", "Il s'est levé dès six heures."), ("他十点才起床。", "Il ne s'est levé qu'à dix heures."), ("我昨天晚上十二点才睡觉。", "Hier soir je ne me suis couché qu'à minuit.")], ""),
    ("HSK 2", "V + 一下 / verbe redoublé — faire un peu, essayer",
     "V + 一下, V + V ou V + 一 + V : action brève, essai, ton adouci. Dans V一V, 一 se prononce au ton neutre. Verbe de deux syllabes : ABAB (休息休息).",
     [("请等一下。", "Attendez un instant, s'il vous plaît."), ("你试一试这件衣服。", "Essaie donc ce vêtement."), ("我想看看那本书。", "J'aimerais jeter un œil à ce livre.")], "cours_L2"),
    ("HSK 2", "还 / 再 / 又 — encore",
     "再 + V : encore une fois, dans le <b>futur</b>. 又 + V + 了 : de nouveau, déjà <b>arrivé</b>. 还 + V : encore, toujours (ça continue) ; en plus.",
     [("明天再说吧。", "On en reparle demain."), ("他又迟到了。", "Il est encore arrivé en retard."), ("她还在睡觉。", "Elle dort encore.")], "cours_L2"),
    ("HSK 2", "V + 了 + durée — complément de durée",
     "V + 了 + durée (+ 的) + objet. Avec un deuxième 了 en fin de phrase, l'action continue jusqu'à maintenant. La durée se place <b>après</b> le verbe.",
     [("我学了两年汉语。", "J'ai étudié le chinois pendant deux ans."), ("我学了两年汉语了。", "Ça fait deux ans que j'étudie le chinois (et je continue)."), ("他每天拉一个半小时小提琴。", "Il joue du violon une heure et demie par jour.")], "cours_L2"),
    ("HSK 2", "次 / 遍 — complément de fréquence",
     "V + (过 / 了) + nombre + 次 + objet : nombre de fois. Avec un nom de lieu, 次 peut suivre : 去过中国一次. 遍 insiste sur le déroulement complet, du début à la fin.",
     [("我去过一次中国。", "Je suis allé une fois en Chine."), ("这个电影我看了两遍。", "J'ai vu ce film deux fois (en entier)."), ("请再说一遍。", "Répétez encore une fois, s'il vous plaît.")], "cours_L2"),
    ("HSK 2", "要 / 会 — deux futurs",
     "要 + V : futur proche, décision ou certitude (volonté forte). 会 + V (+ 的) : forte probabilité, prévision. 快要…了 : être sur le point de.",
     [("我明天要去北京。", "Je pars demain à Pékin. (c'est décidé)"), ("明天会下雨。", "Il pleuvra (probablement) demain."), ("快要考试了。", "L'examen approche.")], "cours_L2"),
    ("HSK 2", "不能 vs 不会 — ne pas pouvoir / il est improbable que",
     "不能 + V : impossibilité due à des conditions connues. 不会 + V : supposition, « il ne va sûrement pas… ».",
     [("我病了，今天不能来。", "Je suis malade, je ne peux pas venir aujourd'hui."), ("他病了，今天不会来。", "Il est malade, il ne viendra sûrement pas aujourd'hui."), ("别担心，他不会忘的。", "Ne t'inquiète pas, il n'oubliera pas.")], "cours_L2"),
    ("HSK 3", "V + 到 / 见 / 完 / 好 — compléments de résultat",
     "Le complément indique le <b>résultat</b> de l'action : 找 chercher → 找到 trouver ; 听 écouter → 听到 / 听见 entendre ; 看 regarder → 看到 / 看见 voir ; 完 = fini ; 好 = bien terminé. Négation avec 没.",
     [("我找到我的手机了。", "J'ai retrouvé mon téléphone."), ("我什么都没看到。", "Je n'ai rien vu du tout."), ("作业你做完了吗？", "As-tu fini tes devoirs ?")], "cours_L2"),
    ("HSK 3", "Lieu + V着 + nom — phrase d'existence",
     "Lieu + V + 着 + (nombre + classificateur) + nom : décrit ce qui se trouve quelque part et dans quelle position (description). Le nom est indéfini.",
     [("床上放着一本书。", "Un livre est posé sur le lit."), ("墙上挂着一张地图。", "Une carte est accrochée au mur."), ("门口站着两个人。", "Deux personnes se tiennent à l'entrée.")], "cours_L2"),
    ("HSK 3", "V1着 + V2 — manière + action",
     "V1 + 着 (+ objet) + V2 : V1着 indique la <b>manière</b> ou la posture dans laquelle se fait l'action principale V2.",
     [("他哭着看爱情小说。", "Il lit un roman d'amour en pleurant."), ("他在床上躺着看小说。", "Allongé sur son lit, il lit un roman."), ("她笑着说：“没关系。”", "Elle dit en souriant : « Ce n'est rien. »")], "cours_L2"),
    ("HSK 3", "了 après le verbe / 了 en fin de phrase",
     "V + 了 + objet : l'action est <b>accomplie</b>. Phrase + 了 : la <b>situation a changé</b> (nouvel état). La place de 了 change le sens. Après 没, jamais de 了.",
     [("他去中国学了中文。", "Il a étudié le chinois en Chine. (action accomplie)"), ("他去中国学中文了。", "Il est parti étudier le chinois en Chine. (situation nouvelle)"), ("我病了。", "Je suis malade. (je ne l'étais pas avant)")], "cours_L2"),
    ("HSK 3", "不但…而且… — non seulement… mais en plus…",
     "Relation de gradation (递进关系). Même sujet : sujet + 不但…，而且…. Sujets différents : 不但 + sujet 1…，而且 + sujet 2 + 也….",
     [("他不但会说汉语，而且会写汉字。", "Non seulement il parle chinois, mais en plus il sait écrire les caractères."), ("这个手机不但好看，而且很便宜。", "Ce téléphone est non seulement joli, mais en plus pas cher."), ("不但他去，而且他的朋友也去。", "Non seulement il y va, mais ses amis aussi.")], "cours_L2"),
    ("HSK 3", "并不是…，而是… — ce n'est pas du tout…, mais…",
     "不是 A，而是 B : ce n'est pas A, c'est B. 并 devant la négation la <b>renforce</b> et contredit ce que l'on pourrait croire.",
     [("我并不是不想去，而是没有时间。", "Ce n'est pas que je ne veuille pas y aller, c'est que je n'ai pas le temps."), ("他得到这份工作并不是因为他能力强，而是因为他太太是老板的女儿。", "S'il a obtenu ce travail, ce n'est pas du tout parce qu'il est compétent, mais parce que sa femme est la fille du patron."), ("这并不难。", "Ce n'est pas difficile du tout.")], "cours_L2"),
    # ---- renforcement écrit : connecteurs et modèles de textes
    ("HSK 3", "为了 — dans le but de (连接目的)",
     "为了 + but, + action : le but se place <b>en tête</b> de phrase (ou juste avant le verbe). Ne pas confondre avec 因为 (cause). À l'écrit on trouve aussi 为的是 après l'action.",
     [("为了学好中文，他每天听中文广播。", "Pour bien apprendre le chinois, il écoute la radio chinoise tous les jours."), ("为了健康，我们应该少吃盐。", "Pour la santé, nous devrions manger moins salé."), ("他这么做，为的是让父母放心。", "Il agit ainsi pour rassurer ses parents.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 3", "不过 / 其实 — mais (atténué) / en fait",
     "不过 = mais, cependant, plus léger que 但是 ; toujours en tête de la seconde proposition. 其实 = en fait, en réalité (corrige une idée reçue) ; se place après le sujet ou en tête.",
     [("这家饭馆的菜很好吃，不过有点贵。", "Les plats de ce restaurant sont délicieux, mais un peu chers."), ("大家都以为他很严肃，其实他很幽默。", "Tout le monde le croit sérieux, en fait il est très drôle."), ("其实我早就知道了。", "En fait, je le savais depuis longtemps.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 4", "由于…，(因此/所以)… — cause, registre écrit (因果关系)",
     "由于 + cause, 因此 / 所以 + conséquence : équivalent écrit et plus formel de 因为…所以…. 因此 = par conséquent (peut ouvrir une phrase seul). Ordre : la cause d'abord.",
     [("由于天气不好，比赛推迟了。", "En raison du mauvais temps, la compétition a été reportée."), ("他工作很努力，因此进步很快。", "Il travaille dur, par conséquent il progresse vite."), ("由于时间有限，我们只能先讨论最重要的问题。", "Le temps étant limité, nous ne pouvons discuter d'abord que de la question la plus importante.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 4", "既…又… — à la fois… et… (并列关系, écrit)",
     "既 + A + 又 + B : deux qualités ou deux actions qui coexistent, même sujet. Plus écrit que 又…又…. Variante : 既…也….",
     [("这个办法既简单又有效。", "Cette méthode est à la fois simple et efficace."), ("她既会说英语，又会说日语。", "Elle parle à la fois anglais et japonais."), ("网购既方便又便宜。", "Les achats en ligne sont à la fois pratiques et bon marché.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 4", "首先…，其次…，最后… / 总之 — organiser un paragraphe",
     "Pour énumérer des arguments à l'écrit : 首先 (d'abord), 其次 (ensuite), 再次 / 另外 (de plus), 最后 (enfin). 总之 = en somme, pour conclure. Chaque connecteur ouvre une phrase, suivi d'une virgule.",
     [("首先，网购很方便；其次，价格比较便宜；最后，选择也更多。", "D'abord, les achats en ligne sont pratiques ; ensuite, les prix sont plutôt bas ; enfin, le choix est plus grand."), ("总之，学习语言需要时间和耐心。", "En somme, apprendre une langue demande du temps et de la patience."), ("另外，别忘了带护照。", "De plus, n'oublie pas de prendre ton passeport.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 3", "描述一个人 — décrire une personne",
     "Apparence : 长得 + adj (长得很高 / 很漂亮), 个子 + 高/矮, 留着长头发, 戴眼镜. Caractère : 性格 + adj (开朗 / 内向 / 热情), 对人很 + adj (对人很友好). Goûts : 喜欢 + V, 对…感兴趣.",
     [("我的朋友个子很高，留着短头发，戴眼镜。", "Mon ami est grand, il a les cheveux courts et porte des lunettes."), ("她性格开朗，对人很热情。", "Elle a un caractère ouvert et elle est chaleureuse avec les gens."), ("他对音乐很感兴趣，周末常去听音乐会。", "Il s'intéresse beaucoup à la musique, le week-end il va souvent au concert.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 3", "描述一个地方 — décrire un lieu",
     "Situation : X 位于 / 在 + lieu, 离…很近/很远. Contenu : lieu + 有 + …, 又…又…, 到处都是…. Appréciation : 风景很美, 很热闹 / 很安静, 值得一去.",
     [("我的家乡位于中国南方，离海很近。", "Ma ville natale se trouve dans le sud de la Chine, tout près de la mer."), ("公园里有一个湖，湖边有很多树，又安静又漂亮。", "Dans le parc il y a un lac, au bord du lac beaucoup d'arbres ; c'est à la fois calme et joli."), ("这个地方风景很美，值得一去。", "Le paysage de cet endroit est très beau, il vaut le détour.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 3", "请假条 — le mot d'excuse (demande de congé)",
     "Modèle : 1) destinataire + 您好！ 2) motif : 因为…，3) demande : 我想请假 + durée (请一天假 / 请假两天), 4) 望批准 (merci d'accepter), 5) formule finale 此致 / 敬礼, 6) nom (学生 X) et date. Registre poli : 您, 请, 麻烦.",
     [("王老师，您好！因为我生病了，明天不能来上课，想请假一天，望批准。", "Bonjour Madame Wang. Comme je suis malade, je ne pourrai pas venir en cours demain ; je souhaite demander un jour de congé, merci de bien vouloir l'accepter."), ("我想请两天假回家看父母。", "Je voudrais prendre deux jours de congé pour rentrer voir mes parents."), ("此致敬礼。学生李明，9月20日。", "Respectueusement. L'étudiant Li Ming, le 20 septembre.")], "cours_L2 L2_renforcement_ecrit"),
    ("HSK 4", "电子邮件 — l'e-mail formel",
     "主题 (objet) court. Ouverture : 尊敬的 / 亲爱的 + nom + ：您好！ Corps : 我是…，我想… / 请问…. Pièce jointe : 附件是…. Clôture : 期待您的回复 (dans l'attente de votre réponse), 祝好 / 祝工作顺利, puis nom et date.",
     [("尊敬的张老师：您好！我是二年级的学生李华。", "Cher Professeur Zhang, bonjour. Je suis Li Hua, étudiant de deuxième année."), ("附件是我的作业，请您查收。", "Vous trouverez mon devoir en pièce jointe, je vous prie de bien vouloir le recevoir."), ("期待您的回复。祝好！", "Dans l'attente de votre réponse. Bien cordialement.")], "cours_L2 L2_renforcement_ecrit"),
    # ---- renforcement oral : discuter d'un enregistrement à l'oral
    ("HSK 2", "我觉得 / 我认为 — donner son avis à l'oral",
     "我觉得 + phrase : le plus courant, ton neutre. 我认为 + phrase : plus affirmé, un peu plus soutenu. Pour demander l'avis de l'autre : 你觉得呢？/ 你怎么看？",
     [("我觉得这篇文章很有意思。", "Je trouve cet article très intéressant."), ("我认为这个说法不太对。", "Je pense que cette affirmation n'est pas tout à fait exacte."), ("你觉得呢？", "Et toi, qu'en penses-tu ?")], "cours_L2 L2_renforcement_oral"),
    ("HSK 2", "我同意 / 我不同意 — être d'accord ou pas, à l'oral",
     "我同意 + (你的看法/这一点) : être d'accord. 我不同意，我觉得… : exprimer un désaccord poliment, toujours suivi de son propre avis. 有道理 = c'est logique / ça se tient (concession partielle).",
     [("我同意你的看法。", "Je suis d'accord avec ton point de vue."), ("我不同意，我觉得应该先讨论问题的原因。", "Je ne suis pas d'accord, je pense qu'il faut d'abord discuter de la cause du problème."), ("你说的有道理。", "Ce que tu dis se tient.")], "cours_L2 L2_renforcement_oral"),
    ("HSK 3", "能不能再说一遍？— demander de répéter ou d'expliquer",
     "能不能再说一遍？/ 你能再说一次吗？ : demander une répétition. 我没听懂 / 我没听清楚 : dire qu'on n'a pas compris (清楚 = clairement, un problème d'écoute ; 懂 = un problème de compréhension). 这是什么意思？: demander le sens d'un mot.",
     [("对不起，能不能再说一遍？", "Pardon, pouvez-vous répéter une fois de plus ?"), ("我没听清楚，你是说几点见面？", "Je n'ai pas bien entendu, tu dis qu'on se retrouve à quelle heure ?"), ("“举例”是什么意思？", "Que veut dire « 举例 » ?")], "cours_L2 L2_renforcement_oral"),
    ("HSK 3", "换句话说 / 简单来说 — reformuler à l'oral",
     "换句话说 = autrement dit (reformule ce qui vient d'être dit). 简单来说 = pour faire simple, en résumé (introduit une synthèse). 也就是说 = c'est-à-dire.",
     [("他没有直接拒绝，换句话说，他还在考虑。", "Il n'a pas refusé directement, autrement dit, il réfléchit encore."), ("简单来说，这篇文章讲的是环境保护。", "Pour faire simple, cet article parle de la protection de l'environnement."), ("也就是说，我们得重新讨论一下。", "C'est-à-dire qu'il va falloir qu'on en rediscute.")], "cours_L2 L2_renforcement_oral"),
    ("HSK 3", "举个例子来说 — donner un exemple à l'oral",
     "举个例子(来说) : formule pour introduire un exemple à l'oral. 比如 / 比如说 : par exemple (plus court, très courant). Placés en tête de la phrase d'exemple.",
     [("举个例子来说，很多年轻人现在喜欢网购。", "Pour donner un exemple, beaucoup de jeunes aiment aujourd'hui faire leurs achats en ligne."), ("比如说，我们可以先讨论第一个问题。", "Par exemple, on pourrait d'abord discuter de la première question."), ("这种情况很常见，比如在大城市。", "Ce cas de figure est très courant, par exemple dans les grandes villes.")], "cours_L2 L2_renforcement_oral"),
    ("HSK 3", "我想补充一点 — prendre la parole dans une discussion",
     "我想补充一点 : ajouter une remarque à ce qui vient d'être dit. 我还有一个问题 : poser une nouvelle question. 打断一下 (可以吗) : interrompre poliment. 我先说完 : demander à finir avant de laisser l'autre parler.",
     [("我想补充一点，这篇文章还提到了…", "Je voudrais ajouter un point : cet article mentionne aussi…"), ("打断一下，可以吗？我还有一个问题。", "Je peux t'interrompre ? J'ai encore une question."), ("等一下，让我先说完。", "Attends, laisse-moi d'abord finir.")], "cours_L2 L2_renforcement_oral"),
]

# ------------------------------------------------------------------ mots complémentaires (thèmes des cours, absents du paquet)
# (mot, sens, cours, exemple, traduction de l'exemple)
VOCAB_SUPPLEMENT = [
    ("请假条", "mot d'excuse, demande de congé (écrit)", "Renforcement écrit", "生病了要给老师写请假条。", "Quand on est malade, il faut écrire un mot d'excuse au professeur."),
    ("邮件", "courrier ; e-mail (电子邮件)", "Renforcement écrit", "我给老师发了一封邮件。", "J'ai envoyé un e-mail au professeur."),
    ("附件", "pièce jointe", "Renforcement écrit", "附件是我的简历。", "Mon CV est en pièce jointe."),
    ("下单", "passer une commande (en ligne)", "Renforcement écrit", "我昨天在网上下单了，今天就到了。", "J'ai commandé en ligne hier, c'est arrivé aujourd'hui."),
    ("转折", "opposition, concession (relation logique 转折关系)", "Renforcement écrit", "“但是”表示转折。", "« 但是 » exprime l'opposition."),
    ("递进", "gradation, renchérissement (递进关系 : 不但…而且)", "Renforcement écrit", "“不但……而且”表示递进关系。", "« 不但…而且 » exprime une gradation."),
    ("民国", "la République de Chine (1912-1949)", "Histoire et civilisation chinoises", "1912年，中华民国成立。", "En 1912, la République de Chine est fondée."),
    ("王朝", "dynastie (régime)", "Histoire et civilisation chinoises", "清朝是中国最后一个王朝。", "Les Qing sont la dernière dynastie chinoise."),
    ("灭亡", "tomber, disparaître (dynastie, État)", "Histoire et civilisation chinoises", "唐朝于907年灭亡。", "La dynastie Tang tombe en 907."),
    ("起义", "soulèvement, insurrection", "Histoire et civilisation chinoises", "黄巢起义削弱了唐朝。", "La révolte de Huang Chao affaiblit les Tang."),
    ("变法", "réforme (des lois et institutions)", "Histoire et civilisation chinoises", "王安石变法发生在宋朝。", "Les réformes de Wang Anshi ont lieu sous les Song."),
    ("首都", "capitale", "Histoire et civilisation chinoises", "唐朝的首都是长安。", "La capitale des Tang était Chang'an."),
    ("法家", "école légiste (法家)", "Philosophie chinoise", "韩非子是法家的代表人物。", "Han Feizi est la figure représentative des légistes."),
    ("墨家", "école mohiste (墨家)", "Philosophie chinoise", "墨家主张兼爱。", "Les mohistes prônent l'amour universel."),
    ("兼爱", "amour universel (Mozi)", "Philosophie chinoise", "墨子提出“兼爱”的思想。", "Mozi a formulé l'idée d'« amour universel »."),
    ("智", "sagesse, intelligence (une des cinq vertus 仁义礼智信)", "Philosophie chinoise", "仁、义、礼、智、信是儒家的五常。", "Humanité, justice, rites, sagesse et confiance sont les cinq vertus constantes du confucianisme."),
    ("性善", "bonté originelle de la nature humaine (Mencius)", "Philosophie chinoise", "孟子主张性善论。", "Mencius soutient la thèse de la bonté de la nature humaine."),
    ("性恶", "nature humaine mauvaise (Xunzi)", "Philosophie chinoise", "荀子主张性恶论。", "Xunzi soutient la thèse d'une nature humaine mauvaise."),
    ("君子", "homme de bien (idéal confucéen)", "Philosophie chinoise", "君子坦荡荡，小人长戚戚。", "L'homme de bien est serein ; l'homme de peu est toujours inquiet."),
    ("小人", "homme de peu (opposé de 君子)", "Philosophie chinoise", "君子和而不同，小人同而不和。", "L'homme de bien s'accorde sans s'identifier ; l'homme de peu s'identifie sans s'accorder."),
    ("举例", "donner un exemple (à l'oral, pour illustrer un point)", "Renforcement oral", "我可以举个例子吗？", "Je peux donner un exemple ?"),
    ("提问", "poser une question", "Renforcement oral", "听完录音后，老师会提问。", "Après l'écoute, le professeur posera des questions."),
    ("详细", "détaillé, en détail", "Renforcement oral", "你能说得详细一点吗？", "Peux-tu en dire un peu plus en détail ?"),
    ("简要", "bref, sommaire", "Renforcement oral", "请简要说说你的想法。", "Donne brièvement ton avis."),
    ("补充", "compléter, ajouter (une remarque)", "Renforcement oral", "我想补充一点。", "Je voudrais ajouter un point."),
    ("抗日战争", "guerre de résistance contre le Japon (1937-1945)", "Histoire et civilisation chinoises", "抗日战争于1945年结束。", "La guerre de résistance contre le Japon s'achève en 1945."),
    ("闭关锁国", "politique de fermeture au monde extérieur (chengyu, fin des Qing)", "Histoire et civilisation chinoises", "清朝后期的闭关锁国政策使中国落后于西方。", "La politique de fermeture de la fin des Qing a fait prendre du retard à la Chine par rapport à l'Occident."),
    ("有教无类", "l'éducation sans distinction (Confucius : tout le monde mérite d'être éduqué)", "Philosophie chinoise", "孔子提出“有教无类”的教育思想。", "Confucius a formulé l'idée que l'éducation doit être offerte à tous, sans distinction."),
    ("舍生取义", "sacrifier sa vie pour la justice (Mencius, chengyu)", "Philosophie chinoise", "孟子提倡“舍生取义”的精神。", "Mencius prônait l'esprit consistant à sacrifier sa vie pour la justice."),
    ("道法自然", "le Dao suit la nature de lui-même (Laozi)", "Philosophie chinoise", "“道法自然”是道家思想的核心。", "« Le Dao suit sa propre nature » est au cœur de la pensée taoïste."),
]

# mots DÉJÀ présents dans le paquet à étiqueter cours_L2 pour un thème à venir (le programme n'y est pas encore,
# mais le mot existe déjà dans le paquet général) : mot -> cours (clé de ETIQUETTE_COURS)
MOTS_A_ETIQUETER = {
    "讨论": "Renforcement oral", "观点": "Renforcement oral", "总结": "Renforcement oral", "换句话说": "Renforcement oral",
    "回答": "Renforcement oral", "简单来说": "Renforcement oral",
    "宋朝": "Histoire et civilisation chinoises", "元朝": "Histoire et civilisation chinoises",
    "明朝": "Histoire et civilisation chinoises", "清朝": "Histoire et civilisation chinoises",
    "鸦片战争": "Histoire et civilisation chinoises", "辛亥革命": "Histoire et civilisation chinoises",
    "五四运动": "Histoire et civilisation chinoises",
    "知行合一": "Philosophie chinoise", "天人合一": "Philosophie chinoise", "无为而治": "Philosophie chinoise",
    "丝绸之路": "Histoire et civilisation chinoises",
}

# ------------------------------------------------------------------ PHRASES (niveau, phrase, traduction, notes, étiquettes)
PHRASES = [
    (1, "真的吗？", "Vraiment ? C'est vrai ?", "真的 = vrai, pour de vrai · 吗 = particule interrogative", "quotidien"),
    (1, "这是我的同学，也是我的好朋友。", "C'est mon / ma camarade de classe, et aussi un(e) bon(ne) ami(e).", "同学 = camarade de classe · 也 = aussi, toujours avant le verbe · pour présenter quelqu'un", "quotidien"),
    (1, "她今年二十四岁。", "Elle a vingt-quatre ans cette année.", "今年 = cette année · 岁 = an (âge) · pas de verbe 是 devant l'âge", "quotidien"),
    (1, "她很喜欢打游戏。", "Elle aime beaucoup jouer aux jeux vidéo.", "打游戏 = jouer aux jeux vidéo · 很喜欢 = aimer beaucoup", "quotidien"),
    (1, "明天再说吧。", "On en reparle demain.", "再 = de nouveau (dans le futur) · 吧 = suggestion · expression toute faite", "quotidien"),
    (2, "快要考试了。", "L'examen approche. / On va bientôt passer l'examen.", "快要…了 = être sur le point de · titre du dialogue 112 (leçon 10)", "grammaire"),
    (2, "我下周有考试。", "J'ai un examen la semaine prochaine.", "下周 = la semaine prochaine · 考试 = examen", "quotidien"),
    (2, "老师，您好！我生病了，想请假一天。", "Bonjour Madame / Monsieur. Je suis malade, je voudrais un jour de congé.", "请假 = demander un congé (verbe séparable : 请一天假) · 您 = vous de politesse", "ecrit"),
    (3, "我在网上买了一件衣服，三天就收到了快递。", "J'ai acheté un vêtement en ligne, j'ai reçu le colis en trois jours.", "在网上买 = acheter en ligne · 快递 = livraison express, colis · 就 = plus vite que prévu", "ecrit"),
    (3, "这件衣服太小了，我想退货。", "Ce vêtement est trop petit, je voudrais le retourner.", "退货 = retourner un article · 太…了 = trop", "ecrit"),
    (3, "他长得很高，性格很开朗，对人很友好。", "Il est grand, il a un caractère ouvert et il est aimable avec les gens.", "长得 + adj = physique · 性格 = caractère · 对人 + adj = avec les gens (description d'une personne)", "ecrit"),
    (3, "我的家乡不大，但是很安静，风景也很美。", "Ma ville natale n'est pas grande, mais elle est très calme et le paysage y est très beau.", "但是 = 转折 (opposition) · 家乡 = ville / pays natal (description d'un lieu)", "ecrit"),
    (4, "由于价格便宜，越来越多的人选择网购。", "Comme les prix sont bas, de plus en plus de gens choisissent les achats en ligne.", "由于 = 因为 à l'écrit · 越来越多 = de plus en plus de · 网购 = achats en ligne", "ecrit"),
    (4, "网购虽然方便，但是也有一些问题，比如质量不好。", "Les achats en ligne sont certes pratiques, mais ils posent aussi quelques problèmes, par exemple la mauvaise qualité.", "虽然…但是 = concession · 比如 = par exemple · 质量 = qualité", "ecrit"),
    (4, "附件是我的作业，请您查收。期待您的回复。", "Mon devoir est en pièce jointe, je vous prie de le recevoir. Dans l'attente de votre réponse.", "查收 = vérifier la réception (formule d'e-mail) · 期待您的回复 = formule de clôture", "ecrit"),
    (2, "我觉得这篇文章很有意思，你觉得呢？", "Je trouve cet article très intéressant, et toi, qu'en penses-tu ?", "我觉得 = donner son avis · 你觉得呢 = demander l'avis de l'autre (discussion à l'oral)", "oral"),
    (3, "我不同意，我觉得应该先讨论原因。", "Je ne suis pas d'accord, je pense qu'il faut d'abord discuter de la cause.", "我不同意 + son propre avis = exprimer un désaccord poliment (discussion à l'oral)", "oral"),
    (3, "对不起，能不能再说一遍？我没听清楚。", "Pardon, pouvez-vous répéter ? Je n'ai pas bien entendu.", "能不能再说一遍 = demander une répétition · 没听清楚 = ne pas avoir bien entendu (compréhension orale)", "oral"),
    (3, "简单来说，这篇文章讲的是环境保护。", "Pour faire simple, cet article parle de la protection de l'environnement.", "简单来说 = reformuler brièvement · 讲的是 = parler de, traiter de (discussion à l'oral)", "oral"),
    (3, "举个例子来说，很多年轻人现在喜欢网购。", "Pour donner un exemple, beaucoup de jeunes aiment aujourd'hui faire leurs achats en ligne.", "举个例子来说 = introduire un exemple à l'oral · 比如 est plus court et tout aussi courant", "oral"),
    (3, "我想补充一点，这篇文章还提到了环境问题。", "Je voudrais ajouter un point : cet article mentionne aussi la question environnementale.", "我想补充一点 = prendre la parole pour ajouter une remarque (discussion à l'oral)", "oral"),
    (2, "我通过考试了。", "J'ai réussi l'examen.", "通过 = réussir, passer · négation : 我没通过考试 · échouer : 不及格", "quotidien"),
    (2, "我什么都没看到。", "Je n'ai rien vu du tout.", "什么都 + négation = rien du tout · 看到 = voir (résultat) · négation du résultat avec 没", "grammaire"),
    (2, "你吃药了吗？", "As-tu pris tes médicaments ?", "吃药 = prendre un médicament (litt. « manger ») · 了…吗 = est-ce fait ?", "sante"),
    (2, "别忘了吃药。", "N'oublie pas de prendre tes médicaments.", "别 = ne… pas (interdiction) · 忘 = oublier", "sante"),
    (2, "我上周生病了，现在快好了。", "Je suis tombé malade la semaine dernière, je suis bientôt guéri.", "生病 = tomber malade · 快…了 = bientôt · 好了 = guéri", "sante"),
    (2, "他病得很重。", "Il est gravement malade.", "V + 得 + adjectif = complément de degré · 重 = grave, lourd ; contraire : 轻", "sante"),
    (2, "我给她打一个电话。", "Je lui passe un coup de téléphone.", "给 + personne + 打电话 = téléphoner à quelqu'un · le groupe 给… se place avant le verbe", "quotidien"),
    (2, "他刚吃了药。", "Il vient de prendre son médicament.", "刚 + V = venir de · ne pas confondre avec 刚才 (nom de temps)", "grammaire"),
    (2, "老师在教室教学生。", "Le professeur enseigne aux élèves dans la salle de classe.", "教室 jiàoshì = salle de classe · 教 jiāo = enseigner · 教师 jiàoshī = enseignant", "grammaire"),
    (2, "他头痛、咳嗽，还发烧。", "Il a mal à la tête, il tousse, et il a aussi de la fièvre.", "顿号 「、」 pour une énumération · 还 = en plus · 发烧 = avoir de la fièvre", "sante"),
    (2, "他早上九点去看医生了。", "Il est allé voir le médecin à neuf heures ce matin.", "complément de temps avant le verbe · 看医生 = consulter un médecin", "sante"),
    (2, "现在他在家里休息。", "Maintenant il se repose à la maison.", "在 + lieu + V : le lieu se place avant le verbe · 休息 = se reposer", "quotidien"),
    (2, "暑假的时候她去了中国学习。", "Pendant les vacances d'été, elle est allée étudier en Chine.", "…的时候 = au moment de, pendant · 暑假 = vacances d'été · récit au passé : ne pas oublier 了", "quotidien"),
    (2, "你跟谁一起去的？", "Avec qui y es-tu allé ?", "(是)…的 met en relief une circonstance d'une action passée, ici « avec qui » · 是 est souvent omis", "grammaire"),
    (2, "你怎么去中国的？", "Comment es-tu allé en Chine ?", "(是)…的 : on sait que l'action a eu lieu, on demande la manière", "grammaire"),
    (2, "他是昨天坐下午三点的火车去的。", "C'est hier qu'il est parti, par le train de trois heures de l'après-midi.", "是…的 : insiste sur le moment et le moyen de transport · 坐火车 = prendre le train", "grammaire"),
    (2, "他是自己一个人来的。", "Il est venu tout seul.", "自己一个人 = tout seul · 是…的 : insiste sur la manière", "grammaire"),
    (2, "他喜欢一边坐车一边看书。", "Il aime lire en prenant le bus.", "一边…一边… = deux actions en même temps", "grammaire"),
    (2, "他每天拉一个半小时小提琴。", "Il joue du violon une heure et demie par jour.", "拉小提琴 = jouer du violon · la durée se place entre le verbe et l'objet · 一个半小时 = une heure et demie", "grammaire"),
    (3, "床上放着一件毛衣。", "Un pull est posé sur le lit.", "lieu + V着 + nom = phrase d'existence (description) · 件 = classificateur des vêtements", "grammaire"),
    (3, "他哭着看爱情小说。", "Il lit un roman d'amour en pleurant.", "V1着 + V2 : V1着 donne la manière · 爱情小说 = roman d'amour", "grammaire"),
    (3, "他在床上躺着看小说。", "Allongé sur son lit, il lit un roman.", "躺 = être allongé · V1着 + V2 · l'aspect duratif se rend souvent par l'imparfait", "grammaire"),
    (3, "他去中国学中文了。", "Il est parti étudier le chinois en Chine.", "了 en fin de phrase : la situation a changé (il est parti)", "grammaire"),
    (3, "他去中国学了中文。", "Il a étudié le chinois en Chine.", "了 après le verbe : l'action est accomplie", "grammaire"),
    (3, "我病了，今天不能来。", "Je suis malade, je ne peux pas venir aujourd'hui.", "病了 : 了 obligatoire (changement d'état) · 不能 : impossibilité due aux circonstances", "grammaire"),
    (3, "他病了，今天不会来。", "Il est malade, il ne viendra sûrement pas aujourd'hui.", "不会 : supposition, probabilité", "grammaire"),
    (3, "你借给我的这本书很有意思。", "Le livre que tu m'as prêté est très intéressant.", "借给 + personne = prêter à · proposition + 的 + nom · 有意思 = intéressant", "grammaire"),
    (3, "他今天没来公司，去德国出差了。", "Il n'est pas venu au bureau aujourd'hui, il est parti en déplacement en Allemagne.", "出差 chūchāi = partir en déplacement professionnel · 没来 : négation du passé", "travail"),
    (3, "刚来的时候他不会说法语。", "Quand il venait d'arriver, il ne savait pas parler français.", "刚 + V + 的时候 = au moment où l'on vient de · 不会 = ne pas savoir", "quotidien"),
    (3, "他一边学法语一边学电脑。", "Il apprenait le français tout en apprenant l'informatique.", "一边…一边… · 电脑 = ordinateur, informatique", "grammaire"),
    (3, "李苗苗昨天去了故宫。", "Li Miaomiao est allée hier au palais impérial.", "故宫 Gùgōng = palais impérial, Cité interdite · complément de temps avant le verbe", "culture"),
    (3, "谢先生想知道多一点，就问了她几个问题。", "M. Xie voulait en savoir un peu plus, alors il lui a posé quelques questions.", "多一点 = un peu plus · 就 = alors (enchaînement) · 问 + personne + 问题", "grammaire"),
    (4, "毕业以后他开始在旅行社工作，后来换了几份工作，最后来到这家公司。", "Après son diplôme, il a commencé à travailler dans une agence de voyages, ensuite il a changé plusieurs fois de travail, et il est finalement arrivé dans cette entreprise.", "…以后，后来…，最后… = après…, ensuite…, finalement… · 份 = classificateur de 工作 · 家 = classificateur des entreprises", "travail"),
    (4, "他能得到这份工作并不是因为他能力强，而是因为他太太是这家公司老板的女儿。", "S'il a pu obtenir ce travail, ce n'est pas du tout parce qu'il est très compétent, mais parce que sa femme est la fille du patron de l'entreprise.", "并不是…而是… = ce n'est pas du tout…, mais… · 得到 = obtenir · 能力强 = compétent · 老板 = patron", "travail"),
    (6, "道之以德，齐之以礼，有耻且格。", "Si on conduit le peuple par la vertu et qu'on l'accorde par les rites, il aura le sens de la honte et se rectifiera de lui-même.", "《论语·为政》 II, 3 (Confucius) · 道 se lit ici dǎo (= 导, conduire) · 德 = vertu · 礼 = rites · réponse confucéenne à « comment obtenir l'ordre ? »", "philosophie"),
    (6, "为政以德，譬如北辰，居其所而众星共之。", "Gouverner par la vertu, c'est être comme l'étoile polaire : elle demeure à sa place et toutes les étoiles se tournent vers elle.", "《论语·为政》 II, 1 · 北辰 = étoile polaire · 共 se lit ici gǒng (= 拱, saluer, entourer) · le gouvernant exemplaire", "philosophie"),
    (6, "礼之用，和为贵。", "Dans l'usage des rites, c'est l'harmonie qui est le plus précieux.", "《论语·学而》 I, 12 (parole de 有子 Youzi) · 和 = harmonie · 为贵 = être tenu pour précieux", "philosophie"),
    (6, "我无为而民自化。", "Je pratique le non-agir, et le peuple se transforme de lui-même.", "《道德经》 chapitre 57 · 无为 wúwéi = non-agir : éviter l'action forcée, ce n'est pas l'inaction · 自化 = se transformer de soi-même", "philosophie"),
    (6, "道常无为而无不为。", "Le Dao agit constamment par le non-agir, et pourtant rien ne reste inaccompli.", "《道德经》 chapitre 37 · 无不为 : double négation, « il n'y a rien qui ne soit fait »", "philosophie"),
    (6, "法不阿贵，绳不挠曲。", "La loi ne favorise pas les puissants, de même que le cordeau ne se plie pas à ce qui est courbe.", "《韩非子·有度》 chapitre 6 · 法 = loi, norme · 阿 ē = flatter, favoriser · 绳 = cordeau · thèse légiste : la règle s'applique à tous", "philosophie"),
]
FORCER["道之以德，齐之以礼，有耻且格。"] = {0: "dǎo"}
FORCER["为政以德，譬如北辰，居其所而众星共之。"] = {0: "wéi", 14: "gǒng"}
FORCER["礼之用，和为贵。"] = {4: "wéi"}
FORCER["我无为而民自化。"] = {2: "wéi"}
FORCER["道常无为而无不为。"] = {3: "wéi", 7: "wéi"}
FORCER["法不阿贵，绳不挠曲。"] = {2: "ē"}

# ------------------------------------------------------------------ EXERCICES (genre, recto, verso)
def _exo(consigne, enonce, choix, reponse, explication, phrase_complete=""):
    recto = f"{consigne}<br><br>{enonce}" + (f"<br><br>Choix : {choix}" if choix else "")
    verso = f"<b>Réponse : {reponse}</b><br><br>" + (f"{phrase_complete}<br><br>" if phrase_complete else "")
    return recto, verso + f'<div class="exemple-bloc"><b>Explication :</b> {explication}</div>'


EXERCICES = [
    ("exercice_ton", *_exo("Comment se prononce 一 dans ce mot ?", '<span class="hanzi">一个</span>', "yī / yí / yì", "yí (2e ton)", "Devant un 4e ton, 一 passe au 2e ton : yí gè. 个 compte comme un 4e ton même prononcé légèrement.")),
    ("exercice_ton", *_exo("Comment se prononce 一 dans ce mot ?", '<span class="hanzi">一起</span>', "yī / yí / yì", "yì (4e ton)", "Devant un 1er, 2e ou 3e ton, 一 passe au 4e ton : yì qǐ, yì tiān, yì nián.")),
    ("exercice_ton", *_exo("Comment se prononce 一 dans ce mot ?", '<span class="hanzi">第一</span>', "yī / yí / yì", "yī (1er ton)", "Dans les nombres, les dates, les ordinaux et en fin de mot, 一 garde son 1er ton : dì yī, yī yuè, xīngqī yī.")),
    ("exercice_ton", *_exo("Comment se prononce 不 dans ce mot ?", '<span class="hanzi">不是</span>', "bù / bú", "bú (2e ton)", "Devant un 4e ton, 不 passe au 2e ton : bú shì, bú qù, bú yào. Partout ailleurs il reste au 4e ton : bù hǎo, bù lái.")),
    ("exercice_ton", *_exo("De quel ton est 教 dans cette phrase ?", '<span class="hanzi">老师在教室教学生。</span> (le second 教)', "1er ton / 4e ton", "1er ton (jiāo)", "教 jiāo = enseigner (verbe seul). Dans les mots 教室, 教师, 教育, il se lit jiào.")),
    ("exercice_ton", *_exo("Comment se lit 只 dans ce groupe ?", '<span class="hanzi">两只猫</span>', "zhī / zhǐ", "zhī (1er ton)", "只 zhī est le classificateur des animaux. 只 zhǐ signifie « seulement » : 我只有一只猫 (wǒ zhǐ yǒu yì zhī māo).")),
    ("exercice_aspect", *_exo("Choisissez la bonne particule aspectuelle :", "床上放___一本书。", "了 / 着 / 过", "着", "Lieu + V着 + nom : phrase d'existence, on décrit un état qui dure (un livre est posé sur le lit).", "床上放<b>[ 着 ]</b>一本书。")),
    ("exercice_aspect", *_exo("Choisissez la bonne particule aspectuelle :", "他哭___看爱情小说。", "了 / 着 / 过", "着", "V1着 + V2 : V1着 exprime la manière (en pleurant) dont se fait l'action principale.", "他哭<b>[ 着 ]</b>看爱情小说。")),
    ("exercice_aspect", *_exo("Où placer 了 pour dire « Il a étudié le chinois en Chine » (action accomplie) ?", "他去中国学中文。", "他去中国学了中文。 / 他去中国学中文了。", "他去中国学了中文。", "了 après le verbe marque l'action accomplie. 他去中国学中文了 (了 final) veut dire qu'il est parti : la situation a changé.")),
    ("exercice_aspect", *_exo("Complétez pour dire « L'examen approche » :", "___考试了。", "快要 / 正在 / 刚", "快要", "快要…了 (ou 要…了, 就要…了) : action sur le point de se produire. 正在 : action en cours. 刚 : action qui vient d'avoir lieu.", "<b>[ 快要 ]</b>考试了。")),
    ("exercice_aspect", *_exo("Complétez pour dire « Il vient de prendre son médicament » :", "他___吃了药。", "刚 / 正在 / 快要", "刚", "刚 + V : l'action vient de s'accomplir.", "他<b>[ 刚 ]</b>吃了药。")),
    ("exercice_remplir", *_exo("Complétez avec 的, 得 ou 地 :", "他病___很重。", "的 / 得 / 地", "得", "V / adjectif + 得 + complément de degré. Rappel : 得 + adjectif ou adverbe, 的 + nom, 地 + verbe.", "他病<b>得</b>很重。")),
    ("exercice_remplir", *_exo("Complétez avec 的, 得 ou 地 :", "你借给我___这本书很有意思。", "的 / 得 / 地", "的", "Proposition + 的 + nom : « le livre que tu m'as prêté ».", "你借给我<b>的</b>这本书很有意思。")),
    ("exercice_remplir", *_exo("Complétez avec 的, 得 ou 地 :", "他慢慢___走进教室。", "的 / 得 / 地", "地", "Adverbe (ou adjectif redoublé) + 地 + verbe : manière de faire l'action.", "他慢慢<b>地</b>走进教室。")),
    ("exercice_remplir", *_exo("Complétez la phrase :", "我什么都没看___。", "到 / 完 / 好", "到", "看到 (ou 看见) = voir : 到 indique que l'action atteint son résultat. Négation du résultat avec 没.", "我什么都没看<b>到</b>。")),
    ("exercice_remplir", *_exo("能 ou 会 ?", "他病了，今天不___来。（supposition : il ne viendra sûrement pas）", "能 / 会", "会", "不会 + V : probabilité, supposition. 不能 + V : impossibilité due à des conditions connues (我病了，今天不能来).", "他病了，今天不<b>会</b>来。")),
    ("exercice_remplir", *_exo("一边…一边… ou 又…又… ?", "这个菜___便宜___好吃。", "一边…一边… / 又…又…", "又…又…", "又…又… relie deux qualités ou états. 一边…一边… relie deux actions faites en même temps.", "这个菜<b>又</b>便宜<b>又</b>好吃。")),
    ("exercice_structure", *_exo("Identifiez la structure grammaticale :", "你跟谁一起去的？ — Pourquoi 的 en fin de phrase ?", "Possession / Structure (是)…的 : on insiste sur une circonstance d'une action passée / Adjectif", "Structure (是)…的", "On sait que l'action a eu lieu ; (是)…的 met en relief avec qui, quand, où ou comment. 是 est souvent omis.")),
    ("exercice_structure", *_exo("Identifiez la structure grammaticale :", "他得到这份工作并不是因为他能力强，而是因为他太太是老板的女儿。 — Que signifie 并不是…而是… ?", "Non seulement… mais aussi… / Ce n'est pas du tout…, mais… / Bien que… cependant…", "Ce n'est pas du tout…, mais…", "不是 A 而是 B = ce n'est pas A mais B ; 并 renforce la négation.")),
    ("exercice_ordre", "Remettez les mots dans le bon ordre :<br><br>一边 / 他 / 看书 / 坐车 / 喜欢 / 一边", "<b>Ordre correct :</b><br>他喜欢一边坐车一边看书。<br><br><div class=\"exemple-bloc\"><b>Traduction :</b> Il aime lire en prenant le bus.</div>"),
    ("exercice_ordre", "Remettez les mots dans le bon ordre :<br><br>去 / 我 / 朋友 / 看电影 / 跟 / 一起", "<b>Ordre correct :</b><br>我跟朋友一起去看电影。<br><br><div class=\"exemple-bloc\"><b>Traduction :</b> Je vais voir un film avec un ami. (跟 + personne + 一起 se place avant le verbe)</div>"),
    ("exercice_ordre", "Remettez les mots dans le bon ordre :<br><br>小提琴 / 他 / 一个半小时 / 每天 / 拉", "<b>Ordre correct :</b><br>他每天拉一个半小时小提琴。<br><br><div class=\"exemple-bloc\"><b>Traduction :</b> Il joue du violon une heure et demie par jour. (la durée se place entre le verbe et l'objet)</div>"),
    ("exercice_correction", "Trouvez et corrigez l'erreur dans cette phrase :<br><br>我昨天没去了学校。", "<b>Phrase correcte :</b><br>我昨天没去学校。<br><br><div class=\"exemple-bloc\"><b>Explication :</b> Avec la négation 没, on ne met jamais 了 : 没 + V.</div>"),
    ("exercice_correction", "Trouvez et corrigez l'erreur dans cette phrase :<br><br>我学习汉语在大学。", "<b>Phrase correcte :</b><br>我在大学学习汉语。<br><br><div class=\"exemple-bloc\"><b>Explication :</b> Les compléments de lieu et de temps se placent <b>avant</b> le verbe : sujet + 在 + lieu + verbe + objet.</div>"),
]

# ------------------------------------------------------------------ exemples rédigés pour les mots du cours absents du paquet
EXEMPLES = {
    "回复": [("请尽快回复我的邮件。", "Merci de répondre rapidement à mon e-mail.")],
    "病人": [("医生正在给病人看病。", "Le médecin est en train d'examiner le patient.")],
    "看医生": [("你发烧了，应该去看医生。", "Tu as de la fièvre, tu devrais aller voir un médecin.")],
    "吃药": [("别忘了吃药。", "N'oublie pas de prendre tes médicaments."), ("他刚吃了药。", "Il vient de prendre son médicament.")],
    "买药": [("我去药店买药。", "Je vais à la pharmacie acheter des médicaments.")],
    "西药": [("西药见效快，中药见效慢。", "Les médicaments occidentaux agissent vite, les médicaments chinois agissent lentement.")],
    "拿起来": [("他把书拿起来看了看。", "Il a pris le livre et y a jeté un œil.")],
    "走进": [("他慢慢地走进教室。", "Il entre lentement dans la salle de classe.")],
    "进来": [("请进来坐一下。", "Entrez donc vous asseoir un instant.")],
    "进去": [("门开着，我们进去吧。", "La porte est ouverte, entrons.")],
    "口试": [("我下周有口试。", "J'ai un examen oral la semaine prochaine.")],
    "笔试": [("笔试比口试难。", "L'examen écrit est plus difficile que l'oral.")],
    "不及格": [("这次考试他不及格。", "Il n'a pas eu la moyenne à cet examen.")],
    "听到": [("我听到有人敲门。", "J'ai entendu quelqu'un frapper à la porte.")],
    "看到": [("我什么都没看到。", "Je n'ai rien vu du tout.")],
    "想要": [("你想要什么礼物？", "Quel cadeau voudrais-tu ?")],
    "暑假": [("暑假的时候她去了中国学习。", "Pendant les vacances d'été, elle est allée étudier en Chine.")],
    "星期天": [("星期天我们一起去公园吧。", "Dimanche, allons ensemble au parc.")],
    "打游戏": [("他每天晚上打游戏。", "Il joue aux jeux vidéo tous les soirs.")],
    "坐火车": [("他是坐火车去德国的。", "C'est en train qu'il est allé en Allemagne.")],
    "看电影": [("我每个周末都去看电影。", "Je vais au cinéma tous les week-ends.")],
    "开会": [("他上午跟客户开会。", "Ce matin il est en réunion avec un client.")],
    "看牙医": [("我牙疼，得去看牙医。", "J'ai mal aux dents, il faut que j'aille chez le dentiste.")],
    "宗教": [("中国有五个官方承认的宗教。", "La Chine compte cinq religions officiellement reconnues.")],
    "战国": [("战国时期出现了很多思想流派。", "De nombreuses écoles de pensée sont apparues à l'époque des Royaumes combattants.")],
    "诸子百家": [("诸子百家出现在春秋战国时期。", "Les Cent écoles sont apparues aux époques des Printemps et Automnes et des Royaumes combattants.")],
    "句号": [("句子写完了要加句号。", "À la fin d'une phrase, il faut mettre un point.")],
    "顿号": [("我喜欢喝茶、咖啡和果汁。", "J'aime boire du thé, du café et du jus de fruits. (「、」 = 顿号, virgule d'énumération)")],
    "书名号": [("我在看《红楼梦》。", "Je suis en train de lire « Le Rêve dans le pavillon rouge ». (《》 = 书名号)")],
}

ETIQUETTE_COURS = {
    "Structures grammaticales": "L2_grammaire", "Lexicologie - Expression écrite": "L2_lexicologie",
    "Compréhension orale": "L2_comprehension_orale", "Expression orale": "L2_expression_orale",
    "Histoire et civilisation chinoises": "L2_histoire", "Philosophie chinoise": "L2_pensee",
    "Renforcement écrit": "L2_renforcement_ecrit", "Renforcement oral": "L2_renforcement_oral", "Version": "L2_version",
}


# ------------------------------------------------------------------ fabrication des notes
def note_grammaire(niveau, titre, explication, exemples, extra):
    recto = (f'<b>Structure :</b><br><br><span style="font-size:130%;color:#2980b9">{titre}</span><br><br>'
             f'<small style="color:#888">{niveau}</small>')
    corps = "".join(f"• {zh}<br><small>{spans_par_mot(zh)}</small><br><i>{fr}</i><br><br>" for zh, fr in exemples)
    verso = f'<div class="exemple-bloc" style="text-align:left"><b>Explication :</b><br>{explication}<br><br><b>Exemples :</b><br>{corps}</div>'
    return [recto, verso, "", " ".join(filter(None, ["grammaire", "deck_v2", "ajout_2026", extra]))]


def note_phrase(niveau, zh, fr, notes, extra):
    verso = (f'<span class="hanzi-trad">{VERS_TRAD.convert(zh)}</span><br>{spans_par_syllabe(zh)}<br>{fr}<br><br>'
             f'<div class="exemple-bloc"><b>Notes :</b><br>{notes}</div>')
    return [zh, verso, "", f"Phrases_HSK{niveau} {extra} cours_L2 ajout_2026"]


def note_vocabulaire(mot, pinyin_note, francais, exemple_cours, source, etiquette):
    lectures = lire_phrase(mot)
    alerte = None
    if pinyin_note and base("".join(lectures)) != base(re.sub(r"[^A-Za-zÀ-ÿǎěǐǒǔǚüāēīōūǖńňǹ]", "", pinyin_note.split("(")[0])):
        alerte = (mot, " ".join(lectures), pinyin_note)
    verso = f'<span class="hanzi-trad">{VERS_TRAD.convert(mot)}</span><br>{"".join(span(l) for l in lectures)}<br>{francais}'
    verso += f'<br><br><div class="exemple-bloc"><b>Notes :</b>Vu en cours de L2 : {source}</div>'
    exemples = list(EXEMPLES.get(mot, []))
    lignes = [f"{ruby(zh)} - {fr}" for zh, fr in exemples]
    if not lignes and exemple_cours and CJK.search(exemple_cours) and len(exemple_cours) <= 30 and mot in exemple_cours:
        lignes = [ruby(exemple_cours) + " (exemple du cours)"]
    if lignes:
        verso += '<br><br><div class="exemple-bloc"><b>Exemple :</b>' + "<br>".join(lignes) + "</div>"
    return [mot, verso, "", f"cours_L2 {etiquette} ajout_2026"], alerte


def mots_du_cours():
    """Les mots des tableaux de vocabulaire du coffre (même extraction que le site)."""
    import build
    notes = build.charger()
    cours = {n.dossier: n for n in notes if n.type == "cours"}
    mots = []
    for n in notes:
        for m in build.extraire_vocabulaire(n, cours.get(n.dossier)):
            formes = [h.strip() for h in re.split(r"\s*/\s*", m["h"])]
            sens = [f.strip() for f in re.split(r"\s+/\s+", m["f"])]
            for i, h in enumerate(formes):  # « 客观 / 主观 » = « objectif / subjectif » : chacun son sens
                if re.fullmatch(r"[一-鿿]{1,4}", h) and VERS_SIMP.convert(h) == h:
                    mots.append({**m, "h": h, "f": sens[i] if len(sens) == len(formes) else m["f"]})
    return mots


def ajouter_contenu(paquets):
    bilan = {}
    # grammaire : on n'ajoute pas une structure dont le titre existe déjà
    titres = {re.sub(r"<[^>]+>", "", r[0]) for r in paquets["Grammaire"]}
    neuves = [note_grammaire(*g) for g in GRAMMAIRE]
    neuves = [n for n in neuves if re.sub(r"<[^>]+>", "", n[0]) not in titres]
    paquets["Grammaire"] += neuves
    bilan["Grammaire : structures ajoutées"] = len(neuves)

    rectos = {r[0] for r in paquets["Phrases"]}
    neuves = [note_phrase(*p) for p in PHRASES if p[1] not in rectos]
    paquets["Phrases"] += neuves
    bilan["Phrases : phrases du cours ajoutées"] = len(neuves)

    rectos = {r[0] for r in paquets["Exercices"]}
    neuves = [[recto, verso, "", f"{genre} deck_v2 cours_L2 ajout_2026"] for genre, recto, verso in EXERCICES if recto not in rectos]
    paquets["Exercices"] += neuves
    bilan["Exercices : exercices sur les points du cours ajoutés"] = len(neuves)

    # vocabulaire : étiqueter les mots déjà présents, créer les absents
    index = {r[0].strip(): r for r in paquets["Vocabulaire"]}
    etiquetes, crees, alertes, vus = 0, 0, [], set()
    for m in mots_du_cours():
        etiquette = ETIQUETTE_COURS.get(m["c"], "L2_autre")
        if m["h"] in index:
            r = index[m["h"]]
            ajout = [e for e in ("cours_L2", etiquette) if e not in r[3].split()]
            if ajout:
                r[3] = (r[3] + " " + " ".join(ajout)).strip()
                etiquetes += "cours_L2" in ajout
        elif m["h"] not in vus:
            vus.add(m["h"])
            note, alerte = note_vocabulaire(m["h"], m["p"], m["f"], m["x"], f'{m["c"]} ({m["n"]})', etiquette)
            paquets["Vocabulaire"].append(note)
            index[m["h"]] = note
            crees += 1
            if alerte:
                alertes.append(alerte)
    bilan["Vocabulaire : mots déjà présents étiquetés cours_L2"] = etiquetes
    bilan["Vocabulaire : mots du cours créés"] = crees
    bilan["Vocabulaire : pinyin à vérifier (différent de celui de la note de cours)"] = alertes

    # mots complémentaires (thèmes des cours)
    ajoutes = 0
    for mot, sens, cours, zh, fr in VOCAB_SUPPLEMENT:
        if mot in index:
            continue
        EXEMPLES.setdefault(mot, [(zh, fr)])
        note, _ = note_vocabulaire(mot, None, sens, "", f"{cours} (thème du programme)", ETIQUETTE_COURS.get(cours, "L2_autre"))
        paquets["Vocabulaire"].append(note)
        index[mot] = note
        ajoutes += 1
    bilan["Vocabulaire : mots des thèmes du programme créés"] = ajoutes

    # mots déjà présents à étiqueter cours_L2 pour un thème du programme pas encore couvert dans le coffre
    etiquetes_avance = 0
    for mot, cours in MOTS_A_ETIQUETER.items():
        if mot not in index:
            continue
        r = index[mot]
        etiquette = ETIQUETTE_COURS.get(cours, "L2_autre")
        ajout = [e for e in ("cours_L2", etiquette) if e not in r[3].split()]
        if ajout:
            r[3] = (r[3] + " " + " ".join(ajout)).strip()
            etiquetes_avance += 1
    bilan["Vocabulaire : mots déjà présents étiquetés pour un thème à venir"] = etiquetes_avance

    # exercices : reconnaître les caractères non simplifiés (exigé par le programme de renforcement écrit)
    rectos = {r[0] for r in paquets["Exercices"]}
    neuves, vus = [], set()
    for r in paquets["Vocabulaire"]:
        mot = r[0].strip()
        niveau = re.search(r"\bHSK([123])\b", r[3])
        if not (niveau or "cours_L2" in r[3].split()) or not re.fullmatch(r"[一-鿿]{1,4}", mot) or mot in vus:
            continue
        trad = VERS_TRAD.convert(mot)
        if trad == mot:
            continue
        lignes = re.sub(r"<div class=\"exemple-bloc\".*", "", r[1]).split("<br>")
        pinyin = " ".join(re.findall(r'<span class="t\d">([^<]+)</span>', lignes[1])) if len(lignes) > 1 else ""
        sens = re.sub(r"<[^>]+>", "", lignes[2]).strip() if len(lignes) > 2 else ""
        if not sens:
            continue
        vus.add(mot)
        detail = " · ".join(f"{t} → {s}" if t != s else f"{s} (inchangé)" for t, s in zip(trad, mot))
        recto = f'Ce mot est écrit en caractères non simplifiés. Lisez-le et donnez sa forme simplifiée :<br><br><span class="hanzi">{trad}</span>'
        verso = (f"<b>Réponse : {mot}</b> ({pinyin})<br><br>{sens}<br><br>"
                 f'<div class="exemple-bloc"><b>Explication :</b> {detail}</div>')
        if recto not in rectos:
            neuves.append([recto, verso, "", "exercice_traditionnel deck_v2 cours_L2 L2_renforcement_ecrit ajout_2026"])
        if len(neuves) >= 200:
            break
    paquets["Exercices"] += neuves
    bilan["Exercices : reconnaissance des caractères non simplifiés"] = len(neuves)
    return bilan


if __name__ == "__main__":  # relecture : affiche tout le pinyin calculé
    for g in GRAMMAIRE:
        print("\n##", g[0], g[1])
        for zh, fr in g[3]:
            print("  ", zh, "|", " ".join(lire_phrase(zh)))
    print("\n## PHRASES")
    for p in PHRASES:
        print("  ", p[1], "|", " ".join(lire_phrase(p[1])))
    print("\n## EXEMPLES DE VOCABULAIRE")
    for mot, ex in EXEMPLES.items():
        for zh, _ in ex:
            print("  ", zh, "|", " ".join(lire_phrase(zh)))
