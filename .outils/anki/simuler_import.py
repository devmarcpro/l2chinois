# -*- coding: utf-8 -*-
"""Simule l'import Anki des fichiers Anki/corrige/*.txt hors ligne, pour détecter avant coup ce qui casserait
l'import réel : mauvais nombre de champs, tabulations ou retours à la ligne non échappés, HTML mal formé,
guillemets déséquilibrés, doublons de premier champ (recto), fichiers non UTF-8, etc.

    python .outils/anki/simuler_import.py
"""
import csv
import html.parser
import re
import sys
from pathlib import Path

csv.field_size_limit(10**8)
VAULT = Path(__file__).resolve().parents[2]
SORTIE = VAULT / "Anki" / "corrige"
ATTENDUS = {"Ecoute": 4, "Exercices": 4, "Grammaire": 4, "Lecture": 4, "Phrases": 4, "Vocabulaire": 5}


class VerifHTML(html.parser.HTMLParser):
    """Détecte les balises mal fermées ou mal imbriquées (Anki affiche du HTML brut si c'est cassé)."""
    BALISES_AUTONOMES = {"br", "img", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.pile = []
        self.erreurs = []

    def handle_starttag(self, tag, attrs):
        if tag not in self.BALISES_AUTONOMES:
            self.pile.append(tag)

    def handle_startendtag(self, tag, attrs):
        pass

    def handle_endtag(self, tag):
        if tag in self.BALISES_AUTONOMES:
            return
        if not self.pile:
            self.erreurs.append(f"</{tag}> sans balise ouvrante")
            return
        if self.pile[-1] == tag:
            self.pile.pop()
        elif tag in self.pile:
            # fermeture dans le désordre : on dépile jusqu'à trouver la bonne balise (tolérant, comme un navigateur)
            self.erreurs.append(f"</{tag}> ferme dans le désordre (attendu </{self.pile[-1]}>)")
            while self.pile and self.pile[-1] != tag:
                self.pile.pop()
            if self.pile:
                self.pile.pop()
        else:
            self.erreurs.append(f"</{tag}> sans balise ouvrante correspondante")

    def error(self, message):
        pass


def verifier_html(champ: str):
    p = VerifHTML()
    try:
        p.feed(champ)
    except Exception as e:
        return [f"exception du parseur : {e}"]
    erreurs = list(p.erreurs)
    if p.pile:
        erreurs.append("balises jamais refermées : " + ", ".join(p.pile))
    return erreurs


def lire_tsv_anki(chemin: Path):
    """Reproduit la lecture TSV d'Anki : #entêtes, séparateur tab, champ entouré de guillemets si besoin."""
    brut = chemin.read_text(encoding="utf-8")
    entetes = [l for l in brut.splitlines() if l.startswith("#")]
    corps = "\n".join(l for l in brut.splitlines() if l and not l.startswith("#"))
    lignes = list(csv.reader(corps.splitlines(), delimiter="\t", quotechar='"'))
    return entetes, lignes


def main():
    total_problemes = 0
    for paquet, n_attendu in ATTENDUS.items():
        chemin = SORTIE / f"Chinois__{paquet}.txt"
        if not chemin.exists():
            print(f"MANQUANT : {chemin}")
            total_problemes += 1
            continue
        try:
            brut_bytes = chemin.read_bytes()
            brut_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            print(f"{paquet} : PAS DE L'UTF-8 VALIDE : {e}")
            total_problemes += 1
            continue
        entetes, lignes = lire_tsv_anki(chemin)
        problemes = []
        if "#separator:tab" not in entetes:
            problemes.append("en-tête #separator:tab manquant")
        if "#html:true" not in entetes:
            problemes.append("en-tête #html:true manquant")
        if not any(e.startswith("#tags column:") for e in entetes):
            problemes.append("en-tête #tags column manquant")
        rectos = {}
        n_champs_faux, n_html_casse, n_recto_vide, n_tab_perdu = 0, 0, 0, 0
        exemples_html = []
        for i, r in enumerate(lignes):
            if len(r) != n_attendu:
                n_champs_faux += 1
                if n_champs_faux <= 3:
                    problemes.append(f"  ligne {i} : {len(r)} champs au lieu de {n_attendu} : {r[0][:40] if r else '(vide)'}")
                continue
            recto = r[0].strip()
            if not recto:
                n_recto_vide += 1
                continue
            if recto in rectos:
                n_tab_perdu += 1  # deux notes avec le même recto : Anki les fusionnera à l'import (mise à jour) au lieu d'en garder deux
            rectos[recto] = rectos.get(recto, 0) + 1
            for champ in (r[0], r[1]):
                erreurs = verifier_html(champ)
                if erreurs:
                    n_html_casse += 1
                    if len(exemples_html) < 5:
                        exemples_html.append((recto[:30], erreurs[:2]))
                    break
        if n_champs_faux:
            problemes.append(f"{n_champs_faux} lignes n'ont pas {n_attendu} champs (tabulation perdue dans un champ ?)")
        if n_recto_vide:
            problemes.append(f"{n_recto_vide} lignes ont un premier champ (recto) vide")
        # une note d'origine dont le recto a disparu resterait dans la collection sans étiquette a_supprimer
        sys.path.insert(0, str(Path(__file__).parent))
        from corriger_decks import lire
        perdus = [r[0] for r in lire(f"Chinois__{paquet}.txt") if r[0].strip() and r[0].strip() not in rectos]
        if perdus:
            problemes.append(f"{len(perdus)} rectos d'origine absents (carte modifiee sans garder l'ancienne avec a_supprimer) : {perdus[:3]}")
        doublons = {r: n for r, n in rectos.items() if n > 1}
        if doublons:
            problemes.append(f"{len(doublons)} rectos en double au sein du même fichier (Anki n'en gardera qu'une version) : {list(doublons)[:5]}")
        if n_html_casse:
            problemes.append(f"{n_html_casse} notes ont du HTML mal formé (balise non refermée ou fermée dans le désordre)")
            for recto, err in exemples_html:
                problemes.append(f"    ex. « {recto} » : {err}")
        print(f"{paquet:12} {len(lignes):5} lignes | {'OK' if not problemes else str(len(problemes)) + ' point(s) à verifier'}")
        for p in problemes:
            print("   -", p)
        total_problemes += len(problemes)
    print(f"\n{'Aucun probleme detecte : les six fichiers sont prets a etre importes.' if total_problemes == 0 else str(total_problemes) + ' point(s) au total, voir le detail ci-dessus.'}")
    return total_problemes


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
