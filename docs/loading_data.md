# Loading Pre-Processed Weaviate Data

This guide explains how to load the provided **chunked and indexed data** into the local Weaviate database and verify that the data has been loaded successfully.

## 1. Download the Processed Data

Download the pre-processed Weaviate data from:

[Processed Weaviate Data](https://drive.google.com/file/d/1_rRLtj4nMVSBR5JV7zchN5c71rL0SSvq/view?usp=sharing)

The downloaded file should be named:

```text
processed_weaviate_data.tar.gz
```

## 2. Move the File to the Project Root

Navigate to the project directory:


***/Financial-Document-Intelligence-Agent***


Place `processed_weaviate_data.tar.gz` directly inside the project root.

## 3. Extract the Data

Extract the archive:

```bash
tar -xzvf processed_weaviate_data.tar.gz
```

This will create or update:

```text
./data/processed/
```

The `data/processed` directory contains the **pre-chunked and pre-indexed Weaviate data**, so the indexing pipeline does not need to be executed again.

## 4. Start Weaviate

Start the Weaviate Docker container using the processed data directory as the persistent storage volume:

```bash
docker run -d \
  --name weaviate \
  -p 8085:8080 \
  -p 50052:50051 \
  -v "$(pwd)/data/processed":/var/lib/weaviate \
  -e QUERY_DEFAULTS_LIMIT=25 \
  -e AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED='true' \
  -e PERSISTENCE_DATA_PATH='/var/lib/weaviate' \
  -e DEFAULT_VECTORIZER_MODULE='none' \
  -e DISK_USE_WARNING_PERCENTAGE=95 \
  -e DISK_USE_READONLY_PERCENTAGE=98 \
  semitechnologies/weaviate:latest
```

> **Note:** If a Weaviate container with the name `weaviate` already exists, remove or stop it before running the command above.

## 5. Verify the Database

Once the container is running, verify that the processed data has been loaded successfully:

```bash
python -m services.retrieval.DB_verification
```

The verification script should confirm that the expected data is available in Weaviate.

---

# Indexing New Data

If you want to **index a new set of documents** instead of loading the provided pre-processed data, use the ingestion pipeline.

First, make sure the `DATA_DIR` path in:

```text
services/retrieval/ingest.py
```

points to the directory containing the documents you want to index.

Then run:

```bash
python -m services.retrieval.ingest
```

After the ingestion process finishes, verify the database:

```bash
python -m services.retrieval.DB_verification
```
