"""API FastAPI pour l'éligibilité à la livraison express.

Fonctionnalités :
- Chargement de l'artefact ML pré-entraîné au démarrage (sans ré-entraînement au boot)
- Inférence unitaire (/predict) et par lot (/predict/batch)
- Monitoring complet API + Machine Learning (/health et /metrics)
- Flux temps-réel (Server-Sent Events) et interface logisticien (/logisticien, /stream/orders, /stream/order)
- Ré-entraînement à la demande (/train)
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from eligibilite_livraison.config import (
    ARTIFACTS_DIR,
    DEFAULT_THRESHOLD,
    MODEL_VERSION,
    PROJECT_NAME,
)
from eligibilite_livraison.predict import (
    batch_predict_orders,
    predict_order_eligibility,
)

logger = logging.getLogger("eligibilite_livraison.api")

# État en mémoire du modèle et du monitoring
_model: Any = None
_start_time: float = time.time()
_monitoring_state: dict[str, Any] = {
    "total_predictions": 0,
    "eligible_predictions": 0,
    "not_eligible_predictions": 0,
    "probability_sum": 0.0,
    "latency_ms_sum": 0.0,
    "error_count": 0,
}

# Files d'abonnés pour le streaming temps-réel (SSE) vers l'interface logisticien
_stream_subscribers: list[asyncio.Queue[dict[str, Any]]] = []
_recent_stream_events: list[dict[str, Any]] = []


def load_model() -> Any:
    """Charge le modèle sérialisé depuis le dossier d'artefacts sans ré-entraîner."""
    global _model
    model_path = ARTIFACTS_DIR / "express_delivery_model.joblib"
    if model_path.exists():
        try:
            _model = joblib.load(model_path)
            logger.info("Modèle chargé depuis %s", model_path)
        except Exception as exc:
            logger.error("Impossible de charger le modèle (%s) : %s", model_path, exc)
            _model = None
    else:
        logger.warning(
            "Aucun artefact modèle trouvé à %s. Lancez l'orchestrateur ou POST /train.",
            model_path,
        )
        _model = None
    return _model


def _load_training_metrics() -> dict[str, float]:
    """Lit les dernières métriques d'évaluation ML depuis artifacts/metrics.json."""
    metrics_path = ARTIFACTS_DIR / "metrics.json"
    if metrics_path.exists():
        try:
            return json.loads(metrics_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _record_prediction(result: dict[str, Any], latency_ms: float) -> None:
    """Met à jour les compteurs de monitoring temps-réel (API + dérive ML)."""
    _monitoring_state["total_predictions"] += 1
    if result.get("express_eligible"):
        _monitoring_state["eligible_predictions"] += 1
    else:
        _monitoring_state["not_eligible_predictions"] += 1
    _monitoring_state["probability_sum"] += float(result.get("probability", 0.0))
    _monitoring_state["latency_ms_sum"] += latency_ms


async def _publish_stream_event(event: dict[str, Any]) -> None:
    """Diffuse une notification de commande temps-réel à tous les logisticiens connectés."""
    _recent_stream_events.append(event)
    if len(_recent_stream_events) > 50:
        _recent_stream_events.pop(0)
    for queue in list(_stream_subscribers):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Cycle de vie FastAPI : charge uniquement l'artefact ML existant (aucun ré-entraînement au démarrage)."""
    global _start_time
    _start_time = time.time()
    load_model()
    yield


app = FastAPI(
    title=f"API {PROJECT_NAME}",
    description="Microservice MLOps d'inférence, monitoring et streaming temps-réel pour l'éligibilité à la livraison express",
    version=MODEL_VERSION,
    lifespan=lifespan,
)


class OrderInput(BaseModel):
    """Schéma validé d'une commande unitaire (sans données personnelles nominatives - RGPD)."""

    order_id: str | None = Field(default=None, description="Identifiant pseudonymisé de la commande")
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
    """État de santé global du microservice (API + ML + Base de données)."""

    status: str
    project: str
    model_version: str
    model_loaded: bool
    database_connected: bool
    database_type: str
    uptime_seconds: float


class MetricsResponse(BaseModel):
    """Indicateurs de monitoring de l'API et de la performance du modèle ML."""

    uptime_seconds: float
    model_version: str
    model_loaded: bool
    api_metrics: dict[str, Any]
    ml_training_metrics: dict[str, float]
    ml_live_monitoring: dict[str, Any]


@app.get("/", tags=["Monitoring"])
def root():
    """Point d'entrée racine."""
    return {
        "message": f"Bienvenue sur l'API {PROJECT_NAME}",
        "docs": "/docs",
        "health": "/health",
        "metrics": "/metrics",
        "logisticien_realtime_ui": "/logisticien",
    }


@app.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health():
    """Vérifie l'état de santé du service, du modèle chargé et de la base de données."""
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
        uptime_seconds=round(time.time() - _start_time, 2),
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["Monitoring"])
def metrics():
    """Expose les métriques de performance système (API) et Machine Learning (entraînement + dérive temps-réel)."""
    total = _monitoring_state["total_predictions"]
    avg_latency = round(_monitoring_state["latency_ms_sum"] / total, 3) if total > 0 else 0.0
    avg_proba = round(_monitoring_state["probability_sum"] / total, 4) if total > 0 else 0.0
    express_rate = round(_monitoring_state["eligible_predictions"] / total, 4) if total > 0 else 0.0

    return MetricsResponse(
        uptime_seconds=round(time.time() - _start_time, 2),
        model_version=MODEL_VERSION,
        model_loaded=_model is not None,
        api_metrics={
            "total_predictions": total,
            "error_count": _monitoring_state["error_count"],
            "avg_latency_ms": avg_latency,
            "active_stream_subscribers": len(_stream_subscribers),
        },
        ml_training_metrics=_load_training_metrics(),
        ml_live_monitoring={
            "eligible_predictions": _monitoring_state["eligible_predictions"],
            "not_eligible_predictions": _monitoring_state["not_eligible_predictions"],
            "express_rate": express_rate,
            "avg_predicted_probability": avg_proba,
        },
    )


