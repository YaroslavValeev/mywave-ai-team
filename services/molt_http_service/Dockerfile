# Molt HTTP runtime — build from Agents repo root:
#   docker compose -f docker-compose.yml -f docker-compose.server-full.yml \
#     -f docker-compose.molt.yml --profile molt up -d --build
FROM python:3.11-slim

WORKDIR /app

COPY packages/shared-core /app/packages/shared-core
COPY packages/agents-http-client /app/packages/agents-http-client
COPY services/molt_http_service /app/services/molt_http_service

RUN pip install --no-cache-dir "fastapi>=0.100,<0.140" "uvicorn[standard]>=0.22,<1"

ENV PYTHONPATH=/app/packages/shared-core:/app/packages/agents-http-client:/app/services
ENV MOLT_HTTP_HOST=0.0.0.0
ENV MOLT_HTTP_PORT=8765
ENV CANONICAL_PATH_ENABLED=1
ENV CANONICAL_STORAGE=sqlite
ENV CANONICAL_SQLITE_PATH=/data/canonical.db
# Default: talk to Agents app on compose network
ENV AGENTS_CONTROL_API_URL=http://app:8080
ENV AGENTS_CONTROL_ENABLED=1

RUN mkdir -p /data
VOLUME ["/data"]
EXPOSE 8765

CMD ["python", "-m", "uvicorn", "molt_http_service.app:app", "--host", "0.0.0.0", "--port", "8765"]
