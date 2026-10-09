import unittest

from eligibilite_livraison.data import generate_orders_dataset
from eligibilite_livraison.model import build_model_pipeline
from eligibilite_livraison.predict import (
    batch_predict_orders,
    predict_order_eligibility,
)
from eligibilite_livraison.config import FEATURE_COLUMNS


class PredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data = generate_orders_dataset(n_rows=200)
        cls.features = data[FEATURE_COLUMNS]
        cls.model = build_model_pipeline()
        cls.model.fit(cls.features, data["express_eligible"])
        cls.order = cls.features.iloc[0].to_dict()

    def test_single_order_prediction_has_expected_shape(self):
        result = predict_order_eligibility(self.order, self.model)

        self.assertIn(result["decision"], {"oui", "non"})
        self.assertIsInstance(result["express_eligible"], bool)
        self.assertGreaterEqual(result["probability"], 0)
        self.assertLessEqual(result["probability"], 1)
        self.assertIn("prediction_timestamp", result)

    def test_single_order_requires_all_features(self):
        incomplete = dict(self.order)
        incomplete.pop("distance_km")

        with self.assertRaisesRegex(ValueError, "distance_km"):
            predict_order_eligibility(incomplete, self.model)

    def test_batch_prediction_adds_decision_columns(self):
        batch = batch_predict_orders(self.features.iloc[:5], self.model)

        self.assertEqual(len(batch), 5)
        self.assertIn("eligibility_probability", batch.columns)
        self.assertIn("decision", batch.columns)

    def test_threshold_must_be_between_zero_and_one(self):
        with self.assertRaisesRegex(ValueError, "seuil"):
            predict_order_eligibility(self.order, self.model, threshold=1.5)


if __name__ == "__main__":
    unittest.main()
