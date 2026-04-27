from app.services.market_tools import parse_portfolio_text
from app.services.retriever import retrieve_research_context


def test_parse_portfolio_text():
    result = parse_portfolio_text("삼성전자, 50%\n현금, 50%")
    assert len(result) == 2


def test_retrieve_research_context():
    result = retrieve_research_context("금리 성장주")
    assert len(result) >= 1
