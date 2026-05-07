from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from app.agents.memory_profile_agent import build_memory_profile_with_llm
from app.agents.planner_agent import _apply_memory_flags
from app.graphs.investment_graph import (
    MEMORY_NAMESPACE,
    MEMORY_STORE,
    _extract_structured_memory,
    get_session_memory,
    memory_bootstrap_node,
    reset_session_memory,
)
from app.rag.retriever import format_rag_context, retrieve_for_query
from app.services.market_tools import parse_portfolio_text
from app.services.retriever import retrieve_research_context


def _sam_doc005930() -> Document:
    return Document(
        page_content="Samsung Electronics equity note snippet for testing retrieval.",
        metadata={
            "source_id": "sam_kr_equity_q2",
            "source_path": "./data/research/sam_kr_equity_q2.md",
            "doc_type": "research_note",
            "ticker": "005930.KS",
        },
    )


def _nvda_us_doc() -> Document:
    return Document(
        page_content="NVDA US semiconductor exposure memo.",
        metadata={
            "source_id": "nvda_macro",
            "source_path": "./data/research/nvda.txt",
            "doc_type": "macro",
            "ticker": "NVDA",
        },
    )


class SmokeParseTests(unittest.TestCase):
    def test_parse_portfolio_text(self):
        result = parse_portfolio_text("삼성전자, 50%\n현금, 50%")
        self.assertEqual(len(result), 2)


class RetrieverContractTests(unittest.TestCase):
    def test_retrieve_research_context_matches_retrieve_for_query(self):
        """서비스 레이어 예전 이름이 rag retriever와 동일 동작해야 한다."""
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [(_sam_doc005930(), 0.41)]

        with patch("app.rag.retriever.build_or_load_vector_store", return_value=mock_store):
            a = retrieve_for_query("금리 성장주", ticker="005930.KS", k=3)
            b = retrieve_research_context("금리 성장주", ticker="005930.KS", k=3)

        self.assertEqual(a, b)

    def test_retrieve_for_query_returns_records_from_store_mock(self):
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [(_sam_doc005930(), 0.41)]

        with patch("app.rag.retriever.build_or_load_vector_store", return_value=mock_store):
            rows = retrieve_for_query("금리 성장주", ticker="005930.KS", k=4)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source_id"], "sam_kr_equity_q2")
        self.assertEqual(rows[0]["ticker"], "005930.KS")
        self.assertEqual(rows[0]["doc_type"], "research_note")
        self.assertIsInstance(rows[0]["score"], float)

    def test_retrieve_for_query_empty_when_store_raises(self):
        with patch("app.rag.retriever.build_or_load_vector_store", side_effect=RuntimeError("no index")):
            rows = retrieve_for_query("any query")
        self.assertEqual(rows, [])

    def test_ticker_filter_fallback_when_no_matching_ticker_returns_unfiltered(self):
        """티커가 맞는 청크가 없으면 빈 필터 결과로 인해 원 후보 목록이 다시 사용된다."""
        mock_store = MagicMock()
        mock_store.similarity_search_with_score.return_value = [(_nvda_us_doc(), 0.52)]

        with patch("app.rag.retriever.build_or_load_vector_store", return_value=mock_store):
            rows = retrieve_for_query("semiconductor cycle", ticker="005930.KS", k=2)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["ticker"], "NVDA")


class RagFormatTests(unittest.TestCase):
    def test_format_rag_context_empty(self):
        text = format_rag_context([])
        self.assertTrue(text.startswith("RAG 근거 없음"))

    def test_format_rag_context_nonempty_snippet(self):
        block = format_rag_context(
            [
                {
                    "text": "테스트 근거 " * 80,
                    "source_id": "doc_a",
                    "doc_type": "research_note",
                    "score": 0.1234,
                    "ticker": "UNKNOWN",
                }
            ]
        )
        self.assertIn("doc_a", block)
        self.assertIn("research_note", block)
        self.assertIn("score=0.1234", block)
        self.assertGreater(len(block), 40)


