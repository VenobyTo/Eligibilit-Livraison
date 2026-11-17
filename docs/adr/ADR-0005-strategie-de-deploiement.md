# ADR-0005 : Quelle stratégie de déploiement ?

* **Statut** : Accepté
* **Date** : 2026-10-26 (Cours 2)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : Mise en production sans interruption des nouvelles versions de l'API et du modèle ML

---

## 1. Contexte et Problématique

Dans un système MLOps en production, deux types de mises à jour surviennent à des rythmes différents :
1. **Déploiement applicatif (Code / Image Docker)** : Nouvelle version de l'API FastAPI ou du pipeline de prétraitement.
2. **Déploiement de modèle (Ré-entraînement continu / CT)** : Nouveau fichier `express_delivery_model.joblib` généré par l'orchestrateur à partir des dernières données MongoDB.

Nous devons choisir une stratégie de déploiement minimisant le temps d'indisponibilité (*downtime*) et le risque de régression des prédictions en production.

---

## 2. Options Considérées

### Option A : Stratégie *Recreate* (Arrêt complet puis redémarrage)
* **Avantages** : Très simple à mettre en œuvre (`docker compose down && docker compose up`).
* **Inconvénients** : Interruption de service pendant le téléchargement et le démarrage du conteneur ; risque de laisser l'API indisponible si le nouveau modèle est corrompu.

### Option B : Stratégie *Canary* ou *Shadow Deployment* avec Service Mesh (Istio / Envoy)
* **Avantages** : Validation progressive sur un sous-ensemble du trafic réel (ex. 5 % des requêtes).
* **Inconvénients** : Requiert un routeur de trafic L7 complexe et une infrastructure de duplication de requêtes disproportionnée pour l'échelle actuelle du projet.

### Option C : Stratégie *Rolling / Blue-Green* pilotée par Healthchecks + *Model Quality Gate* — **[RETENUE]**
* **Avantages** :
  * **Validation préalable en environnement de Test isolé (`docker-compose.test.yml` & CI)** : Tout changement est d'abord validé contre un conteneur MongoDB de test éphémère avant publication de l'image sur GHCR.
  * **Healthcheck applicatif et conteneur (`/health`)** : Le Dockerfile et FastAPI exposent l'endpoint `/health` qui vérifie à la fois le chargement effectif du modèle (`model_loaded: true`) et la connectivité MongoDB (`database_connected: true`). L'ancienne instance n'est remplacée que lorsque la nouvelle répond `200 OK (healthy)`.
  * **Model Quality Gate dans l'Orchestrateur (`orchestrator.py`)** : Lors d'un ré-entraînement automatique, le nouveau modèle n'écrase l'artefact de production (`express_delivery_model.joblib`) **que si** ses métriques dépassent les seuils minimaux (`accuracy >= 0.65` et `roc_auc >= 0.70`).
  * **Rechargement à chaud (Zero-Downtime Model Reload)** : L'endpoint `POST /train` et le gestionnaire `load_model()` permettent de recharger le nouveau modèle en mémoire sans couper le serveur Uvicorn.

---

## 3. Décision Retenue

Nous retenons l'**Option C (Rolling / Blue-Green avec Healthchecks `/health` + Model Quality Gate + Rechargement à chaud)**.

### Justification
1. **Zéro régression silencieuse du modèle** : Le *Quality Gate* intégré à `train_and_evaluate_task` empêche la mise en production d'un modèle dégradé par une anomalie de données.
2. **Haute disponibilité de l'API** : Le mécanisme de `lifespan` FastAPI entraîne ou charge automatiquement un modèle de secours au démarrage si aucun artefact n'est présent, et le `HEALTHCHECK` Docker garantit la supervision automatique (`restart: always`).
3. **Rollback instantané** : Grâce au taggage par SHA et version sémantique sur `ghcr.io` et à l'historisation MLflow, revenir à l'image ou au modèle précédent se fait en une commande.
