from typing import List
from sentence_transformers import SentenceTransformer

class BGEM3EmbeddingProvider:
    def __init__(self, model_name: str = "BAAI/bge-m3"):
        self.model = SentenceTransformer(model_name)

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    def generate_embedding(self, text: str) -> List[float]:
        return self.generate_embeddings([text])[0]