from __future__ import annotations

from app.prompts.system_prompts import MARKET_SYSTEM
from app.services.llm import chat
from app.services.market_tools import get_market_snapshot


def run_market_agent(query: str, ticker: str | None) -> str:
    snapshot = get_market_snapshot(ticker)
    prompt = f"""
질문: {query}
시장 데이터: {snapshot}
위 자료를 바탕으로 시장 관점 핵심 요약을 작성해라.
"""
    return chat(MARKET_SYSTEM, prompt)
