from __future__ import annotations

from typing import Dict, List


def get_market_snapshot(ticker: str | None) -> Dict:
    return {
        "ticker": ticker or "UNKNOWN",
        "price_trend": "최근 1개월 변동성 확대",
        "market_sentiment": "중립~약강세",
        "top_news": [
            "주요 종목 관련 산업 수요 회복 기대",
            "환율과 금리 불확실성 지속",
            "기관 수급 변동성 확대",
        ],
    }


def get_fundamental_snapshot(ticker: str | None) -> Dict:
    return {
        "ticker": ticker or "UNKNOWN",
        "earnings": "최근 분기 실적은 시장 기대 대비 보합",
        "valuation": "밸류에이션 매력은 중간 수준",
        "balance_sheet": "현금흐름/재무안정성은 보통 이상",
    }


def parse_portfolio_text(portfolio_text: str | None) -> List[Dict]:
    if not portfolio_text:
        return []
    lines = [line.strip() for line in portfolio_text.splitlines() if line.strip()]
    results = []
    for line in lines:
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            results.append({"asset": parts[0], "weight": parts[1]})
        else:
            results.append({"asset": line, "weight": "unknown"})
    return results
