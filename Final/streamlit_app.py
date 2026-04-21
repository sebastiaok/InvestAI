import requests
import streamlit as st
import json


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

query = st.text_area(
    "질문",
    value="",
    height=68,
    placeholder="예: 삼성전자 지금 추가매수 괜찮을까? 시장과 리스크까지 함께 봐줘.",
    key="query_input",
    disabled=st.session_state.is_analyzing,
)
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

has_query = bool(query and query.strip())
has_portfolio_text = bool(portfolio_text and portfolio_text.strip())
has_portfolio_file = uploaded_portfolio is not None
can_run_analysis = has_query or has_portfolio_text or has_portfolio_file

if not can_run_analysis:
    st.markdown(
        "<p style='color:#1d4ed8; font-size:0.9rem;'>"
        "입력 안내: 질문 또는 포트폴리오 정보(텍스트/파일) 중 하나를 입력하면 분석 실행 버튼이 활성화됩니다."
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
            resp = requests.post(
                f"{api_base}/analyze",
                json={
                    "query": query,
                    "ticker": "",
                    "portfolio_text": merged_portfolio_text,
                    "risk_profile": risk_profile,
                },
                timeout=120,
            )
            resp.raise_for_status()
            st.session_state.result_data = resp.json()
            st.session_state.result_error = ""
        except requests.RequestException as exc:
            st.session_state.result_data = None
            st.session_state.result_error = f"분석 요청 실패: {exc}"
        finally:
            st.session_state.run_requested = False
            st.session_state.is_analyzing = False
            st.rerun()

if st.session_state.result_error:
    st.error(st.session_state.result_error)

if st.session_state.result_data:
    data = st.session_state.result_data
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
