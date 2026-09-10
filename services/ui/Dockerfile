FROM python:3.11-slim

WORKDIR /app

COPY services/ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/ui/ ./services/ui/
COPY shared/ ./shared/

EXPOSE 7860

CMD ["python", "services/ui/app.py"]