@app.post("/predict", response_model=PredictionResponse, tags=["Inférence"])
def predict(order: OrderInput, threshold: float = DEFAULT_THRESHOLD):
    """Prédit l'éligibilité d'une commande unitaire."""
    start = time.perf_counter()
    if _model is None:
        load_model()
        if _model is None:
            _monitoring_state["error_count"] += 1
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le modèle n'est pas encore entraîné ou chargé.",
            )

    order_dict = order.model_dump()
    result = predict_order_eligibility(order_dict, _model, threshold=threshold)
    result["order_id"] = order.order_id
    latency_ms = (time.perf_counter() - start) * 1000.0
    _record_prediction(result, latency_ms)
    return result


@app.post("/predict/batch", response_model=list[PredictionResponse], tags=["Inférence"])
def predict_batch(request: BatchPredictionRequest):
    """Prédit l'éligibilité pour un lot de commandes."""
    start = time.perf_counter()
    if _model is None:
        load_model()
        if _model is None:
            _monitoring_state["error_count"] += 1
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Le modèle n'est pas encore entraîné ou chargé.",
            )

    orders_data = [o.model_dump() for o in request.orders]
    df = pd.DataFrame(orders_data)
    result_df = batch_predict_orders(df, _model, threshold=request.threshold)
    per_item_latency = ((time.perf_counter() - start) * 1000.0) / max(len(result_df), 1)

    responses: list[PredictionResponse] = []
    for _, row in result_df.iterrows():
        item = {
            "order_id": row.get("order_id"),
            "express_eligible": bool(row["express_eligible"]),
            "decision": row["decision"],
            "probability": float(row["eligibility_probability"]),
            "model_version": MODEL_VERSION,
            "prediction_timestamp": str(pd.Timestamp.now(tz="UTC")),
        }
        _record_prediction(item, per_item_latency)
        responses.append(PredictionResponse(**item))
    return responses


@app.post("/stream/order", response_model=PredictionResponse, tags=["Temps-Réel (Streaming)"])
async def ingest_realtime_order(order: OrderInput, threshold: float = DEFAULT_THRESHOLD):
    """Reçoit une commande en temps réel, calcule son éligibilité et notifie les logisticiens connectés (SSE)."""
    result = predict(order, threshold=threshold)
    event = {
        **result,
        "delivery_zone": order.delivery_zone,
        "distance_km": order.distance_km,
        "weather": order.weather,
        "notification": (
            f"EXPRESS : Commande {order.order_id or 'N/A'} éligible ({result['probability']*100:.1f}%)"
            if result["express_eligible"]
            else f"STANDARD : Commande {order.order_id or 'N/A'} non éligible ({result['probability']*100:.1f}%)"
        ),
    }
    await _publish_stream_event(event)
    return result


