from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from typing import List, Tuple

MODEL_NAME = 'all-MiniLM-L6-v2'

class VectorStore:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)
        self.index = None
        self.ids = []
        self.embeddings = None

    def build(self, docs: List[Tuple[str, str]]):
        # docs: list of (id, text)
        texts = [t for (_id, t) in docs]
        self.ids = [d[0] for d in docs]
        if len(texts) == 0:
            self.index = None
            return
        emb = self.model.encode(texts, convert_to_numpy=True)
        d = emb.shape[1]
        self.index = faiss.IndexFlatIP(d)
        # normalize for cosine similarity
        faiss.normalize_L2(emb)
        self.index.add(emb)
        self.embeddings = emb

    def search(self, query: str, k: int = 5):
        if self.index is None:
            return []
        q_emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(q_emb)
        D, I = self.index.search(q_emb, k)
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0:
                continue
            results.append({'id': self.ids[idx], 'score': float(score)})
        return results
