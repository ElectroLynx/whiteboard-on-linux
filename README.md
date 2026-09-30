# Whiteboard

Un tableau blanc moderne pour GNOME — texte, dessin libre et formes — inspiré
des outils comme Canva. Construit avec **GTK4** et **libadwaita** (Python /
PyGObject), pour une intégration native à l'affichage graphique GNOME.

## Prérequis

Ubuntu 24.04 LTS ou une version plus récente est recommandée. Installez les
dépendances système avec :

```bash
sudo apt update
sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adwaita-1
```

Le projet utilise PyGObject fourni par Ubuntu ; aucun paquet `pip` n'est
nécessaire.

## Lancer l'application

```bash
./run.sh
```

ou directement :

```bash
python3 main.py
```

Aucune compilation n'est nécessaire : l'application est du Python pur qui
s'appuie sur les bibliothèques GTK4 / libadwaita installées par le système.

### Installer pour l'utilisateur courant

Pour installer l'application dans `~/.local/share` et l'ajouter au menu GNOME,
depuis la racine du dépôt :

```bash
./install.sh
```

Le script utilise le chemin réel du clone ; l'installation reste donc valable
si le dépôt est déplacé ou cloné par un autre utilisateur.

### Ajouter l'application au menu GNOME (optionnel)

## Outils

| Outil       | Raccourci | Description                              |
|-------------|-----------|-------------------------------------------|
| Sélection   | `S`       | Sélectionner, déplacer, redimensionner    |
| Stylo       | `P`       | Dessin à main levée                       |
| Rectangle   | `R`       | Rectangle (avec remplissage optionnel)    |
| Ellipse     | `O`       | Ellipse (avec remplissage optionnel)      |
| Ligne       | `L`       | Ligne droite                              |
| Flèche      | `A`       | Ligne avec pointe de flèche               |
| Texte       | `T`       | Cliquer pour écrire ; double-clic pour éditer |
| Gomme       | `E`       | Effacer les formes sous le curseur        |

## Raccourcis clavier

- `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` — Nouveau / Ouvrir / Enregistrer / Enregistrer sous
- `Ctrl+E` — Exporter en PNG
- `Ctrl+Z` / `Ctrl+Shift+Z` — Annuler / Rétablir
- `Suppr` / `Retour arrière` — Supprimer la sélection
- `Ctrl+molette`, `Ctrl+=`/`Ctrl+-`/`Ctrl+0` — Zoomer / dézoomer / réinitialiser
- Molette, glisser avec le bouton du milieu, ou `Espace`+glisser — Se déplacer sur le tableau

## Format de fichier

Les tableaux sont enregistrés en JSON (liste de formes avec leur géométrie,
couleur, épaisseur…), ce qui les rend faciles à inspecter ou à versionner.

## Suites possibles

Sélection multiple (marquee), rotation des formes, panneau de calques,
import d'images, et collaboration temps réel n'ont pas été implémentés dans
cette première version pour rester focalisé sur l'essentiel d'un tableau
blanc moderne.
