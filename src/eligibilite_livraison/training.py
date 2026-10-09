import json
from dataclasses import dataclass
from typing import Any

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mlflow
import mlflow.sklearn
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from eligibilite_livraison.config import (
    ARTIFACTS_DIR,
    CATEGORICAL_FEATURES,
    FEATURE_COLUMNS,
    MLFLOW_DB_PATH,
    MODEL_VERSION,
    NUMERIC_FEATURES,
    PROJECT_NAME,
    RANDOM_STATE,
    REPORTS_DIR,
    TARGET_COLUMN,
)
from eligibilite_livraison.data import validate_dataset
from eligibilite_livraison.model import build_model_pipeline
from eligibilite_livraison.predict import batch_predict_orders


@dataclass
class TrainingResult:
    model: Pipeline
    metrics: dict[str, float]
    X_train: pd.DataFrame
    X_test: pd.DataFrame
    y_train: pd.Series
    y_test: pd.Series
    y_pred: np.ndarray
    y_proba: np.ndarray


def fit_and_evaluate(
    orders: pd.DataFrame,
    random_state: int = RANDOM_STATE,
) -> TrainingResult:
    """Entraîne le modèle et calcule les métriques sur un jeu de test."""
    validate_dataset(orders)
    X = orders[FEATURE_COLUMNS]
    y = orders[TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=random_state,
        stratify=y,
    )

    model = build_model_pipeline(random_state)
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(
            precision_score(y_test, y_pred, zero_division=0)
        ),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1_score": float(f1_score(y_test, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
    }
    return TrainingResult(
        model=model,
        metrics=metrics,
        X_train=X_train,
        X_test=X_test,
        y_train=y_train,
        y_test=y_test,
        y_pred=y_pred,
        y_proba=y_proba,
    )


def _feature_importance(model: Pipeline) -> pd.DataFrame:
    preprocessor = model.named_steps["preprocessor"]
    classifier = model.named_steps["classifier"]
    feature_names = preprocessor.get_feature_names_out()
    coefficients = classifier.coef_[0]
    return (
        pd.DataFrame(
            {
                "feature": feature_names,
                "coefficient": coefficients,
                "absolute_coefficient": np.abs(coefficients),
            }
        )
        .sort_values("absolute_coefficient", ascending=False)
        .reset_index(drop=True)
    )


