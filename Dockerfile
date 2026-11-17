# ----------  Étape 1 : builder (compilation isolée)  ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dépendances système nécessaires uniquement à la compilation éventuelle de wheels
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt && \
    find /install -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true


# ----------  Étape 2 : runtime minimal et sécurisé  ----------
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="eligibilite-livraison-express" \
      org.opencontainers.image.description="Microservice MLOps d'éligibilité à la livraison express (API, entraînement, orchestrateur)" \
      org.opencontainers.image.version="1.0.0" \
      maintainer="mohamedamine.elarjouni@ynov.com"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    GIT_PYTHON_REFRESH=quiet \
    PYTHONPATH=/app/src

WORKDIR /app

# Création d'un utilisateur non-root pour la sécurité en production
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Récupération uniquement des paquets Python installés depuis le builder (sans gcc/g++)
COPY --from=builder /install /usr/local

# Copie du code source et des métadonnées du package
COPY pyproject.toml requirements.txt ./
COPY src/ src/
COPY tests/ tests/

# Installation du package sans re-télécharger les dépendances
RUN pip install --no-cache-dir --no-deps -e . && \
    mkdir -p artifacts data/generated reports && \
    chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Point d'entrée par défaut : API FastAPI
CMD ["uvicorn", "eligibilite_livraison.api:app", "--host", "0.0.0.0", "--port", "8000"]