class GraphMemoryTests(unittest.TestCase):
    def test_apply_memory_flags_forces_related_tasks(self):
        tasks = {
            "market": False,
            "fundamental": False,
            "risk": False,
            "portfolio": False,
            "research": False,
            "rag": False,
        }
        prof = {
            "carry_over_flags": [
                {"type": "risk", "note": "환율 리스크"},
                {"type": "fundamental", "note": "실적 확인"},
                {"type": "portfolio", "note": "리밸런싱"},
            ]
        }
        out = _apply_memory_flags(tasks, prof, portfolio_text="삼성전자 50%\n현금 50%")
        self.assertTrue(out["risk"])
        self.assertTrue(out["fundamental"])
        self.assertTrue(out["portfolio"])
        self.assertTrue(out["research"])
        self.assertTrue(out["rag"])

    def test_apply_memory_flags_with_legacy_string_flags(self):
        tasks = {
            "market": False,
            "fundamental": False,
            "risk": False,
            "portfolio": False,
            "research": False,
            "rag": False,
        }
        prof = {"carry_over_flags": ["뉴스 확인", "환율 리스크"]}
        out = _apply_memory_flags(tasks, prof, portfolio_text=None)
        self.assertTrue(out["market"])
        self.assertTrue(out["risk"])
        self.assertTrue(out["research"])
        self.assertTrue(out["rag"])

    def test_memory_profile_agent_normalizes_json_fields(self):
        with patch(
            "app.agents.memory_profile_agent.json_chat",
            return_value={
                "last_user_intent": "  이어서 분석 ",
                "risk_profile": "Balanced",
                "key_risks": [" 변동성 확대 ", "", 1],
                "action_items": ["현금 비중 유지", None],
                "last_report_excerpt": "요약",
                "carry_over_flags": [
                    {"type": "risk", "note": "환율"},
                    {"type": "portfolio", "note": "리밸런싱"},
                    "",
                ],
            },
        ):
            profile = build_memory_profile_with_llm(
                query="다음 턴",
                risk_profile="balanced",
                final_report="리포트 본문",
                previous_profile={},
            )
        self.assertEqual(profile.get("last_user_intent"), "이어서 분석")
        self.assertEqual(profile.get("risk_profile"), "balanced")
        self.assertTrue(profile.get("key_risks"))
        self.assertTrue(profile.get("action_items"))
        self.assertEqual(
            profile.get("carry_over_flags"),
            [{"type": "risk", "note": "환율"}, {"type": "portfolio", "note": "리밸런싱"}],
        )

    def test_extract_structured_memory_has_risks_and_actions(self):
        profile = _extract_structured_memory(
            "1. 한줄 결론\n2. 핵심 근거\n- 변동성 리스크 확대\n- 현금 비중 20% 유지\n5. 추가 확인 필요",
            "balanced",
            "삼성전자 어떻게 볼까",
        )
        self.assertEqual(profile.get("risk_profile"), "balanced")
        self.assertTrue(profile.get("key_risks"))
        self.assertTrue(profile.get("action_items"))

    def test_memory_bootstrap_node_uses_store_summary(self):
        sid = "ut-memory-1"
        reset_session_memory(sid)
        MEMORY_STORE.put(
            MEMORY_NAMESPACE,
            sid,
            {"turn_index": 2, "last_report_summary": "이전 턴 요약입니다."},
        )
        state = memory_bootstrap_node({"session_id": sid, "query": "그럼 다음 전략은?"})
        self.assertEqual(state.get("turn_index"), 3)
        self.assertIn("이전 대화 요약", state.get("contextual_query", ""))
        self.assertIn("이전 턴 요약", state.get("contextual_query", ""))

    def test_reset_and_get_session_memory(self):
        sid = "ut-memory-2"
        MEMORY_STORE.put(MEMORY_NAMESPACE, sid, {"turn_index": 5, "last_report_summary": "x"})
        self.assertEqual(get_session_memory(sid).get("turn_index"), 5)
        reset_session_memory(sid)
        self.assertEqual(get_session_memory(sid), {})


if __name__ == "__main__":
    unittest.main()
