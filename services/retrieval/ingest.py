import json
import os
from pathlib import Path

from services.retrieval.chunker import DocumentChunker
from services.retrieval.embedding import BGEM3EmbeddingProvider
from services.retrieval.weaviate import WeaviateStore
from shared.schemas import DocumentProcessorResponse

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "dev"


def ingest_all_documents(folder_path: Path):
    if not folder_path.exists():
        print(f"Error: Folder {folder_path} does not exist.")
        return

    print("Connecting to Weaviate and initializing models...")
    weaviate_store = WeaviateStore(port=8085, grpc_port=50052)
    embedder = BGEM3EmbeddingProvider()
    chunker = DocumentChunker()

    # Get collection reference from the weaviate_store
    collection = weaviate_store.client.collections.get("DocumentChunk")

    # skip processed files
    print("Checking already indexed documents...")
    indexed_doc_ids = set()
    try:
        for obj in collection.iterator(return_properties=["doc_id"]):
            doc_id = obj.properties.get("doc_id")
            if doc_id:
                indexed_doc_ids.add(doc_id)
        print(f"Found {len(indexed_doc_ids)} unique documents already indexed.")
    except Exception as e:
        print(f"Notice: Could not fetch existing records ({e}). Proceeding from start.")

    json_files = list(folder_path.glob("*.json"))
    print(f"Found {len(json_files)} total JSON files in directory.")

    total_chunks = 0

    for file_path in json_files:
        # Check if file stem or document ID was already processed
        if file_path.stem in indexed_doc_ids:
            print(f"Skipping {file_path.name} (Already indexed)")
            continue

        print(f"Processing: {file_path.name}")
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Validate against Pydantic schema
            parsed_doc = DocumentProcessorResponse(**data)

            # Generate Chunks
            chunks = chunker.process_parsed_document(parsed_doc)
            if not chunks:
                print(f"No chunks created for {file_path.name}")
                continue

            # Generate Embeddings & Insert into Weaviate
            texts = [chunk.text for chunk in chunks]
            embeddings = embedder.generate_embeddings(texts)

            weaviate_store.insert_chunks(chunks, embeddings)

            total_chunks += len(chunks)
            print(f"  └─ Successfully indexed {len(chunks)} chunks.")

        except Exception as e:
            print(f"Failed to process {file_path.name}: {e}")

    weaviate_store.close()
    print(f"Ingestion complete. Total new chunks indexed: {total_chunks}")


if __name__ == "__main__":
    ingest_all_documents(DATA_DIR)