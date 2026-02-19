from sentence_transformers import SentenceTransformer
import numpy as np

class Embedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> np.ndarray:
        # returns float32 matrix [n, dim]
        embs = self.model.encode(texts, normalize_embeddings=True, show_progress_bar=True)
        return np.asarray(embs, dtype="float32")
