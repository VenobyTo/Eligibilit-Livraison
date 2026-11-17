"""Tests unitaires pour MongoOrderRepository."""

import os
import unittest
from unittest.mock import MagicMock, patch

import pandas as pd

from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
    MongoOrderRepository,
)


class MongoOrderRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.mock_client_patcher = patch(
            "eligibilite_livraison.infrastructure.implementation.mongo_order_repository.MongoClient"
        )
        self.mock_client_class = self.mock_client_patcher.start()
        self.mock_client = MagicMock()
        self.mock_db = MagicMock()
        self.mock_collection = MagicMock()

        self.mock_client.__getitem__.return_value = self.mock_db
        self.mock_db.__getitem__.return_value = self.mock_collection
        self.mock_client_class.return_value = self.mock_client

    def tearDown(self):
        self.mock_client_patcher.stop()

    def test_repository_initialization_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            repo = MongoOrderRepository(uri="mongodb://localhost:27017")
            self.assertEqual(repo.database_name, "livraison_express")
            self.assertEqual(repo.collection_name, "orders")

    def test_repository_initialization_from_env(self):
        with patch.dict(
            os.environ,
            {"MONGO_DB": "livraison_express_test", "MONGO_COLLECTION": "orders_test"},
        ):
            repo = MongoOrderRepository(uri="mongodb://localhost:27017")
            self.assertEqual(repo.database_name, "livraison_express_test")
            self.assertEqual(repo.collection_name, "orders_test")

    def test_count_calls_collection_count(self):
        self.mock_collection.count_documents.return_value = 42
        repo = MongoOrderRepository()
        self.assertEqual(repo.count(), 42)
        self.mock_collection.count_documents.assert_called_once_with({})

    def test_get_by_id(self):
        self.mock_collection.find_one.return_value = {
            "order_id": "ERP-00000001",
            "distance_km": 12.5,
        }
        repo = MongoOrderRepository()
        order = repo.get_by_id("ERP-00000001")
        self.assertIsNotNone(order)
        self.assertEqual(order["order_id"], "ERP-00000001")
        self.mock_collection.find_one.assert_called_once_with(
            {"order_id": "ERP-00000001"}, {"_id": 0}
        )

    def test_get_orders_returns_dataframe(self):
        self.mock_collection.find.return_value = [
            {"order_id": "ERP-1", "distance_km": 10.0, "order_value_eur": 50.0},
            {"order_id": "ERP-2", "distance_km": 20.0, "order_value_eur": 75.0},
        ]
        repo = MongoOrderRepository()
        df = repo.get_orders()
        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 2)
        self.assertIn("order_id", df.columns)


if __name__ == "__main__":
    unittest.main()
