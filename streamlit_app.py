import json
from uuid import uuid4

import requests
import streamlit as st
from pypdf import PdfReader


def format_http_api_error(resp: requests.Response) -> str:
    """FastAPI 표준 에러 본문(success/category/error_code/message)을 한 줄로 요약."""
    try:
        err = resp.json()
        msg = err.get("message") or resp.text or "요청 처리 실패"
        cat = err.get("category") or ""
        code = err.get("error_code") or ""
        parts = [f"[{resp.status_code}]"]
        if code:
            parts.append(code)
        if cat:
            parts.append(f"({cat})")
        return " ".join(parts) + f": {msg}"
    except (ValueError, requests.JSONDecodeError, TypeError):
        return f"HTTP {resp.status_code}: {(resp.text or '')[:500]}"


def profile_rule_summary(risk_profile: str) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return "보수형 규칙 적용: 원금 보전, 변동성 최소화, 방어적 대응(현금 비중/분할매수/손절 기준)을 우선합니다."
    if profile == "aggressive":
        return "공격형 규칙 적용: 성장 기회와 업사이드 분석 비중을 높이고, 손실 허용 범위를 함께 제시합니다."
    return "균형형 규칙 적용: 수익 기회와 리스크 관리 전략을 균형 있게 제시합니다."


def decode_uploaded_portfolio(uploaded_file):
    if uploaded_file is None:
        return ""
    content = uploaded_file.getvalue()
    if not content:
        return ""
    try:
        return content.decode("utf-8").strip()
    except UnicodeDecodeError:
        return content.decode("cp949", errors="ignore").strip()


def decode_uploaded_text(uploaded_file):
    if uploaded_file is None:
        return ""
    content = uploaded_file.getvalue()
    if not content:
        return ""
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return content.decode("cp949", errors="ignore")


def decode_uploaded_research_file(uploaded_file):
    if uploaded_file is None:
        return ""
    name = (uploaded_file.name or "").lower()
    if name.endswith(".pdf"):
        try:
            reader = PdfReader(uploaded_file)
            return "\n".join((page.extract_text() or "") for page in reader.pages)
        except Exception:
            return ""
    return decode_uploaded_text(uploaded_file)


def render_plan(plan):
    if not plan:
        st.info("생성된 계획이 없습니다.")
        return

    if isinstance(plan, dict):
        for key, value in plan.items():
            label = str(key).replace("_", " ").title()
            if isinstance(value, list):
                st.markdown(f"**{label}**")
                for item in value:
                    st.markdown(f"- {item}")
            elif isinstance(value, dict):
                st.markdown(f"**{label}**")
                for sub_key, sub_value in value.items():
                    st.markdown(f"- **{str(sub_key).replace('_', ' ').title()}**: {sub_value}")
            else:
                st.markdown(f"**{label}**: {value}")
        return

    if isinstance(plan, list):
        for item in plan:
            st.markdown(f"- {item}")
        return

    st.write(plan)


st.set_page_config(page_title="InvestAI Agent", layout="wide")
if "is_analyzing" not in st.session_state:
    st.session_state.is_analyzing = False
if "run_requested" not in st.session_state:
    st.session_state.run_requested = False
if "result_data" not in st.session_state:
    st.session_state.result_data = None
if "result_error" not in st.session_state:
    st.session_state.result_error = ""
if "ingest_data" not in st.session_state:
    st.session_state.ingest_data = None
if "ingest_error" not in st.session_state:
    st.session_state.ingest_error = ""
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid4())
if "reset_memory_requested" not in st.session_state:
    st.session_state.reset_memory_requested = False
if "last_submitted_query" not in st.session_state:
    st.session_state.last_submitted_query = ""
if "last_research_used" not in st.session_state:
    st.session_state.last_research_used = False

