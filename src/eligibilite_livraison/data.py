import numpy as np
import pandas as pd


REQUIRED_COLUMNS = {
    "order_id",
    "order_date",
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
    "express_eligible",
}


def compute_express_eligible(
    df: pd.DataFrame,
    random_state: int = 42,
) -> pd.DataFrame:
    """Calcule la variable cible express_eligible selon les règles métier."""
    data = df.copy()
    rng = np.random.default_rng(random_state)

    zone_penalty = data["delivery_zone"].map(
        {
            "centre": 0.0,
            "proche_banlieue": 0.10,
            "banlieue": 0.25,
            "suburb": 0.25,
            "rurale": 0.45,
            "rural": 0.45,
        }
    ).fillna(0.20)

    weather_penalty = data["weather"].map(
        {
            "normal": 0.0,
            "clear": 0.0,
            "pluie": 0.10,
            "rain": 0.10,
            "neige": 0.25,
            "snow": 0.25,
            "orage": 0.30,
            "wind": 0.20,
        }
    ).fillna(0.10)

    customer_bonus = data["customer_type"].isin(["premium", "business"]).astype(int) * 0.15

    # Normalisation de la capacité si échelle ERP (5 à 50)
    carrier_cap = data["carrier_capacity"].astype(float)
    carrier_normalized = np.where(carrier_cap > 1.0, (carrier_cap / 50.0).clip(0.0, 1.0), carrier_cap)

    score = (
        2.5
        - 0.18 * data["distance_km"].astype(float)
        - 0.035 * data["preparation_time_min"].fillna(25.0).astype(float)
        - 0.035 * data["weight_kg"].astype(float)
        - zone_penalty
        - weather_penalty
        + 1.8 * data["stock_available"].astype(int)
        + 1.3 * carrier_normalized
        + customer_bonus
        - 0.40 * data["weekend"].fillna(0).astype(int)
        - 0.08 * np.maximum(data["hour"].astype(int) - 18, 0)
    )
    probability = 1 / (1 + np.exp(-score))
    data["express_eligible"] = rng.binomial(1, probability)
    return data


def generate_orders_dataset(
    n_rows: int = 6000,
    random_state: int = 42,
) -> pd.DataFrame:
    """Génère des commandes synthétiques pour l'entraînement et les tests."""
    if n_rows <= 0:
        raise ValueError("n_rows doit être strictement positif.")

    rng = np.random.default_rng(random_state)
    order_date = pd.date_range(
        start="2025-01-01",
        end="2025-12-31",
        periods=n_rows,
    )
    day_of_week = pd.Series(order_date).dt.day_of_week.to_numpy()

    data = pd.DataFrame(
        {
            "order_id": [f"CMD-{i:06d}" for i in range(1, n_rows + 1)],
            "order_date": order_date,
            "hour": rng.integers(7, 23, size=n_rows),
            "day_of_week": day_of_week,
            "weekend": (day_of_week >= 5).astype(int),
            "distance_km": np.round(
                rng.gamma(shape=2.0, scale=4.0, size=n_rows), 2
            ),
            "order_value_eur": np.round(rng.uniform(10, 250, size=n_rows), 2),
            "weight_kg": np.round(rng.uniform(0.2, 25, size=n_rows), 2),
            "stock_available": rng.binomial(1, 0.85, size=n_rows),
            "preparation_time_min": np.round(
                rng.normal(loc=25, scale=10, size=n_rows).clip(5, 90), 1
            ),
            "carrier_capacity": np.round(
                rng.uniform(0.2, 1.0, size=n_rows), 2
            ),
            "weather": rng.choice(
                ["normal", "pluie", "neige", "orage"],
                size=n_rows,
                p=[0.65, 0.20, 0.10, 0.05],
            ),
            "delivery_zone": rng.choice(
                ["centre", "proche_banlieue", "banlieue", "rurale"],
                size=n_rows,
                p=[0.30, 0.30, 0.25, 0.15],
            ),
            "customer_type": rng.choice(
                ["standard", "premium"],
                size=n_rows,
                p=[0.80, 0.20],
            ),
        }
    )

    return compute_express_eligible(data, random_state=random_state)


