# ADR-0003 : Quelle plateforme de déploiement ?

* **Statut** : Accepté
* **Date** : 2026-10-26 (Cours 2)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : Conteneurisation, registre d'images et exécution du microservice d'IA

---

## 1. Contexte et Problématique

Le projet d'éligibilité à la livraison express comprend plusieurs composants qui doivent interagir :
1. Une **API REST d'inférence** (`FastAPI` + `Uvicorn`) ;
2. Un **Orchestrateur / Worker d'entraînement** (`eligibilite_livraison.orchestrator`) ;
3. Une **Base de données** (`MongoDB 8`) ;
4. Une **Interface de suivi** (`MLflow UI`).

Nous devons choisir la plateforme de packaging, de distribution et d'orchestration de conteneurs pour déployer ces services de façon reproductible en test et en production.

---

## 2. Options Considérées

### Option A : Déploiement natif sur machine virtuelle (Systemd / Virtualenv)
* **Avantages** : Pas de couche de conteneurisation.
* **Inconvénients** : Problèmes de reproductibilité ("ça marche sur ma machine"), conflits de versions Python/librairies C (`gcc`), couplage fort à l'OS hôte.

### Option B : Cluster Kubernetes (EKS / GKE / AKS)
* **Avantages** : Auto-scaling avancé, haute disponibilité multi-nœuds, standard pour des centaines de microservices.
* **Inconvénients** : Surcharge opérationnelle et financière disproportionnée pour une architecture à 3 conteneurs (API + MongoDB + Orchestrateur).

### Option C : Conteneurs OCI Docker (Build Multi-Stage) + Registre GHCR (`ghcr.io`) + Docker Compose — **[RETENUE]**
* **Avantages** :
  * **Image Docker unique, légère et sécurisée** : Construction multi-stage basée sur `python:3.12-slim` (séparation `builder` / `runtime`), exécution sous utilisateur non-root (`appuser`), `HEALTHCHECK` intégré.
  * **GitHub Container Registry (`ghcr.io`)** : Intégré nativement au dépôt GitHub et aux GitHub Actions (`GITHUB_TOKEN`), sans gestion externe de secrets tiers, avec versionnement automatique par tags Git et SHA.
  * **Docker Compose multi-environnements** (`docker-compose.yml`, `docker-compose.test.yml`, `docker-compose.prod.yml`) : Déclaration Infrastructure-as-Code simple, réseaux isolés, gestion des dépendances de démarrage (`depends_on: condition: service_healthy`).

---

## 3. Décision Retenue

Nous retenons l'**Option C (Docker Multi-Stage + GitHub Container Registry `ghcr.io` + Docker Compose)**.

### Justification
1. **Parité Développement / Test / Production** : La même image Docker construite par la CI et publiée sur `ghcr.io/venobyto/eligibilit-livraison` sert à exécuter l'API, les tests et l'orchestrateur d'entraînement.
2. **Optimisation de la taille et de la sécurité** : Le build multi-stage évite d'embarquer `gcc`/`g++` dans l'image finale et `.dockerignore` exclut les données locales et fichiers de documentation.
3. **Standard OCI portable** : L'image hébergée sur GHCR peut être déployée à l'identique sur un serveur Docker Compose, AWS ECS, Google Cloud Run ou Azure Container Apps.
