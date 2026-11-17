"""Tests unitaires pour l'orchestrateur d'entraînement ML (orchestrator.py)."""

import unittest
from unittest.mock import MagicMock

from eligibilite_livraison.data import generate_orders_dataset
from eligibilite_livraison.orchestrator import (
    OrchestrationReport,
    extract_orders_task,
    run_training_flow,
    train_and_evaluate_task,
    validate_and_clean_task,
)


class OrchestratorTests(unittest.TestCase):
    def test_extract_orders_fallback_synthetic(self):
        df, source = extract_orders_task(
            repository=None,
            use_mongo=False,
            n_rows_fallback=150,
        )
        self.assertEqual(len(df), 150)
        self.assertEqual(source, "Synthetic (Fallback)")

    def test_extract_orders_with_injected_repository(self):
        mock_repo = MagicMock()
        sample_df = generate_orders_dataset(n_rows=120, random_state=42)
        mock_repo.get_orders.return_value = sample_df

        df, source = extract_orders_task(repository=mock_repo)
        self.assertEqual(len(df), 120)
        self.assertEqual(source, "Repository (Injected)")

    def test_validate_and_clean_task(self):
        raw_df = generate_orders_dataset(n_rows=100, random_state=42)
        cleaned_df = validate_and_clean_task(raw_df)
        self.assertEqual(len(cleaned_df), 100)
        self.assertIn("express_eligible", cleaned_df.columns)

    def test_train_and_evaluate_quality_gate(self):
        clean_df = validate_and_clean_task(
            generate_orders_dataset(n_rows=300, random_state=42)
        )
        result, gate_passed = train_and_evaluate_task(
            clean_df,
            min_accuracy=0.55,
            min_roc_auc=0.60,
        )
        self.assertTrue(gate_passed)
        self.assertIn("accuracy", result.metrics)
        self.assertIn("roc_auc", result.metrics)

    def test_full_run_training_flow(self):
        report = run_training_flow(
            use_mongo=False,
            n_rows_fallback=250,
            min_accuracy=0.55,
            min_roc_auc=0.60,
        )
        self.assertIsInstance(report, OrchestrationReport)
        self.assertEqual(report.data_source, "Synthetic (Fallback)")
        self.assertEqual(report.rows_cleaned, 250)
        self.assertTrue(report.quality_gate_passed)
        self.assertTrue(len(report.mlflow_run_id) > 0)
        self.assertIn("model", report.artifact_paths)


if __name__ == "__main__":
    unittest.main()
