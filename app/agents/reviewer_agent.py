from __future__ import annotations

from app.prompts.system_prompts import REVIEWER_SYSTEM
from app.services.llm import chat


def run_reviewer_agent(market_notes: str, fundamental_notes: str, risk_notes: str, portfolio_notes: str) -> str:
    prompt = f"""
시장: {market_notes}
재무: {fundamental_notes}
리스크: {risk_notes}
포트폴리오: {portfolio_notes}

누락된 근거, 충돌, 과장 가능성을 검토하고 수정 포인트를 3~5개로 정리하라.
"""
    return chat(REVIEWER_SYSTEM, prompt)
