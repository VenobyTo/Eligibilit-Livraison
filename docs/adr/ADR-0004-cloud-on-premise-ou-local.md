# ADR-0004 : Cloud, On-premise ou local ?

* **Statut** : Accepté
* **Date** : 2026-10-26 (Cours 2)
* **Auteur** : Équipe MLOps / Ingénierie IA
* **Contexte** : Choix de l'environnement d'hébergement de l'infrastructure IA et des bases ERP

---

## 1. Contexte et Problématique

L'application d'éligibilité à la livraison express s'inscrit dans un système d'information existant où l'ERP de l'entreprise alimente deux bases de données internes (PostgreSQL et MongoDB) hébergées dans le réseau de l'entreprise (`localhost` / On-Premise). Parallèlement, l'équipe utilise GitHub pour le contrôle de version, l'intégration continue (GitHub Actions) et le registre d'images (GHCR).

Nous devons déterminer le modèle d'hébergement cible entre **Cloud public**, **On-Premise** et **Local**.

---

## 2. Options Considérées

### Option A : 100 % Cloud Public (Full Cloud AWS / GCP / Azure)
* **Avantages** : Élasticité quasi infinie, services managés (Cloud Run, DocumentDB/Atlas).
* **Inconvénients** : Coûts récurrents d'infrastructure et d'egress réseau, nécessite d'exposer ou de répliquer les bases de données ERP internes vers le cloud public (enjeux de sécurité, RGPD et latence réseau).

### Option B : 100 % Local (Poste développeur uniquement)
* **Avantages** : Coût nul, boucle de feedback immédiate.
* **Inconvénients** : Aucune garantie de disponibilité 24/7, non industrialisable pour les appels de l'ERP en production.

### Option C : Modèle Hybride « On-Premise Conteneurisé & Cloud-Ready » (CI/CD Cloud + Exécution On-Premise/Local Docker) — **[RETENUE]**
* **Avantages** :
  * **Proximité des données (Data Gravity & Sécurité)** : L'API et l'orchestrateur s'exécutent via `docker-compose.prod.yml` au plus près de la base analytique MongoDB alimentée par l'ERP interne, évitant toute exposition des données de commandes sur Internet et garantissant une latence d'inférence `< 10 ms`.
  * **Usine logicielle dans le Cloud (GitHub Actions + GHCR)** : Les tests automatisés, la construction multi-stage et le stockage des images Docker sont délégués au cloud GitHub.
  * **Portabilité Cloud-Native totale (12-Factor App)** : Toute la configuration passe par des variables d'environnement (`MONGO_URI`, `MONGO_DB`, `API_PORT`), permettant une migration transparente vers un conteneur managé Cloud (Cloud Run / ECS / Azure Container Apps) sans modifier une seule ligne de code.

---

## 3. Décision Retenue

Nous retenons l'**Option C (Architecture Hybride : Usine CI/CD Cloud + Exécution On-Premise/Local conteneurisée Cloud-Ready)**.

### Justification
1. **Souveraineté et sécurité des données ERP** : Les bases de données de l'entreprise (notamment MongoDB sans authentification externe par défaut) restent confinées dans le réseau privé Docker (`livraison-express-prod`).
2. **Maîtrise des coûts (FinOps)** : Le modèle de régression logistique est très léger en CPU/RAM et ne nécessite pas d'instances GPU cloud coûteuses.
3. **Réversibilité** : Le respect strict des principes *12-Factor App* et des standards OCI garantit que le déploiement peut basculer sur le Cloud public à tout moment.
