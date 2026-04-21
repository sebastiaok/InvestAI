from __future__ import annotations

from app.services.retriever import retrieve_research_context


def run_research_agent(query: str) -> str:
    docs = retrieve_research_context(query)
    if not docs:
        return "관련 내부 리서치 문서를 찾지 못했다."
    return "\n\n".join([f"[{doc.title}] {doc.content}" for doc in docs])
