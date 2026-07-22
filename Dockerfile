# syntax=docker/dockerfile:1
# Канон профилей: docs/CANONICAL-RUNTIME.md
#   target lite  — office-lite (requirements-minimal, rule_based)
#   target full  — office-full (requirements.txt + crewai, ORCHESTRATION_ENGINE=auto)
FROM python:3.11-slim AS base

WORKDIR /app
ENV PYTHONPATH=/app
ENV ARTIFACTS_DIR=/app/app/artifacts
RUN mkdir -p app/artifacts/handoffs app/artifacts/reports app/artifacts/tasks

FROM base AS deps-lite
COPY requirements-minimal.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM base AS deps-full
COPY requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

FROM deps-lite AS lite
COPY . .
CMD ["python", "-m", "app.main"]

FROM deps-full AS full
COPY . .
CMD ["python", "-m", "app.main"]

# Default build target (office-lite)
FROM lite
