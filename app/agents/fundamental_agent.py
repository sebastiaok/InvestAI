from __future__ import annotations

from app.prompts.system_prompts import FUNDAMENTAL_SYSTEM
from app.services.llm import chat
from app.services.market_tools import get_fundamental_snapshot


def run_fundamental_agent(query: str, ticker: str | None) -> str:
    snapshot = get_fundamental_snapshot(ticker)
    prompt = f"""
질문: {query}
기초재무 데이터: {snapshot}
재무/실적/밸류에이션 관점 요약을 작성해라.
"""
    return chat(FUNDAMENTAL_SYSTEM, prompt)
