"""Test complet du pipeline (ingestion ERP via MongoOrderRepository, entraînement, prédiction et API)."""

import unittest
from datetime import date
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

import pandas as pd

from eligibilite_livraison.api import app, load_model
from eligibilite_livraison.data import load_orders_from_repository
from eligibilite_livraison.infrastructure.implementation.mongo_order_repository import (
    MongoOrderRepository,
)
from eligibilite_livraison.predict import predict_order_eligibility
from eligibilite_livraison.training import run_training


class NewDataPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Jeu de données au format exact du simulateur ERP (MongoDB)
        raw_erp_orders = []
        for i in range(1, 201):
            raw_erp_orders.append(
                {
                    "order_id": f"ERP-{i:08d}",
                    "order_date": date(2024, 6, 1),
                    "hour": 8 + (i % 12),
                    "day_of_week": (i % 7),
                    "weekend": int((i % 7) >= 5),
                    "distance_km": float(2 + (i % 30)),
                    "order_value_eur": float(20 + (i % 200)),
                    "weight_kg": float(0.5 + (i % 20)),
                    "stock_available": 1 if i % 4 != 0 else 0,
                    "preparation_time_min": float(10 + (i % 30)),
                    "carrier_capacity": float(5 + (i % 45)),  # Échelle ERP 5-50
                    "weather": ["clear", "rain", "wind", "snow"][i % 4],
                    "delivery_zone": ["centre", "suburb", "rural"][i % 3],
                    "customer_type": ["individual", "business"][i % 2],
                }
            )
        cls.erp_orders_df = pd.DataFrame(raw_erp_orders)

        # Si une instance MongoDB est joignable (ex: docker-compose.test.yml), on l'utilise réellement
        real_repo = MongoOrderRepository(collection="orders_pipeline_test")
        if real_repo.is_connected():
            real_repo.collection.delete_many({})
            real_repo.save_many(raw_erp_orders)
            cls.repo = real_repo
            cls.using_real_mongo = True
        else:
            real_repo.close()
            mock_repo = MagicMock()
            mock_repo.get_orders.return_value = cls.erp_orders_df.copy()
            mock_repo.count.return_value = len(cls.erp_orders_df)
            cls.repo = mock_repo
            cls.using_real_mongo = False

    @classmethod
    def tearDownClass(cls):
        if getattr(cls, "using_real_mongo", False):
            cls.repo.collection.delete_many({})
            cls.repo.close()

    def test_load_and_clean_erp_data(self):
        cleaned = load_orders_from_repository(self.repo)
        self.assertEqual(len(cleaned), 200)
        self.assertIn("express_eligible", cleaned.columns)
        # Vérifie que la capacité transporteur a bien été normalisée dans [0, 1]
        self.assertTrue(cleaned["carrier_capacity"].between(0.0, 1.0).all())

    def test_training_on_new_erp_data(self):
        outputs = run_training(repository=self.repo)
        self.assertIn("model", outputs)
        self.assertIn("metrics", outputs)
        self.assertGreaterEqual(outputs["metrics_values"]["accuracy"], 0.6)

    def test_prediction_on_new_erp_order(self):
        run_training(repository=self.repo)
        model = load_model()

        new_order = {
            "order_id": "ERP-00999999",
            "hour": 10,
            "day_of_week": 2,
            "weekend": 0,
            "distance_km": 4.5,
            "order_value_eur": 85.0,
            "weight_kg": 3.0,
            "stock_available": 1,
            "preparation_time_min": 12.0,
            "carrier_capacity": 30.0,
            "weather": "clear",
            "delivery_zone": "centre",
            "customer_type": "business",
        }
        prediction = predict_order_eligibility(new_order, model)
        self.assertIn("decision", prediction)
        self.assertIn(prediction["decision"], {"oui", "non"})
        self.assertGreaterEqual(prediction["probability"], 0.0)
        self.assertLessEqual(prediction["probability"], 1.0)

    def test_api_on_new_erp_orders(self):
        client = TestClient(app)
        load_model()

        new_order = {
            "order_id": "ERP-LIVE-001",
            "hour": 15,
            "day_of_week": 3,
            "weekend": 0,
            "distance_km": 8.0,
            "order_value_eur": 110.0,
            "weight_kg": 5.0,
            "stock_available": 1,
            "preparation_time_min": 18.0,
            "carrier_capacity": 25.0,
            "weather": "rain",
            "delivery_zone": "suburb",
            "customer_type": "individual",
        }
        response = client.post("/predict", json=new_order)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["order_id"], "ERP-LIVE-001")
        self.assertIn(data["decision"], {"oui", "non"})


if __name__ == "__main__":
    unittest.main()
