FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# CPU-only PyTorch (smaller, faster download). Remove --index-url for CUDA if GPU available.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY services/reranker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/reranker/ ./services/reranker/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "services.reranker.main:app", "--host", "0.0.0.0", "--port", "8000"]