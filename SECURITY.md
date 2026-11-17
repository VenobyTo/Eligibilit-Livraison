# Politique de sécurité

## Versions supportées

| Version | Supportée |
|---------|-----------|
| 1.0.x   | Oui    |
| < 1.0   | Non    |

Seule la dernière version stable reçoit des correctifs de sécurité.

---

## Signaler une vulnérabilité

Si vous découvrez une faille de sécurité dans ce projet, **ne créez pas
d'Issue publique**. Contactez-nous de manière confidentielle :

- **E-mail** : [mohamedamine.elarjouni@ynov.com]`

### Informations à fournir

1. **Description** de la vulnérabilité.
2. **Étapes de reproduction** détaillées.
3. **Impact potentiel** (exécution de code, fuite de données, etc.).
4. **Version** du projet et environnement (OS, Python, dépendances).
5. **Correctif proposé**, si vous en avez un.

### Délai de réponse

| Étape | Délai indicatif |
|-------|-----------------|
| Accusé de réception | 48 heures |
| Évaluation initiale | 5 jours ouvrés |
| Correctif ou plan d'action | 30 jours ouvrés |

Nous nous engageons à traiter les signalements avec diligence et à tenir le
rapporteur informé de l'avancement.

---

## Bonnes pratiques de sécurité pour les contributeurs

### Dépendances

- Épinglez les versions de production dans `requirements.txt` lorsque
  possible.
- Vérifiez régulièrement les vulnérabilités connues :

  ```powershell
  pip install pip-audit
  pip-audit
  ```

### Données et secrets

- Ne committez **jamais** de secrets, clés API, mots de passe ou tokens dans
  le dépôt.
- Les fichiers sensibles (`mlflow.db`, `artifacts/`, `data/generated/`) sont
  déjà exclus via le `.gitignore` — ne les retirez pas.
- Utilisez des **variables d'environnement** pour toute information sensible.

### Modèle et artefacts

- Le fichier `express_delivery_model.joblib` est un objet sérialisé Python
  (pickle). Ne chargez **jamais** un fichier `.joblib` provenant d'une source
  non fiable, car la désérialisation peut exécuter du code arbitraire.
- Validez l'intégrité des artefacts avant de les utiliser en production
  (somme de contrôle, signature).

### Entrées utilisateur

- Toute donnée passée aux fonctions de prédiction (`predict_order_eligibility`,
  `predict_batch`) doit être **validée et nettoyée** avant traitement.
- Ne faites pas confiance aux entrées brutes : vérifiez les types, les bornes
  et les valeurs attendues.

---

## Divulgation responsable

Nous suivons une politique de **divulgation coordonnée** :

1. Le rapporteur signale la vulnérabilité en privé.
2. L'équipe confirme, corrige et prépare une version de sécurité.
3. Un avis de sécurité est publié une fois le correctif disponible.
4. Le rapporteur est crédité (sauf s'il souhaite rester anonyme).

Nous demandons aux rapporteurs de ne pas divulguer publiquement la
vulnérabilité avant la publication du correctif.

---

Merci de contribuer à la sécurité de ce projet.
