from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from typing import List, Tuple, Dict
from collections import Counter
import re

MODEL_NAME = 'all-MiniLM-L6-v2'

class VectorStore:
    def __init__(self):
        self.model = SentenceTransformer(MODEL_NAME)
        self.index = None
        self.ids = []
        self.embeddings = None
        self.texts = []  # Store original texts for keyword search

    def build(self, docs: List[Tuple[str, str]]):
        # docs: list of (id, text)
        texts = [t for (_id, t) in docs]
        self.ids = [d[0] for d in docs]
        self.texts = texts  # Store for hybrid search
        
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

    def search(self, query: str, k: int = 5, hybrid: bool = True, alpha: float = 0.5):
        """
        Search with optional hybrid mode combining vector and keyword search.
        
        Args:
            query: Search query
            k: Number of results to return
            hybrid: If True, combine vector and keyword search
            alpha: Weight for vector search (0-1). (1-alpha) is weight for keyword search
        
        Returns:
            List of dicts with 'id' and 'score'
        """
        if self.index is None:
            return []
        
        # Vector search
        vector_results = self._vector_search(query, k * 2)  # Get more for reranking
        
        if not hybrid:
            return vector_results[:k]
        
        # Keyword search (BM25-like)
        keyword_results = self._keyword_search(query, k * 2)
        
        # Hybrid fusion: combine scores
        combined = self._combine_results(vector_results, keyword_results, alpha)
        
        return combined[:k]
    
    def _vector_search(self, query: str, k: int) -> List[Dict]:
        """Pure vector similarity search"""
        if self.index is None:
            return []
        
        q_emb = self.model.encode([query], convert_to_numpy=True)
        faiss.normalize_L2(q_emb)
        D, I = self.index.search(q_emb, min(k, len(self.ids)))
        
        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < 0 or idx >= len(self.ids):
                continue
            results.append({'id': self.ids[idx], 'score': float(score)})
        return results
    
    def _keyword_search(self, query: str, k: int) -> List[Dict]:
        """Simple keyword-based search with TF-IDF-like scoring"""
        query_terms = self._tokenize(query.lower())
        
        if not query_terms:
            return []
        
        scores = {}
        for idx, text in enumerate(self.texts):
            doc_terms = self._tokenize(text.lower())
            score = self._compute_bm25_score(query_terms, doc_terms, len(self.texts))
            if score > 0:
                scores[idx] = score
        
        # Sort by score and return top k
        sorted_results = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:k]
        
        return [{'id': self.ids[idx], 'score': score} for idx, score in sorted_results]
    
    def _tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        # Remove punctuation and split
        text = re.sub(r'[^\w\s]', ' ', text)
        return [t for t in text.split() if len(t) > 2]  # Filter short words
    
    def _compute_bm25_score(self, query_terms: List[str], doc_terms: List[str], 
                           corpus_size: int, k1: float = 1.5, b: float = 0.75) -> float:
        """
        Simplified BM25 scoring.
        In production, you'd precompute IDF scores and average document length.
        """
        doc_term_freq = Counter(doc_terms)
        doc_len = len(doc_terms)
        avg_doc_len = 100  # Simplified assumption
        
        score = 0.0
        for term in query_terms:
            if term in doc_term_freq:
                tf = doc_term_freq[term]
                # Simplified IDF (would normally be precomputed)
                idf = np.log((corpus_size + 1) / (1 + 1))  # Simplified
                
                # BM25 formula
                numerator = tf * (k1 + 1)
                denominator = tf + k1 * (1 - b + b * (doc_len / avg_doc_len))
                score += idf * (numerator / denominator)
        
        return score
    
    def _combine_results(self, vector_results: List[Dict], keyword_results: List[Dict], 
                        alpha: float) -> List[Dict]:
        """
        Combine vector and keyword results using weighted sum.
        Normalize scores to [0, 1] before combining.
        """
        # Normalize scores
        vector_normalized = self._normalize_scores(vector_results)
        keyword_normalized = self._normalize_scores(keyword_results)
        
        # Combine scores
        combined_scores = {}
        
        for result in vector_normalized:
            doc_id = result['id']
            combined_scores[doc_id] = alpha * result['score']
        
        for result in keyword_normalized:
            doc_id = result['id']
            if doc_id in combined_scores:
                combined_scores[doc_id] += (1 - alpha) * result['score']
            else:
                combined_scores[doc_id] = (1 - alpha) * result['score']
        
        # Sort by combined score
        sorted_results = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)
        
        return [{'id': doc_id, 'score': score} for doc_id, score in sorted_results]
    
    def _normalize_scores(self, results: List[Dict]) -> List[Dict]:
        """Normalize scores to [0, 1] range"""
        if not results:
            return []
        
        scores = [r['score'] for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return [{'id': r['id'], 'score': 1.0} for r in results]
        
        normalized = []
        for r in results:
            norm_score = (r['score'] - min_score) / (max_score - min_score)
            normalized.append({'id': r['id'], 'score': norm_score})
        
        return normalized

