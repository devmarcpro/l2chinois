# -*- coding: utf-8 -*-
"""Correction du pinyin d'une phrase chinoise déjà annotée caractère par caractère.

Principe : on ne touche une syllabe que si on a une bonne raison.
  1. mots à lecture particulière (dictionnaire de pypinyin, contrôlé par la segmentation de jieba, + liste maison) ;
  2. règles pour les caractères grammaticaux et les caractères à plusieurs lectures (得, 地, 着, 了, 只, 长, 教, 为, 都, 种, 切…) ;
  3. accent manquant : remis d'après le ton indiqué par la couleur de la carte ;
  4. tons neutres usuels (朋友, 喜欢, 东西…) ;
  5. sandhi de 一 et 不 (ton réellement prononcé).
"""
import re
import unicodedata

import jieba
import jieba.posseg as pseg
from pypinyin import Style, lazy_pinyin, load_phrases_dict
from pypinyin.constants import PHRASES_DICT
from pypinyin.contrib.tone_convert import to_tone
from pypinyin.seg import mmseg

jieba.setLogLevel(60)
CJK = re.compile(r"[一-鿿]")
ACCENTS = "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ"
TON = {c: i % 4 + 1 for i, c in enumerate(ACCENTS)}
CHIFFRES = "零〇一二三四五六七八九十百千万亿两"

