FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Создать директории для артефактов
RUN mkdir -p app/artifacts/handoffs app/artifacts/reports

ENV PYTHONPATH=/app
ENV ARTIFACTS_DIR=/app/app/artifacts

CMD ["python", "-m", "app.main"]
