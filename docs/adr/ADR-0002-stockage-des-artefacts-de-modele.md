# ADR-0002 : Stockage des artefacts de modèle

* **Statut** : Accepté
* **Date** : 2026-10-09 (Cours 1)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : Industrialisation du pipeline d'éligibilité à la livraison express

---

## 1. Contexte et Problématique

L'entraînement du modèle de Machine Learning (`Pipeline` scikit-learn composé d'un `ColumnTransformer` et d'une `LogisticRegression`) produit plusieurs artefacts critiques :
- Le binaire du pipeline entraîné (prétraitement + classifieur) ;
- Les métriques d'évaluation (`accuracy`, `precision`, `recall`, `f1_score`, `roc_auc`) ;
- Le contrat des variables d'entrée (`features.json`) et la fiche descriptive du modèle (`model_card.json`) ;
- Les rapports visuels d'audit (`confusion_matrix.png`, `feature_importance.png`, `classification_report.txt`).

Nous devons décider du format de sérialisation et du système de stockage/versionnement de ces artefacts afin qu'ils soient consommables de manière fiable par l'API FastAPI en production et traçables dans le temps.

---

## 2. Options Considérées

### Option A : Sérialisation `pickle` standard sur disque local uniquement
* **Avantages** : Inclus dans la bibliothèque standard Python.
* **Inconvénients** : Moins performant sur les tableaux NumPy de `scikit-learn`, aucun suivi d'expériences, écrasement silencieux des versions précédentes sans historique des hyperparamètres ni des métriques.

### Option B : Stockage Cloud Object Storage pur (AWS S3 / GCS / Azure Blob)
* **Avantages** : Haute disponibilité, stockage illimité et partagé nativement à grande échelle.
* **Inconvénients** : Nécessite des clés d'accès cloud payantes, complexifie l'exécution locale/étudiante et ne fournit pas à lui seul un registre de métriques ML.

### Option C : Double stockage `joblib` + Métadonnées JSON + Tracking & Model Registry `MLflow` — **[RETENUE]**
* **Avantages** :
  * **`joblib`** est le standard recommandé par `scikit-learn` pour sérialiser efficacement les pipelines contenant des matrices NumPy (`artifacts/express_delivery_model.joblib`).
  * **Métadonnées JSON auto-portantes** (`metrics.json`, `features.json`, `model_card.json`) permettant d'auditer le modèle sans même le désérialiser.
  * **MLflow Tracking & Artifacts** (`sqlite:///mlflow.db` + `mlruns/`) enregistre chaque run avec ses hyperparamètres, ses métriques, la source de données et le modèle complet (`mlflow.sklearn.log_model` avec validation de sécurité `skops_trusted_types`).
  * Montage par volume Docker (`./artifacts:/app/artifacts`) permettant un partage immédiat entre le conteneur `orchestrator`/`train` et le conteneur `api`.

---

## 3. Décision Retenue

Nous retenons l'**Option C (`joblib` + JSON Model Card + MLflow Tracking)**.

### Justification
1. **Bundle atomique Prétraitement + Modèle** : En sérialisant l'intégralité du `sklearn.pipeline.Pipeline` via `joblib`, nous éliminons tout risque de *training-serving skew* (les imputations et normalisations sont embarquées dans l'artefact).
2. **Gouvernance et Auditabilité (Model Card)** : La génération systématique de `model_card.json` et `metrics.json` documente la version du modèle (`1.0.0`), les seuils et les limites connues.
3. **Historisation MLOps via MLflow** : Chaque ré-entraînement orchestré crée un `run_id` unique dans MLflow, permettant de comparer les performances avant promotion en production.
