"""호환 레이어: 예전 테스트/외부 참조 이름 `retrieve_research_context`.

신규 코드는 `app.rag.retriever.retrieve_for_query`를 직접 사용한다.
"""

from __future__ import annotations

from app.rag.retriever import format_rag_context, retrieve_for_query


def retrieve_research_context(query: str, ticker: str | None = None, *, k: int = 4) -> list:
    """`retrieve_for_query`의 별칭. 행렬·메타 형식은 동일."""
    return retrieve_for_query(query, ticker=ticker, k=k)


__all__ = ["retrieve_for_query", "retrieve_research_context", "format_rag_context"]