def validate_dataset(df: pd.DataFrame) -> bool:
    """Vérifie les colonnes et contraintes élémentaires du jeu de données."""
    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        raise ValueError(
            f"Colonnes obligatoires absentes : {sorted(missing_columns)}"
        )

    if df["order_id"].duplicated().any():
        raise ValueError("Des identifiants de commande sont dupliqués.")
    if df["express_eligible"].isna().any():
        raise ValueError("La variable cible contient des valeurs manquantes.")
    if not df["hour"].between(0, 23).all():
        raise ValueError("Certaines heures sont invalides.")
    if not df["distance_km"].ge(0).all():
        raise ValueError("La distance ne peut pas être négative.")
    if not df["weight_kg"].ge(0).all():
        raise ValueError("Le poids ne peut pas être négatif.")
    if not df["preparation_time_min"].ge(0).all():
        raise ValueError("Le temps de préparation ne peut pas être négatif.")
    if not (df["carrier_capacity"].between(0, 1).all() or df["carrier_capacity"].ge(0).all()):
        raise ValueError(
            "La capacité du transporteur doit être positive."
        )
    if not df["stock_available"].isin([0, 1]).all():
        raise ValueError(
            "La variable stock_available doit contenir uniquement 0 ou 1."
        )
    return True


def clean_orders_data(df: pd.DataFrame) -> pd.DataFrame:
    """Supprime doublons et lignes invalides, puis normalise les colonnes."""
    cleaned = df.copy()
    cleaned = cleaned.drop_duplicates(subset=["order_id"], keep="last")
    cleaned["order_date"] = pd.to_datetime(
        cleaned["order_date"],
        errors="coerce",
    )

    # Calcul de express_eligible si absent
    if "express_eligible" not in cleaned.columns:
        cleaned = compute_express_eligible(cleaned)

    # Imputation des colonnes historiques éventuellement nulles
    if "weekend" in cleaned.columns and cleaned["weekend"].isna().any():
        cleaned["weekend"] = (cleaned["order_date"].dt.day_of_week >= 5).astype(int)
    if "preparation_time_min" in cleaned.columns and cleaned["preparation_time_min"].isna().any():
        cleaned["preparation_time_min"] = cleaned["preparation_time_min"].fillna(25.0)

    essential_columns = [
        "order_id",
        "distance_km",
        "weight_kg",
        "stock_available",
        "preparation_time_min",
        "carrier_capacity",
        "express_eligible",
    ]
    cleaned = cleaned.dropna(subset=essential_columns)
    cleaned = cleaned[cleaned["distance_km"] >= 0]
    cleaned = cleaned[cleaned["weight_kg"] >= 0]
    cleaned = cleaned[cleaned["preparation_time_min"] >= 0]
    cleaned = cleaned[cleaned["carrier_capacity"] >= 0]
    cleaned = cleaned[cleaned["stock_available"].isin([0, 1])]

    # Normalisation de carrier_capacity si > 1 (échelle ERP 5-50)
    cleaned["carrier_capacity"] = np.where(
        cleaned["carrier_capacity"] > 1.0,
        (cleaned["carrier_capacity"] / 50.0).clip(0.0, 1.0),
        cleaned["carrier_capacity"],
    )
    cleaned["carrier_capacity"] = np.round(cleaned["carrier_capacity"], 2)

    return cleaned.reset_index(drop=True)


def load_orders_from_repository(
    repository,
    limit: int | None = None,
) -> pd.DataFrame:
    """Charge les commandes depuis un OrderRepository (MongoDB ou PostgreSQL)."""
    df = repository.get_orders(limit=limit)
    if df.empty:
        raise ValueError("Aucune commande récupérée depuis le repository.")
    cleaned = clean_orders_data(df)
    validate_dataset(cleaned)
    return cleaned
