# Guide de contribution

Merci de votre intérêt pour le projet **Éligibilité à la livraison express** !
Ce document décrit les règles et bonnes pratiques à suivre pour contribuer de
manière efficace et cohérente.

---

## Table des matières

1. [Prérequis](#prérequis)
2. [Mise en place de l'environnement](#mise-en-place-de-lenvironnement)
3. [Organisation du projet](#organisation-du-projet)
4. [Workflow Git](#workflow-git)
5. [Conventions de code](#conventions-de-code)
6. [Tests](#tests)
7. [Suivi des expériences (MLflow)](#suivi-des-expériences-mlflow)
8. [Signaler un problème](#signaler-un-problème)
9. [Proposer une amélioration](#proposer-une-amélioration)
10. [Revue de code](#revue-de-code)
11. [Code de conduite](#code-de-conduite)

---

## Prérequis

| Outil | Version minimale |
|-------|-----------------|
| Python | 3.10+ |
| pip | dernière version stable |
| Git | 2.x |

Dépendances principales : `scikit-learn`, `pandas`, `numpy`, `matplotlib`,
`seaborn`, `mlflow`, `joblib` (voir `requirements.txt`).

---

## Mise en place de l'environnement

```powershell
# 1. Cloner le dépôt
git clone <url-du-dépôt>
cd Projet

# 2. Créer et activer un environnement virtuel
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # PowerShell
# ou : source .venv/bin/activate      # Linux / macOS

# 3. Installer les dépendances + le paquet en mode éditable
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

> **Vérification rapide** : lancez `python -m unittest discover -s tests -v`
> pour vous assurer que tout fonctionne.

---

## Organisation du projet

```text
Projet/
├── artifacts/                  Modèle sérialisé, métriques, configuration
├── data/generated/             Jeu synthétique produit par l'entraînement
├── reports/                    Graphiques et rapport d'évaluation
├── src/eligibilite_livraison/
│   ├── config.py                Chemins et constantes
│   ├── data.py                  Génération, validation, nettoyage
│   ├── model.py                 Pipeline scikit-learn
│   ├── predict.py               Prédictions unitaires et batch
│   ├── train.py                 Point d'entrée exécutable
│   └── training.py              Entraînement, évaluation, sauvegardes
├── tests/                       Tests unitaires
├── pyproject.toml               Configuration du build (setuptools)
├── requirements.txt             Dépendances
└── README.md                    Documentation principale
```

Respectez cette arborescence : tout nouveau module Python va dans
`src/eligibilite_livraison/`, tout nouveau test dans `tests/`.

---

## Workflow Git (GitFlow)

Le projet applique le modèle de branches **GitFlow** afin de séparer strictement le code en production, l'intégration continue et les développements en cours.

### Branches

| Branche | Rôle |
|---------|------|
| `main` | Branche de **production** stable ; chaque fusion correspond à une version livrable taguée (`vX.Y.Z`) |
| `develop` | Branche principale d'**intégration** regroupant les fonctionnalités validées pour la prochaine version |
| `feature/<nom>` | Développement d'une nouvelle fonctionnalité (créée depuis `develop`, fusionnée dans `develop`) |
| `release/<version>` | Préparation et stabilisation d'une livraison (créée depuis `develop`, fusionnée dans `main` et `develop`) |
| `hotfix/<nom>` | Correction urgente en production (créée depuis `main`, fusionnée dans `main` et `develop`) |
| `fix/<nom>` / `docs/<nom>` | Corrections de bugs ou améliorations documentaires ciblant `develop` |

### Étapes pour contribuer

1. **Créer une branche** à partir de `develop` :

   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/ma-fonctionnalite
   ```

2. **Développer** en faisant des commits atomiques et explicites (voir
   *Conventions de commits* ci-dessous).

3. **Lancer les tests** pour vérifier que rien n'est cassé :

   ```powershell
   python -m unittest discover -s tests -v
   ```

4. **Pousser** votre branche et ouvrir une **Pull Request** vers `develop` (ou vers `main` lors d'une `release/*` / `hotfix/*`).

5. **Attendre la validation de la CI GitHub Actions** et la revue d'au moins un autre contributeur avant de fusionner.

### Conventions de commits

Utilisez le format [Conventional Commits](https://www.conventionalcommits.org/) :

```
<type>(<portée>): <description courte>

<corps optionnel>
```

| Type | Usage |
|------|-------|
| `feat` | Nouvelle fonctionnalité |
| `fix` | Correction de bug |
| `docs` | Documentation uniquement |
| `test` | Ajout ou modification de tests |
| `refactor` | Remaniement sans changement fonctionnel |
| `chore` | Tâches annexes (dépendances, CI…) |

**Exemples** :

```
feat(model): ajouter la normalisation des features numériques
fix(data): corriger la validation du champ weather
docs: mettre à jour le README avec les nouvelles métriques
test(predict): ajouter le test de prédiction batch vide
```

---

## Conventions de code

### Style

- **PEP 8** : respectez le guide de style Python standard.
- **Longueur de ligne** : 88 caractères max (compatible `black`).
- **Docstrings** : au format
  [Google](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  pour toute fonction ou classe publique.
- **Type hints** : encouragés sur les signatures de fonctions.

### Outils recommandés

```powershell
# Formateur
pip install black
black src/ tests/

# Linter
pip install ruff
ruff check src/ tests/

# Vérification des types (optionnel)
pip install mypy
mypy src/
```

### Nommage

- Variables et fonctions : `snake_case`
- Classes : `PascalCase`
- Constantes : `UPPER_SNAKE_CASE`
- Modules : noms courts et descriptifs en `snake_case`

---

## Tests

Les tests se trouvent dans le répertoire `tests/` et utilisent le module
standard `unittest`.

### Lancer les tests

```powershell
python -m unittest discover -s tests -v
```

### Règles

- Tout nouveau code doit être accompagné de tests unitaires.
- Les tests doivent être **indépendants** les uns des autres et ne pas dépendre
  d'un état partagé.
- Nommez vos fichiers de test `test_<module>.py` et vos méthodes
  `test_<comportement_attendu>`.
- Utilisez des **données synthétiques** ou des fixtures ; ne dépendez jamais
  de fichiers générés par l'entraînement.

### Exemple

```python
import unittest

from eligibilite_livraison.data import validate_order


class TestValidateOrder(unittest.TestCase):
    def test_order_valide_retourne_true(self):
        order = {
            "hour": 10,
            "distance_km": 5.0,
            "stock_available": 1,
            # … autres champs requis
        }
        self.assertTrue(validate_order(order))

    def test_order_sans_champ_requis_leve_erreur(self):
        with self.assertRaises(KeyError):
            validate_order({})
```

---

## Suivi des expériences (MLflow)

Le projet utilise **MLflow** avec un backend SQLite (`mlflow.db`) pour tracer
les expériences d'entraînement.

- Ne committez **jamais** les fichiers `mlflow.db`, `mlruns/` ou
  `mlartifacts/` (ils sont dans le `.gitignore`).
- Si vous modifiez les hyperparamètres ou le pipeline, documentez les
  changements dans le message de commit et dans la docstring de la fonction
  modifiée.
- Consultez les résultats localement :

  ```powershell
  mlflow ui --backend-store-uri sqlite:///mlflow.db
  ```

---

## Signaler un problème

Ouvrez une **Issue** en précisant :

1. **Description** : ce qui ne fonctionne pas ou ce qui pourrait être amélioré.
2. **Étapes de reproduction** : commandes exactes, entrées utilisées.
3. **Comportement attendu vs obtenu**.
4. **Environnement** : OS, version de Python, versions des dépendances
   (`pip freeze`).

---

## Proposer une amélioration

1. Vérifiez qu'une Issue similaire n'existe pas déjà.
2. Ouvrez une Issue de type *enhancement* décrivant le besoin et la solution
   envisagée.
3. Attendez un retour avant de commencer à coder — cela évite le travail
   inutile.
4. Une fois validé, suivez le [workflow Git](#workflow-git) pour soumettre
   votre contribution.

---

## Revue de code

Toute Pull Request sera examinée selon les critères suivants :

| Critère | Détail |
|---------|--------|
| **Fonctionnalité** | Le code fait ce qu'il prétend faire |
| **Tests** | Les nouveaux comportements sont couverts par des tests |
| **Style** | Le code respecte les conventions PEP 8 / projet |
| **Documentation** | Les fonctions publiques ont des docstrings à jour |
| **Pas de régression** | Les tests existants passent toujours |
| **Pas de fichiers générés** | Aucun artefact, données ou base MLflow commité |

Les retours de revue sont formulés de manière constructive. N'hésitez pas à
poser des questions si un commentaire n'est pas clair.

---

## Code de conduite

- Soyez respectueux et bienveillant dans vos échanges.
- Privilégiez la collaboration : proposez des alternatives plutôt que de
  simplement rejeter une idée.
- Toute forme de harcèlement ou de discrimination est inacceptable.

---
Merci pour vos contributions !