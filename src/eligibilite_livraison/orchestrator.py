"""Orchestrateur MLOps pour le pipeline d'entraînement du modèle d'éligibilité.

Ce module implémente un workflow orchestré (compatible Prefect 2/3 s'il est installé,
avec repli natif léger sans dépendance lourde pour conserver une image Docker minimale).
Il découpe le cycle de vie d'entraînement en tâches atomiques observables avec :
- Tentatives automatiques (retries) sur l'extraction des données de production (MongoDB)
- Validation et nettoyage des données (Data Quality Gate)
- Entraînement et vérification des seuils de performance (Model Quality Gate)
- Publication des artefacts et journalisation MLflow
- Planification périodique intégrée (mode démon / cron)
"""

from __future__ import annotations

import argparse
import functools
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

import pandas as pd

from eligibilite_livraison.config import RANDOM_STATE
from eligibilite_livraison.data import (
    clean_orders_data,
    generate_orders_dataset,
    validate_dataset,
)
from eligibilite_livraison.training import (
    TrainingResult,
    _save_generated_data,
    fit_and_evaluate,
    save_training_outputs,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | [Orchestrator] %(message)s",
)
logger = logging.getLogger("eligibilite_livraison.orchestrator")

# Compatibilité Prefect native si disponible, sinon décorateurs légers
try:
    from prefect import flow as prefect_flow  # type: ignore
    from prefect import task as prefect_task  # type: ignore

    ORCHESTRATOR_BACKEND = "prefect"
except ImportError:
    ORCHESTRATOR_BACKEND = "native-mlops-scheduler"

    def prefect_task(
        name: str | None = None,
        retries: int = 0,
        retry_delay_seconds: int = 1,
    ) -> Callable[..., Any]:
        """Décorateur de tâche avec gestion de retries et journalisation."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            task_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                attempts = retries + 1
                for attempt in range(1, attempts + 1):
                    try:
                        logger.info("▶ Début tâche [%s] (tentative %d/%d)", task_name, attempt, attempts)
                        start_ts = time.perf_counter()
                        result = func(*args, **kwargs)
                        elapsed = time.perf_counter() - start_ts
                        logger.info("✔ Fin tâche [%s] en %.2fs", task_name, elapsed)
                        return result
                    except Exception as exc:
                        logger.warning(
                            "✖ Échec tâche [%s] (tentative %d/%d) : %s",
                            task_name,
                            attempt,
                            attempts,
                            exc,
                        )
                        if attempt >= attempts:
                            raise
                        time.sleep(retry_delay_seconds)

            return wrapper

        return decorator

    def prefect_flow(name: str | None = None) -> Callable[..., Any]:
        """Décorateur de flux principal (DAG)."""

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            flow_name = name or func.__name__

            @functools.wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                logger.info("====================================================")
                logger.info("🚀 Démarrage du Flow MLOps : %s (backend=%s)", flow_name, ORCHESTRATOR_BACKEND)
                start_ts = time.perf_counter()
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_ts
                logger.info("🏁 Flow [%s] terminé avec succès en %.2fs", flow_name, elapsed)
                logger.info("====================================================")
                return result

            return wrapper

        return decorator


@dataclass
class OrchestrationReport:
    """Rapport complet d'une exécution du pipeline orchestré."""

    flow_run_timestamp: str
    orchestrator_backend: str
    data_source: str
    rows_extracted: int
    rows_cleaned: int
    metrics: dict[str, float]
    quality_gate_passed: bool
    mlflow_run_id: str
    artifact_paths: dict[str, Any]


@prefect_task(name="1-extract-production-orders", retries=2, retry_delay_seconds=1)
def extract_orders_task(
    repository: Any | None = None,
    use_mongo: bool = True,
    n_rows_fallback: int = 6000,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, str]:
    """Tâche 1 : Extraction des commandes depuis la base de production (MongoDB) ou repli synthétique."""
    if repository is not None:
        df = repository.get_orders()
        if not df.empty:
            return df, "Repository (Injected)"

    if use_mongo:
        try:
            from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
                MongoOrderRepository,
            )

            repo = MongoOrderRepository()
            if repo.is_connected() and repo.count() > 0:
                df = repo.get_orders()
                repo.close()
                if not df.empty:
                    return df, "MongoDB (Production)"
            repo.close()
        except Exception as exc:
            logger.warning("MongoDB indisponible (%s), bascule sur générateur synthétique.", exc)

    df = generate_orders_dataset(n_rows=n_rows_fallback, random_state=random_state)
    return df, "Synthetic (Fallback)"


@prefect_task(name="2-validate-and-clean-data")
def validate_and_clean_task(raw_orders: pd.DataFrame) -> pd.DataFrame:
    """Tâche 2 : Nettoyage, imputation, normalisation ERP et validation Data Quality."""
    if raw_orders.empty:
        raise ValueError("Le jeu de données extrait est vide.")

    cleaned = clean_orders_data(raw_orders)
    validate_dataset(cleaned)
    return cleaned


@prefect_task(name="3-train-and-evaluate-model")
def train_and_evaluate_task(
    clean_orders: pd.DataFrame,
    random_state: int = RANDOM_STATE,
    min_accuracy: float = 0.65,
    min_roc_auc: float = 0.70,
) -> tuple[TrainingResult, bool]:
    """Tâche 3 : Entraînement du pipeline scikit-learn et contrôle du Model Quality Gate."""
    result = fit_and_evaluate(clean_orders, random_state=random_state)
    acc = result.metrics.get("accuracy", 0.0)
    auc = result.metrics.get("roc_auc", 0.0)
    quality_gate_passed = bool(acc >= min_accuracy and auc >= min_roc_auc)

    logger.info(
        "Métriques obtenues : accuracy=%.4f (seuil=%.2f), roc_auc=%.4f (seuil=%.2f) -> Quality Gate=%s",
        acc,
        min_accuracy,
        auc,
        min_roc_auc,
        "PASS" if quality_gate_passed else "FAIL",
    )
    return result, quality_gate_passed


