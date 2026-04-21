from __future__ import annotations

from app.prompts.system_prompts import PLANNER_SYSTEM
from app.services.llm import json_chat


def run_planner(query: str, ticker: str | None, portfolio_text: str | None) -> dict:
    prompt = f"""
사용자 질문: {query}
티커: {ticker}
포트폴리오 정보: {portfolio_text}

아래 키를 포함한 JSON을 반환해라.
- objective
- tasks: market, fundamental, risk, portfolio, research에 대한 true/false
- output_style
"""
    return json_chat(PLANNER_SYSTEM, prompt)