st.title("📈 InvestAI Agent")
st.caption("시장/재무/리스크/포트폴리오 투자분석 AI Agent")
st.markdown(
    """
    <style>
    div[data-testid="stFileUploaderDropzone"] {
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    div[data-testid="stFileUploaderDropzoneInstructions"] small {
        display: none;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("입력")
    api_base = st.text_input(
        "FastAPI URL",
        value="http://127.0.0.1:8000",
        key="api_base_input",
        disabled=st.session_state.is_analyzing,
    )
    risk_profile = st.selectbox(
        "Risk Profile",
        ["conservative", "balanced", "aggressive"],
        index=1,
        key="risk_profile_input",
        disabled=st.session_state.is_analyzing,
    )
    session_id = st.text_input(
        "Conversation Session ID",
        value=st.session_state.session_id,
        key="session_id_input",
        help="같은 Session ID를 유지하면 이전 분석 맥락(체크포인트/메모리)을 이어갑니다.",
        disabled=st.session_state.is_analyzing,
    )
    st.session_state.session_id = session_id.strip() or st.session_state.session_id
    if st.button("세션 메모리 초기화", use_container_width=True, disabled=st.session_state.is_analyzing):
        st.session_state.reset_memory_requested = True
        st.info("다음 분석 요청에서 세션 메모리를 초기화합니다.")

query = st.text_area(
    "질문",
    value="",
    height=68,
    placeholder="예: 삼성전자 지금 추가매수 괜찮을까? 시장과 리스크까지 함께 봐줘.",
    key="query_input",
    disabled=st.session_state.is_analyzing,
)
st.caption("질문 입력 규칙: 최소 5자 이상 입력해야 합니다. (포트폴리오 입력은 선택)")
st.markdown("---")
portfolio_text = st.text_area(
    "포트폴리오 (종목, 비중 형식)",
    value="",
    height=100,
    placeholder="예: 삼성전자, 35%\nTIGER 미국나스닥100, 25%\n현금, 20%",
    key="portfolio_text_input",
    disabled=st.session_state.is_analyzing,
)
uploaded_portfolio = st.file_uploader(
    "포트폴리오 파일 업로드 (txt, csv)",
    type=["txt", "csv"],
    help="파일 내용은 텍스트 입력값과 합쳐서 분석에 사용됩니다.",
    key="portfolio_file_input",
    disabled=st.session_state.is_analyzing,
)

st.markdown("---")
research_files = st.file_uploader(
    "리서치 문서/보고서 업로드 (md, txt, pdf)",
    type=["md", "txt", "pdf"],
    accept_multiple_files=True,
    key="research_docs_input",
    disabled=st.session_state.is_analyzing,
    help="파일이 있으면 분석 실행 시 자동으로 전처리/인덱싱 후 질문에 대해 RAG 검색을 수행합니다.",
)
doc_type_for_upload = st.selectbox(
    "문서 유형",
    ["research_note", "report", "news_snapshot"],
    index=0,
    key="doc_type_input",
    disabled=st.session_state.is_analyzing,
)
ticker_for_upload = st.text_input(
    "연관 티커 (선택)",
    value="",
    placeholder="예: 005930.KS",
    key="doc_ticker_input",
    disabled=st.session_state.is_analyzing,
)
chunk_col1, chunk_col2 = st.columns(2)
with chunk_col1:
    chunk_size = st.number_input("Chunk Size", min_value=200, max_value=2000, value=900, step=50)
with chunk_col2:
    chunk_overlap = st.number_input("Chunk Overlap", min_value=0, max_value=400, value=120, step=20)

if st.session_state.ingest_error:
    st.error(st.session_state.ingest_error)

if st.session_state.ingest_data:
    ingest = st.session_state.ingest_data
    st.success(
        f"입력 {ingest.get('input_documents',0)}개 중 {ingest.get('accepted_documents',0)}개 수용, "
        f"청크 {ingest.get('generated_chunks',0)}개 생성"
    )
    if ingest.get("warnings"):
        for warning in ingest["warnings"]:
            st.warning(warning)
    with st.expander("생성된 문서/청크 메타데이터", expanded=False):
        st.json(
            {
                "saved_files": ingest.get("saved_files", []),
                "chunk_previews": ingest.get("chunk_previews", []),
            }
        )

if st.session_state.result_data and st.session_state.last_research_used:
    rag_results = []
    for section in st.session_state.result_data.get("sections", []):
        rag_results.extend(section.get("evidence") or [])
    seen = set()
    deduped = []
    for row in rag_results:
        if row not in seen:
            seen.add(row)
            deduped.append(row)
    with st.expander("질문 기반 RAG 검색 결과", expanded=True):
        if deduped:
            for item in deduped:
                st.markdown(f"- {item}")
        else:
            st.caption("검색된 RAG 근거가 없습니다.")

has_query = bool(query and query.strip())
can_run_analysis = has_query

if not can_run_analysis:
    st.markdown(
        "<p style='color:#1d4ed8; font-size:0.9rem;'>"
        "입력 안내: 질문은 필수입니다. 포트폴리오/리서치 문서 업로드는 선택 입력입니다."
        "</p>",
        unsafe_allow_html=True,
    )
else:
    st.caption("입력이 확인되었습니다. 분석 실행 버튼을 눌러 진행하세요.")

if st.button(
    "분석 실행",
    use_container_width=True,
    disabled=(not can_run_analysis) or st.session_state.is_analyzing,
):
    st.session_state.last_submitted_query = query.strip()
    st.session_state.run_requested = True
    st.session_state.is_analyzing = True
    st.rerun()

if st.session_state.run_requested:
    with st.spinner("InvestAI Agent가 분석 중입니다..."):
        uploaded_text = decode_uploaded_portfolio(st.session_state.portfolio_file_input)
        merged_portfolio_text = portfolio_text.strip()
        if uploaded_text:
            merged_portfolio_text = f"{merged_portfolio_text}\n{uploaded_text}" if merged_portfolio_text else uploaded_text

        try:
            # 선택 입력: 리서치 문서가 있을 때만 선행 전처리/인덱싱
            st.session_state.last_research_used = bool(research_files)
            if research_files:
                documents = []
                for file in research_files:
                    text = decode_uploaded_research_file(file)
                    if not text.strip():
                        continue
                    documents.append(
                        {
                            "filename": file.name,
                            "content": text,
                            "doc_type": doc_type_for_upload,
                            "ticker": (ticker_for_upload.strip() or "UNKNOWN"),
                            "section": "body",
                        }
                    )
                if documents:
                    ingest_resp = requests.post(
                        f"{api_base}/ingest-docs",
                        json={
                            "documents": documents,
                            "chunk_size": int(chunk_size),
                            "chunk_overlap": int(chunk_overlap),
                            "save_to_research_dir": True,
                            "rebuild_index": True,
                        },
                        timeout=180,
                    )
                    if ingest_resp.ok:
                        st.session_state.ingest_data = ingest_resp.json()
                        st.session_state.ingest_error = ""
                    else:
                        st.session_state.ingest_data = None
                        st.session_state.ingest_error = f"문서 전처리 실패 — {format_http_api_error(ingest_resp)}"
                        raise requests.RequestException(st.session_state.ingest_error)

            resp = requests.post(
                f"{api_base}/analyze",
                json={
                    "query": query,
                    "ticker": "",
                    "portfolio_text": merged_portfolio_text,
                    "risk_profile": risk_profile,
                    "session_id": st.session_state.session_id,
                    "reset_memory": st.session_state.reset_memory_requested,
                },
                timeout=120,
            )
            if resp.ok:
                st.session_state.result_data = resp.json()
                st.session_state.result_error = ""
            else:
                st.session_state.result_data = None
                st.session_state.result_error = f"분석 실패 — {format_http_api_error(resp)}"
        except requests.RequestException as exc:
            st.session_state.result_data = None
            st.session_state.result_error = f"분석 요청 실패: {exc}"
        finally:
            st.session_state.reset_memory_requested = False
            st.session_state.run_requested = False
            st.session_state.is_analyzing = False
            st.rerun()

if st.session_state.result_error:
    st.error(st.session_state.result_error)

if st.session_state.result_data:
    data = st.session_state.result_data
    if data.get("session_id"):
        st.caption(f"Session: `{data.get('session_id')}` · Turn: {data.get('turn_index', 1)}")
    if data.get("memory_profile"):
        with st.expander("Session Memory Profile", expanded=False):
            st.json(data.get("memory_profile", {}))
    if st.session_state.last_submitted_query:
        st.subheader("질문")
        st.write(st.session_state.last_submitted_query)
    st.subheader("분석 결과")
    st.info(f"리스크 성향: {risk_profile}\n\n{profile_rule_summary(risk_profile)}")
    st.write(data["final_report"])
    st.download_button(
        "최종 리포트 다운로드 (.txt)",
        data=data["final_report"],
        file_name="investai_final_report.txt",
        mime="text/plain",
        use_container_width=True,
    )

    with st.expander("Planner Result", expanded=False):
        render_plan(data.get("plan"))

    st.subheader("Agent 결과")
    for section in data["sections"]:
        with st.expander(section["title"], expanded=False):
            st.write(section["summary"])
            evidences = section.get("evidence") or []
            if evidences:
                st.caption("RAG Evidence")
                for item in evidences:
                    st.markdown(f"- {item}")

    citations = data.get("citations", {})
    if citations:
        with st.expander("Citations", expanded=False):
            for agent_name, items in citations.items():
                st.markdown(f"**{agent_name.title()}**")
                for item in items:
                    source = item.get("source", "")
                    title = item.get("title", "")
                    url = item.get("url", "")
                    if url:
                        st.markdown(f"- {source} | {title} | {url}")
                    else:
                        st.markdown(f"- {source} | {title}")
