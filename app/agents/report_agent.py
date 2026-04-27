from __future__ import annotations

from app.prompts.system_prompts import REPORT_SYSTEM
from app.services.llm import chat


def _report_profile_instruction(risk_profile: str | None) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return (
            "보수형 리포트 작성: 방어적 결론을 우선하고, 리스크 경감 전략(현금 비중, 분산, 손절 라인)을 "
            "구체적이고 실행 가능하게 제시하라."
        )
    if profile == "aggressive":
        return (
            "공격형 리포트 작성: 성장 기회와 기대 수익 논리를 강조하되, 변동성 확대와 손실 가능성도 "
            "동일 비중으로 명시하라."
        )
    return (
        "균형형 리포트 작성: 기대 수익과 리스크 관리 전략을 균형 있게 제시하고, "
        "중립적 실행 계획(분할매수/비중조절)을 포함하라."
    )


def run_report_agent(
    query: str,
    risk_profile: str | None,
    market_notes: str,
    fundamental_notes: str,
    risk_notes: str,
    portfolio_notes: str,
    review_notes: str,
) -> str:
    profile_instruction = _report_profile_instruction(risk_profile)
    prompt = f"""
질문: {query}
리스크 성향: {risk_profile}
성향별 리포트 지침: {profile_instruction}
시장 메모: {market_notes}
재무 메모: {fundamental_notes}
리스크 메모: {risk_notes}
포트폴리오 메모: {portfolio_notes}
리뷰어 수정 포인트: {review_notes}

다음 형식으로 최종 투자 브리프를 작성하라.
1. 한줄 결론
2. 핵심 근거 3개
3. 리스크 3개
4. 포트폴리오 관점 메모
5. 추가 확인 필요 항목
"""
    return chat(REPORT_SYSTEM, prompt)
