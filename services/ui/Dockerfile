FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY services/ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ui/ ./services/ui/
COPY mock-data/ ./mock-data/

EXPOSE 7860

CMD ["python", "services/ui/app.py"]