from __future__ import annotations

from app.prompts.system_prompts import PLANNER_SYSTEM
from app.services.llm import json_chat


def _planner_profile_hint(risk_profile: str | None) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return "보수형: 리스크 점검과 자본보전 항목의 우선순위를 높여 계획하라."
    if profile == "aggressive":
        return "공격형: 성장 모멘텀/업사이드 분석 비중을 높이고 리스크 허용 범위를 함께 명시하라."
    return "균형형: 수익 기회와 리스크 관리가 균형되도록 계획 우선순위를 배치하라."


def run_planner(query: str, ticker: str | None, portfolio_text: str | None, risk_profile: str | None) -> dict:
    profile_hint = _planner_profile_hint(risk_profile)
    prompt = f"""
사용자 질문: {query}
티커: {ticker}
포트폴리오 정보: {portfolio_text}
리스크 성향: {risk_profile}
성향별 계획 지침: {profile_hint}

아래 키를 포함한 Plan 흐름도를 작성해라.
- objective
- tasks: market, fundamental, risk, portfolio에 대한 true/false
- output_style
"""
    return json_chat(PLANNER_SYSTEM, prompt)
