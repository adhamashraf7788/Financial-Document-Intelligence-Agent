FROM python:3.10-slim

WORKDIR /app

# System libraries needed by PDF/image processing
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libgl1 \
    libgomp1 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY services/doc_processor/requirements.txt .

RUN pip install --no-cache-dir --default-timeout=1000 --upgrade pip

# Install your Python dependencies
RUN pip install --no-cache-dir --default-timeout=1000 -r requirements.txt

COPY services/doc_processor/ ./services/doc_processor/
COPY shared/ ./shared/

EXPOSE 8000

CMD ["uvicorn", "services.doc_processor.main:app", "--host", "0.0.0.0", "--port", "8000"]