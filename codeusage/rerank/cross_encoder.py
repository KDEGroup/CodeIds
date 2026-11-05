from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
from codeusage.build_db import Doc
from pathlib import Path


class CrossEncoderReranker:
    def __init__(
        self,
        model_name_or_path: str,
        ) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name_or_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name_or_path, device_map="auto")
    
    def rerank(
        self,
        query: str,
        docs: list[Doc],
        exclude_path: Path,
        top_k: int
    ) -> list[Doc]:
        if len(docs) == 0:
            return []
        doc_strs = [it.content for it in docs]
        inputs = self.tokenizer(
            [query] * len(docs), doc_strs,
            padding=True,
            truncation=True,
            return_tensors="pt",
        )
        device = self.model.device  
        inputs = {k: v.to(device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits  # shape: [batch_size, 1]
            scores = F.softmax(logits, dim=0).squeeze(dim=1)  # Softmax 

        scored_docs = sorted(zip(docs, scores), key=lambda x: x[1], reverse=True)
        result: list[Doc] = [doc for (doc, score) in scored_docs]
        result = [it for it in result if it.path.resolve() != exclude_path.resolve()]
        return result[:top_k]
