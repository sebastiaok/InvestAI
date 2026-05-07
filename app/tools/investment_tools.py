from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.rag.retriever import format_rag_context, retrieve_for_query
from app.services.market_tools import fetch_fundamental_data, fetch_news_data, fetch_quote_data, parse_portfolio_text
from app.tools.mcp_tools import optional_mcp_tools


def extend_with_optional_mcp(core: list[StructuredTool]) -> list[StructuredTool]:
    """코어 LangChain 도구 목록 뒤에 환경 설정 시 MCP 확장 도구를 붙인다."""
    return [*core, *optional_mcp_tools()]


class TickerInput(BaseModel):
    ticker: Optional[str] = Field(default=None, description="Ticker symbol like AAPL or 005930.KS")


class NewsInput(BaseModel):
    ticker: Optional[str] = Field(default=None, description="Ticker symbol like AAPL or 005930.KS")
    limit: int = Field(default=5, ge=1, le=10)


class PortfolioHoldingsInput(BaseModel):
    portfolio_text: Optional[str] = Field(
        default="", description="Raw portfolio lines (종목, 비중) pasted by user"
    )


class RagSearchInput(BaseModel):
    query: str = Field(..., description="연구 노트 검색 질의(키워드·질문 형태 모두 가능)")
    ticker: Optional[str] = Field(
        default=None, description="선택 시 메타 ticker(예: 005930.KS)로 후보를 좁힘; 없으면 전체 검색"
    )
    k: int = Field(default=6, ge=1, le=16)


def _quote_tool(ticker: Optional[str] = None) -> dict[str, Any]:
    return fetch_quote_data(ticker)


def _news_tool(ticker: Optional[str] = None, limit: int = 5) -> dict[str, Any]:
    return fetch_news_data(ticker, limit=limit)


def _fundamental_tool(ticker: Optional[str] = None) -> dict[str, Any]:
    return fetch_fundamental_data(ticker)


def _portfolio_holdings_tool(portfolio_text: Optional[str] = None) -> dict[str, Any]:
    holdings = parse_portfolio_text(portfolio_text or None)
    return {
        "holdings": holdings,
        "line_count": len(holdings),
        "source": "user_portfolio_structure",
        "url": "",
        "title": "parsed_holdings",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def _rag_search_tool(query: str, ticker: Optional[str] = None, k: int = 6) -> dict[str, Any]:
    chunks = retrieve_for_query(query.strip(), ticker=ticker, k=k)
    return {
        "chunk_count": len(chunks),
        "chunks": chunks,
        "formatted_context": format_rag_context(chunks),
        "source": "faiss_vector_store",
    }


def get_rag_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_rag_search_tool,
            name="rag_search",
            description=(
                "내부 리서치/전처리 벡터 스토어(FAISS)에서 질문에 맞는 구절을 검색한다. "
                "외부 증거를 단정하지 못할 때 또는 리서치 메모 근거가 필요할 때 먼저 호출한다."
            ),
            args_schema=RagSearchInput,
        )
    ]


def get_market_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_quote_tool,
            name="quote_lookup",
            description="Look up latest market quote and market state for a ticker.",
            args_schema=TickerInput,
        ),
        StructuredTool.from_function(
            func=_news_tool,
            name="news_lookup",
            description="Fetch recent market news headlines and links for a ticker.",
            args_schema=NewsInput,
        ),
    ]


def get_fundamental_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_fundamental_tool,
            name="fundamental_lookup",
            description="Fetch financial and valuation indicators for a ticker.",
            args_schema=TickerInput,
        )
    ]


def get_risk_tools() -> list[StructuredTool]:
    return [*get_market_tools(), *get_fundamental_tools()]


def get_portfolio_tools() -> list[StructuredTool]:
    return [
        StructuredTool.from_function(
            func=_portfolio_holdings_tool,
            name="portfolio_holdings",
            description="Parse user portfolio lines into structured holdings for concentration analysis.",
            args_schema=PortfolioHoldingsInput,
        )
    ]


def get_planner_tools() -> list[StructuredTool]:
    """Planner: 근거가 불확실하면 RAG·시장 도구를 먼저 호출한 뒤 JSON 플랜을 낸다."""
    return [*get_rag_tools(), *get_market_tools()]


def get_reviewer_tools() -> list[StructuredTool]:
    """리뷰어: 검증 중 리서치 출처 재확인이 필요하면 rag_search를 호출한다."""
    return [*get_rag_tools()]


def get_report_tools() -> list[StructuredTool]:
    """최종 브리프: 누락된 시세·재무·내부 근거를 보강하기 위해 도구를 적극 사용한다."""
    return [*get_rag_tools(), *get_market_tools(), *get_fundamental_tools()]
