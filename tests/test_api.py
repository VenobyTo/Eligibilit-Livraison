"""Tests unitaires pour l'API FastAPI."""

import unittest
from fastapi.testclient import TestClient

from eligibilite_livraison.api import app, load_model
from eligibilite_livraison.training import run_training


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Entraîne un modèle rapide pour les tests si aucun n'est chargé
        run_training(n_rows=200)
        load_model()
        cls.client = TestClient(app)

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.json())

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("model_loaded", data)
        self.assertIn("database_type", data)
        self.assertEqual(data["database_type"], "MongoDB")

    def test_predict_endpoint_valid_order(self):
        order = {
            "order_id": "TEST-001",
            "hour": 14,
            "day_of_week": 2,
            "weekend": 0,
            "distance_km": 5.2,
            "order_value_eur": 65.0,
            "weight_kg": 2.5,
            "stock_available": 1,
            "preparation_time_min": 15.0,
            "carrier_capacity": 0.8,
            "weather": "clear",
            "delivery_zone": "centre",
            "customer_type": "business",
        }
        response = self.client.post("/predict", json=order)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["order_id"], "TEST-001")
        self.assertIn(data["decision"], {"oui", "non"})
        self.assertIsInstance(data["express_eligible"], bool)
        self.assertGreaterEqual(data["probability"], 0.0)
        self.assertLessEqual(data["probability"], 1.0)

    def test_predict_endpoint_erp_scale_capacity(self):
        # Vérifie qu'une capacité ERP (ex: 35) est bien acceptée et normalisée
        order = {
            "order_id": "ERP-00099999",
            "hour": 10,
            "day_of_week": 1,
            "weekend": 0,
            "distance_km": 12.0,
            "order_value_eur": 120.0,
            "weight_kg": 4.0,
            "stock_available": 1,
            "preparation_time_min": 20.0,
            "carrier_capacity": 35.0,
            "weather": "rain",
            "delivery_zone": "suburb",
            "customer_type": "individual",
        }
        response = self.client.post("/predict", json=order)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn(data["decision"], {"oui", "non"})

    def test_predict_endpoint_invalid_input(self):
        # Commande avec heure invalide
        order = {
            "hour": 28,  # Invalide
            "day_of_week": 2,
            "weekend": 0,
            "distance_km": 5.0,
            "order_value_eur": 50.0,
            "weight_kg": 2.0,
            "stock_available": 1,
            "preparation_time_min": 10.0,
            "carrier_capacity": 0.5,
            "weather": "clear",
            "delivery_zone": "centre",
            "customer_type": "business",
        }
        response = self.client.post("/predict", json=order)
        self.assertEqual(response.status_code, 422)

    def test_batch_predict_endpoint(self):
        payload = {
            "orders": [
                {
                    "order_id": "BATCH-1",
                    "hour": 11,
                    "day_of_week": 0,
                    "weekend": 0,
                    "distance_km": 3.0,
                    "order_value_eur": 40.0,
                    "weight_kg": 1.0,
                    "stock_available": 1,
                    "preparation_time_min": 10.0,
                    "carrier_capacity": 0.9,
                    "weather": "clear",
                    "delivery_zone": "centre",
                    "customer_type": "business",
                },
                {
                    "order_id": "BATCH-2",
                    "hour": 22,
                    "day_of_week": 6,
                    "weekend": 1,
                    "distance_km": 35.0,
                    "order_value_eur": 15.0,
                    "weight_kg": 20.0,
                    "stock_available": 0,
                    "preparation_time_min": 45.0,
                    "carrier_capacity": 0.2,
                    "weather": "snow",
                    "delivery_zone": "rural",
                    "customer_type": "individual",
                },
            ],
            "threshold": 0.5,
        }
        response = self.client.post("/predict/batch", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["order_id"], "BATCH-1")
        self.assertEqual(data[1]["order_id"], "BATCH-2")

    def test_metrics_endpoint(self):
        response = self.client.get("/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("api_metrics", data)
        self.assertIn("ml_training_metrics", data)
        self.assertIn("ml_live_monitoring", data)
        self.assertTrue(data["model_loaded"])

    def test_realtime_stream_order_and_dashboard(self):
        dashboard = self.client.get("/logisticien")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn("Notifications Logisticien", dashboard.text)

        order = {
            "order_id": "STREAM-001",
            "hour": 10,
            "day_of_week": 1,
            "weekend": 0,
            "distance_km": 3.5,
            "order_value_eur": 95.0,
            "weight_kg": 1.8,
            "stock_available": 1,
            "preparation_time_min": 12.0,
            "carrier_capacity": 0.9,
            "weather": "clear",
            "delivery_zone": "centre",
            "customer_type": "business",
        }
        response = self.client.post("/stream/order", json=order)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["order_id"], "STREAM-001")
        self.assertIn(data["decision"], {"oui", "non"})


if __name__ == "__main__":
    unittest.main()

