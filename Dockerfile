# syntax=docker/dockerfile:1

FROM node:22-bookworm-slim AS frontend-build
WORKDIR /app/frontend

# Only public, non-secret build settings belong in the frontend bundle.
ENV VITE_BASE_PATH=/ \
    VITE_BACKEND_URL="" \
    DISABLE_VISUAL_EDITS=true \
    DISABLE_EMERGENT_OVERLAY=true \
    DISABLE_HOT_RELOAD=true

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    CLOUD_SINGLE_WRITER=true \
    FRONTEND_DIST=/app/frontend/dist \
    WORKBOOK_DIR=/app/imports/workbooks \
    PORT=10000

COPY backend/requirements-local.txt /app/backend/requirements-local.txt
RUN python -m pip install --no-cache-dir -r /app/backend/requirements-local.txt \
    && useradd --create-home --uid 10001 app

# The build context allowlist excludes local env, backups, tests, and archives.
COPY --chown=10001:10001 backend/ /app/backend/
COPY --from=frontend-build --chown=10001:10001 /app/frontend/dist/ /app/frontend/dist/
COPY --chown=10001:10001 ["imports/workbooks/09 - Laporan Bulan September.xlsx", "imports/workbooks/Perkasa Jaya - Store information system (wecompress.com).xlsx", "/app/imports/workbooks/"]
COPY --chown=10001:10001 ["refrensi-spreadsheet/Perkasa Jaya - Store information system (1).xlsx", "/app/refrensi-spreadsheet/"]

USER 10001:10001
EXPOSE 10000

# exec forwards Render's shutdown signal to the only Uvicorn process.
CMD ["sh", "-c", "exec python -m uvicorn server:app --app-dir backend --host 0.0.0.0 --port \"${PORT:-10000}\" --workers 1"]
