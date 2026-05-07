from __future__ import annotations

from typing import Any

from app.rag.vector_store import build_or_load_vector_store


def _filter_by_ticker(records: list[dict[str, Any]], ticker: str | None) -> list[dict[str, Any]]:
    if not ticker:
        return records
    normalized = ticker.upper()
    filtered = [item for item in records if item.get("ticker") in {normalized, "UNKNOWN", None}]
    return filtered if filtered else records


def retrieve_for_query(
    query: str,
    ticker: str | None = None,
    k: int = 4,
    store_dir: str = "./data/vector_store/faiss",
    research_dir: str = "./data/research",
) -> list[dict[str, Any]]:
    try:
        store = build_or_load_vector_store(input_dir=research_dir, store_dir=store_dir)
        docs_with_scores = store.similarity_search_with_score(query, k=max(k * 2, 6))
    except Exception:
        return []

    records: list[dict[str, Any]] = []
    for doc, score in docs_with_scores:
        metadata = doc.metadata or {}
        records.append(
            {
                "text": doc.page_content,
                "source_id": metadata.get("source_id", "unknown"),
                "source_path": metadata.get("source_path", ""),
                "doc_type": metadata.get("doc_type", "research_note"),
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "score": float(score),
            }
        )

    filtered = _filter_by_ticker(records, ticker=ticker)
    return filtered[:k]


def format_rag_context(items: list[dict[str, Any]]) -> str:
    if not items:
        return "RAG 근거 없음"
    lines: list[str] = []
    for item in items:
        snippet = item.get("text", "")[:280].strip()
        lines.append(
            f"[{item.get('source_id','unknown')}|{item.get('doc_type','research_note')}|score={item.get('score',0):.4f}] {snippet}"
        )
    return "\n".join(lines)
