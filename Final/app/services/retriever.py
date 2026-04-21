from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class ResearchDoc:
    title: str
    content: str


MOCK_DOCS = [
    ResearchDoc(
        title="반도체 업황 메모",
        content="메모리 수급 정상화와 AI 서버 수요 확대로 반도체 업황은 점진 회복 가능성이 있다.",
    ),
    ResearchDoc(
        title="금리와 성장주",
        content="금리 하락 기대는 성장주 밸류에이션에 우호적이지만 환율 변동성은 리스크 요인이다.",
    ),
    ResearchDoc(
        title="포트폴리오 분산 원칙",
        content="동일 섹터 편중은 하락 구간에서 손실 폭을 확대시킬 수 있어 분산이 필요하다.",
    ),
]


def retrieve_research_context(query: str, k: int = 3) -> List[ResearchDoc]:
    scored = []
    tokens = set(query.lower().split())
    for doc in MOCK_DOCS:
        score = sum(1 for token in tokens if token in doc.content.lower() or token in doc.title.lower())
        scored.append((score, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:k]]
