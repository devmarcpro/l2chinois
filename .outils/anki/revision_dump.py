# -*- coding: utf-8 -*-
"""Exporte les paquets (pinyin déjà corrigé) en texte lisible, par tranches, pour une relecture du contenu.

    python .outils/anki/revision_dump.py <dossier de sortie>

Chaque note reçoit un identifiant stable (lettre du paquet + rang dans le fichier d'origine).
index.json associe chaque identifiant au paquet et au recto d'origine.
"""
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import corriger_decks as cd  # noqa: E402

RUBY_BLOC = re.compile(r"(?:<ruby>.<rt[^>]*>[^<]*</rt></ruby>|[，。！？、；：,.!?“”\"‘’《》（）()…—·])+")
SPANS = re.compile(r'(?:<span class="t\d">[^<]+</span>[\s，。！？、；：,.!?“”]*)+')


def lisible(champ: str) -> str:
    def ruby(m):
        bloc = m.group(0)
        if "<ruby>" not in bloc:
            return bloc
        hanzi = re.sub(r"<rt[^>]*>[^<]*</rt>|<[^>]+>", "", bloc)
        pinyin = " ".join(re.findall(r"<rt[^>]*>([^<]*)</rt>", bloc))
        return f"{hanzi} [{pinyin}]"
    t = RUBY_BLOC.sub(ruby, champ)
    t = SPANS.sub(lambda m: "[" + " ".join(re.findall(r">([^<]+)</span>", m.group(0))) + "] ", t)
    t = re.sub(r"<br\s*/?>|</div>|</p>", "\n", t)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    return re.sub(r"\n\s*\n+", "\n", re.sub(r"[ \t]+", " ", t)).strip()


def main(sortie: Path):
    sortie.mkdir(parents=True, exist_ok=True)
    index = {}
    plans = {  # paquet : (lettre, filtre, nombre de tranches)
        "Exercices": ("E", lambda r: True, 5),
        "Grammaire": ("G", lambda r: True, 1),
        "Lecture": ("L", lambda r: True, 1),
        "Ecoute": ("C", lambda r: True, 1),
        "Phrases": ("P", lambda r: re.search(r"Phrases_HSK[123]\b", r[3]) is not None, 3),
        "Vocabulaire": ("V", lambda r: re.search(r"\bHSK[123]\b", r[3]) is not None, 8),
    }
    for paquet, (lettre, filtre, tranches) in plans.items():
        rangs = cd.lire(f"Chinois__{paquet}.txt")
        blocs = []
        for i, r in enumerate(rangs):
            if not filtre(r):
                continue
            ident = f"{lettre}{i:04d}"
            index[ident] = {"paquet": paquet, "recto": r[0]}
            n = cd.traiter_note(paquet, r)
            blocs.append(f"### {ident}  [{n[3].strip()}]\nRECTO: {lisible(n[0])}\nVERSO: {lisible(n[1])}\n")
        taille = -(-len(blocs) // tranches)
        for k in range(tranches):
            morceau = blocs[k * taille:(k + 1) * taille]
            (sortie / f"{paquet.lower()}_{k + 1}.txt").write_text("\n".join(morceau), encoding="utf-8", newline="\n")
            print(f"{paquet.lower()}_{k + 1}.txt : {len(morceau)} notes, {sum(len(b) for b in morceau) // 1000} k caractères")
    (sortie / "index.json").write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
