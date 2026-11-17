# ADR-0006 : PostgreSQL, MongoDB, autre ?

* **Statut** : Accepté
* **Date** : 2026-10-29 (Cours 4)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : TP4 – Connexion de l'application à une base de données de production pour l'entraînement ML

---

## 1. Contexte et Problématique

L'application d'éligibilité à la livraison express doit être connectée à une base de données d'entreprise afin d'extraire les données de commandes nécessaires à l'entraînement du modèle, aux prédictions et au service de l'API.

Deux bases de données alimentées par l'ERP sont actuellement disponibles dans l'infrastructure :

1. **PostgreSQL (`localhost:5432`)** :
   * Base de données relationnelle historique (en production depuis 2015).
   * Schéma modifié en 2017 et 2023.
   * Partagée avec une autre application critique de l'entreprise.
   * Plus aucun DBA/administrateur de base de données dédié depuis sa démission en 2023 (aucun remplacement).
   * Authentification activée (`livraison` / `livraison`).

2. **MongoDB (`localhost:27017`)** :
   * Base de données NoSQL orientée documents, mise en place en 2023 comme **base analytique**.
   * Conçue spécifiquement pour isoler les charges de requêtes des Data Analysts afin d'éviter qu'ils ne surchargent ou ne fassent planter la base PostgreSQL de production.
   * Alimentée en temps réel depuis PostgreSQL via un pipeline ETL unilatéral.
   * Contient uniquement l'historique récent (depuis 2023).
   * Maintenue actuellement par un alternant en fin de contrat.
   * Actuellement accessible sans authentification requise.

### Problématique
Quelle base de données doit être sélectionnée comme source de données pour notre application d'IA, tout en garantissant la disponibilité des systèmes critiques, la qualité des features pour le modèle et la pérennité de l'infrastructure ?

---

## 2. Facteurs de Décision (Decision Drivers)

* **Isolation et Disponibilité Opérationnelle (Blast Radius)** : Ne sous aucun prétexte dégrader ou faire tomber l'application critique métier tournant sur PostgreSQL.
* **Qualité et Consistance des Données ML** : Pertinence de l'historique, présence des features obligatoires sans valeurs nulles dues aux migrations passées.
* **Architecture Cible & Séparation des Responsabilités (OLTP vs OLAP/Analytics)** : Respect du pattern d'isolation des lectures analytiques vis-à-vis des écritures transactionnelles.
* **Maintenabilité et Compétences** : Gestion du départ de l'alternant et absence de DBA.
* **Sécurité & Conformité** : Contrôle d'accès et authentification pour les environnements de Test et Production.

---

## 3. Options Considérées

### Option 1 : PostgreSQL (Base Transactionnelle OLTP)

* **Avantages** :
  * **Source de vérité primaire (SSoT)** : Les données proviennent directement de l'ERP Pro 2015 sans passer par un ETL intermédiaire.
  * **Historique complet (2015 - aujourd'hui)** : Plus grand volume brut de données (plus de 10 ans d'historique potentiel).
  * **Sécurité déjà configurée** : Authentification et utilisateurs en place (`livraison` / `livraison`).
  * **Cohérence transactionnelle stricte (ACID)** et schéma relationnel formel.

* **Inconvénients majeurs** :
  * **Risque opérationnel critique** : La base héberge une autre application critique de l'entreprise. Les requêtes lourdes d'extraction batch ML risquent d'entraîner des contentions (verrous, consommation CPU/I/O) ou des interruptions de service.
  * **Antécédents d'incidents** : L'administrateur historique avait expressément monté MongoDB car les requêtes analytiques "cassaient" la production PostgreSQL.
  * **Absence de DBA** : En cas d'incident sur PostgreSQL, personne n'est en poste pour diagnostiquer ou réparer le cluster.
  * **Dette de schéma et données incomplètes (2015-2022)** :
    * Avant le 01/07/2015, la feature `weekend` est systématiquement `NULL`.
    * Avant le 01/07/2017, la feature `preparation_time_min` est systématiquement `NULL`.
    * Risque fort de *Data Drift* et de dégradation des performances du modèle si on entraîne sur des données très anciennes dont les processus de livraison ont changé.

