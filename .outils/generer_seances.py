# -*- coding: utf-8 -*-
"""Génère la structure du coffre Obsidian : fiches de cours, modèles, accueil.

Ne crée AUCUNE note de séance : c'est l'utilisateur qui les crée au fil des cours, avec les modèles.

Ne remplace jamais un fichier existant : on peut le relancer sans risque.
Pour un nouveau semestre : adapter SEMESTRE, PAUSES et COURS puis relancer
    python .outils/generer_seances.py
"""
from datetime import date, timedelta
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent

# Calendrier UT2J 2026-2027, semestre 1 : cours du 14/09 au 18/12, pause du 24/10 soir au 02/11 matin
SEMESTRE = (date(2026, 9, 14), date(2026, 12, 18))
PAUSES = [(date(2026, 10, 26), date(2026, 11, 1))]

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]

MAGISTRAL = ["plan", "notes", "notions", "reperes", "retenir", "devoirs", "revoir"]
LANGUE = ["notes", "vocab", "phrases", "devoirs", "revoir"]
GENERIQUE = ["objectifs", "notes", "afaire", "revoir"]

COURS = [
    dict(nom="Philosophie chinoise", ue="CH00303T", ue_titre="Histoire de la pensée chinoise",
         jour=0, heure="10:50", salle="LA342", sections=MAGISTRAL),
    dict(nom="Structures grammaticales", ue="CH00301T", ue_titre="Compréhension écrite et orale",
         jour=0, heure="14:10", salle="LA342", sections=["notes", "gram", "vocab", "exos", "devoirs", "revoir"]),
    dict(nom="Histoire et civilisation chinoises", ue="CH00302T", ue_titre="Histoire et civilisation chinoises 2",
         jour=1, heure="10:50", salle="LA342", sections=MAGISTRAL),
    dict(nom="Expression orale", ue="CH00304T", ue_titre="Production écrite et orale",
         jour=1, heure="14:10", salle="LA387", sections=LANGUE),
    dict(nom="Version", ue="CH00301T", ue_titre="Compréhension écrite et orale",
         jour=1, heure="16:25", salle="LA202",
         sections=["texte", "vocab", "difficultes", "traduction", "correction", "devoirs", "revoir"]),
    dict(nom="Compréhension orale", ue="CH00301T", ue_titre="Compréhension écrite et orale",
         jour=3, heure="08:50", salle="LA202", sections=["docs"] + LANGUE),
    dict(nom="Renforcement écrit", ue="CH00306T", ue_titre="Chinois : renforcement (écrit)",
         jour=3, heure="11:50", salle="GA123", sections=LANGUE),
    dict(nom="DD3 - PIX", ue="PIX0307T", ue_titre="Préparation à la certification informatique - partie 1",
         jour=3, heure="14:10", salle="AC104 (salle informatique)",
         sections=["competences", "notes", "afaire", "revoir"]),
    dict(nom="Renforcement oral", ue="CH00306T", ue_titre="Chinois : renforcement (oral)",
         jour=3, heure="16:25", salle="LA202", sections=LANGUE),
    dict(nom="Lexicologie - Expression écrite", ue="CH00304T", ue_titre="Production écrite et orale",
         jour=4, heure="08:20", salle="LA342",
         sections=["notes", "vocab", "caracteres", "production", "devoirs", "revoir"]),
    dict(nom="Accompagnement de projet 2", ue="CH00305T", ue_titre="Accompagnement de projet 2",
         jour=4, heure="10:50", salle="LA220 (multimédia)", sections=GENERIQUE),
]

