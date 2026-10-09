from pathlib import Path

PROJECT_NAME = "eligibilite-livraison-express"
MODEL_VERSION = "1.0.0"
RANDOM_STATE = 42
DEFAULT_THRESHOLD = 0.5

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
GENERATED_DATA_DIR = PROJECT_ROOT / "data" / "generated"
REPORTS_DIR = PROJECT_ROOT / "reports"
MLFLOW_DB_PATH = PROJECT_ROOT / "mlflow.db"

TARGET_COLUMN = "express_eligible"

FEATURE_COLUMNS = [
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
    "weather",
    "delivery_zone",
    "customer_type",
]

NUMERIC_FEATURES = [
    "hour",
    "day_of_week",
    "weekend",
    "distance_km",
    "order_value_eur",
    "weight_kg",
    "stock_available",
    "preparation_time_min",
    "carrier_capacity",
]

CATEGORICAL_FEATURES = [
    "weather",
    "delivery_zone",
    "customer_type",
]
