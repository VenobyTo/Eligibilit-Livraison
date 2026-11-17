# Architecture Decision Records (ADR) – Éligibilité à la Livraison Express

Ce document regroupe et indexe l'ensemble des **Architecture Decision Records (ADR-0001 à ADR-0006)** rédigés tout au long de l'industrialisation du projet de Machine Learning dans le cloud.

---

## Index des Décisions d'Architecture

| Réf. | Titre de l'ADR | Cours | Décision Retenue | Fichier Détaillé | Statut |
| :--- | :--- | :---: | :--- | :--- | :---: |
| **ADR-0001** | Stockage des commandes | Cours 1 | **Pattern Repository (`OrderRepository`)** découplant le stockage BDD (MongoDB/PostgreSQL) avec snapshot CSV d'audit (`data/generated/orders.csv`) et générateur synthétique de repli. | [ADR-0001-stockage-des-commandes.md](docs/adr/ADR-0001-stockage-des-commandes.md) | ✅ Accepté |
| **ADR-0002** | Stockage des artefacts de modèle | Cours 1 | **Pipeline complet sérialisé via `joblib`** (`express_delivery_model.joblib`) + Métadonnées JSON (`metrics.json`, `features.json`, `model_card.json`) + **MLflow Tracking** (`sqlite:///mlflow.db`). | [ADR-0002-stockage-des-artefacts-de-modele.md](docs/adr/ADR-0002-stockage-des-artefacts-de-modele.md) | ✅ Accepté |
| **ADR-0003** | Quelle plateforme de déploiement ? | Cours 2 | **Conteneurs Docker Multi-Stage (`python:3.12-slim`)** publiés sur **GitHub Container Registry (`ghcr.io`)** et orchestrés par **Docker Compose**. | [ADR-0003-plateforme-de-deploiement.md](docs/adr/ADR-0003-plateforme-de-deploiement.md) | ✅ Accepté |
| **ADR-0004** | Cloud, On-premise ou local ? | Cours 2 | **Architecture Hybride Cloud-Ready** : Usine logicielle CI/CD dans le Cloud (GitHub Actions + GHCR) et exécution conteneurisée On-Premise/Locale au plus près des bases ERP (réversible vers Cloud Run / ECS via 12-Factor App). | [ADR-0004-cloud-on-premise-ou-local.md](docs/adr/ADR-0004-cloud-on-premise-ou-local.md) | ✅ Accepté |
| **ADR-0005** | Quelle stratégie de déploiement ? | Cours 2 | **Rolling / Blue-Green avec Healthcheck (`/health`)**, validation en environnement de test éphémère (`docker-compose.test.yml`) et **Model Quality Gate** dans l'orchestrateur avant publication d'un nouveau modèle. | [ADR-0005-strategie-de-deploiement.md](docs/adr/ADR-0005-strategie-de-deploiement.md) | ✅ Accepté |
| **ADR-0006** | PostgreSQL, MongoDB, autre ? | Cours 4 | **MongoDB (Base Analytique Découplée)** via `MongoOrderRepository` pour isoler à 100 % la base PostgreSQL OLTP critique (sans DBA) et bénéficier de données complètes post-2023 sans valeurs `NULL`. | [ADR-0006-postgresql-mongodb-autre.md](docs/adr/ADR-0006-postgresql-mongodb-autre.md) | ✅ Accepté |

---

## Résumé Exécutif par ADR

### ADR-0001 : Stockage des commandes
* **Problématique** : Comment stocker et exposer les commandes pour l'entraînement et l'inférence sans coupler le code métier à un fichier plat ou à un moteur de base de données unique ?
* **Choix** : Définition du contrat `OrderRepository` (`src/eligibilite_livraison/infrastructure/contract/order_repository.py`) implémenté par `MongoOrderRepository` et `PostgresOrderRepository`, complété par un export `data/generated/orders.csv` horodaté par run.

### ADR-0002 : Stockage des artefacts de modèle
* **Problématique** : Comment garantir l'absence de *training-serving skew* et l'auditabilité des modèles entraînés ?
* **Choix** : Sérialisation atomique du `Pipeline` scikit-learn (`ColumnTransformer` + `LogisticRegression`) avec `joblib`, accompagnée d'une *Model Card* (`model_card.json`), des métriques (`metrics.json`), et du suivi d'expériences dans `MLflow`.

### ADR-0003 : Quelle plateforme de déploiement ?
* **Problématique** : Quelle plateforme choisir pour packager, distribuer et exécuter l'API, la base de données et l'orchestrateur ?
* **Choix** : Image Docker multi-stage minimale et sécurisée (utilisateur non-root `appuser`), publiée automatiquement sur **GitHub Container Registry (`ghcr.io`)** via GitHub Actions, et déployée avec **Docker Compose** (`docker-compose.yml`, `docker-compose.test.yml`, `docker-compose.prod.yml`).

### ADR-0004 : Cloud, On-premise ou local ?
* **Problématique** : Où héberger les composants compte tenu de la présence des bases ERP internes et des contraintes de coûts/sécurité ?
* **Choix** : Approche hybride : CI/CD et registre d'images dans le Cloud (GitHub), exécution conteneurisée On-Premise / Locale à faible latence à côté du flux ERP, avec portabilité Cloud immédiate grâce à la configuration par variables d'environnement.

### ADR-0005 : Quelle stratégie de déploiement ?
* **Problématique** : Comment déployer une nouvelle version de l'application ou un modèle ré-entraîné sans coupure de service ni régression ?
* **Choix** : Vérification par sonde `/health` (modèle chargé + base connectée), tests d'intégration sur conteneur MongoDB dédié avant publication, et *Model Quality Gate* (`accuracy >= 0.65`, `roc_auc >= 0.70`) dans l'orchestrateur MLOps avant remplacement de l'artefact en production.

### ADR-0006 : PostgreSQL, MongoDB, autre ?
* **Problématique** : Faut-il entraîner le modèle sur la base PostgreSQL historique (2015+, partagée avec une application critique, sans DBA, colonnes `weekend` et `preparation_time_min` nulles avant 2017) ou sur la base MongoDB analytique (2023+, dédiée, alimentée en temps réel par ETL) ?
* **Choix** : **MongoDB** est retenue comme source primaire en production afin de garantir un *Zero Blast Radius* sur PostgreSQL et d'entraîner le modèle sur des données récentes, complètes et représentatives (exemptes de *Concept Drift* historique).
