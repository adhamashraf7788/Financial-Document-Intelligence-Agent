import hashlib
import uuid
import weaviate
import weaviate.classes.config as wvc
from typing import List, Dict, Any
from shared.schemas import Chunk
import json
import weaviate.classes.query as wvc_query

class WeaviateStore:
    def __init__(self, host: str = "localhost", port: int = 8085, collection_name: str = "DocumentChunk"):
        self.client = weaviate.connect_to_local(host=host, port=port)
        self.collection_name = collection_name
        self._ensure_collection()


    def _ensure_collection(self):
            if not self.client.collections.exists(self.collection_name):
                self.client.collections.create(
                    name=self.collection_name,

                    # Don't use the builtin embedding module
                    vectorizer_config=wvc.Configure.Vectorizer.none(),

                    # Database Schema
                    properties=[
                        wvc.Property(name="chunk_id", data_type=wvc.DataType.TEXT, tokenization=wvc.Tokenization.FIELD),
                        wvc.Property(name="document_id", data_type=wvc.DataType.TEXT, tokenization=wvc.Tokenization.FIELD),
                        wvc.Property(name="page", data_type=wvc.DataType.INT),
                        wvc.Property(name="section", data_type=wvc.DataType.TEXT),
                        wvc.Property(name="content_type", data_type=wvc.DataType.TEXT),
                        wvc.Property(name="text", data_type=wvc.DataType.TEXT, tokenization=wvc.Tokenization.WORD),
                        wvc.Property(
                            name="metadata",
                            data_type=wvc.DataType.OBJECT,
                            nested_properties=[
                                wvc.Property(name="is_complete_table", data_type=wvc.DataType.BOOL),
                                wvc.Property(name="num_rows", data_type=wvc.DataType.INT),
                                wvc.Property(name="row_start", data_type=wvc.DataType.INT),
                                wvc.Property(name="row_end", data_type=wvc.DataType.INT),
                                wvc.Property(name="is_parent", data_type=wvc.DataType.BOOL),
                                wvc.Property(name="parent_id", data_type=wvc.DataType.TEXT),
                            ]
                        ),
                    ]
                )


    # create deterministic hex from chunk_id
    # formats it as a standard 8-4-4-4-12 UUID string required by Weaviate
    def _generate_hex_uuid(self, chunk_id: str) -> str:
        hex_hash = hashlib.sha256(chunk_id.encode("utf-8")).hexdigest()[:32]
        formatted_uuid = f"{hex_hash[:8]}-{hex_hash[8:12]}-{hex_hash[12:16]}-{hex_hash[16:20]}-{hex_hash[20:32]}"
        return formatted_uuid

    def insert_chunks(self, chunks: List[Chunk], embeddings: List[List[float]]):
        collection = self.client.collections.get(self.collection_name)

        # opens dynamic batching context
        with collection.batch.dynamic() as batch:
            for chunk, vector in zip(chunks, embeddings):

                # Deterministic hex UUID generation ( using sha256 hashing )
                weaviate_uuid = self._generate_hex_uuid(chunk.chunk_id)
                
                properties = {"chunk_id": chunk.chunk_id,
                              "document_id": chunk.document_id,
                              "page": chunk.page,
                              "section": chunk.section,
                              "content_type": chunk.content_type,
                              "text": chunk.text,
                              }
                
                batch.add_object(properties=properties,
                                 vector=vector,
                                 uuid=weaviate_uuid
                                 )


    # Gets the contents of the Vector DB
    def fetch_all_chunks(self, limit: int = 100) -> List[Dict[str, Any]]:
        collection = self.client.collections.get(self.collection_name)
        results = []
        
        # Iterate through objects in the collection
        for obj in collection.iterator():
            results.append({
                "chunk_id": obj.properties.get("chunk_id"),
                "document_id": obj.properties.get("document_id"),
                "page": obj.properties.get("page"),
                "section": obj.properties.get("section"),
                "content_type": obj.properties.get("content_type"),
                "text": obj.properties.get("text"),
                "metadata": obj.properties.get("metadata", {})
            })
            if len(results) >= limit:
                break
                
        return results



    # Vector Search Only
    def vector_search(self, query_vector: List[float], limit: int = 30) -> List[Dict[str, Any]]:
        collection = self.client.collections.get(self.collection_name)
        response = collection.query.near_vector(
            near_vector=query_vector,
            limit=limit,
            return_metadata=wvc_query.MetadataQuery(distance=True, certainty=True)
        )
        return self._format_response_objects(response.objects, score_attr="certainty")




    # BM25 Search Only
    def bm25_search(self, query_text: str, limit: int = 30) -> List[Dict[str, Any]]:
        collection = self.client.collections.get(self.collection_name)
        response = collection.query.bm25(
            query=query_text,
            limit=limit,
            return_metadata=wvc_query.MetadataQuery(score=True)
        )
        return self._format_response_objects(response.objects, score_attr="score")




    #  Hybrid Search (Vector + BM25)
    def hybrid_search(self, query_text: str, query_vector: List[float], alpha: float = 0.5, limit: int = 30) -> List[Dict[str, Any]]:
        collection = self.client.collections.get(self.collection_name)
        response = collection.query.hybrid(
            query=query_text,
            vector=query_vector,
            alpha=alpha,
            limit=limit,
            return_metadata=wvc_query.MetadataQuery(score=True)
        )
        return self._format_response_objects(response.objects, score_attr="score")




    # Helper method to format search responses
    def _format_response_objects(self, objects, score_attr: str = "score") -> List[Dict[str, Any]]:
        results = []
        for obj in objects:
            metadata_val = obj.properties.get("metadata")
            if isinstance(metadata_val, str):
                try:
                    metadata_val = json.loads(metadata_val)
                except Exception:
                    metadata_val = {}

            score = getattr(obj.metadata, score_attr, 0.0) if obj.metadata else 0.0

            results.append({
                "chunk_id": obj.properties.get("chunk_id"),
                "document_id": obj.properties.get("document_id"),
                "page": obj.properties.get("page"),
                "section": obj.properties.get("section"),
                "content_type": obj.properties.get("content_type"),
                "text": obj.properties.get("text"),
                "score": float(score) if score is not None else 0.0,
                "metadata": metadata_val or {}
            })
        return results



    def close(self):
        self.client.close()