@app.get("/stream/orders", tags=["Temps-Réel (Streaming)"])
async def stream_orders():
    """Flux Server-Sent Events (SSE) envoyant en temps réel les notifications d'éligibilité aux logisticiens."""
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)
    _stream_subscribers.append(queue)

    async def event_generator():
        try:
            for past in _recent_stream_events[-10:]:
                yield f"data: {json.dumps(past, ensure_ascii=False)}\n\n"
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if queue in _stream_subscribers:
                _stream_subscribers.remove(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/logisticien", response_class=HTMLResponse, tags=["Temps-Réel (Streaming)"])
def logisticien_dashboard():
    """Interface web temps-réel (streaming SSE) à destination du logisticien."""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8" />
  <title>Tableau Logisticien – Livraison Express Temps-Réel</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 24px; }
    h1 { margin-top: 0; color: #38bdf8; }
    .bar { display: flex; gap: 12px; margin-bottom: 18px; align-items: center; }
    button { background: #0ea5e9; color: white; border: none; padding: 10px 16px; border-radius: 8px; cursor: pointer; font-weight: 600; }
    button:hover { background: #0284c7; }
    .status { font-size: 0.9rem; color: #4ade80; }
    .card { background: #1e293b; border-left: 5px solid #64748b; padding: 14px 16px; border-radius: 8px; margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; }
    .express { border-left-color: #22c55e; }
    .standard { border-left-color: #ef4444; }
    .badge { padding: 4px 10px; border-radius: 999px; font-weight: 700; font-size: 0.85rem; }
    .badge-ok { background: #14532d; color: #86efac; }
    .badge-no { background: #7f1d1d; color: #fca5a5; }
  </style>
</head>
<body>
  <h1>📦 Notifications Logisticien – Flux Temps-Réel</h1>
  <div class="bar">
    <button onclick="simulateOrder()">Simuler l'arrivée d'une commande</button>
    <span class="status" id="status">● Connecté au flux SSE (/stream/orders)</span>
  </div>
  <div id="feed"></div>
  <script>
    const feed = document.getElementById("feed");
    const evtSource = new EventSource("/stream/orders");
    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data);
      const card = document.createElement("div");
      card.className = "card " + (data.express_eligible ? "express" : "standard");
      card.innerHTML = `
        <div>
          <strong>${data.order_id || "CMD-LIVE"}</strong> — Zone: ${data.delivery_zone} (${data.distance_km} km, météo: ${data.weather})<br/>
          <small>${data.notification} • ${data.prediction_timestamp}</small>
        </div>
        <span class="badge ${data.express_eligible ? "badge-ok" : "badge-no"}">
          ${data.express_eligible ? "EXPRESS ✔" : "STANDARD ✖"} (${(data.probability * 100).toFixed(1)}%)
        </span>`;
      feed.prepend(card);
    };
    async function simulateOrder() {
      const id = "LIVE-" + Math.floor(1000 + Math.random() * 9000);
      const isClose = Math.random() > 0.4;
      await fetch("/stream/order", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          order_id: id,
          hour: 11,
          day_of_week: 2,
          weekend: 0,
          distance_km: isClose ? 4.2 : 28.5,
          order_value_eur: 79.9,
          weight_kg: isClose ? 2.1 : 18.0,
          stock_available: isClose ? 1 : 0,
          preparation_time_min: isClose ? 12 : 45,
          carrier_capacity: isClose ? 0.9 : 0.25,
          weather: isClose ? "clear" : "snow",
          delivery_zone: isClose ? "centre" : "rural",
          customer_type: isClose ? "business" : "individual"
        })
      });
    }
  </script>
</body>
</html>"""


@app.post("/train", tags=["Entraînement"])
def trigger_training(use_mongo: bool = True, n_rows: int = 5000):
    """Déclenche l'entraînement à la demande sur MongoDB ou sur données synthétiques, puis recharge le modèle."""
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
