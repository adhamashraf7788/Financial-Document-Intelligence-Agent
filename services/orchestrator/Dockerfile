FROM python:3.11-slim

WORKDIR /app

COPY services/orchestrator/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY services/orchestrator ./services/orchestrator
COPY shared ./shared

EXPOSE 8000

CMD ["uvicorn", "services.orchestrator.main:app", "--host", "0.0.0.0", "--port", "8000"]