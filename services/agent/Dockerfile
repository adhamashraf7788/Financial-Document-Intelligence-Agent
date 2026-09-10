FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY services/agent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/agent/ ./services/agent/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "services.agent.main:app", "--host", "0.0.0.0", "--port", "8000"]