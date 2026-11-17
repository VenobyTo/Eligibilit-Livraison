"""API FastAPI pour l'éligibilité à la livraison express."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

import joblib
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

from eligibilite_livraison.config import (
    ARTIFACTS_DIR,
    DEFAULT_THRESHOLD,
    FEATURE_COLUMNS,
    MODEL_VERSION,
    PROJECT_NAME,
)
from eligibilite_livraison.predict import (
    batch_predict_orders,
    predict_order_eligibility,
)

# Variable globale contenant le modèle en mémoire
_model: Any = None


def load_model():
    """Charge le modèle sérialisé depuis le dossier d'artefacts."""
    global _model
    model_path = ARTIFACTS_DIR / "express_delivery_model.joblib"
    if model_path.exists():
        try:
            _model = joblib.load(model_path)
        except Exception:
            _model = None
    return _model


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie de l'application FastAPI."""
    if load_model() is None:
        try:
            from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
                MongoOrderRepository,
            )
            from eligibilite_livraison.training import run_training

            repo = MongoOrderRepository()
            if repo.is_connected() and repo.count() > 0:
                run_training(repository=repo)
            else:
                run_training(n_rows=1000)
            repo.close()
            load_model()
        except Exception:
            pass
    yield


app = FastAPI(
    title=f"API {PROJECT_NAME}",
    description="Microservice d'inférence et d'entraînement pour l'éligibilité à la livraison express",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


class OrderInput(BaseModel):
    """Schéma d'une commande unitaire."""

    order_id: str | None = Field(default=None, description="Identifiant unique de la commande")
    hour: int = Field(..., ge=0, le=23, description="Heure de passage de la commande (0-23)")
    day_of_week: int = Field(..., ge=0, le=6, description="Jour de la semaine (0=lundi, 6=dimanche)")
    weekend: int = Field(..., ge=0, le=1, description="Indicateur week-end (1) ou semaine (0)")
    distance_km: float = Field(..., ge=0, description="Distance de livraison en km")
    order_value_eur: float = Field(..., ge=0, description="Montant du panier en euros")
    weight_kg: float = Field(..., ge=0, description="Poids du colis en kg")
    stock_available: int = Field(..., ge=0, le=1, description="Disponibilité en stock (1 ou 0)")
    preparation_time_min: float = Field(..., ge=0, description="Temps estimé de préparation en minutes")
    carrier_capacity: float = Field(..., ge=0, description="Capacité du transporteur")
    weather: str = Field(..., description="Conditions météo (ex: clear, normal, rain, snow...)")
    delivery_zone: str = Field(..., description="Zone de livraison (centre, suburb, rural...)")
    customer_type: str = Field(..., description="Type de client (individual, business, standard, premium)")


class PredictionResponse(BaseModel):
    """Résultat de prédiction pour une commande."""

    order_id: str | None = None
    express_eligible: bool
    decision: str
    probability: float
    model_version: str
    prediction_timestamp: str


class BatchPredictionRequest(BaseModel):
    """Requête de prédiction par lot."""

    orders: list[OrderInput]
    threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)


class HealthResponse(BaseModel):
    """État de santé du microservice."""

    status: str
    project: str
    model_version: str
    model_loaded: bool
    database_connected: bool
    database_type: str


@app.get("/", tags=["Monitoring"])
def root():
    """Point d'entrée racine."""
    return {
        "message": f"Bienvenue sur l'API {PROJECT_NAME}",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health():
    """Vérifie l'état du service, du modèle et de la base de données."""
    db_connected = False
    try:
        from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
            MongoOrderRepository,
        )

        repo = MongoOrderRepository()
        db_connected = repo.is_connected()
        repo.close()
    except Exception:
        db_connected = False

    return HealthResponse(
        status="healthy" if _model is not None else "degraded",
        project=PROJECT_NAME,
        model_version=MODEL_VERSION,
        model_loaded=_model is not None,
        database_connected=db_connected,
        database_type="MongoDB",
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Inférence"])
def predict(order: OrderInput, threshold: float = DEFAULT_THRESHOLD):
    """Prédit l'éligibilité d'une commande."""
    if _model is None:
        load_model()
        if _model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le modèle n'est pas encore entraîné ou chargé.",
            )

    order_dict = order.model_dump()
    result = predict_order_eligibility(order_dict, _model, threshold=threshold)
    result["order_id"] = order.order_id
    return result


@app.post("/predict/batch", response_model=list[PredictionResponse], tags=["Inférence"])
def predict_batch(request: BatchPredictionRequest):
    """Prédit l'éligibilité pour un lot de commandes."""
    if _model is None:
        load_model()
        if _model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le modèle n'est pas encore entraîné ou chargé.",
            )

    orders_data = [o.model_dump() for o in request.orders]
    import pandas as pd

    df = pd.DataFrame(orders_data)
    result_df = batch_predict_orders(df, _model, threshold=request.threshold)

    responses: list[PredictionResponse] = []
    for _, row in result_df.iterrows():
        responses.append(
            PredictionResponse(
                order_id=row.get("order_id"),
                express_eligible=bool(row["express_eligible"]),
                decision=row["decision"],
                probability=float(row["eligibility_probability"]),
                model_version=MODEL_VERSION,
                prediction_timestamp=str(pd.Timestamp.now(tz="UTC")),
            )
        )
    return responses


@app.post("/train", tags=["Entraînement"])
def trigger_training(use_mongo: bool = True, n_rows: int = 5000):
    """Déclenche l'entraînement sur MongoDB ou sur données synthétiques."""
    from eligibilite_livraison.training import run_training

    repo = None
    if use_mongo:
        try:
            from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
                MongoOrderRepository,
            )

            repo = MongoOrderRepository()
            if not repo.is_connected() or repo.count() == 0:
                repo = None
        except Exception:
            repo = None

    outputs = run_training(n_rows=n_rows, repository=repo)
    load_model()

    return {
        "status": "success",
        "message": "Entraînement terminé avec succès.",
        "mlflow_run_id": outputs["mlflow_run_id"],
        "metrics": outputs["metrics_values"],
        "data_source": "MongoDB" if repo is not None else "Synthetic",
    }