# lectures que pypinyin ne connaît pas ou rend mal
load_phrases_dict({
    "睡觉": [["shuì"], ["jiào"]], "午觉": [["wǔ"], ["jiào"]], "睡懒觉": [["shuì"], ["lǎn"], ["jiào"]],
    "有空": [["yǒu"], ["kòng"]], "没空": [["méi"], ["kòng"]], "空儿": [["kòng"], ["r"]], "抽空": [["chōu"], ["kòng"]],
    "教书": [["jiāo"], ["shū"]], "长发": [["cháng"], ["fà"]], "头发": [["tóu"], ["fa"]], "理发": [["lǐ"], ["fà"]],
    "银行": [["yín"], ["háng"]], "长期": [["cháng"], ["qī"]], "长途": [["cháng"], ["tú"]], "长城": [["cháng"], ["chéng"]],
    "好吃": [["hǎo"], ["chī"]], "爱好": [["ài"], ["hào"]], "便宜": [["pián"], ["yi"]], "暖和": [["nuǎn"], ["huo"]],
    "答应": [["dā"], ["ying"]], "了解": [["liǎo"], ["jiě"]], "重新": [["chóng"], ["xīn"]], "重复": [["chóng"], ["fù"]],
    "干净": [["gān"], ["jìng"]], "干什么": [["gàn"], ["shén"], ["me"]], "干吗": [["gàn"], ["má"]], "干活": [["gàn"], ["huó"]],
    "少年": [["shào"], ["nián"]], "青少年": [["qīng"], ["shào"], ["nián"]], "背包": [["bēi"], ["bāo"]],
    "着急": [["zháo"], ["jí"]], "睡着": [["shuì"], ["zháo"]], "成都": [["chéng"], ["dū"]], "首都": [["shǒu"], ["dū"]],
    "空调": [["kōng"], ["tiáo"]], "出差": [["chū"], ["chāi"]], "差不多": [["chà"], ["bu"], ["duō"]],
    "觉得": [["jué"], ["de"]], "记得": [["jì"], ["de"]], "认得": [["rèn"], ["de"]], "懂得": [["dǒng"], ["de"]],
    "显得": [["xiǎn"], ["de"]], "舍得": [["shě"], ["de"]], "使得": [["shǐ"], ["de"]], "免得": [["miǎn"], ["de"]],
    "省得": [["shěng"], ["de"]], "懒得": [["lǎn"], ["de"]], "来得及": [["lái"], ["de"], ["jí"]], "晓得": [["xiǎo"], ["de"]],
    "得到": [["dé"], ["dào"]], "获得": [["huò"], ["dé"]], "取得": [["qǔ"], ["dé"]], "不得不": [["bù"], ["dé"], ["bù"]],
    "值得": [["zhí"], ["dé"]], "难得": [["nán"], ["dé"]], "得分": [["dé"], ["fēn"]], "得意": [["dé"], ["yì"]], "心得": [["xīn"], ["dé"]],
    "赢得": [["yíng"], ["dé"]], "博得": [["bó"], ["dé"]], "所得": [["suǒ"], ["dé"]], "不得了": [["bù"], ["dé"], ["liǎo"]],
    "对不起": [["duì"], ["bu"], ["qǐ"]], "了不起": [["liǎo"], ["bu"], ["qǐ"]], "来不及": [["lái"], ["bu"], ["jí"]],
    "怪不得": [["guài"], ["bu"], ["de"]], "舍不得": [["shě"], ["bu"], ["de"]], "恨不得": [["hèn"], ["bu"], ["de"]],
    "马虎": [["mǎ"], ["hu"]], "人家": [["rén"], ["jia"]], "户人家": [["hù"], ["rén"], ["jiā"]],
    "音乐": [["yīn"], ["yuè"]], "乐器": [["yuè"], ["qì"]], "处理": [["chǔ"], ["lǐ"]], "相处": [["xiāng"], ["chǔ"]],
    "反应": [["fǎn"], ["yìng"]], "适应": [["shì"], ["yìng"]], "应该": [["yīng"], ["gāi"]], "对应": [["duì"], ["yìng"]],
    "倒是": [["dào"], ["shì"]], "倒不如": [["dào"], ["bù"], ["rú"]], "请假": [["qǐng"], ["jià"]], "华为": [["huá"], ["wéi"]],
    "划算": [["huá"], ["suàn"]], "长达": [["cháng"], ["dá"]], "长时间": [["cháng"], ["shí"], ["jiān"]], "调整": [["tiáo"], ["zhěng"]],
    "遛狗": [["liù"], ["gǒu"]], "遛弯": [["liù"], ["wān"]], "银发": [["yín"], ["fà"]], "美发": [["měi"], ["fà"]], "白发": [["bái"], ["fà"]],
    "主题曲": [["zhǔ"], ["tí"], ["qǔ"]], "炸鸡": [["zhá"], ["jī"]], "油炸": [["yóu"], ["zhá"]], "戳中": [["chuō"], ["zhòng"]],
    "五子棋": [["wǔ"], ["zǐ"], ["qí"]], "阿德勒": [["ā"], ["dé"], ["lè"]], "鹿茸": [["lù"], ["róng"]], "麻将": [["má"], ["jiàng"]],
    "什刹海": [["shí"], ["chà"], ["hǎi"]], "成蹊": [["chéng"], ["xī"]], "帖子": [["tiě"], ["zi"]], "当红": [["dāng"], ["hóng"]],
    "嚼劲": [["jiáo"], ["jìn"]], "行业": [["háng"], ["yè"]], "处心积虑": [["chǔ"], ["xīn"], ["jī"], ["lǜ"]],
    "干煸": [["gān"], ["biān"]], "干香菇": [["gān"], ["xiāng"], ["gū"]], "干燥": [["gān"], ["zào"]], "干旱": [["gān"], ["hàn"]],
    "犯愁": [["fàn"], ["chóu"]], "厚积薄发": [["hòu"], ["jī"], ["bó"], ["fā"]], "累土": [["lěi"], ["tǔ"]],
    "孽子": [["niè"], ["zǐ"]], "电子": [["diàn"], ["zǐ"]], "孔子": [["kǒng"], ["zǐ"]], "孟子": [["mèng"], ["zǐ"]], "老子": [["lǎo"], ["zǐ"]],
    "庄子": [["zhuāng"], ["zǐ"]], "孙子": [["sūn"], ["zǐ"]], "君子": [["jūn"], ["zǐ"]], "弟子": [["dì"], ["zǐ"]], "王子": [["wáng"], ["zǐ"]],
    "男子": [["nán"], ["zǐ"]], "女子": [["nǚ"], ["zǐ"]], "原子": [["yuán"], ["zǐ"]], "分子": [["fēn"], ["zǐ"]], "量子": [["liàng"], ["zǐ"]],
    "才子": [["cái"], ["zǐ"]], "父子": [["fù"], ["zǐ"]], "母子": [["mǔ"], ["zǐ"]], "天子": [["tiān"], ["zǐ"]], "太子": [["tài"], ["zǐ"]],
    "种植": [["zhòng"], ["zhí"]], "种地": [["zhòng"], ["dì"]], "种田": [["zhòng"], ["tián"]], "耕种": [["gēng"], ["zhòng"]],
    "弹钢琴": [["tán"], ["gāng"], ["qín"]], "弹吉他": [["tán"], ["jí"], ["tā"]], "弹琴": [["tán"], ["qín"]],
    "照片": [["zhào"], ["piàn"]], "相片": [["xiàng"], ["piàn"]], "名片": [["míng"], ["piàn"]], "影片": [["yǐng"], ["piàn"]],
    "机器": [["jī"], ["qì"]], "机器人": [["jī"], ["qì"], ["rén"]], "缘分": [["yuán"], ["fèn"]], "拖累": [["tuō"], ["lěi"]],
    "晕机": [["yùn"], ["jī"]], "晕车": [["yùn"], ["chē"]], "晕船": [["yùn"], ["chuán"]], "加缪": [["jiā"], ["miù"]],
    "弄堂": [["lòng"], ["táng"]], "摒弃": [["bìng"], ["qì"]], "摒除": [["bìng"], ["chú"]], "章子怡": [["zhāng"], ["zǐ"], ["yí"]],
    "瓷都": [["cí"], ["dū"]], "反差": [["fǎn"], ["chā"]], "发帖": [["fā"], ["tiě"]], "发帖子": [["fā"], ["tiě"], ["zi"]],
    "来得": [["lái"], ["de"]], "听得懂": [["tīng"], ["de"], ["dǒng"]], "听得见": [["tīng"], ["de"], ["jiàn"]], "看得见": [["kàn"], ["de"], ["jiàn"]],
    "看得懂": [["kàn"], ["de"], ["dǒng"]], "看得出": [["kàn"], ["de"], ["chū"]], "听得出": [["tīng"], ["de"], ["chū"]], "买得起": [["mǎi"], ["de"], ["qǐ"]],
    "看得起": [["kàn"], ["de"], ["qǐ"]], "对得起": [["duì"], ["de"], ["qǐ"]], "吃得消": [["chī"], ["de"], ["xiāo"]], "受得了": [["shòu"], ["de"], ["liǎo"]],
    "过得去": [["guò"], ["de"], ["qù"]], "说得过去": [["shuō"], ["de"], ["guò"], ["qù"]], "吃得下": [["chī"], ["de"], ["xià"]], "睡得着": [["shuì"], ["de"], ["zháo"]], "附着": [["fù"], ["zhuó"]], "执着": [["zhí"], ["zhuó"]], "沉着": [["chén"], ["zhuó"]],
    "着重": [["zhuó"], ["zhòng"]], "着手": [["zhuó"], ["shǒu"]], "着眼": [["zhuó"], ["yǎn"]], "着装": [["zhuó"], ["zhuāng"]],
    "着落": [["zhuó"], ["luò"]], "着陆": [["zhuó"], ["lù"]], "着实": [["zhuó"], ["shí"]], "着色": [["zhuó"], ["sè"]],
    "着凉": [["zháo"], ["liáng"]], "着火": [["zháo"], ["huǒ"]], "着迷": [["zháo"], ["mí"]],
    "划水": [["huá"], ["shuǐ"]], "发夹": [["fà"], ["jiā"]], "发卡": [["fà"], ["qiǎ"]], "长一智": [["zhǎng"], ["yí"], ["zhì"]],
    "时差": [["shí"], ["chā"]], "温差": [["wēn"], ["chā"]], "误差": [["wù"], ["chā"]], "偏差": [["piān"], ["chā"]], "差距": [["chā"], ["jù"]],
})

