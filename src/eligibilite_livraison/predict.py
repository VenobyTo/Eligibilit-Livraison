from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from eligibilite_livraison.config import (
    DEFAULT_THRESHOLD,
    FEATURE_COLUMNS,
    MODEL_VERSION,
)


def _validate_threshold(threshold: float) -> None:
    if not 0 <= threshold <= 1:
        raise ValueError("Le seuil doit être compris entre 0 et 1.")


def predict_with_threshold(
    model: Pipeline,
    data: pd.DataFrame,
    threshold: float = DEFAULT_THRESHOLD,
) -> pd.DataFrame:
    """Ajoute probabilité, classe et décision à un lot de commandes."""
    _validate_threshold(threshold)
    missing_features = set(FEATURE_COLUMNS) - set(data.columns)
    if missing_features:
        raise ValueError(
            f"Variables manquantes dans les données : {sorted(missing_features)}"
        )

    probabilities = model.predict_proba(data[FEATURE_COLUMNS])[:, 1]
    predictions = (probabilities >= threshold).astype(int)
    result = data.copy()
    result["eligibility_probability"] = probabilities.round(4)
    result["express_eligible"] = predictions
    result["decision"] = np.where(predictions == 1, "oui", "non")
    return result


def predict_order_eligibility(
    order_data: dict[str, Any],
    model: Pipeline,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Retourne la décision d'éligibilité pour une commande."""
    _validate_threshold(threshold)
    missing_features = set(FEATURE_COLUMNS) - set(order_data)
    if missing_features:
        raise ValueError(f"Variables manquantes : {sorted(missing_features)}")

    input_df = pd.DataFrame(
        [{feature: order_data[feature] for feature in FEATURE_COLUMNS}]
    )
    probability = float(model.predict_proba(input_df)[0, 1])
    eligible = probability >= threshold
    return {
        "express_eligible": bool(eligible),
        "decision": "oui" if eligible else "non",
        "probability": round(probability, 4),
        "model_version": MODEL_VERSION,
        "prediction_timestamp": datetime.now(timezone.utc).isoformat(),
    }


def batch_predict_orders(
    input_df: pd.DataFrame,
    model: Pipeline,
    threshold: float = DEFAULT_THRESHOLD,
) -> pd.DataFrame:
    """Réalise une prédiction batch en conservant les colonnes d'entrée."""
    return predict_with_threshold(model, input_df, threshold)