---

### Option 2 : MongoDB (Base Analytique Découplée) — **[RETENUE]**

* **Avantages** :
  * **Isolation stricte de la production (Zero Blast Radius)** : MongoDB a été expressément conçue pour absorber les charges d'extraction et de lecture analytique/ML sans impacter l'application critique.
  * **Conformité au pattern CQRS / Read-Replica Analytique** : Le flux ETL unilatéral garantit que l'application d'IA ne peut jamais altérer ni verrouiller la base transactionnelle OLTP.
  * **Données propres et stabilisées (2023 - aujourd'hui)** :
    * Toutes les variables requises par le modèle (`weekend`, `preparation_time_min`, `distance_km`, etc.) sont complètes et exemptes des valeurs `NULL` historiques.
    * Données récentes reflétant fidèlement les conditions actuelles de livraison (réduction du concept drift).
  * **Flexibilité documentaire** : Modèle JSON adapté aux structures de données Python (dictionnaires/DataFrames) et requêtage rapide par identifiant de commande indexé (`order_id`).

* **Inconvénients et risques identifiés** :
  * Dépendance envers le pipeline ETL (latence éventuelle de synchronisation).
  * L'alternant responsable part bientôt (risque de perte de connaissance).
  * Absence actuelle d'authentification par mot de passe.
  * Historique limité aux données post-2023.

---

## 4. Matrice Comparative

| Critère | PostgreSQL (Prod OLTP) | MongoDB (Analytique) | Gagnant |
| :--- | :--- | :--- | :---: |
| **Impact sur les systèmes critiques** | Risque très élevé (app critique partagée) | Aucun risque (base dédiée isolée) | **MongoDB** |
| **Respect des patrons d'architecture** | Anti-pattern (requêtage direct de l'OLTP) | Best practice (séparation OLTP/OLAP) | **MongoDB** |
| **Qualité des features (features complètes)** | Altérée (colonnes `NULL` 2015-2017) | Parfaite (100% renseigné 2023+) | **MongoDB** |
| **Pertinence temporelle (Concept Drift)** | Données 2015 obsolètes pour l'éligibilité | Données récentes représentatives | **MongoDB** |
| **Sécurité par défaut actuelle** | Utilisateur & mot de passe configurés | Authentification désactivée | **PostgreSQL** |
| **Pérennité de la maintenance** | Plus de DBA depuis 2023 | Alternant en fin de contrat | **Égalité** |
| **Profondeur d'historique** | 10 ans (depuis 2015) | 3 ans (depuis 2023) | **PostgreSQL** |

---

## 5. Décision Retenue

Nous choisissons d'intégrer les données depuis **MongoDB** (tout en fournissant également l'adaptateur `PostgresOrderRepository` grâce au pattern Repository pour garantir la réversibilité).

### Justification de la décision
1. **Priorité absolue à la stabilité de l'entreprise** : Il est inacceptable d'exposer l'application métier critique à des pannes induites par les charges de Machine Learning sur PostgreSQL, d'autant plus qu'aucun DBA n'est présent pour intervenir.
2. **Adéquation avec l'objectif de conception initial** : MongoDB a été mise en service dans l'infrastructure spécifiquement pour servir de zone d'atterrissage analytique et décharger PostgreSQL. Exploiter MongoDB respecte la gouvernance des flux mise en place.
3. **Qualité et fraîcheur des données** : L'historique disponible depuis 2023 est homogène, sans colonnes manquantes (contrairement aux années 2015-2017 sur PostgreSQL), ce qui fiabilise l'entraînement du modèle scikit-learn sans nécessiter d'imputations fragiles.