# mots dont la dernière syllabe se prononce au ton neutre (liste volontairement courte et sûre)
NEUTRES = set("""东西 衣服 喜欢 朋友 时候 先生 学生 知道 认识 什么 怎么 这么 那么 多么 名字 漂亮 意思 地方 告诉 休息 明白 清楚
舒服 麻烦 事情 关系 消息 眼睛 耳朵 妈妈 爸爸 哥哥 姐姐 弟弟 妹妹 爷爷 奶奶 叔叔 谢谢 客气 聪明 热闹 凉快 厉害 行李 故事 功夫
豆腐 葡萄 月亮 晚上 早上 商量 打算 窗户 钥匙 大夫 护士 看看 试试 想想 听听 走走 等等 你们 我们 他们 她们 咱们 人们""".split())

# mots du dictionnaire de pypinyin à ne pas suivre : lecture rare, ou suite de caractères qui n'est en général pas ce mot
A_IGNORER = set("都会 中都 亲家 一场 肚子 质的 落下 落了 少不了 更深 无处 用处 出处 好处 到处 长处 短处 曲张 散发 大汗 释迦牟尼".split())

DEGRE = set("很太真挺更最极越这那多不好快慢早晚高低远近少大小长短胖瘦美丑对错清流怎像非特比十相")
COMPLEMENT = DEGRE | set("连直住开下上起动完成见懂出到手")  # ce qui suit 得 dans un complément (V得…)
VERBE_EI = set("我你他她您咱们还就总也都才可是")
APRES_WEI2 = set("成认以作称变分改列定评选视誉译化转升降判命封尊叫当极最颇甚更尤广华意职之留")
AVANT_CHANG = set("很太多更最不好非常么越挺够较别当分体身全加延漫冗修细狭擅特专")
APRES_CHANG = set("短度裤袖达期途久时寿城江处跑远篇廊条方约裙头" + CHIFFRES)
APRES_ZHANG = set("大得高出成辈相老子官进势")
VERBES_UN_PIVOT = set("说想看试听等找问走坐站笑聊读写念查算数摸碰动歇玩")  # V一V : verbes d'une syllabe qui se redoublent


def dans(c: str, ensemble) -> bool:
    """Vrai si c est un caractère (non vide) de l'ensemble : « '' in 'abc' » est vrai en Python, d'où ce garde-fou."""
    return bool(c) and c in ensemble


def ton(s: str) -> int:
    return next((TON[c] for c in s if c in TON), 0)


def base(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c)).lower().replace("ü", "u").replace("v", "u")


def avec_ton(syllabe: str, t: int) -> str:
    """'zhong', 1 -> 'zhōng' ; ton 0 -> sans accent."""
    nue = "".join(c for c in unicodedata.normalize("NFD", syllabe) if unicodedata.category(c) != "Mn" or c == "̈")
    nue = unicodedata.normalize("NFC", nue)
    if t in (1, 2, 3, 4):
        try:
            return to_tone(nue.replace("ü", "v") + str(t))
        except Exception:
            return syllabe
    return nue


def _mots_jieba(texte):
    """[(mot, nature, début, fin)]"""
    res, pos = [], 0
    for m in pseg.cut(texte):
        res.append((m.word, m.flag, pos, pos + len(m.word)))
        pos += len(m.word)
    return res


