# Éligibilité à la Livraison Express – Industrialisation MLOps

Application Python industrialisée (Clean Code & MLOps) issue du prototype `project_test_v1_final_final2.ipynb`. Elle assure l'ingestion de commandes depuis une base de données de production (**MongoDB** ou **PostgreSQL** via le pattern *Repository*, avec repli sur générateur synthétique), la validation et le nettoyage des données, l'entraînement orchestré d'un pipeline `scikit-learn` tracé dans **MLflow**, et l'exposition d'une **API REST FastAPI** conteneurisée via **Docker** et publiée sur **GitHub Container Registry (`ghcr.io`)**.

---

## Architecture du Projet

```text
Projet/
├── .github/workflows/
│   └── ci-cd.yml                  Pipeline CI/CD (Tests + Build & Push GHCR)
├── artifacts/                     Modèle sérialisé (joblib), métriques et Model Card
├── data/generated/                Snapshots CSV des données nettoyées d'entraînement
├── docs/adr/                      Architecture Decision Records (ADR-0001 à ADR-0006)
├── reports/                       Graphiques d'audit, matrice de confusion, importance des variables
├── src/eligibilite_livraison/
│   ├── config.py                  Chemins, hyperparamètres et constantes du modèle
│   ├── data.py                    Génération, validation, nettoyage et normalisation ERP
│   ├── model.py                   Pipeline scikit-learn (ColumnTransformer + LogisticRegression)
│   ├── predict.py                 Prédictions unitaires et batch avec seuil configurable
│   ├── training.py                Entraînement, évaluation, suivi MLflow et sauvegarde d'artefacts
│   ├── train.py                   Point d'entrée CLI d'entraînement direct
│   ├── orchestrator.py            Orchestrateur MLOps (DAG de tâches, retries, Quality Gate, scheduler)
│   ├── api.py                     Microservice FastAPI (/health, /predict, /predict/batch, /train)
│   └── infrastructure/
│       ├── contract/
│       │   └── order_repository.py        Contrat générique OrderRepository (Protocol)
│       └── implementation/
│           ├── mongo_order_repository.py  Adaptateur MongoDB (Base analytique de production)
│           └── postgres_order_repository.py Adaptateur PostgreSQL (Base OLTP historique)
├── tests/                         Suite de tests unitaires et d'intégration (API, Data, Repo, Orchestrateur)
├── ADR.md                         Index consolidé des 6 ADR du projet
├── CONTRIBUTING.md                Guide de contribution et workflow GitFlow
├── CODE_OF_CONDUCT.md             Code de conduite
├── SECURITY.md                    Politique de sécurité
├── Dockerfile                     Image Docker multi-stage optimisée et sécurisée (non-root)
├── docker-compose.yml             Environnement local (API, Train, Orchestrator, Tests, MLflow UI)
├── docker-compose.test.yml        Environnement de test d'intégration isolé avec MongoDB 8
└── docker-compose.prod.yml        Environnement de production (API + MongoDB + Orchestrateur planifié)
```

---

## Installation Locale

Depuis le dossier `Projet` :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -e .
```

---

## Utilisation

### 1. Entraînement du modèle (CLI direct)

```powershell
python -m eligibilite_livraison.train
```

Pour entraîner directement sur la base **MongoDB** de production :

```powershell
$env:USE_MONGO_REPOSITORY="true"
$env:MONGO_URI="mongodb://localhost:27017"
python -m eligibilite_livraison.train
```

### 2. Orchestrateur MLOps (Pipeline DAG & Planification)

L'orchestrateur découpe l'entraînement en 4 tâches atomiques (`extract_orders_task` avec retries, `validate_and_clean_task`, `train_and_evaluate_task` avec **Model Quality Gate**, et `publish_artifacts_task` vers MLflow) :

```powershell
# Exécution unique du flow orchestré
python -m eligibilite_livraison.orchestrator

# Mode démon planifié (ex. ré-entraînement toutes les 24h sur MongoDB)
python -m eligibilite_livraison.orchestrator --schedule --interval-seconds 86400
```

### 3. API de Service (FastAPI)

```powershell
uvicorn eligibilite_livraison.api:app --host 0.0.0.0 --port 8000 --reload
```

Endpoints exposés :
- `GET /` : Accueil et liens utiles
- `GET /health` : État de santé du microservice, statut du modèle en mémoire et connectivité MongoDB
- `POST /predict` : Prédiction d'éligibilité express pour une commande unitaire
- `POST /predict/batch` : Prédiction par lot de commandes avec seuil personnalisable
- `POST /train` : Déclenchement d'un ré-entraînement à chaud (MongoDB ou synthétique)
- `GET /docs` : Documentation interactive OpenAPI / Swagger UI

### 4. Suivi des expériences (MLflow)

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

---

## Conteneurisation Docker & Environnements

L'image Docker utilise un **build multi-stage** (`python:3.12-slim`), s'exécute sous un utilisateur non-root (`appuser`) et intègre un `HEALTHCHECK` natif sur `/health`.

```powershell
# Lancer les tests d'intégration avec une base MongoDB 8 de test dédiée
docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

# Déployer la stack complète de production (MongoDB + API FastAPI + Orchestrateur)
docker compose -f docker-compose.prod.yml up -d --build
```

---

## Tests Automatisés & CI/CD

Lancer l'ensemble des tests unitaires et d'intégration localement :

```powershell
python -m unittest discover -s tests -v
```

Le workflow GitHub Actions (`.github/workflows/ci-cd.yml`) s'exécute à chaque `push` / `pull_request` :
1. **Job `test`** : Monte un conteneur de service `mongo:8` et exécute toute la suite de tests.
2. **Job `build-and-push`** : Construit l'image Docker multi-stage et la publie sur **GitHub Container Registry** (`ghcr.io/venobyto/eligibilit-livraison`).

---

## Architecture Decision Records (ADR)

Toutes les décisions structurantes sont documentées dans [ADR.md](ADR.md) et dans `docs/adr/` :
- [ADR-0001 : Stockage des commandes](docs/adr/ADR-0001-stockage-des-commandes.md)
- [ADR-0002 : Stockage des artefacts de modèle](docs/adr/ADR-0002-stockage-des-artefacts-de-modele.md)
- [ADR-0003 : Quelle plateforme de déploiement ?](docs/adr/ADR-0003-plateforme-de-deploiement.md)
- [ADR-0004 : Cloud, On-premise ou local ?](docs/adr/ADR-0004-cloud-on-premise-ou-local.md)
- [ADR-0005 : Quelle stratégie de déploiement ?](docs/adr/ADR-0005-strategie-de-deploiement.md)
- [ADR-0006 : PostgreSQL, MongoDB, autre ?](docs/adr/ADR-0006-postgresql-mongodb-autre.md)
