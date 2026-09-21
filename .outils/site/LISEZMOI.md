# Site de révision (version web du coffre)

Le site est généré à partir des notes par `build.py`. Il ne modifie jamais les notes.

## Voir le site sur l'ordinateur

    pip install -r .outils/site/requirements.txt   (une seule fois)
    python .outils/site/build.py

puis ouvrir `.site/index.html` dans un navigateur.

## Mettre à jour le site en ligne

    git add -A
    git commit -m "Notes du jour"
    git push

Ou, plus simple : double-cliquer sur `publier.bat` à la racine du coffre (il fait ces trois commandes).

GitHub Actions (`.github/workflows/pages.yml`) reconstruit et publie le site en une à deux minutes.
Réglage à faire une seule fois sur GitHub : Settings > Pages > Source : « GitHub Actions ».

## Ce que fait le générateur

- une page par note ; l'accueil est `Accueil.md` ; les dossiers `Modèles`, `_Archive…` et `Pièces jointes` ne sont pas publiés ;
- liens `[[…]]`, encadrés `> [!info]`, surlignage `==…==`, cases à cocher, tableaux ;
- les vues Bases d'Obsidian sont remplacées par des listes de séances calculées à partir des propriétés ;
- recherche sans accents ni tons (« zhanguo » trouve « Zhànguó »), menu des cours, sommaire, liens retour ;
- lecture hors connexion après une première visite (service worker) ;
- page **Vocabulaire** (`vocabulaire.html`) : tous les tableaux qui ont une colonne 汉字 (ou 字) et une colonne 拼音, ou une colonne « 汉字 · 拼音 », y sont repris ; liste filtrable, cartes de révision (`vocabulaire.html#cartes`), export pour Anki ;
- icône et manifeste pour ajouter le site à l'écran d'accueil du téléphone ;
- le site est public : les adresses e-mail sont retirées des pages (`MASQUER_EMAILS`) et les pages demandent aux moteurs de recherche de ne pas les indexer.
