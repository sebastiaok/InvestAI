from __future__ import annotations

from app.prompts.system_prompts import RISK_SYSTEM
from app.services.llm import chat


def _risk_profile_guideline(risk_profile: str | None) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return (
            "보수형 기준: 원금 보전과 변동성 최소화를 우선하라. "
            "최대 손실 가능 구간, 방어적 대응(현금 비중/분할매수/손절 기준)을 구체적으로 제시하라."
        )
    if profile == "aggressive":
        return (
            "공격형 기준: 변동성 허용을 전제로 상승 잠재력과 하방 리스크의 비대칭을 함께 제시하라. "
            "고위험 시나리오와 감내 조건(투자 기간/손실 허용 범위)을 명확히 제시하라."
        )
    return (
        "균형형 기준: 수익 기회와 리스크 관리의 균형을 맞춰라. "
        "기본 시나리오와 스트레스 시나리오를 함께 제시하고, 대응 우선순위를 정리하라."
    )


def run_risk_agent(query: str, market_notes: str, fundamental_notes: str, risk_profile: str | None) -> str:
    guideline = _risk_profile_guideline(risk_profile)
    prompt = f"""
질문: {query}
시장 메모: {market_notes}
재무 메모: {fundamental_notes}
리스크 성향: {risk_profile}
성향별 가이드: {guideline}
하방 리스크와 반대 시나리오를 정리해라.
"""
    return chat(RISK_SYSTEM, prompt)