def _mots_pypinyin(texte):
    res, pos = [], 0
    for mot in mmseg.seg.cut(texte):
        res.append((mot, pos, pos + len(mot)))
        pos += len(mot)
    return res


def corriger(texte: str, lectures, seulement_sandhi=False):
    """texte : la phrase (hanzi + ponctuation). lectures : pinyin existant de chaque hanzi, dans l'ordre.
    Renvoie (nouvelles lectures, journal des changements [(index, caractère, avant, après, raison)])."""
    positions = [i for i, c in enumerate(texte) if CJK.match(c)]
    if len(positions) != len(lectures):
        return list(lectures), []
    index_de = {p: k for k, p in enumerate(positions)}
    neuf = list(lectures)
    journal = []

    def poser(k, valeur, raison):
        if valeur and valeur != neuf[k]:
            journal.append((k, texte[positions[k]], neuf[k], valeur, raison))
            neuf[k] = valeur

    jb = _mots_jieba(texte)
    limites_jieba = {d for _, _, d, _ in jb} | {len(texte)}
    nature_a = {}
    mot_jieba_a = {}
    for mot, nat, d, f in jb:
        for p in range(d, f):
            nature_a[p], mot_jieba_a[p] = nat, (mot, d, f)

    def nature_avant(p):
        """Nature (jieba) du mot qui précède le caractère p."""
        mot, md, _ = mot_jieba_a.get(p, (None, p, p))
        d = md if md < p else p
        return nature_a.get(d - 1, "") if d > 0 else ""

    # 1) mots du dictionnaire de lectures : découpage de pypinyin (s'il respecte celui de jieba), puis mots de jieba
    candidats = []
    if not seulement_sandhi:
        for mot, d, f in _mots_pypinyin(texte):
            coupe_dedans = any(d < b < f for b in limites_jieba)
            chevauches = [m for m, _n, md, mf in jb if md < f and mf > d and not (d <= md and mf <= f)]
            if not coupe_dedans or (d in limites_jieba and f in limites_jieba) or not any(m in PHRASES_DICT for m in chevauches):
                candidats.append((mot, d, f))
        candidats += [(mot, d, f) for mot, _n, d, f in jb]
    for mot, d, f in candidats:
        if f - d < 2 or not all(CJK.match(c) for c in mot) or mot not in PHRASES_DICT or mot in A_IGNORER:
            continue
        lu = lazy_pinyin(mot, style=Style.TONE)
        if len(lu) != f - d:
            continue
        for p, nouvelle in zip(range(d, f), lu):
            k = index_de[p]
            ancienne = neuf[k]
            if base(nouvelle) != base(ancienne):
                poser(k, nouvelle, f"mot {mot}")
            elif ton(nouvelle) and ton(ancienne) and ton(nouvelle) != ton(ancienne):
                poser(k, nouvelle, f"mot {mot}")
            elif not ton(ancienne) and ton(nouvelle) and texte[p] not in "一不":
                poser(k, nouvelle, f"accent manquant ({mot})")
            elif not ton(nouvelle) and ton(ancienne) and (mot in PHRASES_MAISON_NEUTRES or texte[p] in "得着了的地们么"):
                poser(k, nouvelle, f"ton neutre ({mot})")  # particule au ton neutre dans un mot du dictionnaire (来得, 听得懂)

    # 2) règles sur les caractères grammaticaux et les caractères à plusieurs lectures
    n = len(texte)
    for p in ([] if seulement_sandhi else positions):
        k, c = index_de[p], texte[p]
        avant = texte[p - 1] if p > 0 else ""
        apres = texte[p + 1] if p + 1 < n else ""
        apres2 = texte[p + 1:p + 3]
        mot, md, mf = mot_jieba_a.get(p, (c, p, p + 1))
        seul = mf - md == 1
        nat = nature_a.get(p, "")
        dans_dict = mot in PHRASES_DICT
        fenetre = texte[max(0, p - 8):p]
        if c == "得":
            morceau = re.split(r"[，。！？；：、,.!?\s]", texte[:p])[-1] + re.split(r"[，。！？；：、,.!?\s]", texte[p:])[0]
            if len(morceau) == 4 and all(CJK.match(x) for x in morceau):
                continue  # expression figée de quatre caractères (如鱼得水, 适得其反) : on ne touche pas
            if p > 0 and texte[p - 1:p + 1] in PHRASES_DICT and lazy_pinyin(texte[p - 1:p + 1], style=Style.TONE)[1] == "dé":
                continue  # 值得, 所得, 习得
            if mf - md >= 3 and md < p < mf - 1 and mot[0] not in "不非":
                poser(k, "de", "得 de complément")  # 走得快, 看得见, 听得懂 : 得 au milieu d'un groupe verbe + complément
                continue
            if mf - md == 2 and p == md and avant and CJK.match(avant) and avant not in VERBE_EI and mot[1] in COMPLEMENT and nature_avant(p)[:1] not in ("r", "t", "m"):
                poser(k, "de", "得 de complément")  # 紧张得手都在抖, 唱得比我好 : jieba colle 得 au mot suivant
                continue
            if dans_dict:
                continue
            if mf - md >= 2 and p == mf - 1 and mot[0] not in "不非":
                if mot[0] in VERBE_EI and len(mot) == 2 and apres and CJK.match(apres) and not dans(apres, "了到过"):
                    poser(k, "děi", "得 = devoir")  # 还得, 就得
                else:
                    poser(k, "de", "得 de complément")  # 病得很重, 变得复杂 : jieba colle 得 au verbe
            elif mf - md >= 2 and p == md and (not (avant and CJK.match(avant)) or avant in VERBE_EI or nature_avant(p)[:1] in ("r", "n", "t", "m")):
                poser(k, "děi", "得 = devoir")  # 我得去…, 得先…, 有时间得去
            elif seul and not (avant and CJK.match(avant)) and apres and CJK.match(apres) and not dans(apres, "了到过出知以") and apres not in DEGRE:
                poser(k, "děi", "得 = devoir")  # en tête de proposition : 得去看牙医
            elif seul:
                if avant in VERBE_EI and apres and CJK.match(apres) and apres not in "了到过很不太真非特比更最这那多得的":
                    poser(k, "děi", "得 = devoir")
                elif dans(apres, "了到过"):
                    pass  # 得了满分, 得到 : dé
                elif avant and CJK.match(avant) and (nat == "ud" or apres in DEGRE or not CJK.match(apres or "。")):
                    poser(k, "de", "得 de complément")
                elif avant and CJK.match(avant) and apres and CJK.match(apres):
                    prec = nature_avant(p)
                    if prec[:1] in ("v", "a", "i", "z"):
                        poser(k, "de", "得 de complément")  # 看得我很累, 累得腰都直不起来
                    elif prec[:1] in ("r", "n", "t", "m"):
                        poser(k, "děi", "得 = devoir")  # 有时间得去看看
        elif c == "地" and avant and CJK.match(avant) and apres and CJK.match(apres) and avant != "等":
            prec = nature_avant(p)
            if seul and (nat == "uv" or prec[:1] in ("a", "d", "z", "o") or (p >= 2 and texte[p - 1] == texte[p - 2])):
                poser(k, "de", "地 adverbial")  # 慢慢地, 哗哗地, 亲切地
            elif p == mf - 1 and mf - md >= 3 and not dans_dict:
                poser(k, "de", "地 adverbial")  # 悄悄地, 勇敢地, 流利地 : jieba en fait un seul mot
            elif p == md and mf - md == 2 and (not dans_dict or texte[p:p + 3] == "地面对") and (prec[:1] in ("a", "d", "z") or (p >= 2 and mot_jieba_a.get(p - 1, ("", 0, 0))[2] - mot_jieba_a.get(p - 1, ("", 0, 0))[1] == 2 and prec[:1] in ("n", "v", "a", "d"))):
                poser(k, "de", "地 adverbial")  # 亲切|地称, 小心|地将 : jieba colle 地 au verbe qui suit
        elif c == "着":
            if texte[p - 2:p] == "睡不" or texte[p - 2:p] == "睡得" or (dans(avant, "不得") and p >= 2 and CJK.match(texte[p - 2])):
                poser(k, "zháo", "V不着 / V得着")
            elif (nat == "uz" and seul) or (mf - md == 2 and p == mf - 1 and nat[:1] == "v" and not dans_dict):
                poser(k, "zhe", "着 duratif")
        elif c == "了" and avant == "不" and apres != "解":
            poser(k, "liǎo", "V不了")
        elif c == "了" and nat == "ul" and seul and avant != "不" and base(neuf[k]) != "le":
            poser(k, "le", "了 aspect")
        elif c == "的" and nat == "uj" and seul and base(neuf[k]) != "de":
            poser(k, "de", "的 particule")
        elif c == "西" and avant == "东" and not dans(apres, "方部南北向"):
            poser(k, "xi", "ton neutre (东西)")
        elif c == "只":
            if avant and (avant in CHIFFRES or avant in "这那几每半哪") and apres not in "有是要好能会想需不":
                poser(k, "zhī", "只 classificateur")
            elif "量词" in fenetre and not (apres and CJK.match(apres)):
                poser(k, "zhī", "只 classificateur")
        elif c == "长":
            if (dans(avant, AVANT_CHANG) or texte[max(0, p - 2):p] in ("这么", "那么", "越来", "非常") or dans(apres, APRES_CHANG)) and not dans(apres, APRES_ZHANG):
                poser(k, "cháng", "长 = long")
        elif c == "教" and seul and apres and (apres in "我你他她您咱书了过着" or apres2 in ("学生", "孩子", "中文", "汉语", "英语", "法语", "数学", "大家")):
            poser(k, "jiāo", "教 = enseigner")
        elif c == "教" and mf - md == 2 and p == md and mot[1] in "了过着" and not dans_dict:
            poser(k, "jiāo", "教 = enseigner")  # 教了十年
        elif c == "觉" and re.search(r"睡[^，。！？]{0,4}$", texte[:p]) and "觉得" not in texte[p:p + 2]:
            poser(k, "jiào", "睡…觉")
        elif c == "为":
            if dans(apres, "什何"):
                continue
            yi = fenetre.rfind("以")
            avant_yi = texte[max(0, p - 8) + yi - 1] if yi > 0 else ""
            structure_yi = (yi >= 0 and yi < len(fenetre) - 1 and not re.search(r"[，。！？；：、]", fenetre[yi:])
                            and avant_yi not in "可所足难得用予借加给何")
            verbe_avant = re.search(r"[称收视选拜封尊立推奉认译叫升变转化分改合并列评定判命取]", fenetre[-4:-1]) and not re.search(r"[，。！？；：、]", fenetre[-4:])
            if avant in APRES_WEI2:
                poser(k, "wéi", f"{avant}为")
            elif dans(apres, "零主止期首生难准") and not dans(avant, "因"):
                poser(k, "wéi", "为 + " + apres)
            elif (structure_yi or verbe_avant) and not dans(apres, "了你我他她它们"):
                poser(k, "wéi", "以…为… / 称…为…")
        elif c == "空" and seul and dans(avant, "有没"):
            poser(k, "kòng", "有空")
        elif c == "都" and seul and nat == "d" and apres and CJK.match(apres) and not dans(avant, "成首京古国建定迁旧瓷"):
            poser(k, "dōu", "都 adverbe")
        elif c == "待" and dans(apres, "在了着上会一几多久") and not dans(avant, "等对招期接看优款虐善亏担交以"):
            poser(k, "dāi", "待 = rester")
        elif c == "种" and dans(apres, "满了树菜花地田植在上下好过着些几的一菊草果瓜豆米麦稻苗") and not dans(avant, CHIFFRES + "这那各每哪多品各种物剧") and not dans_dict:
            poser(k, "zhòng", "种 = planter")
        elif c == "弹" and not dans(avant, "子炸导枪原氢核飞流") and (dans(apres, "钢吉琴奏唱得了过一性簧跳开出起回弹") or dans(avant, "反弹")):
            poser(k, "tán", "弹 = jouer, rebondir")
        elif c == "量" and not dans(avant, "数质重力容能音产销流分批测") and dans(apres, "了一体血身尺过出好"):
            poser(k, "liáng", "量 = mesurer")
        elif c == "片" and not dans(apres, "子儿") and base(neuf[k]) == "pian":
            poser(k, "piàn", "片")
        elif c == "汗" and not dans(avant, "可思"):
            poser(k, "hàn", "汗")
        elif c == "涨" and dans(apres, "红得"):
            poser(k, "zhàng", "涨红")
        elif c == "重" and avant == "重" and dans(apres, "的地") and not dans(texte[p - 2:p - 1], "重"):
            pass
        elif c == "重" and apres == "重" and dans(texte[p + 2:p + 3], "的地"):
            poser(k, "zhòng", "重重的")
            poser(k + 1, "zhòng", "重重的")
        elif c == "哦" and avant and CJK.match(avant) and not (apres and CJK.match(apres)):
            poser(k, "o", "哦 particule finale")
        elif c == "夫" and dans(avant, "斯也矣") and not (apres and CJK.match(apres)):
            poser(k, "fú", "夫 particule classique")  # 逝者如斯夫
        elif c == "拧" and dans(apres, "开紧螺"):
            poser(k, "nǐng", "拧开")
        elif c == "落" and apres == "在" and "把" in fenetre:
            poser(k, "là", "把…落在 = oublier")
        elif c == "没" and dans(apres, "过去来到有能会想吃喝看说做买去") and not dans(avant, "淹沉出埋覆吞"):
            poser(k, "méi", "没 négation")
        elif c == "撒" and dans(apres, "了在上下点些盐糖粉种") and not dans(apres2[:2], "谎娇"):
            poser(k, "sǎ", "撒 = répandre")
        elif c == "琢" and avant == "不" and texte[p - 2:p - 1] == "玉":
            poser(k, "zhuó", "玉不琢")
        elif c == "还" and dans(apres, "了给书钱款债清回") and not dans(avant, "还"):
            poser(k, "huán", "还 = rendre")
        elif c == "假" and (dans(avant, "请休放度暑寒病事产年婚丧长短") or dans(apres, "期日条") or (dans(avant, CHIFFRES + "天周月年个") and ("请" in fenetre or "休" in fenetre))):
            poser(k, "jià", "假 = congé")
        elif c == "薄" and (apres == "发" or dans(avant, "稀单刻淡浅菲微轻") or dans(apres, "弱膜雾命利情")):
            poser(k, "bó", "薄 bó")
        elif c == "挣" and apres != "扎":
            poser(k, "zhèng", "挣 = gagner")
        elif c == "卡" and dans(apres, "住在"):
            poser(k, "qiǎ", "卡住")
        elif c == "应" and dans(avant, "对反适响供回呼报效感顺照策") and not dans(apres, "该当有邀聘"):
            poser(k, "yìng", "应 yìng")
        elif c == "分" and dans(avant, "缘成本过职名养水情天福股") and not dans(apres, "钟开数别析手配布"):
            poser(k, "fèn", "分 fèn")
        elif c == "倒":
            if dans(apres, "是也不退流影数计挂立贴序装车") or dans(avant, "反颠"):
                poser(k, "dào", "倒 = à l'envers, au contraire")
            elif dans(apres, "了下塌闭台霉掉在") or dans(avant, "摔跌推打滑绊卧病"):
                poser(k, "dǎo", "倒 = tomber")
        elif c == "似" and apres != "的":
            poser(k, "sì", "似")
        elif c == "尽" and not dans(apres, "管量快早可先速"):
            poser(k, "jìn", "尽 = épuiser, tout")
        elif c == "铺" and dans(apres, "了上开着好床路设垫满平") and not dans(avant, "店床卧当上下"):
            poser(k, "pū", "铺 = étaler")
        elif c == "切":
            if dans(apres, "菜成开片肉碎丝块好了掉断" ) or dans(avant, "把刀"):
                poser(k, "qiē", "切 = couper")
            elif dans(avant, "一亲密迫确关急恳深") or dans(apres, "实记忌勿"):
                poser(k, "qiè", "切")
        elif c == "处":
            if dans(apres, "理于在境罚分置事世方心变") or dans(avant, "相共独同") or (not (avant and CJK.match(avant)) and apres and CJK.match(apres) and apres != "处"):
                poser(k, "chǔ", "处 verbe")
        elif c == "好" and dans(apres, "之奇客胜色战斗") and not dans(avant, "很太不真更最挺也都才"):
            poser(k, "hào", "好 = aimer")
        elif c == "遛":
            poser(k, "liù", "遛")
        elif c == "发" and ((dans(avant, "头银白理美假短卷染黑金烫剪洗脱秀") and not dans(apres, "现生展出表达明言布动票射育挥放烧热炎酵财")) or dans(apres, "型廊胶夹卡")):
            if not (avant == "头" and mot == "头发"):
                poser(k, "fà", "发 = cheveux")
        elif c == "中" and (dans(avant, "戳打击命猜射选考") and not (apres and CJK.match(apres) and apres not in "了的") or dans(apres, "奖毒暑风弹计")):
            poser(k, "zhòng", "中 = atteindre")
        elif c == "炸" and (dans(apres, "鸡薯油酱了鱼虾丸豆糕") or avant == "油"):
            poser(k, "zhá", "炸 = frire")
        elif c == "曲" and (dans(avant, "歌乐题舞戏名插序组小作谱") or dans(apres, "子调目谱")):
            poser(k, "qǔ", "曲 = chanson")
        elif c == "和" and seul and nat in ("c", "p"):
            poser(k, "hé", "和 conjonction")
        elif c == "嚼" and avant != "咀":
            poser(k, "jiáo", "嚼")
        elif c == "背" and dans(apres, "着起上了") and re.search(r"[包袋箱子行李孩人枪柴]", texte[p + 1:p + 9]):
            poser(k, "bēi", "背 = porter sur le dos")
        elif c == "划":
            if (dans(apres, "算船桨过来得不") or dans(avant, "划")) and not dans(avant, "计规策筹刻"):
                poser(k, "huá", "划")
            elif dans(apres, "分定清线归时") or dans(avant, "计规策筹刻"):
                poser(k, "huà", "划")
        elif c == "吐":
            if dans(apres, "了得过") or dans(avant, "呕想要会恶欲") or (dans(avant, "在直") and not (apres and CJK.match(apres))):
                poser(k, "tù", "吐 = vomir")
            elif dans(apres, "痰出露槽字气舌"):
                poser(k, "tǔ", "吐 = cracher")

    # 3) accent manquant ailleurs : géré par l'appelant (il connaît la couleur de la carte)

    # 4) tons neutres usuels
    for mot, _nat, d, f in ([] if seulement_sandhi else jb):
        if mot in NEUTRES and all(p in index_de for p in range(d, f)) and not (mot == "学生" and texte[f:f + 1] == "物"):
            k = index_de[f - 1]
            if ton(neuf[k]):
                poser(k, avec_ton(neuf[k], 0), f"ton neutre ({mot})")

    # 5) sandhi de 一 et 不
    for p in positions:
        k, c = index_de[p], texte[p]
        if c not in "一不":
            continue
        avant = texte[p - 1] if p > 0 else ""
        apres = texte[p + 1] if p + 1 < n else ""
        suivant = ton(neuf[k + 1]) if (k + 1 < len(neuf) and apres and CJK.match(apres)) else None
        mot, md, mf = mot_jieba_a.get(p, (c, p, p + 1))
        if avant and avant == apres and CJK.match(avant):  # 看一看, 好不好
            pivot = nature_a.get(p - 1, "")[:1]
            if c == "不" and pivot in ("v", "a", "i") or c == "一" and (pivot == "v" or avant in VERBES_UN_PIVOT):
                poser(k, "yi" if c == "一" else "bu", "V一V / V不V")
                continue
        if base(neuf[k]) not in ("yi", "bu"):
            continue
        if c == "不":
            if not ton(neuf[k]) and mot in PHRASES_DICT and not ton(lazy_pinyin(mot, style=Style.TONE)[p - md]):
                continue  # 对不起, 差不多 : ton neutre voulu
            poser(k, "bú" if suivant == 4 else "bù", "sandhi 不")
            continue
        grand_nombre = dans(apres, "百千万亿两") and not dans(avant, CHIFFRES)  # 一百 yì bǎi, 一万 yí wàn
        mot_fige = texte[p:p + 2] in ("一定", "一直", "一切", "一般", "一共", "一样", "一边", "一些")
        ordinal = not grand_nombre and not mot_fige and (
            dans(avant, CHIFFRES + "第初") or dans(apres, CHIFFRES) or texte[max(0, p - 2):p] in ("星期", "礼拜") or avant == "周"
            or dans(apres, "月号日楼") or apres2 in ("年级", "等奖") or suivant is None
            or (mf - md > 1 and p == mf - 1))
        if ordinal:
            poser(k, "yī", "一 nombre / fin de mot")
        elif suivant == 4 or (suivant == 0 and apres == "个"):
            poser(k, "yí", "sandhi 一")
        elif suivant in (1, 2, 3):
            poser(k, "yì", "sandhi 一")
    # V不得 en fin de proposition (吃不得, 马虎不得, 进也进不得) : complément potentiel, 不 et 得 au ton neutre.
    # Suivi d'un verbe (不得入内 « il est interdit de ») ou de 不 / 了 / 已 (不得不, 不得了), il garde bùdé.
    if not seulement_sandhi:
        for p in positions:
            if texte[p:p + 2] == "不得" and p > 0 and CJK.match(texte[p - 1]) and (
                    p + 2 >= n or not CJK.match(texte[p + 2]) or texte[p + 2] in "的呀啊呢吧"
                    or texte[p - 1:p + 2] in MOTS_BU_DE):  # 舍不得你走 : le mot figé garde bu de devant un complément
                poser(index_de[p], "bu", "V不得 (complément potentiel)")
                poser(index_de[p + 1], "de", "V不得 (complément potentiel)")
            if texte[p:p + 2] == "人家" and p > 0 and texte[p - 1] in "户" and p + 1 < n:
                poser(index_de[p + 1], "jiā", "人家 = foyer (几户人家)")
    return neuf, journal


