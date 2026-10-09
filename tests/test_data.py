import unittest

import pandas as pd

from eligibilite_livraison.data import (
    clean_orders_data,
    generate_orders_dataset,
    validate_dataset,
)


class DatasetTests(unittest.TestCase):
    def test_generated_dataset_passes_validation(self):
        data = generate_orders_dataset(n_rows=100)

        self.assertEqual(len(data), 100)
        self.assertTrue(validate_dataset(data))

    def test_validation_reports_duplicate_order_ids(self):
        data = generate_orders_dataset(n_rows=10)
        duplicated = pd.concat([data, data.iloc[[0]]], ignore_index=True)

        with self.assertRaisesRegex(ValueError, "dupliqués"):
            validate_dataset(duplicated)

    def test_cleaning_removes_duplicate_and_invalid_rows(self):
        data = generate_orders_dataset(n_rows=10)
        data.loc[1, "distance_km"] = -1
        data = pd.concat([data, data.iloc[[0]]], ignore_index=True)

        cleaned = clean_orders_data(data)

        self.assertEqual(len(cleaned), 9)
        self.assertTrue(validate_dataset(cleaned))


if __name__ == "__main__":
    unittest.main()
