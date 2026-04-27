from __future__ import annotations

from app.prompts.system_prompts import PORTFOLIO_SYSTEM
from app.services.llm import chat
from app.services.market_tools import parse_portfolio_text


def run_portfolio_agent(query: str, portfolio_text: str | None) -> str:
    portfolio = parse_portfolio_text(portfolio_text)
    prompt = f"""
질문: {query}
포트폴리오: {portfolio}
집중도, 분산도, 기존 보유 종목과의 관계를 분석해라.
"""
    return chat(PORTFOLIO_SYSTEM, prompt)
