# Classess single deployable — the gateway (wall) + spine + capability modules
# composed into ONE FastAPI process. Build context is the REPOSITORY ROOT
# (the loader resolves the spine/ and modules/ trees by path), so build with:
#
#   docker build -f backend/Dockerfile -t classess-backend .
#
FROM python:3.12-slim

# - no .pyc, unbuffered logs (so Railway captures stdout immediately)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install third-party deps first for layer caching. The repo libs themselves are
# NOT pip-installed — they are imported in-process from the copied tree.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy the parts of the repo the deployable composes in-process. The loader
# resolves spine/ and modules/ relative to the repo root (the parent of backend/).
COPY backend/ /app/backend/
COPY spine/ /app/spine/
COPY modules/ /app/modules/

# /app is the repo root on PYTHONPATH so `backend.main:app` and the path-based
# loader resolve. PORT is supplied by the platform (Railway); default for local.
ENV PYTHONPATH=/app \
    PORT=8080

EXPOSE 8080

# Bind to $PORT (read by NAME). Shell form so $PORT is expanded at runtime.
CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
