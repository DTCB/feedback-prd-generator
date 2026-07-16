from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any, Callable, Optional

import streamlit as st

try:
    import pandas as pd
except ImportError:  # pragma: no cover - Streamlit demo expects pandas, but keeps import message friendly.
    pd = None

try:
    from src.feedback_prd.analysis import (
        analyze_feedback,
        build_need_pool,
        generate_prd_markdown,
        generate_prd_with_metadata,
        load_feedback_file,
        standardize_feedback,
    )
    from src.feedback_prd.llm import get_llm_status

    ANALYSIS_READY = True
except Exception as exc:  # pragma: no cover - lets UI explain missing backend instead of crashing.
    ANALYSIS_READY = False
    ANALYSIS_IMPORT_ERROR = exc


APP_ROOT = Path(__file__).parent
DEFAULT_SAMPLE_PATH = APP_ROOT / "data" / "sample_feedback.csv"

st.set_page_config(
    page_title="用户反馈洞察与 PRD 生成",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_style() -> None:
    st.markdown(
        """
        <style>
        :root {
            --pm-ink: #172026;
            --pm-muted: #65727f;
            --pm-line: #dde4ea;
            --pm-soft: #f6f8fb;
            --pm-blue: #2563eb;
            --pm-green: #0f766e;
            --pm-amber: #b45309;
            --pm-red: #b91c1c;
        }
        .block-container {
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
            max-width: 1280px;
        }
        h1, h2, h3 {
            letter-spacing: 0;
        }
        .pm-hero {
            padding: 1.1rem 0 0.75rem;
            border-bottom: 1px solid var(--pm-line);
            margin-bottom: 1rem;
        }
        .pm-hero h1 {
            margin: 0 0 0.25rem;
            color: var(--pm-ink);
            font-size: 2rem;
            line-height: 1.22;
        }
        .pm-hero p {
            color: var(--pm-muted);
            margin: 0;
            max-width: 860px;
        }
        .pm-note {
            background: var(--pm-soft);
            border: 1px solid var(--pm-line);
            border-radius: 8px;
            color: var(--pm-muted);
            padding: 0.85rem 1rem;
            margin: 0.5rem 0 1rem;
        }
        .pm-section-label {
            color: var(--pm-muted);
            font-size: 0.88rem;
            margin-bottom: 0.25rem;
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid var(--pm-line);
            border-radius: 8px;
            padding: 0.8rem 0.9rem;
        }
        div[data-testid="stMetricValue"] {
            color: var(--pm-ink);
            font-size: 1.55rem;
        }
        div[data-testid="stMetricLabel"] {
            color: var(--pm-muted);
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.25rem;
            border-bottom: 1px solid var(--pm-line);
        }
        .stTabs [data-baseweb="tab"] {
            height: 2.45rem;
            padding: 0 0.9rem;
        }
        .stDownloadButton button,
        .stButton button {
            border-radius: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def as_dataframe(value: Any) -> Any:
    if pd is None:
        return value
    if value is None:
        return pd.DataFrame()
    if isinstance(value, pd.DataFrame):
        return value
    if isinstance(value, list):
        return pd.DataFrame(value)
    if isinstance(value, dict):
        rows = value.get("data") or value.get("rows") or value.get("items")
        if isinstance(rows, list):
            return pd.DataFrame(rows)
        try:
            return pd.DataFrame(value)
        except ValueError:
            return pd.DataFrame([value])
    return value


def is_dataframe(value: Any) -> bool:
    return pd is not None and isinstance(value, pd.DataFrame)


def pick_dataframe(value: Any, keys: Optional[list[str]] = None) -> Any:
    if is_dataframe(value):
        return value
    if isinstance(value, dict):
        search_keys = keys or ["data", "result", "analysis", "summary", "items", "rows"]
        for key in search_keys:
            if key in value:
                candidate = as_dataframe(value[key])
                if is_dataframe(candidate):
                    return candidate
    return as_dataframe(value)


def pick_text(value: Any, keys: Optional[list[str]] = None, fallback: str = "") -> str:
    if value is None:
        return fallback
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in keys or ["markdown", "prd", "content", "text"]:
            if key in value and value[key]:
                return str(value[key])
    return fallback


def first_existing_column(df: Any, candidates: list[str]) -> Optional[str]:
    if not is_dataframe(df):
        return None
    normalized = {str(col).strip().lower(): col for col in df.columns}
    for candidate in candidates:
        if candidate in df.columns:
            return candidate
        key = candidate.strip().lower()
        if key in normalized:
            return normalized[key]
    return None


def read_input(uploaded_file: Any) -> Any:
    if not ANALYSIS_READY:
        raise RuntimeError(f"分析模块暂未就绪：{ANALYSIS_IMPORT_ERROR}")

    if uploaded_file is not None:
        return load_feedback_file(uploaded_file)
    return load_feedback_file(DEFAULT_SAMPLE_PATH)


def call_with_fallback(func: Callable[..., Any], *arg_options: Any) -> Any:
    last_error: Optional[Exception] = None
    for arg in arg_options:
        try:
            return func(arg)
        except TypeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return func()


@st.cache_data(show_spinner=False)
def run_pipeline(uploaded_bytes: Optional[bytes], uploaded_name: Optional[str]) -> dict[str, Any]:
    uploaded_file = None
    if uploaded_bytes is not None:
        uploaded_file = BytesIO(uploaded_bytes)
        uploaded_file.name = uploaded_name or "uploaded_feedback.csv"

    raw_feedback = read_input(uploaded_file)
    feedback_df = as_dataframe(standardize_feedback(raw_feedback))
    analysis_result = analyze_feedback(feedback_df)
    analysis_df = pick_dataframe(
        analysis_result,
        ["analysis_df", "feedback", "details", "items", "rows", "data"],
    )
    overview = analysis_result if isinstance(analysis_result, dict) else {}
    need_pool_result = call_with_fallback(build_need_pool, analysis_result, analysis_df)
    need_pool_df = pick_dataframe(
        need_pool_result,
        ["need_pool", "needs", "requirements", "items", "rows", "data"],
    )
    if is_dataframe(need_pool_df) and not need_pool_df.empty:
        top_need = need_pool_df.sort_values("priority_score", ascending=False).iloc[0]
        prd_result = generate_prd_markdown(top_need, analysis_df, use_llm=False)
        prd_markdown = pick_text(prd_result, fallback=str(prd_result or ""))
    else:
        prd_markdown = ""

    return {
        "feedback": feedback_df,
        "analysis_result": analysis_result,
        "analysis": analysis_df,
        "overview": overview,
        "need_pool_result": need_pool_result,
        "need_pool": need_pool_df,
        "prd": prd_markdown,
    }


def dataframe_to_csv(df: Any) -> bytes:
    if not is_dataframe(df):
        return b""
    return df.to_csv(index=False).encode("utf-8-sig")


def dataframe_to_excel_bytes(sheets: dict[str, Any]) -> Optional[bytes]:
    if pd is None:
        return None
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        return None

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        wrote_sheet = False
        for sheet_name, df in sheets.items():
            if is_dataframe(df) and not df.empty:
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
                wrote_sheet = True
        if not wrote_sheet:
            return None
    return output.getvalue()


def render_empty_state(message: str) -> None:
    st.info(message)


def render_llm_status() -> None:
    if not ANALYSIS_READY:
        return

    try:
        status = get_llm_status()
    except Exception as exc:
        st.warning(f"LLM 状态读取失败：{exc}")
        return

    st.subheader("LLM 配置状态")
    if status["status"] == "ready":
        st.success("真实 LLM 已就绪")
    elif status["status"] == "missing_sdk":
        st.warning("已配置 Key，但缺少 openai 包")
    else:
        st.info("未配置 API Key，使用模板兜底")

    st.caption(f"模型：{status['model']}")
    st.caption(f"接口：{status['base_url']}")


def render_dataframe(df: Any, height: int = 360) -> None:
    if is_dataframe(df) and not df.empty:
        st.dataframe(df, use_container_width=True, height=height)
    else:
        render_empty_state("当前没有可展示的数据。")


def metric_value(df: Any, col_candidates: list[str], default: str = "-") -> str:
    col = first_existing_column(df, col_candidates)
    if not col:
        return default
    try:
        return str(df[col].nunique())
    except Exception:
        return default


def filter_badcases(analysis_df: Any) -> Any:
    if not is_dataframe(analysis_df) or analysis_df.empty:
        return pd.DataFrame() if pd is not None else analysis_df

    badcase_col = first_existing_column(
        analysis_df,
        ["badcase", "is_badcase", "bad_case", "是否BadCase", "是否坏案例", "风险标签"],
    )
    severity_col = first_existing_column(analysis_df, ["severity", "risk_level", "严重程度", "风险等级", "优先级"])
    rating_col = first_existing_column(analysis_df, ["rating", "score", "评分"])
    sentiment_col = first_existing_column(analysis_df, ["sentiment", "情绪", "情感", "满意度"])

    if badcase_col:
        series = analysis_df[badcase_col]
        if series.dtype == bool:
            return analysis_df[series].copy()
        return analysis_df[
            series.astype(str).str.contains("true|是|bad|高风险|严重", case=False, regex=True, na=False)
        ].copy()

    if severity_col:
        mask = analysis_df[severity_col].astype(str).str.contains(
            "High|Critical|高|严重|P0|P1", case=False, regex=True, na=False
        )
        return analysis_df[mask].copy()

    mask = pd.Series(False, index=analysis_df.index)
    if rating_col:
        mask |= pd.to_numeric(analysis_df[rating_col], errors="coerce").fillna(5) <= 2
    if sentiment_col:
        mask |= analysis_df[sentiment_col].astype(str).str.contains(
            "negative|负面|消极", case=False, regex=True, na=False
        )
    return analysis_df[mask].copy()


def render_overview(feedback_df: Any, analysis_df: Any) -> None:
    total = len(feedback_df) if is_dataframe(feedback_df) else 0
    badcases = filter_badcases(analysis_df)
    badcase_count = str(len(badcases)) if is_dataframe(badcases) else "-"

    cols = st.columns(4)
    cols[0].metric("反馈总量", f"{total:,}")
    cols[1].metric("渠道覆盖", metric_value(feedback_df, ["channel", "source", "来源", "渠道"]))
    cols[2].metric("分类数量", metric_value(analysis_df, ["category", "分类", "一级分类", "问题分类"]))
    cols[3].metric("BadCase 线索", badcase_count)

    text_col = first_existing_column(feedback_df, ["content", "feedback", "comment", "text", "评论内容", "反馈内容", "用户反馈"])
    if text_col and is_dataframe(feedback_df):
        with st.expander("查看原始反馈样例", expanded=False):
            st.dataframe(feedback_df.head(8), use_container_width=True, height=260)


def render_category_analysis(analysis_df: Any) -> None:
    category_col = first_existing_column(analysis_df, ["category", "分类", "一级分类", "问题分类", "主题"])
    sentiment_col = first_existing_column(analysis_df, ["sentiment", "情绪", "情感", "满意度"])

    chart_cols = st.columns(2)
    if category_col and is_dataframe(analysis_df):
        category_counts = analysis_df[category_col].fillna("未分类").value_counts().reset_index()
        category_counts.columns = ["分类", "反馈量"]
        chart_cols[0].bar_chart(category_counts, x="分类", y="反馈量", use_container_width=True)
    else:
        chart_cols[0].info("分析结果中暂未发现分类字段。")

    if sentiment_col and is_dataframe(analysis_df):
        sentiment_counts = analysis_df[sentiment_col].fillna("未标注").value_counts().reset_index()
        sentiment_counts.columns = ["情绪", "反馈量"]
        chart_cols[1].bar_chart(sentiment_counts, x="情绪", y="反馈量", use_container_width=True)
    else:
        chart_cols[1].info("分析结果中暂未发现情绪字段。")

    st.markdown("#### 分类明细")
    render_dataframe(analysis_df)


def render_need_pool(need_pool_df: Any) -> None:
    if is_dataframe(need_pool_df) and not need_pool_df.empty:
        sort_col = first_existing_column(need_pool_df, ["rice", "RICE", "rice_score", "优先级分", "优先级评分"])
        display_df = need_pool_df.copy()
        if sort_col:
            display_df = display_df.sort_values(sort_col, ascending=False)
        render_dataframe(display_df)
    else:
        render_empty_state("需求池还没有生成结果，请确认分析函数已返回需求列表。")


def render_badcases(analysis_df: Any) -> None:
    if not is_dataframe(analysis_df) or analysis_df.empty:
        render_empty_state("当前没有 BadCase 数据。")
        return

    badcases = filter_badcases(analysis_df)

    if badcases.empty:
        st.success("当前样本中未识别到明确 BadCase。")
    else:
        st.warning(f"识别到 {len(badcases)} 条需要优先复盘的 BadCase 线索。")
        render_dataframe(badcases, height=420)


def render_prd(need_pool_df: Any, analysis_df: Any) -> str:
    if not is_dataframe(need_pool_df) or need_pool_df.empty:
        render_empty_state("需求池为空，暂时无法生成 PRD。")
        return ""

    sorted_needs = need_pool_df.sort_values("priority_score", ascending=False).reset_index(drop=True)
    options = [
        f"{row.get('need_id', index + 1)} | {row.get('need_summary', '未命名需求')} | 优先级 {row.get('priority_score', '-')}"
        for index, row in sorted_needs.iterrows()
    ]
    selected_label = st.selectbox("选择要生成 PRD 的需求", options, index=0)
    selected_index = options.index(selected_label)
    selected_need = sorted_needs.iloc[selected_index]
    llm_status = get_llm_status()
    toggle_label = (
        "使用真实 LLM 优化 PRD"
        if llm_status["status"] == "ready"
        else "尝试使用 LLM 优化 PRD（当前会自动模板兜底）"
    )
    use_llm = st.toggle(toggle_label, value=False)
    prd_result = generate_prd_with_metadata(selected_need, analysis_df, use_llm=use_llm)
    prd_markdown = pick_text(prd_result, fallback="")

    if prd_result.get("used_llm"):
        st.success(prd_result.get("message", "已使用真实 LLM 生成 PRD。"))
    elif use_llm:
        st.warning(prd_result.get("message", "LLM 不可用，已使用模板兜底。"))
    else:
        st.info(prd_result.get("message", "当前使用模板生成 PRD。"))

    if prd_markdown.strip():
        st.markdown(prd_markdown)
    else:
        render_empty_state("PRD Markdown 暂未生成。")
    return prd_markdown


def render_export_center(analysis_df: Any, need_pool_df: Any, prd_markdown: str) -> None:
    st.markdown(
        '<div class="pm-note">导出文件面向项目评审与团队流转：分析结果用于洞察复盘，需求池用于排期评估，PRD Markdown 可继续进入协作文档。</div>',
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    cols[0].download_button(
        "下载分析结果 CSV",
        data=dataframe_to_csv(analysis_df),
        file_name="feedback_analysis.csv",
        mime="text/csv",
        disabled=not (is_dataframe(analysis_df) and not analysis_df.empty),
        use_container_width=True,
    )
    cols[1].download_button(
        "下载需求池 CSV",
        data=dataframe_to_csv(need_pool_df),
        file_name="need_pool_rice.csv",
        mime="text/csv",
        disabled=not (is_dataframe(need_pool_df) and not need_pool_df.empty),
        use_container_width=True,
    )
    cols[2].download_button(
        "下载 PRD Markdown",
        data=prd_markdown.encode("utf-8"),
        file_name="generated_prd.md",
        mime="text/markdown",
        disabled=not prd_markdown.strip(),
        use_container_width=True,
    )

    excel_bytes = dataframe_to_excel_bytes(
        {
            "分析结果": analysis_df,
            "需求池RICE": need_pool_df,
        }
    )
    if excel_bytes:
        st.download_button(
            "下载 Excel 工作簿",
            data=excel_bytes,
            file_name="feedback_prd_workspace.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        st.caption("Excel 导出依赖 pandas/openpyxl；当前环境不可用时，CSV 与 Markdown 导出不受影响。")


def main() -> None:
    inject_style()

    st.markdown(
        """
        <div class="pm-hero">
          <h1>用户反馈洞察与 PRD 自动生成</h1>
          <p>面向产品经理的离线评论分析工作台：从公开评论沉淀样例或上传文件中归纳问题、提炼需求池，并生成可评审的 PRD 初稿。</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("数据导入")
        st.caption("默认读取 data/sample_feedback.csv；也可以上传本地 CSV 或 Excel。")
        uploaded_file = st.file_uploader(
            "上传反馈文件",
            type=["csv", "xlsx", "xls"],
            accept_multiple_files=False,
        )
        st.markdown(
            '<div class="pm-note">样例数据来自公开评论的离线沉淀，不在演示过程中实时爬取或请求外部站点。</div>',
            unsafe_allow_html=True,
        )
        st.divider()
        render_llm_status()
        st.divider()
        st.caption("建议字段包含：评论内容、来源、时间、评分、产品版本。系统会交给分析模块统一标准化。")

    if pd is None:
        st.error("当前环境缺少 pandas，无法运行数据分析演示。请先安装项目依赖。")
        return

    if not ANALYSIS_READY:
        st.error("分析模块暂未就绪，页面结构已准备好。")
        st.code(f"from src.feedback_prd.analysis import ...\n\n{ANALYSIS_IMPORT_ERROR}", language="text")
        return

    uploaded_bytes = uploaded_file.getvalue() if uploaded_file else None
    uploaded_name = uploaded_file.name if uploaded_file else None

    with st.spinner("正在整理反馈、归类问题并生成需求池..."):
        try:
            result = run_pipeline(uploaded_bytes, uploaded_name)
        except FileNotFoundError:
            st.error(f"未找到默认样例文件：{DEFAULT_SAMPLE_PATH}")
            st.info("请放置 data/sample_feedback.csv，或在左侧上传 CSV/Excel 文件。")
            return
        except Exception as exc:
            st.error("分析流程执行失败，请检查上传文件格式或分析函数实现。")
            st.exception(exc)
            return

    feedback_df = result["feedback"]
    analysis_df = result["analysis"]
    need_pool_df = result["need_pool"]
    prd_markdown = result["prd"]

    tab_import, tab_overview, tab_category, tab_needs, tab_badcase, tab_prd, tab_export = st.tabs(
        ["数据导入", "反馈总览", "分类分析", "需求池/RICE", "BadCase", "PRD 生成", "导出中心"]
    )

    with tab_import:
        st.markdown("### 数据导入")
        st.markdown(
            '<div class="pm-note">当前数据源：'
            + (f"上传文件 {uploaded_name}" if uploaded_name else "默认样例 data/sample_feedback.csv")
            + "。样例仅用于项目展示和方法验证。</div>",
            unsafe_allow_html=True,
        )
        render_dataframe(feedback_df)

    with tab_overview:
        st.markdown("### 反馈总览")
        render_overview(feedback_df, analysis_df)

    with tab_category:
        st.markdown("### 分类分析")
        render_category_analysis(analysis_df)

    with tab_needs:
        st.markdown("### 需求池 / RICE")
        render_need_pool(need_pool_df)

    with tab_badcase:
        st.markdown("### BadCase 复盘")
        render_badcases(analysis_df)

    with tab_prd:
        st.markdown("### PRD 生成")
        prd_markdown = render_prd(need_pool_df, analysis_df)

    with tab_export:
        st.markdown("### 导出中心")
        render_export_center(analysis_df, need_pool_df, prd_markdown)


if __name__ == "__main__":
    main()
