# Éligibilité à la livraison express

Projet Python issu du notebook `project_test_v1_final_final2.ipynb`. Il génère
des commandes synthétiques, vérifie et nettoie les données, entraîne une
régression logistique et expose des fonctions de prédiction unitaire et batch.
Les données étant simulées, les résultats ne doivent pas être utilisés pour
prendre des décisions opérationnelles réelles.

## Structure

```text
Projet/
├── artifacts/                 Modèle sérialisé, métriques et configuration
├── data/generated/            Jeu synthétique généré par l'entraînement
├── reports/                   Graphiques, rapport et importance des variables
├── src/eligibilite_livraison/
│   ├── config.py               Chemins et constantes du modèle
│   ├── data.py                 Génération, validation et nettoyage
│   ├── model.py                Pipeline scikit-learn
│   ├── predict.py              Prédictions unitaires et batch
│   ├── train.py                Point d'entrée exécutable
│   └── training.py             Entraînement, évaluation et sauvegardes
└── tests/                      Tests unitaires
```

## Installation

Depuis le dossier `Projet` (PowerShell ou terminal Windows) :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pip install -e .
```

## Entraînement

```powershell
python -m eligibilite_livraison.train
```

Les résultats sont enregistrés dans `artifacts/`, `data/generated/`,
`reports/`, ainsi que dans `mlflow.db` et `mlartifacts/` pour le suivi MLflow.
Les chemins de sortie sont calculés par rapport à la racine du projet, quel que
soit le dossier courant.

Pour consulter les expériences MLflow :

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

## Prédiction depuis Python

```python
import joblib

from eligibilite_livraison.config import ARTIFACTS_DIR
from eligibilite_livraison.predict import predict_order_eligibility

model = joblib.load(ARTIFACTS_DIR / "express_delivery_model.joblib")
order = {
    "hour": 14,
    "day_of_week": 2,
    "weekend": 0,
    "distance_km": 3.5,
    "order_value_eur": 89.90,
    "weight_kg": 2.4,
    "stock_available": 1,
    "preparation_time_min": 18,
    "carrier_capacity": 0.85,
    "weather": "normal",
    "delivery_zone": "centre",
    "customer_type": "premium",
}
print(predict_order_eligibility(order, model))
```

La fonction exige toutes les variables du modèle et accepte un seuil de
décision configurable (0,5 par défaut).

## Tests

```powershell
python -m unittest discover -s tests -v
```
