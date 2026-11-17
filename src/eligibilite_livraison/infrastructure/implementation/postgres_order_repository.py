"""Implémentation PostgreSQL du contrat OrderRepository."""

from __future__ import annotations

import os
from collections.abc import Sequence
from datetime import date
from typing import Any

import pandas as pd

try:
    from eligibilite_livraison.infrastructure.contract.order_repository import OrderRepository
except ImportError:
    from infrastructure.contract.order_repository import OrderRepository  # type: ignore


class PostgresOrderRepository(OrderRepository):
    """Accès aux commandes stockées dans la base PostgreSQL de production."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.getenv(
            "POSTGRES_DSN",
            "postgresql://livraison:livraison@localhost:5432/livraison_express",
        )
        try:
            import psycopg
            from psycopg.rows import dict_row

            self._psycopg = psycopg
            self.connection = psycopg.connect(self.dsn, row_factory=dict_row)
        except ImportError:
            raise ImportError(
                "Le paquet 'psycopg' est nécessaire pour PostgresOrderRepository. "
                "Installez-le avec : pip install psycopg[binary]"
            )

    def is_connected(self) -> bool:
        """Vérifie si la connexion PostgreSQL est active."""
        try:
            with self.connection.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def get_orders(
        self,
        limit: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Récupère les commandes sous forme de DataFrame Pandas."""
        query = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []

        if start_date:
            query += " AND order_date >= %s"
            params.append(start_date)
        if end_date:
            query += " AND order_date <= %s"
            params.append(end_date)
        if limit and limit > 0:
            query += " LIMIT %s"
            params.append(limit)

        with self.connection.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        if "order_date" in df.columns:
            df["order_date"] = pd.to_datetime(df["order_date"])
        return df

    def get_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Retourne une commande par son identifiant unique."""
        with self.connection.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            row = cur.fetchone()
            if row and "order_date" in row and isinstance(row["order_date"], date):
                row["order_date"] = row["order_date"].isoformat()
            return row

    def count(self) -> int:
        """Retourne le nombre total de commandes."""
        with self.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS total FROM orders")
            row = cur.fetchone()
            return int(row["total"]) if row else 0

    def save(self, order: dict[str, Any]) -> None:
        """Sauvegarde une commande (insert ou ignore on conflict)."""
        columns = list(order.keys())
        placeholders = [f"%({col})s" for col in columns]
        sql = (
            f"INSERT INTO orders ({', '.join(columns)}) "
            f"VALUES ({', '.join(placeholders)}) "
            f"ON CONFLICT (order_id) DO NOTHING"
        )
        with self.connection.cursor() as cur:
            cur.execute(sql, order)
        self.connection.commit()

    def save_many(self, orders: Sequence[dict[str, Any]]) -> int:
        """Sauvegarde un lot de commandes."""
        if not orders:
            return 0
        inserted = 0
        with self.connection.transaction():
            with self.connection.cursor() as cur:
                for order in orders:
                    cols = list(order.keys())
                    placeholders = [f"%({col})s" for col in cols]
                    sql = (
                        f"INSERT INTO orders ({', '.join(cols)}) "
                        f"VALUES ({', '.join(placeholders)}) "
                        f"ON CONFLICT (order_id) DO NOTHING"
                    )
                    cur.execute(sql, order)
                    inserted += cur.rowcount
        self.connection.commit()
        return inserted

    def close(self) -> None:
        """Ferme la connexion PostgreSQL."""
        if hasattr(self, "connection") and self.connection:
            self.connection.close()

