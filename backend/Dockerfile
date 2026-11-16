# Turnos odontología (Cattaneo) — imagen única (SPA + API) C-12 D-2/D-3.
# Build desde la raíz del repo:  docker build -f backend/Dockerfile .
# Stage 1: compila el frontend (Vite) con URLs relativas (mismo origen).
FROM node:20-alpine AS frontend

WORKDIR /fe

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

# Stage 2: runtime Python 3.12 no-root con la SPA en ./static.
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=America/Argentina/Buenos_Aires

WORKDIR /code

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app/ ./app/
COPY backend/alembic/ ./alembic/
COPY backend/alembic.ini .

COPY --from=frontend /fe/dist ./static

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --create-home app \
    && chown -R app:app /code

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:${PORT:-8000}/api/health', timeout=3).status == 200 else sys.exit(1)"

# `PORT` lo inyecta el PaaS; 8000 por defecto (compose/PaaS single host).
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
