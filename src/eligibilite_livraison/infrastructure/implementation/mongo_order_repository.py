"""Implémentation MongoDB du contrat OrderRepository."""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date, datetime, time
from typing import Any

import pandas as pd
from pymongo import MongoClient, ReplaceOne
from pymongo.collection import Collection
from pymongo.database import Database

try:
    from eligibilite_livraison.infrastructure.contract.order_repository import OrderRepository
except ImportError:
    from infrastructure.contract.order_repository import OrderRepository  # type: ignore


class MongoOrderRepository(OrderRepository):
    """Accès aux commandes stockées dans la base MongoDB analytique."""

    def __init__(
        self,
        uri: str | None = None,
        database: str | None = None,
        collection: str | None = None,
        timeout_ms: int = 1500,
    ) -> None:
        self.uri = uri or os.getenv("MONGO_URI", "mongodb://localhost:27017")
        self.database_name = database or os.getenv("MONGO_DB", "livraison_express")
        self.collection_name = collection or os.getenv("MONGO_COLLECTION", "orders")

        self.client: MongoClient = MongoClient(self.uri, serverSelectionTimeoutMS=timeout_ms)
        self.db: Database = self.client[self.database_name]
        self.collection: Collection = self.db[self.collection_name]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """Garantit l'unicité de l'identifiant de commande."""
        try:
            self.collection.create_index("order_id", unique=True)
        except Exception:
            pass

    def is_connected(self) -> bool:
        """Vérifie si la connexion à MongoDB est active."""
        try:
            self.client.admin.command("ping", maxTimeMS=1000)
            return True
        except Exception:
            return False

    @staticmethod
    def _to_document(order: dict[str, Any]) -> dict[str, Any]:
        """Formate une commande pour l'insertion MongoDB."""
        doc = dict(order)
        order_date = doc.get("order_date")
        if isinstance(order_date, date) and not isinstance(order_date, datetime):
            doc["order_date"] = datetime.combine(order_date, time.min)
        return doc

    def get_orders(
        self,
        limit: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Récupère les commandes sous forme de DataFrame Pandas."""
        query: dict[str, Any] = {}

        if start_date or end_date:
            date_filter: dict[str, Any] = {}
            if start_date:
                dt_start = (
                    datetime.combine(start_date, time.min)
                    if isinstance(start_date, date) and not isinstance(start_date, datetime)
                    else start_date
                )
                date_filter["$gte"] = dt_start
            if end_date:
                dt_end = (
                    datetime.combine(end_date, time.min)
                    if isinstance(end_date, date) and not isinstance(end_date, datetime)
                    else end_date
                )
                date_filter["$lte"] = dt_end
            query["order_date"] = date_filter

        cursor = self.collection.find(query, {"_id": 0})
        if limit and limit > 0:
            cursor = cursor.limit(limit)

        data = list(cursor)
        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        if "order_date" in df.columns:
            df["order_date"] = pd.to_datetime(df["order_date"])
        return df

    def get_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Retourne une commande par son order_id."""
        doc = self.collection.find_one({"order_id": order_id}, {"_id": 0})
        if doc and "order_date" in doc and isinstance(doc["order_date"], datetime):
            doc["order_date"] = doc["order_date"].date().isoformat()
        return doc

    def count(self) -> int:
        """Retourne le nombre total de documents dans la collection."""
        return int(self.collection.count_documents({}))

    def save(self, order: dict[str, Any]) -> None:
        """Insère ou met à jour une commande via son order_id."""
        if "order_id" not in order:
            raise ValueError("La commande doit comporter une clé 'order_id'.")
        doc = self._to_document(order)
        self.collection.replace_one({"order_id": order["order_id"]}, doc, upsert=True)

    def save_many(self, orders: Sequence[dict[str, Any]]) -> int:
        """Insère ou met à jour un lot de commandes."""
        if not orders:
            return 0
        operations = [
            ReplaceOne({"order_id": order["order_id"]}, self._to_document(order), upsert=True)
            for order in orders
            if "order_id" in order
        ]
        if not operations:
            return 0
        result = self.collection.bulk_write(operations)
        return int(result.upserted_count + result.modified_count)

    def close(self) -> None:
        """Ferme la connexion au client MongoDB."""
        self.client.close()
