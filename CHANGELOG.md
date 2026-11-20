# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.

Le format est basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/),
et ce projet adhère au [Semantic Versioning](https://semver.org/lang/fr/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Passage du `Dockerfile` en build multi-stage 3 couches (`builder`, `prod`, `test`) afin de retirer `tests/` et `requirements.txt` de l'image de production finale.
- Restriction de la publication GHCR dans `.github/workflows/ci-cd.yml` aux branches de livraison (`main`, `develop`, `release/*`) et aux tags SemVer (`v*.*.*`).

### Security
- Exclusion explicite des fichiers `.env` / `.env.*` dans `.dockerignore`.

## [1.0.0] - 2026-11-17

### Added
- Transformation du prototype en application Python structurée (`src/eligibilite_livraison/`, `pyproject.toml`) suivant les principes Clean Code (SOLID).
- Pipeline d'entraînement `scikit-learn` (`ColumnTransformer` + `LogisticRegression`) avec suivi d'expériences **MLflow** et génération de `model_card.json`.
- API REST **FastAPI** avec documentation **OpenAPI / Swagger** (`/docs`), sonde `/health`, inférence `/predict`, `/predict/batch` et `/train`.
- Abstraction `OrderRepository` et implémentations **MongoDB** (`pymongo`) et **PostgreSQL** (`psycopg`).
- Orchestrateur MLOps (`orchestrator.py`) avec DAG en 4 tâches, retries, *Model Quality Gate* et planification périodique.
- Environnements conteneurisés séparés : `docker-compose.yml` (dev), `docker-compose.test.yml` (test), `docker-compose.prod.yml` (prod).
- Pipeline CI/CD GitHub Actions (tests automatisés + build et publication Docker sur `ghcr.io`).
- Gouvernance Open Source : `README.md`, `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, `LICENSE`.
