"""Contrat de repository pour les commandes."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any, Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class OrderRepository(Protocol):
    """Interface définissant le contrat d'accès aux commandes."""

    def get_orders(
        self,
        limit: int | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Récupère un DataFrame de commandes selon les filtres fournis."""
        ...

    def get_by_id(self, order_id: str) -> dict[str, Any] | None:
        """Récupère une commande par son identifiant unique."""
        ...

    def count(self) -> int:
        """Retourne le nombre total de commandes stockées."""
        ...

    def save(self, order: dict[str, Any]) -> None:
        """Sauvegarde ou met à jour une commande."""
        ...

    def save_many(self, orders: Sequence[dict[str, Any]]) -> int:
        """Sauvegarde ou met à jour un lot de commandes et renvoie le nombre traité."""
        ...

    def close(self) -> None:
        """Libère les ressources de connexion."""
        ...

