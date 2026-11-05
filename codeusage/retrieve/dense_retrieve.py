import torch
import numpy as np
from pathlib import Path
from typing import List
from transformers.tokenization_utils import PreTrainedTokenizer
from transformers.modeling_utils import PreTrainedModel
from sklearn.metrics.pairwise import cosine_similarity
from dataclasses import dataclass
import torch.nn.functional as F
from .common import Doc


class DenseElementIndexer:
    """
    Dense vector-based indexer using the transformers library.
    """
    def __init__(self, tokenizer, model) -> None:
        self.tokenizer = tokenizer
        self.model = model
        self.device = model.device
        self.keys: List[str] = []
        self.embeddings: torch.Tensor = torch.empty(0)
        self.empty: bool = True

    def _encode(self, texts: List[str]) -> torch.Tensor:
        """
        Encode a list of texts into dense embeddings using the model.
        """
        batch_embedding_results = []
        batch_size = 256
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            inputs = self.tokenizer(batch_texts, padding=True, truncation=True, return_tensors="pt").to(self.device)
            with torch.no_grad():
                # (batch_size, emb_dim)
                outputs = self.model(**inputs)
                batch_embedding_results.append(outputs)
        # (len(texts), emb_dim)
        return torch.cat(batch_embedding_results, 0)

    def fit(self, elements: list[Doc]) -> None:
        if len(elements) == 0:
            self.empty = True
            return
        self.empty = False
        """
        Build the dense vector index from a list of elements.
        """
        self.keys = [it.content for it in elements]
        self.meta = list(elements)
        if len(self.keys) > 0:
            self.embeddings = self._encode(self.keys)

    def search(self, query: str, k: int = 5) -> List[Doc]:
        """
        Search for the top-k most similar elements to the query.
        """
        if self.empty:
            return []
        # (1, emb_dim)
        query_embedding = self._encode([query])
        similarities = F.cosine_similarity(query_embedding, self.embeddings)
        k = min(k, similarities.size(0))
        topk_scores, topk_indices = torch.topk(similarities, k)
        return [self.meta[i] for i in topk_indices]



def dense_retrieve_docs(
    docs: list[Doc],
    query: str,
    exclude_path: Path,
    top_k: int,
    tokenizer: PreTrainedTokenizer,
    model: PreTrainedModel,
) -> list[Doc]:
    
    docs = [it for it in docs if not it.path.resolve() == exclude_path.resolve()]
    if len(docs) == 0 or query.strip() == "":
        return []

    indexer = DenseElementIndexer(
        tokenizer=tokenizer,
        model=model
    )
    indexer.fit(docs)
    return indexer.search(query=query, k=top_k)