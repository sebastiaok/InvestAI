from __future__ import annotations

from app.prompts.system_prompts import REPORT_SYSTEM
from app.services.llm import chat


def run_report_agent(query: str, market_notes: str, fundamental_notes: str, risk_notes: str, portfolio_notes: str, research_context: str, review_notes: str) -> str:
    prompt = f"""
질문: {query}
시장 메모: {market_notes}
재무 메모: {fundamental_notes}
리스크 메모: {risk_notes}
포트폴리오 메모: {portfolio_notes}
RAG 컨텍스트: {research_context}
리뷰어 수정 포인트: {review_notes}

다음 형식으로 최종 투자 브리프를 작성하라.
1. 한줄 결론
2. 핵심 근거 3개
3. 리스크 3개
4. 포트폴리오 관점 메모
5. 추가 확인 필요 항목
"""
    return chat(REPORT_SYSTEM, prompt)
