from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

import httpx


TICKER_ALIAS = {
    "삼성전자": "005930.KS",
    "sk하이닉스": "000660.KS",
    "하이닉스": "000660.KS",
    "네이버": "035420.KS",
    "카카오": "035720.KS",
    "apple": "AAPL",
    "애플": "AAPL",
    "microsoft": "MSFT",
    "마이크로소프트": "MSFT",
    "tesla": "TSLA",
    "테슬라": "TSLA",
    "nvidia": "NVDA",
    "엔비디아": "NVDA",
}


def normalize_ticker_input(value: str | None) -> str | None:
    """Allow stock name input and normalize into a ticker-like string."""
    if not value:
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    mapped = TICKER_ALIAS.get(cleaned.lower()) or TICKER_ALIAS.get(cleaned)
    if mapped:
        return mapped

    # If user already entered a ticker-like value, keep canonical uppercase form.
    return cleaned.upper()


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


def fetch_quote_data(ticker: str | None) -> Dict:
    normalized = ticker or "AAPL"
    url = "https://query1.finance.yahoo.com/v7/finance/quote"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url, params={"symbols": normalized})
            response.raise_for_status()
        result = response.json().get("quoteResponse", {}).get("result", [])
        if not result:
            raise ValueError("No quote result")
        quote = result[0]
        return {
            "ticker": quote.get("symbol", normalized),
            "price": quote.get("regularMarketPrice"),
            "change_percent": quote.get("regularMarketChangePercent"),
            "market_state": quote.get("marketState"),
            "source": "Yahoo Finance Quote API",
            "url": f"https://finance.yahoo.com/quote/{quote.get('symbol', normalized)}",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        fallback = get_market_snapshot(normalized)
        fallback.update(
            {
                "source": "mock_quote_fallback",
                "url": "",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return fallback


def fetch_news_data(ticker: str | None, limit: int = 5) -> Dict:
    search_term = ticker or "stock market"
    rss_url = "https://news.google.com/rss/search"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(rss_url, params={"q": search_term, "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
            response.raise_for_status()
        items = []
        body = response.text
        chunks = body.split("<item>")
        for chunk in chunks[1 : limit + 1]:
            title = _extract_between(chunk, "<title>", "</title>")
            link = _extract_between(chunk, "<link>", "</link>")
            pub_date = _extract_between(chunk, "<pubDate>", "</pubDate>")
            items.append({"title": title, "url": link, "published": pub_date})
        if not items:
            raise ValueError("No news items")
        return {
            "ticker": ticker or "UNKNOWN",
            "items": items,
            "source": "Google News RSS",
            "url": "https://news.google.com",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        snapshot = get_market_snapshot(ticker)
        fallback_items = [{"title": headline, "url": "", "published": ""} for headline in snapshot.get("top_news", [])]
        return {
            "ticker": ticker or "UNKNOWN",
            "items": fallback_items[:limit],
            "source": "mock_news_fallback",
            "url": "",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }


def fetch_fundamental_data(ticker: str | None) -> Dict:
    normalized = ticker or "AAPL"
    url = f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{normalized}"
    try:
        with httpx.Client(timeout=8.0) as client:
            response = client.get(url, params={"modules": "financialData,defaultKeyStatistics"})
            response.raise_for_status()
        result = response.json().get("quoteSummary", {}).get("result", [])
        if not result:
            raise ValueError("No fundamentals result")
        payload = result[0]
        financial_data = payload.get("financialData", {})
        key_stats = payload.get("defaultKeyStatistics", {})
        return {
            "ticker": normalized,
            "target_mean_price": _read_raw(financial_data, "targetMeanPrice"),
            "recommendation_key": financial_data.get("recommendationKey"),
            "forward_pe": _read_raw(key_stats, "forwardPE"),
            "peg_ratio": _read_raw(key_stats, "pegRatio"),
            "source": "Yahoo Finance QuoteSummary API",
            "url": f"https://finance.yahoo.com/quote/{normalized}/analysis",
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception:
        fallback = get_fundamental_snapshot(normalized)
        fallback.update(
            {
                "source": "mock_fundamental_fallback",
                "url": "",
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        return fallback


def _read_raw(container: Dict, key: str):
    value = container.get(key)
    if isinstance(value, dict):
        return value.get("raw", value.get("fmt"))
    return value


def _extract_between(content: str, start: str, end: str) -> str:
    if start not in content or end not in content:
        return ""
    return content.split(start, 1)[1].split(end, 1)[0].strip()


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
