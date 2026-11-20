# ----------  Étape 1 : builder (compilation des dépendances isolée)  ----------
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

# Installation du paquet dans /install sans embarquer requirements.txt dans l'image finale
COPY pyproject.toml ./
COPY src/ src/
RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    pip install --no-cache-dir --no-deps --prefix=/install .


# ----------  Étape 2 : prod (image finale minimale et rootless, sans tests ni requirements.txt)  ----------
FROM python:3.12-slim AS prod

LABEL org.opencontainers.image.title="eligibilite-livraison-express" \
      org.opencontainers.image.description="Microservice MLOps d'éligibilité à la livraison express (API, entraînement, orchestrateur)" \
      org.opencontainers.image.version="1.0.0" \
      maintainer="mohamedamine.elarjouni@ynov.com"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    GIT_PYTHON_REFRESH=quiet \
    PYTHONPATH=/app/src

WORKDIR /app

# Utilisateur non-root (Rootless) pour la sécurité en production
RUN groupadd -r appgroup && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

# Récupération uniquement des paquets Python compilés (sans gcc/g++, sans requirements.txt, sans tests)
COPY --from=builder /install /usr/local
COPY src/ src/

RUN mkdir -p artifacts data/generated reports && \
    chown -R appuser:appgroup /app

USER appuser

# Exposition uniquement du port strictement nécessaire (pas de SSH/22)
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "eligibilite_livraison.api:app", "--host", "0.0.0.0", "--port", "8000"]


# ----------  Étape 3 : test (image dédiée à l'exécution des tests dans docker-compose.test.yml)  ----------
FROM prod AS test

USER root
COPY tests/ tests/
RUN chown -R appuser:appgroup /app/tests
USER appuser

CMD ["python", "-m", "unittest", "discover", "-s", "tests", "-v"]
