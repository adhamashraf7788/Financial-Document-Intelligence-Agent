FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY services/evaluation/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/evaluation/ ./services/evaluation/
COPY shared/ ./shared/
COPY mock-data/ ./mock-data/

EXPOSE 8000

CMD ["uvicorn", "services.evaluation.main:app", "--host", "0.0.0.0", "--port", "8000"]