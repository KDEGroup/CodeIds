from rank_bm25 import BM25Okapi
from .extract_tokens_with_tree_sitter import extract_tokens_with_tree_sitter
from pathlib import Path
from codeusage.build_db import Doc, split_by_lines
from pydantic import BaseModel
import contexttimer

class SparseTimeConsuming(BaseModel):
    index_ms: int | None = None
    search_ms: int | None = None

def sparse_retrieve(
    repo_path: Path,
    query: str,
    exclude_path: Path,
    top_k: int,
    time_consuming: SparseTimeConsuming | None = None
) -> list[Doc]:
    if time_consuming is None:
        time_consuming = SparseTimeConsuming()

    with contexttimer.Timer(factor=1000) as t:
        docs = split_by_lines(
            repo_path=repo_path,
            each_line_n=6,
            overlap=3
        )
        docs = [it for it in docs if not it.path.resolve() == exclude_path.resolve()]
    time_consuming.index_ms = round(t.elapsed)

    return sparse_retrieve_docs(
        docs=docs,
        query=query,
        exclude_path=exclude_path,
        top_k=top_k,
        time_consuming=time_consuming
    )

def sparse_retrieve_docs(
    docs: list[Doc],
    query: str,
    exclude_path: Path,
    top_k: int,
    time_consuming: SparseTimeConsuming | None = None
) -> list[Doc]:
    if time_consuming is None:
        time_consuming = SparseTimeConsuming()
    with contexttimer.Timer(factor=1000) as t:
        docs = [it for it in docs if not it.path.resolve() == exclude_path.resolve()]
        corpus_tokens = [extract_tokens_with_tree_sitter(it.content) for it in docs]
        corpus_tokens = [it for it in corpus_tokens if len(it) > 0]
        if len(corpus_tokens) == 0 or query.strip() == "":
            return []
        bm25 = BM25Okapi(corpus_tokens)
    time_consuming.index_ms = round(t.elapsed)

    with contexttimer.Timer(factor=1000) as t:
        query_tokens = extract_tokens_with_tree_sitter(query)
        scores = bm25.get_scores(query_tokens)
    time_consuming.search_ms = round(t.elapsed)

    top_k_result = sorted(zip(scores, docs), reverse=True, key=lambda x: x[0])[:top_k]
    return [it[1] for it in top_k_result]
