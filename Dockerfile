FROM python:3.11-slim

WORKDIR /app

# Профиль office-lite: requirements-minimal.txt (без crewai). Канон см. docs/CANONICAL-RUNTIME.md.
# docker-compose задаёт ORCHESTRATION_ENGINE=rule_based по умолчанию (согласовано с этим образом).
# Полный requirements.txt с crewai тяжёлый и может ломать pip install (хеши/зависимости).
COPY requirements-minimal.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создать директории для артефактов
RUN mkdir -p app/artifacts/handoffs app/artifacts/reports

ENV PYTHONPATH=/app
ENV ARTIFACTS_DIR=/app/app/artifacts

CMD ["python", "-m", "app.main"]