SECTIONS = {
    "plan": "## Plan du cours\n\n1. \n",
    "notes": "## Notes du cours\n\n",
    "notions": "## Notions clés\n\n| Terme | 汉字 · 拼音 | Définition |\n| --- | --- | --- |\n|  |  |  |\n",
    "reperes": "## Dates, personnages, œuvres\n\n- \n",
    "retenir": "## À retenir\n\n> Résumé de la séance en 3 lignes.\n",
    "gram": "## Points de grammaire\n\n### Structure : \n\n- **Formule** : \n- **Emploi** : \n- **Exemples** :\n    - \n",
    "vocab": "## Vocabulaire\n\n| 汉字 | 拼音 | Français | Exemple |\n| --- | --- | --- | --- |\n|  |  |  |  |\n",
    "phrases": "## Phrases et expressions utiles\n\n- \n",
    "exos": "## Exercices faits en cours\n\n- \n",
    "docs": "## Documents travaillés\n\n- \n",
    "texte": "## Texte à traduire\n\n> \n",
    "difficultes": "## Difficultés et choix de traduction\n\n- \n",
    "traduction": "## Ma traduction\n\n",
    "correction": "## Correction\n\n",
    "caracteres": "## Caractères et composants\n\n| 字 | 拼音 | Clé / composants | Sens | Mots |\n| --- | --- | --- | --- | --- |\n|  |  |  |  |  |\n",
    "production": "## Expression écrite\n\n- **Consigne** : \n- **Mon texte** : \n- **Corrections** : \n",
    "objectifs": "## Objectifs de la séance\n\n- \n",
    "competences": "## Compétences PIX travaillées\n\n- \n",
    "afaire": "## À faire\n\n- [ ] \n",
    "devoirs": "## Devoirs pour la prochaine fois\n\n- [ ] \n",
    "revoir": "## À revoir / questions\n\n- \n",
}

# Notes déjà prises avant la mise en place du coffre : (cours, date) -> (ancien fichier, thème, fait)
ANCIENNES = {
    ("Philosophie chinoise", date(2026, 9, 14)): (
        "Philosophie Chinoise/Cours 1 du 14 09 26.md",
        "Philosophie ou pensée chinoise ? Contexte des Royaumes combattants", True),
    ("Structures grammaticales", date(2026, 9, 14)): (
        "Cours 1 du 14 09 26 de CH00301T Compréhension écrite et orale - Structures Grammaticales.md",
        "Révisions leçon 10 du manuel", True),
    ("Structures grammaticales", date(2026, 9, 21)): (
        "Cours 2 du 21 09 26 de CH00301T Compréhension écrite et orale - Structures Grammaticales.md",
        "Insistance 是…的, actions successives, actions simultanées (一边…一边 / 又…又)", False),
}


def ecrire(chemin: Path, contenu: str) -> bool:
    if chemin.exists():
        return False
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(contenu, encoding="utf-8", newline="\n")
    return True


def dates_du_cours(jour: int):
    d = SEMESTRE[0] + timedelta(days=(jour - SEMESTRE[0].weekday()) % 7)
    while d <= SEMESTRE[1]:
        if not any(a <= d <= b for a, b in PAUSES):
            yield d
        d += timedelta(days=7)


def dossier(c) -> str:
    return f"Cours/{c['ue']} {c['nom']}"


def nom_seance(c, d: date) -> str:
    return f"{d.isoformat()} {c['nom']}"


def corps(c, exclure=()) -> str:
    return "\n".join(SECTIONS[s] for s in c["sections"] if s not in exclure)


def entete(c, d, n, theme="", fait=False) -> str:
    theme_yaml = f'"{theme}"' if theme else ""
    return (
        "---\n"
        "type: seance\n"
        f'cours: "[[{c["nom"]}]]"\n'
        f"ue: {c['ue']}\n"
        f"date: {d}\n"
        f"seance: {n}\n"
        f"theme: {theme_yaml}\n"
        f"fait: {'true' if fait else 'false'}\n"
        "---\n"
    )


def note_seance(c, dates, i) -> str:
    d = dates[i]
    nav = [f"[[{c['nom']}]]"]
    if i > 0:
        nav.append(f"← [[{nom_seance(c, dates[i - 1])}|Séance {i}]]")
    if i < len(dates) - 1:
        nav.append(f"[[{nom_seance(c, dates[i + 1])}|Séance {i + 2}]] →")
    nav_ligne = " · ".join(nav) + "\n\n"

    ancienne = ANCIENNES.get((c["nom"], d))
    if ancienne and (VAULT / ancienne[0]).exists():
        texte = (VAULT / ancienne[0]).read_text(encoding="utf-8").strip("\n")
        return (entete(c, d, i + 1, ancienne[1], ancienne[2]) + nav_ligne
                + "## Notes du cours\n\n" + texte + "\n\n" + corps(c, exclure=("notes", "plan")))
    return entete(c, d, i + 1) + nav_ligne + corps(c)


