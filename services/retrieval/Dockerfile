FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Install system dependencies for sentence-transformers / torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install PyTorch with CUDA 12.1 support (falls back to CPU if no GPU)
RUN pip install --no-cache-dir --default-timeout=1000 torch --index-url https://download.pytorch.org/whl/cu121

# Install Python dependencies
COPY services/retrieval/requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

# Copy service code and shared schemas
COPY services/retrieval/ ./services/retrieval/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "services.retrieval.main:app", "--host", "0.0.0.0", "--port", "8000"]