def save_training_outputs(
    result: TrainingResult,
    orders: pd.DataFrame,
) -> dict[str, Any]:
    """Sauvegarde les modèles, résultats, prédictions et rapports du run."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    model_path = ARTIFACTS_DIR / "express_delivery_model.joblib"
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    features_path = ARTIFACTS_DIR / "features.json"
    model_card_path = ARTIFACTS_DIR / "model_card.json"
    joblib.dump(result.model, model_path)

    with metrics_path.open("w", encoding="utf-8") as file:
        json.dump(result.metrics, file, indent=2, ensure_ascii=False)

    feature_config = {
        "model_version": MODEL_VERSION,
        "target": TARGET_COLUMN,
        "features": FEATURE_COLUMNS,
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
    }
    with features_path.open("w", encoding="utf-8") as file:
        json.dump(feature_config, file, indent=2, ensure_ascii=False)

    model_card = {
        "project": PROJECT_NAME,
        "model_version": MODEL_VERSION,
        "model_type": "Régression logistique",
        "task": "Classification binaire",
        "target": TARGET_COLUMN,
        "positive_class": "Commande éligible à la livraison express",
        "negative_class": "Commande non éligible à la livraison express",
        "features": FEATURE_COLUMNS,
        "threshold": 0.5,
        "training_rows": len(result.X_train),
        "test_rows": len(result.X_test),
        "metrics": result.metrics,
        "limitations": [
            "Le jeu de données utilisé est synthétique.",
            "La décision doit être validée avec les règles métier.",
            "Les performances peuvent varier sur des données réelles.",
            "Le modèle ne remplace pas l'analyse des contraintes opérationnelles.",
        ],
    }
    with model_card_path.open("w", encoding="utf-8") as file:
        json.dump(model_card, file, indent=2, ensure_ascii=False)

    sample = orders.sample(n=min(10, len(orders)), random_state=RANDOM_STATE)
    batch_predictions = batch_predict_orders(
        sample[FEATURE_COLUMNS],
        result.model,
    )
    batch_path = ARTIFACTS_DIR / "batch_predictions.csv"
    batch_predictions.to_csv(batch_path, index=False)

    _save_reports(result, orders)
    return {
        "model": model_path,
        "metrics": metrics_path,
        "features": features_path,
        "model_card": model_card_path,
        "batch_predictions": batch_path,
    }


def _save_reports(result: TrainingResult, orders: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    sns.countplot(data=orders, x=TARGET_COLUMN, ax=axes[0])
    axes[0].set_title("Répartition de la cible")
    axes[0].set_xlabel("Éligibilité express")
    axes[0].set_ylabel("Nombre de commandes")
    sns.boxplot(
        data=orders,
        x=TARGET_COLUMN,
        y="distance_km",
        ax=axes[1],
    )
    axes[1].set_title("Distance selon l'éligibilité")
    axes[1].set_xlabel("Éligibilité express")
    axes[1].set_ylabel("Distance en kilomètres")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "data_overview.png", dpi=150)
    plt.close(fig)

    matrix = confusion_matrix(result.y_test, result.y_pred)
    fig, axis = plt.subplots(figsize=(6, 5))
    sns.heatmap(
        matrix,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=["Non éligible", "Éligible"],
        yticklabels=["Non éligible", "Éligible"],
        ax=axis,
    )
    axis.set_title("Matrice de confusion")
    axis.set_xlabel("Prédiction")
    axis.set_ylabel("Valeur réelle")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "confusion_matrix.png", dpi=150)
    plt.close(fig)

    importance = _feature_importance(result.model)
    importance.to_csv(REPORTS_DIR / "feature_importance.csv", index=False)
    top_features = importance.head(15).sort_values("coefficient")
    colors = [
        "crimson" if value < 0 else "seagreen"
        for value in top_features["coefficient"]
    ]
    fig, axis = plt.subplots(figsize=(10, 6))
    axis.barh(top_features["feature"], top_features["coefficient"], color=colors)
    axis.set_title("Variables ayant le plus d'influence")
    axis.set_xlabel("Coefficient du modèle")
    axis.set_ylabel("Variable")
    fig.tight_layout()
    fig.savefig(REPORTS_DIR / "feature_importance.png", dpi=150)
    plt.close(fig)

    report = classification_report(
        result.y_test,
        result.y_pred,
        target_names=["Non éligible", "Éligible"],
        zero_division=0,
    )
    (REPORTS_DIR / "classification_report.txt").write_text(
        report,
        encoding="utf-8",
    )


def run_training(
    n_rows: int = 6000,
    random_state: int = RANDOM_STATE,
) -> dict[str, Any]:
    """Exécute le flux complet de génération, entraînement et sauvegarde."""
    from eligibilite_livraison.data import (
        clean_orders_data,
        generate_orders_dataset,
    )

    raw_orders = generate_orders_dataset(n_rows, random_state)
    clean_orders = clean_orders_data(raw_orders)
    validate_dataset(clean_orders)
    data_path = _save_generated_data(clean_orders)

    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB_PATH.as_posix()}")
    mlflow.set_experiment("livraison-express")
    with mlflow.start_run(run_name="logistic-regression-baseline") as run:
        result = fit_and_evaluate(clean_orders, random_state)
        mlflow.log_param("model_type", "LogisticRegression")
        mlflow.log_param("random_state", random_state)
        mlflow.log_param("feature_count", len(FEATURE_COLUMNS))
        mlflow.log_param("training_rows", len(result.X_train))
        mlflow.log_metrics(result.metrics)
        mlflow.sklearn.log_model(
            result.model,
            artifact_path="model",
            skops_trusted_types=["numpy.dtype"],
        )
        output_paths = save_training_outputs(result, clean_orders)

    output_paths["dataset"] = data_path
    output_paths["mlflow_run_id"] = run.info.run_id
    output_paths["metrics_values"] = result.metrics
    return output_paths


def _save_generated_data(orders: pd.DataFrame):
    from eligibilite_livraison.config import GENERATED_DATA_DIR

    GENERATED_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data_path = GENERATED_DATA_DIR / "orders.csv"
    orders.to_csv(data_path, index=False)
    return data_path