def fiche_cours(c) -> str:
    return f"""---
type: cours
ue: {c['ue']}
jour: {JOURS[c['jour']]}
heure: "{c['heure']}"
salle: {c['salle']}
enseignant:
---
> [!info] Infos pratiques
> **UE** : {c['ue']} – {c['ue_titre']}
> **Créneau** : {JOURS[c['jour']]} {c['heure']} · salle {c['salle']}
> **Enseignant·e** :
> **Manuel / supports** :
> **Évaluation** :

## Séances

```base
filters:
  and:
    - 'file.inFolder("{dossier(c)}")'
    - 'note.type == "seance"'
views:
  - type: table
    name: Séances
    order:
      - file.name
      - note.seance
      - note.theme
      - note.fait
    sort:
      - property: note.date
        direction: ASC
```

## Ressources et liens

-

## Fiches de révision

-
"""


def modele(c) -> str:
    return (
        "---\n"
        "type: seance\n"
        f'cours: "[[{c["nom"]}]]"\n'
        f"ue: {c['ue']}\n"
        'date: "{{date}}"\n'
        "seance: \n"
        "theme: \n"
        "fait: false\n"
        "---\n"
        f"[[{c['nom']}]]\n\n" + corps(c)
    )


BASE = """filters:
  and:
    - 'file.inFolder("Cours")'
    - 'note.type == "seance"'
properties:
  note.cours:
    displayName: Cours
  note.date:
    displayName: Date
  note.seance:
    displayName: Séance
  note.theme:
    displayName: Thème
  note.fait:
    displayName: Fait
views:
  - type: table
    name: À compléter
    filters:
      and:
        - 'note.fait != true'
    order:
      - file.name
      - note.cours
      - note.date
      - note.fait
    sort:
      - property: note.date
        direction: ASC
  - type: table
    name: Toutes les séances
    groupBy:
      property: note.cours
      direction: ASC
    order:
      - file.name
      - note.seance
      - note.theme
      - note.fait
    sort:
      - property: note.date
        direction: ASC
"""


def accueil() -> str:
    lignes = "\n".join(
        f"| {JOURS[c['jour']]} | {c['heure']} | [[{c['nom']}]] | {c['ue']} | {c['salle']} |"
        for c in sorted(COURS, key=lambda c: (c["jour"], c["heure"]))
    )
    return f"""---
type: accueil
---
> [!tip] Routine après chaque cours
> 1. Ouvre la fiche du cours (tableau *Emploi du temps* ci-dessous) puis crée une note (`Ctrl+N`) : elle se range dans le dossier du cours.
> 2. Nomme-la `AAAA-MM-JJ Nom du cours`, puis `Alt+T` (插入模板) et choisis le modèle du cours.
> 3. Remplis le numéro de séance, le thème et les sections. Quand la note est finie, coche **fait**.

## Notes en cours (pas encore cochées « fait »)

![[Séances.base#À compléter]]

## Emploi du temps

| Jour | Heure | Cours | UE | Salle |
| --- | --- | --- | --- | --- |
{lignes}

## Calendrier du semestre 1 (UT2J 2026-2027)

- **Cours** : du 14/09/2026 au 18/12/2026
- **Pause pédagogique** : du 24/10 au soir au 02/11 au matin
- **Vacances de Noël** : du 19/12 au soir au 04/01 au matin
- **Examens** : du 04/01/2027 au 18/01/2027
- **Semestre 2** : à partir du 25/01/2027

## Toutes les séances

![[Séances.base#Toutes les séances]]
"""


def main():
    crees = 0
    for c in COURS:
        crees += ecrire(VAULT / dossier(c) / f"{c['nom']}.md", fiche_cours(c))
        crees += ecrire(VAULT / "Modèles" / f"Séance - {c['nom']}.md", modele(c))
    crees += ecrire(VAULT / "Séances.base", BASE)
    crees += ecrire(VAULT / "Accueil.md", accueil())
    (VAULT / "Pièces jointes").mkdir(exist_ok=True)
    print(f"{crees} fichiers créés")


if __name__ == "__main__":
    main()