@prefect_task(name="4-log-mlflow-and-publish-artifacts")
def publish_artifacts_task(
    result: TrainingResult,
    clean_orders: pd.DataFrame,
    data_source: str,
    quality_gate_passed: bool,
    random_state: int = RANDOM_STATE,
) -> tuple[str, dict[str, Any]]:
    """Tâche 4 : Enregistrement dans MLflow et publication des artefacts du modèle."""
    import mlflow
    import mlflow.sklearn

    from eligibilite_livraison.config import FEATURE_COLUMNS, MLFLOW_DB_PATH

    data_path = _save_generated_data(clean_orders)

    mlflow.set_tracking_uri(f"sqlite:///{MLFLOW_DB_PATH.as_posix()}")
    mlflow.set_experiment("livraison-express")

    with mlflow.start_run(run_name="orchestrated-logistic-regression") as run:
        mlflow.log_param("orchestrator", ORCHESTRATOR_BACKEND)
        mlflow.log_param("data_source", data_source)
        mlflow.log_param("model_type", "LogisticRegression")
        mlflow.log_param("random_state", random_state)
        mlflow.log_param("feature_count", len(FEATURE_COLUMNS))
        mlflow.log_param("training_rows", len(result.X_train))
        mlflow.log_param("quality_gate_passed", quality_gate_passed)
        mlflow.log_metrics(result.metrics)

        try:
            mlflow.sklearn.log_model(
                result.model,
                artifact_path="model",
                skops_trusted_types=[
                    "numpy.dtype",
                    "sklearn.compose._column_transformer._RemainderColsList",
                ],
            )
        except Exception:
            pass

        if quality_gate_passed:
            output_paths = save_training_outputs(result, clean_orders)
        else:
            logger.warning("Quality Gate non atteint : le modèle en production n'est pas écrasé.")
            output_paths = {}

    output_paths["dataset"] = data_path
    return run.info.run_id, output_paths


@prefect_flow(name="express-delivery-training-pipeline")
def run_training_flow(
    repository: Any | None = None,
    use_mongo: bool = True,
    n_rows_fallback: int = 6000,
    random_state: int = RANDOM_STATE,
    min_accuracy: float = 0.65,
    min_roc_auc: float = 0.70,
) -> OrchestrationReport:
    """Flux principal orchestrant de bout en bout l'entraînement du modèle ML."""
    raw_orders, data_source = extract_orders_task(
        repository=repository,
        use_mongo=use_mongo,
        n_rows_fallback=n_rows_fallback,
        random_state=random_state,
    )
    rows_extracted = len(raw_orders)

    clean_orders = validate_and_clean_task(raw_orders)
    rows_cleaned = len(clean_orders)

    training_result, quality_gate_passed = train_and_evaluate_task(
        clean_orders=clean_orders,
        random_state=random_state,
        min_accuracy=min_accuracy,
        min_roc_auc=min_roc_auc,
    )

    mlflow_run_id, artifact_paths = publish_artifacts_task(
        result=training_result,
        clean_orders=clean_orders,
        data_source=data_source,
        quality_gate_passed=quality_gate_passed,
        random_state=random_state,
    )

    return OrchestrationReport(
        flow_run_timestamp=datetime.now(timezone.utc).isoformat(),
        orchestrator_backend=ORCHESTRATOR_BACKEND,
        data_source=data_source,
        rows_extracted=rows_extracted,
        rows_cleaned=rows_cleaned,
        metrics=training_result.metrics,
        quality_gate_passed=quality_gate_passed,
        mlflow_run_id=mlflow_run_id,
        artifact_paths=artifact_paths,
    )


def main() -> None:
    """Point d'entrée CLI de l'orchestrateur (exécution unique ou planifiée)."""
    parser = argparse.ArgumentParser(
        description="Orchestrateur d'entraînement ML – Éligibilité Livraison Express"
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Active l'exécution périodique en continu (mode démon).",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=int(os.getenv("ORCHESTRATOR_INTERVAL_SECONDS", "86400")),
        help="Intervalle en secondes entre deux entraînements planifiés (défaut: 86400s = 24h).",
    )
    parser.add_argument(
        "--no-mongo",
        action="store_true",
        help="Force l'utilisation des données synthétiques sans interroger MongoDB.",
    )
    parser.add_argument(
        "--n-rows",
        type=int,
        default=6000,
        help="Nombre de lignes synthétiques en cas de repli (défaut: 6000).",
    )
    args = parser.parse_args()

    use_mongo = not args.no_mongo

    if not args.schedule:
        report = run_training_flow(use_mongo=use_mongo, n_rows_fallback=args.n_rows)
        print(f"Flow exécuté avec succès ({report.orchestrator_backend})")
        print(f"  Source de données : {report.data_source} ({report.rows_cleaned} commandes)")
        print(f"  Run MLflow        : {report.mlflow_run_id}")
        print(f"  Quality Gate      : {'PASS' if report.quality_gate_passed else 'FAIL'}")
        print(f"  Accuracy / ROC-AUC: {report.metrics['accuracy']:.4f} / {report.metrics['roc_auc']:.4f}")
        return

    logger.info(
        "Planificateur activé : exécution du pipeline toutes les %d secondes.",
        args.interval_seconds,
    )
    while True:
        try:
            run_training_flow(use_mongo=use_mongo, n_rows_fallback=args.n_rows)
        except Exception as exc:
            logger.error("Erreur lors du run planifié : %s", exc)
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    main()
