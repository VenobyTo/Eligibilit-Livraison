# ADR-0001 : Stockage des commandes

* **Statut** : Accepté
* **Date** : 2026-10-09 (Cours 1)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : Industrialisation du pipeline d'éligibilité à la livraison express

---

## 1. Contexte et Problématique

Dans le notebook initial (`project_test_v1_final_final2.ipynb`), les données de commandes étaient générées à la volée en mémoire sous forme de `DataFrame` Pandas puis exportées localement dans un simple fichier `data/generated/orders.csv`.

Pour passer d'une expérimentation Data Science à une application industrielle prête pour la production, nous devons définir **comment stocker, structurer et exposer les commandes** utilisées par le pipeline d'entraînement et de prédiction, tout en assurant :
- La reproductibilité des entraînements hors-ligne (offline) ;
- La capacité à se brancher sur une base de données d'entreprise alimentée par l'ERP (online / batch) sans réécrire la logique métier ;
- La validation stricte du schéma des commandes (15 colonnes dont 12 features explicatives et la cible `express_eligible`).

---

## 2. Options Considérées

### Option A : Stockage exclusivement sur fichiers plats locaux (CSV)
* **Avantages** : Simplicité immédiate, lisible humainement, aucune infrastructure requise.
* **Inconvénients** : Pas d'indexation ni de requêtage filtré par dates, absence de typage strict, gestion concurrente impossible en production, couplage fort aux chemins du système de fichiers.

### Option B : Stockage fichiers orientés colonnes (Apache Parquet)
* **Avantages** : Compression élevée, conservation du typage des colonnes, lecture analytique très rapide.
* **Inconvénients** : Format binaire non interrogeable transactionnellement par commande (`order_id`), nécessite un moteur supplémentaire pour l'alimentation temps réel depuis l'ERP.

### Option C : Architecture Hybride découplée par Pattern Repository (Base de données + Export CSV/Snapshot versionné) — **[RETENUE]**
* **Avantages** :
  * **Séparation Domain / Infrastructure (Clean Architecture)** via un contrat `OrderRepository` (`Protocol` Python dans `src/eligibilite_livraison/infrastructure/contract/order_repository.py`).
  * Stockage primaire des commandes de production dans une base de données indexée sur `order_id` et `order_date`.
  * Sauvegarde automatique d'un snapshot `data/generated/orders.csv` nettoyé lors de chaque entraînement pour garantir l'auditabilité et le repli hors-ligne (fallback synthétique pour les tests unitaires et la CI).
* **Inconvénients** : Légère complexité architecturale initiale (création d'interfaces et d'adaptateurs).

---

## 3. Décision Retenue

Nous retenons l'**Option C (Pattern Repository + Base de données + Snapshot CSV d'entraînement)**.

### Justification
1. **Inversion de dépendance (Clean Code)** : Le pipeline d'entraînement (`training.py` et `orchestrator.py`) dépend uniquement de l'abstraction `OrderRepository` (`get_orders`, `get_by_id`, `count`, `save_many`) et non d'un format de fichier ou d'un driver de base de données spécifique.
2. **Résilience et testabilité** : En environnement de développement isolé ou lors de tests unitaires rapides, l'application peut générer et stocker un jeu de commandes synthétique reproductible (`RANDOM_STATE = 42`), tandis qu'en production elle consomme directement les commandes issues du flux ERP.
3. **Traçabilité** : Chaque exécution d'entraînement fige le jeu nettoyé dans `data/generated/orders.csv`.