MOTS_BU_DE = set("舍不得 怪不得 恨不得 巴不得 顾不得 记不得 由不得 要不得 见不得 少不得 免不得 怨不得 说不得 动不得 惹不得".split())


PHRASES_MAISON_NEUTRES = {"便宜", "头发", "暖和", "答应", "觉得", "记得", "认得", "懂得", "显得", "舍得", "使得", "免得", "省得", "懒得", "晓得",
                          "来得及", "差不多", "对不起", "了不起", "来不及", "怪不得", "舍不得", "恨不得", "帖子", "马虎", "人家"}


if __name__ == "__main__":
    essais = [
        ("我家有两只猫，一只白色。", "wǒ jiā yǒu liǎng zhǐ māo yī zhǐ bái sè"),
        ("他认为这个问题很重要，需要重新处理。", "tā rèn wèi zhè gè wèn tí hěn zhòng yào xū yào zhòng xīn chù lǐ"),
        ("他跑得很快，我得走了，他得到了第一名。", "tā pǎo dé hěn kuài wǒ dé zǒu le tā dé dào le dì yī míng"),
        ("她高兴地说：这个地方不错，头发很长。", "tā gāo xìng dì shuō zhè gè dì fāng bù cuò tóu fā hěn zhǎng"),
        ("我不去，你看一看，不是一个人，一起去，一定要来，星期一见。", "wǒ bù qù nǐ kàn yī kàn bù shì yī gè rén yī qǐ qù yī dìng yào lái xīng qī yī jiàn"),
        ("他教我中文，我们在教室睡了一觉，今天没空。", "tā jiào wǒ zhōng wén wǒ men zài jiào shì shuì le yī jué jīn tiān méi kōng"),
        ("这件衣服很便宜，我喜欢我的朋友，吃不了。", "zhè jiàn yī fú hěn biàn yí wǒ xǐ huān wǒ de péng yǒu chī bù le"),
        ("有人为了钱，成为了坏人。", "yǒu rén wèi le qián chéng wèi le huài rén"),
        ("每天早上都会去公园，我喜欢待在有空调的地方，海面上一浪高过一浪。", "měi tiān zǎo shàng dū huì qù gōng yuán wǒ xǐ huān dài zài yǒu kòng diào de dì fāng hǎi miàn shàng yī làng gāo guò yī làng"),
        ("他以诚信为本，升职为经理，看得我很累，有时间得去看看他。", "tā yǐ chéng xìn wèi běn shēng zhí wèi jīng lǐ kàn dé wǒ hěn lèi yǒu shí jiān dé qù kàn kàn tā"),
    ]
    for phrase, py in essais:
        apres, journal = corriger(phrase, py.split())
        print(phrase)
        print("   ", " ".join(apres))
        print("    changements :", [(c, a, b) for _, c, a, b, _ in journal])
