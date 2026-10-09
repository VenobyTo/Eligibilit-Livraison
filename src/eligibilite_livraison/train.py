from eligibilite_livraison.training import run_training


def main() -> None:
    outputs = run_training()
    print("Entraînement terminé.")
    print(f"Run MLflow : {outputs['mlflow_run_id']}")
    print("Fichiers produits :")
    for name, path in outputs.items():
        if name not in {"mlflow_run_id", "metrics_values"}:
            print(f"  {name}: {path}")
    print("Métriques :")
    for name, value in outputs["metrics_values"].items():
        print(f"  {name}: {value:.4f}")


if __name__ == "__main__":
    main()
