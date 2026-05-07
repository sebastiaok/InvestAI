from __future__ import annotations

import re
from typing import Any

from app.rag.vector_store import build_or_load_vector_store


def _filter_by_ticker(records: list[dict[str, Any]], ticker: str | None) -> list[dict[str, Any]]:
    if not ticker:
        return records
    normalized = ticker.upper()
    filtered = [item for item in records if item.get("ticker") in {normalized, "UNKNOWN", None}]
    return filtered if filtered else records


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[0-9A-Za-z가-힣]+", text.lower()))


def _lexical_overlap_score(query: str, text: str) -> float:
    query_tokens = _tokenize(query)
    if not query_tokens:
        return 0.0
    text_tokens = _tokenize(text)
    if not text_tokens:
        return 0.0
    overlap = query_tokens & text_tokens
    return len(overlap) / len(query_tokens)


def _normalize_vector_similarity(records: list[dict[str, Any]]) -> list[float]:
    if not records:
        return []
    raw_scores = [float(item.get("score", 0.0)) for item in records]
    mn = min(raw_scores)
    mx = max(raw_scores)
    if mx == mn:
        return [1.0 for _ in records]
    return [(mx - value) / (mx - mn) for value in raw_scores]


def _ticker_boost(record_ticker: str | None, target_ticker: str | None) -> float:
    if not target_ticker:
        return 0.0
    if not record_ticker or record_ticker == "UNKNOWN":
        return 0.4
    return 1.0 if record_ticker.upper() == target_ticker.upper() else 0.0


def _rerank_records(records: list[dict[str, Any]], query: str, ticker: str | None) -> list[dict[str, Any]]:
    vector_sim_scores = _normalize_vector_similarity(records)
    reranked: list[dict[str, Any]] = []
    for idx, item in enumerate(records):
        lexical = _lexical_overlap_score(query, item.get("text", ""))
        ticker_score = _ticker_boost(item.get("ticker"), ticker)
        final_score = (0.55 * vector_sim_scores[idx]) + (0.35 * lexical) + (0.10 * ticker_score)
        updated = dict(item)
        updated["raw_score"] = float(item.get("score", 0.0))
        updated["score"] = float(final_score)
        updated["lexical_score"] = float(lexical)
        reranked.append(updated)
    return sorted(reranked, key=lambda row: row["score"], reverse=True)


def retrieve_for_query(
    query: str,
    ticker: str | None = None,
    k: int = 4,
    store_dir: str = "./data/vector_store/faiss",
    research_dir: str = "./data/research",
) -> list[dict[str, Any]]:
    try:
        store = build_or_load_vector_store(input_dir=research_dir, store_dir=store_dir)
    except Exception:
        return []

    search_k = max(k * 2, 6)
    max_search_k = max(k * 8, 24)
    records_by_key: dict[str, dict[str, Any]] = {}

    while True:
        docs_with_scores = store.similarity_search_with_score(query, k=search_k)
        for doc, score in docs_with_scores:
            metadata = doc.metadata or {}
            source_id = str(metadata.get("source_id", "unknown"))
            source_path = str(metadata.get("source_path", ""))
            unique_key = f"{source_id}|{source_path}|{hash(doc.page_content)}"
            candidate = {
                "text": doc.page_content,
                "source_id": source_id,
                "source_path": source_path,
                "doc_type": metadata.get("doc_type", "research_note"),
                "ticker": metadata.get("ticker", "UNKNOWN"),
                "score": float(score),
            }
            previous = records_by_key.get(unique_key)
            if previous is None or candidate["score"] < previous["score"]:
                records_by_key[unique_key] = candidate

        pooled = list(records_by_key.values())
        filtered = _filter_by_ticker(pooled, ticker=ticker)
        if len(filtered) >= k or search_k >= max_search_k:
            break
        search_k = min(search_k * 2, max_search_k)

    reranked = _rerank_records(filtered, query=query, ticker=ticker)
    return reranked[:k]


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
