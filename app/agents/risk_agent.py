from __future__ import annotations

from app.prompts.system_prompts import RISK_SYSTEM
from app.services.llm import chat


def run_risk_agent(query: str, market_notes: str, fundamental_notes: str) -> str:
    prompt = f"""
질문: {query}
시장 메모: {market_notes}
재무 메모: {fundamental_notes}
하방 리스크와 반대 시나리오를 정리해라.
"""
    return chat(RISK_SYSTEM, prompt)
