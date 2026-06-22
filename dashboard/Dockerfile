FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY checker/ ./checker/
COPY dashboard/ ./dashboard/
ENV EXPIRY_WATCHER_DB=/app/results.db
ENV EXPIRY_WATCHER_CHECK_INTERVAL_HOURS=6
CMD ["uvicorn", "dashboard.main:app", "--host", "0.0.0.0", "--port", "8080"]
