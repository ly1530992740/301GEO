from __future__ import annotations

from dataclasses import fields
from datetime import datetime
import html
import json
import re
import sys
from pathlib import Path
from typing import Any

import streamlit as st
from geo_app.config import (
    AppConfig,
    BudgetConfig,
    GEOAIConfig,
    MeijiekuConfig,
    QwenConfig,
    load_config,
    normalize_meijieku_base_url,
)
from geo_app.integrated_report_renderer import enrich_analysis_data, render_integrated_outputs
from geo_app.integrated_workflow import create_product_profile_run, run_integrated_geo_analysis
from geo_app.product_ingestion import UploadedPdf
from geo_app.storage import Storage


LEGACY_HISTORY_PREFIX = "fs:"


SERVICE_SCOPE_OPTIONS = {
    "本地/城市": "local_city",
    "省内/区域": "regional",
    "全国": "national",
    "全球/海外": "global",
}

GEO_AUDIENCE_OPTIONS = {
    "综合受众": "mixed",
    "C端消费者": "consumer_recommendation",
    "B端加盟/招商客户": "franchise",
    "B端采购/企业客户": "b2b_purchase",
    "品牌声量诊断": "brand_geo",
}
ANALYSIS_GOAL_OPTIONS = GEO_AUDIENCE_OPTIONS


def code_last_modified_text() -> str:
    files = [
        Path(__file__),
        Path("geo_app/integrated_workflow.py"),
        Path("geo_app/multi_ai_geo_workflow.py"),
        Path("geo_app/multi_ai_clients.py"),
        Path("geo_app/geo_visibility_metrics.py"),
        Path("geo_app/sentiment_scoring.py"),
        Path("geo_app/qwen_client.py"),
        Path("geo_app/integrated_report_renderer.py"),
        Path("geo_app/topic_analysis.py"),
        Path("geo_app/brand_normalizer.py"),
    ]
    existing = [path for path in files if path.exists()]
    if not existing:
        return "未知"
    latest = max(path.stat().st_mtime for path in existing)
    return datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M:%S")


@st.cache_resource
def get_storage() -> Storage:
    return Storage()


def sidebar_config() -> AppConfig:
    base = load_config()
    with st.sidebar:
        st.header("配置")
        st.caption("当前主入口为 GEO 一键分析；Google Trends 配置已从该流程移除。")

        qwen_api_key = st.text_input("Qwen API Key", value=base.qwen.api_key, type="password")
        qwen_api_host = st.text_input(
            "Qwen API Host（可选）",
            value=getattr(base.qwen, "api_host", ""),
            placeholder="例如 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1",
        )
        search_model = st.text_input("搜索模型", value=base.qwen.search_model)
        analysis_model = st.text_input("分析模型", value=base.qwen.analysis_model)
        writing_model = st.text_input("写作模型", value=base.qwen.writing_model)

        st.divider()
        meijieku_base_url = st.text_input("媒介库 API 地址", value=base.meijieku.base_url)
        meijieku_mobile = st.text_input("媒介库手机号", value=base.meijieku.mobile)
        meijieku_password = st.text_input("媒介库密码", value=base.meijieku.password, type="password")
        meijieku_token = st.text_input("媒介库 Token（可选）", value=base.meijieku.token, type="password")
        meijieku_mock_mode = st.checkbox("媒介库模拟模式", value=base.meijieku.mock_mode)
        page_size = st.number_input("资源每页数量", min_value=20, max_value=200, value=base.meijieku.resource_page_size, step=10)
        max_pages = st.number_input("资源最大页数", min_value=1, max_value=200, value=base.meijieku.resource_max_pages, step=1)

        st.divider()
        st.caption("百度搜索 API 由后端客户端读取配置；本页不再要求 SerpApi。")

    return AppConfig(
        qwen=QwenConfig(
            api_key=qwen_api_key.strip(),
            api_host=qwen_api_host.strip().rstrip("/"),
            search_model=search_model.strip() or "qwen-plus",
            analysis_model=analysis_model.strip() or "qwen3.7-max",
            writing_model=writing_model.strip() or "qwen-plus",
            search_strategy=base.qwen.search_strategy,
            analysis_strategy=base.qwen.analysis_strategy,
            forced_search=base.qwen.forced_search,
            enable_source=base.qwen.enable_source,
            enable_citation=base.qwen.enable_citation,
            timeout_seconds=base.qwen.timeout_seconds,
        ),
        meijieku=MeijiekuConfig(
            base_url=normalize_meijieku_base_url(meijieku_base_url),
            mobile=meijieku_mobile.strip(),
            password=meijieku_password.strip(),
            token=meijieku_token.strip(),
            resource_page_size=int(page_size),
            resource_max_pages=int(max_pages),
            mock_mode=bool(meijieku_mock_mode),
        ),
        serpapi=base.serpapi,
        budget=BudgetConfig(
            max_price_per_platform=base.budget.max_price_per_platform,
            max_total_budget=base.budget.max_total_budget,
            require_fuzzy_confirmation=True,
        ),
        geo_ai=_build_geo_ai_config(base.geo_ai),
    )


def _build_geo_ai_config(base_geo_ai: Any) -> GEOAIConfig:
    values = {
        "prompt_count": getattr(base_geo_ai, "prompt_count", 5),
        "brand_diagnostic_prompt_count": getattr(base_geo_ai, "brand_diagnostic_prompt_count", 3),
        "comparison_prompt_count": getattr(base_geo_ai, "comparison_prompt_count", 2),
        "recommendations_per_prompt": getattr(base_geo_ai, "recommendations_per_prompt", 10),
        "visibility_brand_limit": getattr(base_geo_ai, "visibility_brand_limit", 10),
        "source_link_limit": getattr(base_geo_ai, "source_link_limit", 80),
        "article_fetch_limit": getattr(base_geo_ai, "article_fetch_limit", 40),
        "enable_ai_prompt_discovery": getattr(base_geo_ai, "enable_ai_prompt_discovery", True),
    }
    supported = {field.name for field in fields(GEOAIConfig)}
    return GEOAIConfig(**{key: value for key, value in values.items() if key in supported})


def require_qwen(config: AppConfig) -> bool:
    if config.qwen.api_key:
        lowered = config.qwen.api_key.lower()
        if config.qwen.api_key in {"sk-your-qwen-key", "YOUR_API_KEY"} or "your-qwen-key" in lowered:
            st.error("当前 Qwen API Key 还是示例值，请填写真实 API Key。")
            return False
        return True
    st.error("请先在左侧配置 Qwen API Key，或在 .env 中设置 DASHSCOPE_API_KEY。")
    return False


def add_log(message: str) -> None:
    logs = st.session_state.setdefault("geo_console_logs", [])
    logs.append(str(message))
    st.session_state.geo_console_logs = logs[-160:]


def _analysis_progress_percent(message: str) -> int:
    text = str(message or "")
    stages = [
        (10, ["启动", "Prompt", "问题组"]),
        (20, ["中立推荐", "主流推荐", "推荐排名"]),
        (35, ["品牌诊断"]),
        (45, ["竞品直接对比"]),
        (55, ["品牌声量", "传统搜索", "新媒体"]),
        (68, ["抓取 AI 文章链接", "抓取 AI 返回", "文章链接正文"]),
        (78, ["提炼", "文章宣传", "定位分析"]),
        (88, ["媒介库", "报价", "媒介"]),
        (96, ["报告", "保存"]),
        (100, ["完成"]),
    ]
    matched = 5
    for percent, keywords in stages:
        if any(keyword in text for keyword in keywords):
            matched = percent
    return matched


def inject_styles() -> None:
    st.markdown(
        """
<style>
  .main .block-container { padding-top: 1.5rem; padding-right: 360px; }
  .dev-console {
    position: fixed;
    top: 64px;
    right: 18px;
    z-index: 9999;
    width: 330px;
    max-height: 70vh;
    padding: 12px;
    border: 1px solid rgba(15, 23, 42, 0.18);
    border-radius: 8px;
    background: rgba(255, 255, 255, 0.74);
    backdrop-filter: blur(10px);
    box-shadow: 0 16px 40px rgba(15, 23, 42, 0.12);
    overflow: hidden;
  }
  .dev-console-title {
    font-size: 12px;
    font-weight: 700;
    color: #334155;
    margin-bottom: 8px;
  }
  .dev-console pre {
    margin: 0;
    max-height: 62vh;
    overflow: auto;
    white-space: pre-wrap;
    word-break: break-word;
    font-size: 12px;
    line-height: 1.45;
    color: #111827;
    background: transparent;
  }
  @media (max-width: 1100px) {
    .main .block-container { padding-right: 1rem; }
    .dev-console { position: static; width: auto; max-height: 260px; margin: 0 1rem 1rem; }
  }
</style>
""",
        unsafe_allow_html=True,
    )


def render_console() -> None:
    logs = st.session_state.get("geo_console_logs", [])
    code_mtime = html.escape(code_last_modified_text())
    content = "\n".join(f"{idx + 1}. {html.escape(str(line))}" for idx, line in enumerate(logs[-50:])) or "等待执行..."
    st.markdown(
        f"""
<div class="dev-console">
  <div class="dev-console-title">DEV CONSOLE</div>
  <div class="dev-console-title">CODE UPDATED: {code_mtime}</div>
  <pre>{content}</pre>
</div>
""",
        unsafe_allow_html=True,
    )


def render_input_panel(storage: Storage, config: AppConfig) -> None:
    st.subheader("GEO 一键分析")
    st.caption("输入官网 URL 或上传 PDF，先生成产品画像，再确认品牌信息并执行完整分析。")

    with st.form("one_click_input"):
        website_url = st.text_input("产品官网 URL", placeholder="https://example.com")
        uploaded_files = st.file_uploader("产品介绍 PDF（可多选）", type=["pdf"], accept_multiple_files=True)
        preferred_product_name = st.text_input("产品名 / 品牌名（可选，用于辅助识别）")
        category_local_hint = st.text_input("产品类目（中文，建议必填）", placeholder="例如：奶茶、火锅、汽车零部件")
        scope_label = st.selectbox("服务范围", list(SERVICE_SCOPE_OPTIONS.keys()), index=0)
        service_region = st.text_input("服务地区", placeholder="例如：福州；全国/全球可留空")
        geo_audience_label = st.selectbox("GEO 目标受众", list(GEO_AUDIENCE_OPTIONS.keys()), index=0)
        report_language_label = st.radio("报告语言", ["中文", "English"], horizontal=True)
        submitted = st.form_submit_button("生成产品画像", type="primary")

    if not submitted:
        return
    if not website_url.strip() and not uploaded_files:
        st.error("官网 URL 和 PDF 至少提供一个。")
        return
    service_scope = SERVICE_SCOPE_OPTIONS[scope_label]
    if service_scope in {"local_city", "regional"} and not service_region.strip():
        st.error("选择本地/区域服务时，请填写服务地区，例如：福州。")
        return
    if not require_qwen(config):
        return

    st.session_state.pop("integrated_result", None)
    st.session_state.pop("confirmed_profile", None)
    st.session_state.geo_console_logs = []
    report_language = "zh" if report_language_label == "中文" else "en"
    user_market_context = {
        "service_scope": service_scope,
        "service_scope_label": scope_label,
        "service_region": service_region.strip(),
        "category_local": category_local_hint.strip(),
        "geo_audience": GEO_AUDIENCE_OPTIONS[geo_audience_label],
        "geo_audience_label": geo_audience_label,
        "analysis_goal": GEO_AUDIENCE_OPTIONS[geo_audience_label],
        "analysis_goal_label": geo_audience_label,
        "market_language": "en" if service_scope == "global" and report_language == "en" else "zh",
        "target_market": "overseas" if service_scope == "global" else "domestic",
    }
    uploaded_pdfs = [UploadedPdf(name=file.name, data=file.getvalue()) for file in uploaded_files]

    with st.status("正在生成产品画像", expanded=True) as status:
        try:
            result = create_product_profile_run(
                storage=storage,
                config=config,
                website_url=website_url.strip(),
                uploaded_pdfs=uploaded_pdfs,
                preferred_product_name=preferred_product_name.strip(),
                user_market_context=user_market_context,
                report_language=report_language,
                progress=add_log,
            )
            st.session_state.profile_run = result
            st.session_state.report_language = report_language
            st.session_state.user_market_context = user_market_context
            status.update(label="产品画像已生成，请确认品牌信息", state="complete")
        except Exception as exc:
            status.update(label="产品画像生成失败", state="error")
            st.error(exc)
            add_log(f"错误：产品画像生成失败：{exc}")


def render_profile_confirmation(storage: Storage, config: AppConfig) -> None:
    profile_run = st.session_state.get("profile_run")
    if not profile_run or st.session_state.get("integrated_result"):
        return

    profile = profile_run.get("product_profile") or {}
    market_context = st.session_state.get("user_market_context") or profile_run.get("user_market_context") or {}
    is_domestic = (market_context.get("target_market") or profile.get("target_market")) != "overseas"
    st.markdown("### 确认产品与品牌信息")
    with st.form("confirm_profile"):
        product_name = st.text_input("产品名", value=str(profile.get("product_name", "")))
        brand_name = st.text_input("品牌名", value=str(profile.get("brand_name", "")))
        aliases = st.text_area(
            "品牌别名 / 产品线 / 母品牌（每行一个，用于合并统计）",
            value="\n".join(str(item) for item in profile.get("brand_aliases") or []),
            height=100,
        )
        c1, c2 = st.columns(2)
        category_local = c1.text_input(
            "产品类目（中文）",
            value=str(market_context.get("category_local") or profile.get("category_local", "")),
        )
        service_region = c2.text_input(
            "服务地区",
            value=str(market_context.get("service_region") or profile.get("primary_region", "")),
        )
        scope_labels = list(SERVICE_SCOPE_OPTIONS.keys())
        current_scope = market_context.get("service_scope", "local_city")
        current_scope_label = next((label for label, value in SERVICE_SCOPE_OPTIONS.items() if value == current_scope), "本地/城市")
        service_scope_label = st.selectbox("服务范围", scope_labels, index=scope_labels.index(current_scope_label))
        audience_labels = list(GEO_AUDIENCE_OPTIONS.keys())
        current_audience = market_context.get("geo_audience") or market_context.get("analysis_goal", "mixed")
        current_audience_label = next((label for label, value in GEO_AUDIENCE_OPTIONS.items() if value == current_audience), "综合受众")
        geo_audience_label = st.selectbox("GEO 目标受众", audience_labels, index=audience_labels.index(current_audience_label))
        if is_domestic:
            category_en = profile.get("category_en", "")
        else:
            category_en = st.text_input("英文类目", value=str(profile.get("category_en", "")))
        summary = st.text_area("产品简要分析", value=str(profile.get("summary", "")), height=120)
        submitted = st.form_submit_button("确认并执行完整分析", type="primary")

    with st.expander("查看 AI 生成的产品画像", expanded=False):
        st.markdown(profile.get("profile_md", ""))

    if not submitted:
        return
    if not product_name.strip() and not brand_name.strip():
        st.error("产品名或品牌名至少填写一个。")
        return
    service_scope = SERVICE_SCOPE_OPTIONS[service_scope_label]
    if service_scope in {"local_city", "regional"} and not service_region.strip():
        st.error("选择本地/区域服务时，请填写服务地区，例如：福州。")
        return
    if is_domestic and not category_local.strip():
        st.error("国内项目请填写中文产品类目，例如：奶茶。")
        return
    if not require_qwen(config):
        return

    final_market_context = {
        **market_context,
        "service_scope": service_scope,
        "service_scope_label": service_scope_label,
        "service_region": service_region.strip(),
        "category_local": category_local.strip(),
        "geo_audience": GEO_AUDIENCE_OPTIONS[geo_audience_label],
        "geo_audience_label": geo_audience_label,
        "analysis_goal": GEO_AUDIENCE_OPTIONS[geo_audience_label],
        "analysis_goal_label": geo_audience_label,
        "market_language": "en" if service_scope == "global" and not is_domestic else "zh",
        "target_market": "overseas" if service_scope == "global" and not is_domestic else "domestic",
    }
    confirmed_profile = {
        **profile,
        "product_name": product_name.strip(),
        "brand_name": brand_name.strip(),
        "brand_aliases": [line.strip() for line in aliases.splitlines() if line.strip()],
        "category_local": category_local.strip(),
        "category_en": str(category_en or "").strip(),
        "primary_region": service_region.strip(),
        "region_level": "city" if service_scope == "local_city" else ("province" if service_scope == "regional" else ("country" if service_scope == "national" else "global")),
        "service_scope": service_scope,
        "geo_audience": final_market_context["geo_audience"],
        "analysis_goal": final_market_context["analysis_goal"],
        "market_language": final_market_context["market_language"],
        "target_market": final_market_context["target_market"],
        "geo_probe_subject": f"{service_region.strip()}{category_local.strip()}品牌推荐".strip() if service_region.strip() else f"{category_local.strip()}品牌推荐",
        "summary": summary.strip(),
        "user_market_context": final_market_context,
    }
    st.session_state.confirmed_profile = confirmed_profile
    with st.status("正在执行 GEO 一键分析", expanded=True) as status:
        progress_bar = st.progress(0, text="准备启动")
        progress_text = st.empty()
        progress_events = st.empty()

        def progress_with_ui(message: str) -> None:
            add_log(message)
            percent = _analysis_progress_percent(message)
            progress_bar.progress(percent, text=message)
            progress_text.caption(f"当前进度：{percent}% · {message}")
            recent = st.session_state.get("geo_console_logs", [])[-8:]
            progress_events.markdown("\n".join(f"- {item}" for item in recent))

        try:
            result = run_integrated_geo_analysis(
                storage=storage,
                config=config,
                profile_run=profile_run,
                confirmed_profile=confirmed_profile,
                report_language=st.session_state.get("report_language", "zh"),
                trend_count=10,
                recommendations_per_term=10,
                progress=progress_with_ui,
            )
            st.session_state.integrated_result = result
            progress_bar.progress(100, text="GEO 一键分析完成")
            status.update(label="GEO 一键分析完成", state="complete")
        except Exception as exc:
            status.update(label="GEO 一键分析失败", state="error")
            st.error(exc)
            add_log(f"错误：GEO 一键分析失败：{exc}")


def render_history(storage: Storage) -> None:
    rows = storage.query(
        """
        select id, created_at, subject, customer_product, industry, file_path
        from strategy_reports
        where report_type='integrated_geo'
        order by id desc
        limit 30
        """
    )
    rows.extend(_scan_filesystem_history(rows))
    with st.expander("History", expanded=True):
        if not rows:
            st.info("No history found yet. Completed integrated GEO runs will appear here.")
            return
        st.dataframe(
            [
                {
                    "ID": item.get("id"),
                    "Created At": item.get("created_at"),
                    "Subject": item.get("subject") or item.get("customer_product"),
                    "Industry": item.get("industry"),
                    "Report": item.get("file_path"),
                }
                for item in rows
            ],
            width="stretch",
            hide_index=True,
        )
        options = {
            f"#{item.get('id')} | {item.get('created_at')} | {item.get('subject') or item.get('customer_product') or 'Untitled'}": item.get("id")
            for item in rows
        }
        selected_label = st.selectbox("Select history", list(options.keys()), key="history_report_select")
        if st.button("Load into current dashboard", key="load_history_report"):
            load_history_report(storage, options[selected_label])


def _scan_filesystem_history(existing_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing_paths = {
        str(Path(item.get("file_path")).resolve())
        for item in existing_rows
        if item.get("file_path")
    }
    report_dirs = Path("output/integrated_reports")
    if not report_dirs.exists():
        return []

    discovered: list[dict[str, Any]] = []
    for run_dir in sorted(report_dirs.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
        if not run_dir.is_dir():
            continue
        md_path = run_dir / "integrated_report.md"
        data_path = run_dir / "integrated_data.json"
        if not md_path.exists() and not data_path.exists():
            continue
        resolved_md = str(md_path.resolve()) if md_path.exists() else ""
        if resolved_md and resolved_md in existing_paths:
            continue
        payload: dict[str, Any] = {}
        if data_path.exists():
            try:
                payload = json.loads(data_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        subject = payload.get("subject") or payload.get("customer_product") or payload.get("product_profile", {}).get("product_name")
        discovered.append(
            {
                "id": f"{LEGACY_HISTORY_PREFIX}{run_dir.resolve()}",
                "created_at": datetime.fromtimestamp(run_dir.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "subject": subject,
                "customer_product": payload.get("customer_product"),
                "industry": payload.get("industry") or payload.get("product_profile", {}).get("industry"),
                "file_path": str(md_path if md_path.exists() else data_path),
            }
        )
    return discovered[:30]


def load_history_report(storage: Storage, report_id: Any) -> None:
    report: dict[str, Any] | None = None
    data: dict[str, Any] = {}
    if isinstance(report_id, str) and report_id.startswith(LEGACY_HISTORY_PREFIX):
        run_dir = Path(report_id[len(LEGACY_HISTORY_PREFIX) :])
        report = {
            "id": report_id,
            "raw_json": "{}",
            "file_path": str(run_dir / "integrated_report.md"),
        }
    else:
        report = storage.get_one(
            """
            select id, raw_json, file_path
            from strategy_reports
            where id=? and report_type='integrated_geo'
            """,
            (int(report_id),),
        )
        if not report:
            st.error("History report not found.")
            return
        data = json.loads(report.get("raw_json") or "{}")
        run_dir = Path(data.get("run_dir") or Path(report.get("file_path") or ".").parent)
    data_path = run_dir / "integrated_data.json"
    if data_path.exists():
        try:
            data = json.loads(data_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    md_path = Path(report.get("file_path") or run_dir / "integrated_report.md")
    html_path = run_dir / "integrated_report.html"
    dashboard_html_path = run_dir / "dashboard_report.html"
    data = enrich_analysis_data(data)
    if run_dir.exists():
        try:
            outputs = render_integrated_outputs(run_dir, data, data.get("report_language", "zh"))
            md_path = Path(outputs["report_md_path"])
            html_path = Path(outputs["report_html_path"])
            dashboard_html_path = Path(outputs["dashboard_html_path"])
        except Exception:
            pass
    st.session_state.integrated_result = {
        "report_id": report_id,
        "report_md_path": str(md_path),
        "report_html_path": str(html_path),
        "dashboard_html_path": str(dashboard_html_path),
        "data_path": str(data_path),
        "report_md": md_path.read_text(encoding="utf-8") if md_path.exists() else "",
        "analysis_data": data,
    }
    st.success("History loaded into the current dashboard.")


def render_result() -> None:
    result = st.session_state.get("integrated_result")
    if not result:
        return
    data = enrich_analysis_data(result.get("analysis_data") or {})
    run_dir_value = data.get("run_dir")
    if run_dir_value:
        run_dir = Path(run_dir_value)
        if run_dir.exists():
            try:
                outputs = render_integrated_outputs(run_dir, data, data.get("report_language", "zh"))
                dashboard_path = outputs.get("dashboard_html_path") or str(run_dir / "dashboard_report.html")
                result.update(
                    {
                        "report_md_path": outputs["report_md_path"],
                        "report_html_path": outputs["report_html_path"],
                        "dashboard_html_path": dashboard_path,
                        "data_path": outputs["data_path"],
                        "report_md": outputs["report_md"],
                        "analysis_data": enrich_analysis_data(data),
                    }
                )
                st.session_state.integrated_result = result
                data = result["analysis_data"]
            except Exception as exc:
                st.caption(f"报告已加载，但自动刷新 HTML/Markdown 失败：{exc}")
    labels = _labels(data.get("report_language", "zh"))

    st.markdown("### 分析结果")
    render_downloads(result)

    profile = data.get("product_profile") or {}
    strategy = data.get("analysis_strategy") or {}
    question_discovery = data.get("question_discovery") or data.get("trend_discovery") or {}
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(labels["product"], profile.get("product_name", ""))
    c2.metric(labels["brand"], profile.get("brand_name", ""))
    c3.metric(labels["category"], profile.get("category_local") or profile.get("category_en", ""))
    c4.metric("目标市场", question_discovery.get("target_market") or profile.get("target_market", ""))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("主要地区", question_discovery.get("primary_region") or profile.get("primary_region", ""))
    c6.metric("市场语言", question_discovery.get("market_language") or profile.get("market_language", ""))
    c7.metric("业务类型", question_discovery.get("business_type") or profile.get("business_type", ""))
    c8.metric("GEO 目标受众", strategy.get("geo_audience") or profile.get("geo_audience") or strategy.get("analysis_goal") or profile.get("analysis_goal", ""))

    tab_dashboard, tab_questions, tab_media, tab_report = st.tabs(["可视化看板", "AI 搜索问题", "媒介成本", "HTML/Markdown 报告"])
    with tab_dashboard:
        render_dashboard_charts_v2(data, labels)
    with tab_questions:
        questions = question_discovery.get("questions") or data.get("trend_discovery", {}).get("probe_questions") or []
        st.markdown("#### 第一步：AI 搜索问题设计")
        st.dataframe(questions, width="stretch", hide_index=True)
        neutral_queries = strategy.get("neutral_search_queries") or question_discovery.get("neutral_search_queries") or []
        if neutral_queries:
            st.markdown("#### 中立推荐问题（参与主排名）")
            st.dataframe([{"query": item} for item in neutral_queries], width="stretch", hide_index=True)
        diagnostic_queries = question_discovery.get("brand_diagnostic_questions") or []
        if diagnostic_queries:
            st.markdown("#### 品牌诊断问题（不参与主排名）")
            st.dataframe([{"query": item} for item in diagnostic_queries], width="stretch", hide_index=True)
        comparison_queries = question_discovery.get("comparison_questions") or []
        if comparison_queries:
            st.markdown("#### 竞品直接对比问题（不参与主排名）")
            st.dataframe([{"query": item} for item in comparison_queries], width="stretch", hide_index=True)
        visibility_queries = (data.get("visibility_query_strategy") or {}).get("visibility_queries") or []
        if visibility_queries:
            st.markdown("#### 全网声量查询方案")
            st.dataframe(visibility_queries, width="stretch", hide_index=True)
        if strategy:
            st.markdown("#### 分析策略")
            st.json(
                {
                    "geo_audience": strategy.get("geo_audience") or strategy.get("analysis_goal"),
                    "geo_probe_subject": strategy.get("geo_probe_subject"),
                    "service_scope": strategy.get("service_scope"),
                    "service_region": strategy.get("service_region"),
                    "topic_taxonomy": strategy.get("topic_taxonomy"),
                    "validation_notes": strategy.get("validation_notes"),
                },
                expanded=False,
            )
        st.json(
            {
                "source_language": question_discovery.get("source_language"),
                "market_language": question_discovery.get("market_language"),
                "target_market": question_discovery.get("target_market"),
                "primary_region": question_discovery.get("primary_region"),
                "region_level": question_discovery.get("region_level"),
                "business_type": question_discovery.get("business_type"),
                "geo_probe_subject": question_discovery.get("geo_probe_subject"),
                "market_reason": question_discovery.get("market_reason"),
            },
            expanded=False,
        )
        competitor_rows = _competitor_rows(data.get("competitor_discovery") or {})
        if competitor_rows:
            st.markdown("#### 竞品校准（按 AI 平台拆分）")
            platform_rows = _competitor_platform_rows(data.get("recommendation_items") or [])
            if platform_rows:
                _render_competitor_platform_tables(platform_rows)
            with st.expander("查看跨平台汇总校准", expanded=False):
                st.dataframe(competitor_rows, width="stretch", hide_index=True)
    with tab_media:
        render_media_cost(data)
    with tab_report:
        html_path = result.get("report_html_path", "")
        md = result.get("report_md") or ""
        if html_path and Path(html_path).exists():
            st.iframe(Path(html_path), height=900)
        if md:
            with st.expander("Markdown 原文", expanded=False):
                st.markdown(md)


def render_downloads(result: dict[str, Any]) -> None:
    paths = [
        ("下载 Markdown 报告", result.get("report_md_path", ""), "text/markdown"),
        ("下载 HTML 报告", result.get("report_html_path", ""), "text/html"),
        ("下载可视化看板 HTML", result.get("dashboard_html_path", ""), "text/html"),
        ("下载完整 JSON", result.get("data_path", ""), "application/json"),
    ]
    cols = st.columns(4)
    for idx, (label, path, mime) in enumerate(paths):
        file_path = Path(path) if path else None
        if file_path and file_path.exists():
            cols[idx].download_button(
                label,
                file_path.read_bytes(),
                file_name=file_path.name,
                mime=mime,
                key=f"download_{file_path}",
            )


def render_dashboard_charts_v2(data: dict[str, Any], labels: dict[str, str]) -> None:
    data = enrich_analysis_data(data)
    ranking = data.get("ai_recommendation_ranking") or data.get("brand_ranking") or []
    search_volume = data.get("search_volume_ranking") or []
    search_ranking = data.get("search_visibility_ranking") or []
    gap_ranking = data.get("competitive_gap_ranking") or []
    baidu = [
        {
            "brand_name": item.get("brand_name"),
            "mentioned_count": item.get("mentioned_count", 0),
            "result_count": item.get("result_count", 0),
            "query": item.get("query"),
            "error": item.get("error", ""),
            "is_user_brand": item.get("is_user_brand", False),
        }
        for item in data.get("baidu_mentions") or []
    ]
    topics = (data.get("content_topic_analysis") or {}).get("topics") or []
    matrix = (data.get("content_topic_analysis") or {}).get("brand_topic_matrix") or []
    provider_status = data.get("multi_ai_provider_status") or _provider_status_from_available_data(data)
    recommendation_source_rows = _recommendation_source_rows(data.get("recommendation_items") or [], ranking)
    source_articles = data.get("source_articles") or []
    visibility_summary = data.get("geo_visibility_summary") or {}
    neutral_summary = data.get("neutral_visibility_summary") or visibility_summary
    diagnostic_summary = data.get("brand_diagnostic_summary") or {}
    comparison_summary = data.get("comparison_summary") or {}
    brand_metrics = data.get("brand_visibility_metrics") or []
    prompt_runs = data.get("prompt_runs") or []
    diagnostic_prompt_runs = data.get("brand_diagnostic_prompt_runs") or []
    comparison_prompt_runs = data.get("comparison_prompt_runs") or []
    provider_matrix = data.get("provider_visibility_matrix") or []

    tab_overview, tab_step1, tab_step2, tab_step3 = st.tabs(["GEO可见度总览", "第一步：AI推荐排名", "第二步：五平台声量", "第三步：文章与定位分析"])
    with tab_overview:
        st.markdown("#### GEO 可见度体检")
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        k1.metric("中立推荐可见度", f"{neutral_summary.get('visibility_score', 0)}%")
        k2.metric("中立推荐提及", neutral_summary.get("mention_count", 0))
        avg_position = neutral_summary.get("avg_position")
        k3.metric("平均推荐位置", f"#{avg_position}" if avg_position else "未出现")
        k4.metric("品牌诊断情绪分", f"{diagnostic_summary.get('sentiment_score', neutral_summary.get('sentiment_score', 50))}/100")
        k5.metric("中立Prompt成功率", f"{round(float(neutral_summary.get('prompt_success_rate') or 0) * 100, 1)}%")
        k6.metric("平台覆盖", f"{neutral_summary.get('provider_coverage_count', 0)}/{neutral_summary.get('provider_total_count', 0)}")

        d1, d2, d3 = st.columns(3)
        d1.metric("品牌诊断提及", diagnostic_summary.get("brand_mentioned_responses", 0))
        d2.metric("诊断问题数", diagnostic_summary.get("prompt_count", len({item.get("prompt") for item in diagnostic_prompt_runs if item.get("prompt")})))
        d3.metric("竞品对比提及", comparison_summary.get("brand_mentioned_responses", 0))

        st.caption("主 GEO 可见度只计算不含客户品牌名的中立推荐问题；品牌诊断和竞品对比单独展示，不参与主推荐排名。当前五平台声量仍为 AI 估算。")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 平均推荐位置")
            _render_bar(brand_metrics, x="brand_name", y="avg_position", color="is_user_brand")
        with c2:
            st.markdown("#### AI 描述情绪分")
            _render_bar(brand_metrics, x="brand_name", y="sentiment_score", color="is_user_brand", use_index_axis=True, show_mapping_table=True)

        c3, c4 = st.columns(2)
        with c3:
            st.markdown("#### Prompt 触发表现")
            prompt_pie_rows = _prompt_pie_rows(prompt_runs)
            _render_pie(prompt_pie_rows, names="状态", values="数量")
        with c4:
            st.markdown("#### AI平台 x 品牌提及矩阵")
            matrix_rows = [
                {
                    "brand": item.get("brand_name", ""),
                    "topic": _provider_label(item.get("provider", "")),
                    "count": item.get("mention_count", 0),
                }
                for item in provider_matrix
            ]
            _render_heatmap(matrix_rows)

        with st.expander("查看 Prompt 级表现明细", expanded=False):
            if prompt_runs:
                st.dataframe(_prompt_run_display_rows(prompt_runs), width="stretch", hide_index=True)
            else:
                st.info("暂无 Prompt 级明细。")

    with tab_step1:
        st.markdown("#### 第一步输入：AI 搜索问题设计")
        _render_question_planning(data)

        st.markdown("#### 综合 AI 推荐排名")
        _render_bar(ranking, x="brand_name", y="recommendation_count", color="is_user_brand")

        st.markdown("#### 分 AI 平台推荐来源")
        if recommendation_source_rows:
            _render_recommendation_source_charts(recommendation_source_rows)
            with st.expander("查看完整 AI 推荐来源表", expanded=False):
                st.caption("Qwen / 豆包 / 元宝 / DeepSeek 列中的数字是该平台给出的推荐名次；空白表示该平台未推荐该品牌或调用失败。")
                st.dataframe(_stringify_rows(recommendation_source_rows), width="stretch", hide_index=True)
                st.table(_compact_recommendation_source_rows(recommendation_source_rows[:20]))
        else:
            st.info("暂无 AI 推荐来源明细。")

        platform_rows = _competitor_platform_rows(data.get("recommendation_items") or [])
        if platform_rows:
            st.markdown("#### 竞品校准（按 AI 平台展示）")
            _render_competitor_platform_tables(platform_rows)

        st.markdown("#### 品牌诊断与竞品直接对比")
        _render_diagnostic_and_comparison(data)

        st.markdown("#### 多 AI 平台调用状态")
        if provider_status:
            provider_rows = _provider_status_rows(provider_status)
            metric_cols = st.columns(min(4, len(provider_rows)))
            for idx, row in enumerate(provider_rows[:4]):
                metric_cols[idx].metric(
                    row["AI平台"],
                    row["推荐排名"],
                    f"推荐{row['推荐条数']} / 声量{row['声量品牌数']}",
                )
            _render_provider_status_chart(provider_rows)
            with st.expander("查看 AI 平台调用明细", expanded=False):
                st.table(_stringify_rows(provider_rows))
        else:
            st.info("暂无多 AI 平台状态数据。")

    with tab_step2:
        st.markdown("#### 综合五平台声量拆分")
        _render_platform_breakdown_charts(search_volume)
        st.markdown("#### 分 AI 平台五平台声量估算")
        _render_provider_visibility_charts(data)
        platform_rows = _visibility_platform_rows(search_volume)
        with st.expander("查看全网声量平台拆分明细", expanded=False):
            if platform_rows:
                st.dataframe(platform_rows, width="stretch", hide_index=True)
            else:
                st.info("暂无平台拆分数据。")

        st.markdown("#### 品牌内容声量排名")
        st.caption("含义：基于 AI 对百度、搜狗、360 搜索、抖音、小红书五个平台内容数量的估算，用来判断品牌在传统搜索与新媒体里的可见度；不是单一百度提及数。")
        _render_bar(search_ranking or baidu, x="brand_name", y="mentioned_count", color="is_user_brand")
        if search_ranking:
            with st.expander("查看品牌内容声量明细", expanded=False):
                st.dataframe(_search_visibility_display_rows(search_ranking), width="stretch", hide_index=True)
        st.markdown("#### AI 推荐与声量差距")
        _render_bar(gap_ranking, x="brand_name", y="gap_score", color="is_user_brand")
        if gap_ranking:
            with st.expander("查看 AI 推荐与内容声量差异明细", expanded=False):
                st.dataframe(_gap_display_rows(gap_ranking), width="stretch", hide_index=True)

    with tab_step3:
        st.markdown("#### 品牌调研与市场定位分析")
        content_report = data.get("content_pattern_report") or ""
        meta = data.get("content_analysis_meta") or _content_analysis_meta_from_articles(source_articles)
        if meta:
            c1, c2, c3 = st.columns(3)
            c1.metric("分析模型", meta.get("analysis_provider", "qwen"))
            c2.metric("成功抓取", meta.get("article_success_count", 0))
            c3.metric("抓取失败", meta.get("article_failed_count", 0))
        if content_report:
            positioning = data.get("content_positioning_analysis") or _derive_content_positioning_analysis(data)
            _render_content_positioning_charts(positioning, source_articles)
            with st.expander("查看完整品牌调研与市场定位文字报告", expanded=False):
                st.markdown(content_report)
        else:
            st.info("暂无文章分析报告。")

        st.markdown("#### 内容主题分布")
        _render_pie(topics, names="topic", values="count")
        if matrix:
            st.markdown("#### 品牌内容重点矩阵")
            _render_heatmap(matrix)

        st.markdown("#### 文章链接与抓取状态")
        article_rows = _source_article_rows(source_articles)
        if article_rows:
            _render_article_status_charts(article_rows)
            with st.expander("查看文章链接抓取明细", expanded=False):
                st.dataframe(article_rows, width="stretch", hide_index=True)
                st.caption("抓取失败通常表示目标站点 TLS、反爬、502 或连接中断；这只能说明本次自动抓取不可用，不代表该品牌没有内容资产。")
        else:
            st.info("暂无文章链接抓取数据。")


def render_dashboard_charts(data: dict[str, Any], labels: dict[str, str]) -> None:
    ranking = data.get("ai_recommendation_ranking") or data.get("brand_ranking") or []
    search_volume = data.get("search_volume_ranking") or []
    search_ranking = data.get("search_visibility_ranking") or []
    gap_ranking = data.get("competitive_gap_ranking") or []
    baidu = [
        {
            "brand_name": item.get("brand_name"),
            "mentioned_count": item.get("mentioned_count", 0),
            "result_count": item.get("result_count", 0),
            "query": item.get("query"),
            "error": item.get("error", ""),
        }
        for item in data.get("baidu_mentions") or []
    ]
    topics = (data.get("content_topic_analysis") or {}).get("topics") or []
    matrix = (data.get("content_topic_analysis") or {}).get("brand_topic_matrix") or []

    st.markdown("#### 全网搜索声量估算")
    _render_bar(search_volume, x="brand_name", y="estimated_result_count", color="is_user_brand")
    st.markdown("#### Top N 中立共现排名")
    _render_bar(search_ranking or baidu, x="brand_name", y="mentioned_count", color="is_user_brand")
    st.markdown(f"#### {labels['ranking']}（AI 可推荐度，不等于市场知名度）")
    _render_bar(ranking, x="brand_name", y="recommendation_count", color="is_user_brand")
    st.markdown("#### AI 推荐与搜索声量差距")
    _render_bar(gap_ranking, x="brand_name", y="gap_score", color="is_user_brand")
    st.markdown(f"#### {labels['baidu']}")
    _render_bar(baidu, x="brand_name", y="mentioned_count")
    st.markdown("#### 内容主题分布")
    _render_pie(topics, names="topic", values="count")
    if matrix:
        st.markdown("#### 品牌内容重点矩阵")
        _render_heatmap(matrix)


def render_media_cost(data: dict[str, Any]) -> None:
    cost = data.get("media_cost_analysis") or {}
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("对标竞品", cost.get("benchmark_brand", ""))
    c2.metric("竞品声量", cost.get("benchmark_mentioned_count", 0))
    c3.metric("客户声量", cost.get("user_brand_count", 0))
    c4.metric("内容资产差距", cost.get("content_asset_gap", 0))
    c5.metric("建议发布篇数", cost.get("target_articles", 0))
    st.caption(cost.get("planning_note", ""))
    st.metric("平均单篇成本", f"{cost.get('avg_unit_price', 0)} {cost.get('currency', 'CNY')}")
    _render_bar(cost.get("rows") or [], x="resource_title", y="estimated_total_cost")

    media_matches = (data.get("media_matches") or {}).get("matches") or []
    st.markdown("#### 媒介库匹配明细")
    st.dataframe(
        [
            {
                "domain": item.get("source_domain"),
                "match_type": item.get("match_type"),
                "resource_title": item.get("resource_title"),
                "confidence": item.get("confidence"),
                "price_1": item.get("price_1", 0),
                "price_2": item.get("price_2", 0),
                "price_3": item.get("price_3", 0),
                "warning": item.get("warning", ""),
            }
            for item in media_matches
        ],
        width="stretch",
        hide_index=True,
    )


def _recommendation_source_rows(items: list[dict[str, Any]], ranking: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank_lookup = {str(item.get("brand_name") or ""): item for item in ranking}
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if not brand:
            continue
        row = grouped.setdefault(
            brand,
            {
                "brand_name": brand,
                "综合排名": (rank_lookup.get(brand) or {}).get("ai_recommendation_rank", ""),
                "Qwen": "",
                "豆包": "",
                "元宝": "",
                "DeepSeek": "",
                "来源链接数": 0,
                "主要推荐理由": "",
                "_urls": [],
            },
        )
        provider = str(item.get("engine") or "").lower()
        label = {"qwen": "Qwen", "doubao": "豆包", "yuanbao": "元宝", "deepseek": "DeepSeek"}.get(provider)
        if label:
            current = row.get(label)
            rank = item.get("rank", "")
            row[label] = min([value for value in (current, rank) if isinstance(value, int)], default=rank) if current else rank
        row["_urls"].extend(item.get("citation_urls") or [])
        if not row["主要推荐理由"] and item.get("reason"):
            row["主要推荐理由"] = str(item.get("reason"))[:260]
    rows = []
    for row in grouped.values():
        row["来源链接数"] = len(list(dict.fromkeys(row.pop("_urls", []))))
        rows.append(row)
    return sorted(rows, key=lambda item: (int(item.get("综合排名") or 999), item.get("brand_name", "")))[:30]


def _render_question_planning(data: dict[str, Any]) -> None:
    question_discovery = data.get("question_discovery") or {}
    strategy = data.get("analysis_strategy") or {}
    trend = data.get("trend_discovery") or {}
    prompt_groups = question_discovery.get("prompt_groups") or strategy.get("prompt_groups") or {}
    questions = question_discovery.get("questions") or trend.get("probe_questions") or []
    neutral_queries = strategy.get("neutral_search_queries") or question_discovery.get("neutral_search_queries") or []
    diagnostic_queries = question_discovery.get("brand_diagnostic_questions") or []
    comparison_queries = question_discovery.get("comparison_questions") or []
    visibility_queries = (data.get("visibility_query_strategy") or {}).get("visibility_queries") or []

    rows: list[dict[str, Any]] = []
    group_labels = {
        "neutral_recommendation": "中立推荐排名",
        "brand_diagnostic": "品牌诊断",
        "comparison": "竞品直接对比",
    }
    if isinstance(prompt_groups, dict) and prompt_groups:
        for group_key, group_rows in prompt_groups.items():
            for item in group_rows or []:
                rows.append(
                    {
                        "模块": group_labels.get(group_key, group_key),
                        "输入/探测主题": item.get("intent") or "",
                        "实际问题/查询词": item.get("question") or "",
                        "用途": "主排名" if group_key == "neutral_recommendation" else "诊断展示，不参与主排名",
                        "说明": item.get("reason") or "",
                    }
                )
    else:
        for item in questions:
            rows.append(
                {
                    "模块": "中立推荐排名",
                    "输入/探测主题": item.get("term") or item.get("question") or "",
                    "实际问题/查询词": item.get("question") or item.get("term") or "",
                    "用途": item.get("intent") or item.get("question_type") or "AI 推荐排名",
                    "说明": item.get("reason") or "",
                }
            )
    for query in neutral_queries:
        rows.append(
            {
                "模块": "中立推荐问题",
                "输入/探测主题": query,
                "实际问题/查询词": query,
                "用途": "AI 推荐排名",
                "说明": "不包含客户品牌名，用于统计主流竞争排名。",
            }
        )
    for query in diagnostic_queries:
        rows.append(
            {
                "模块": "品牌诊断问题",
                "输入/探测主题": query,
                "实际问题/查询词": query,
                "用途": "品牌口碑/情绪分析",
                "说明": "允许包含客户品牌名，不参与主推荐排名。",
            }
        )
    for query in comparison_queries:
        rows.append(
            {
                "模块": "竞品直接对比问题",
                "输入/探测主题": query,
                "实际问题/查询词": query,
                "用途": "客户品牌 vs 头部竞品表现",
                "说明": "基于中立推荐排名选取竞品，不参与主推荐排名。",
            }
        )
    for item in visibility_queries[:12]:
        rows.append(
            {
                "模块": "品牌声量查询词",
                "输入/探测主题": item.get("brand_name", ""),
                "实际问题/查询词": item.get("query", ""),
                "用途": item.get("metric_goal", "五平台内容数量估算"),
                "说明": "",
            }
        )

    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("暂无 AI 搜索问题设计数据。")


def _prompt_pie_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"状态": "客户品牌被推荐", "数量": len([item for item in rows if item.get("brand_mentioned")])},
        {"状态": "客户品牌未出现", "数量": len([item for item in rows if not item.get("brand_mentioned")])},
    ]


def _render_diagnostic_and_comparison(data: dict[str, Any]) -> None:
    diagnostic_runs = data.get("brand_diagnostic_prompt_runs") or []
    comparison_runs = data.get("comparison_prompt_runs") or []
    diagnostic_items = data.get("brand_diagnostic_items") or []
    comparison_items = data.get("comparison_items") or []
    if not diagnostic_runs and not comparison_runs:
        st.info("暂无品牌诊断或竞品直接对比数据。")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### 品牌诊断触发表现")
        _render_pie(_prompt_pie_rows(diagnostic_runs), names="状态", values="数量")
        if diagnostic_items:
            _render_bar(_recommendation_source_rows(diagnostic_items, []), x="brand_name", y="来源链接数")
        with st.expander("查看品牌诊断明细", expanded=False):
            st.dataframe(_prompt_run_display_rows(diagnostic_runs), width="stretch", hide_index=True)
    with c2:
        st.markdown("##### 竞品直接对比表现")
        _render_pie(_prompt_pie_rows(comparison_runs), names="状态", values="数量")
        if comparison_items:
            _render_bar(_recommendation_source_rows(comparison_items, []), x="brand_name", y="来源链接数")
        with st.expander("查看竞品对比明细", expanded=False):
            st.dataframe(_prompt_run_display_rows(comparison_runs), width="stretch", hide_index=True)


def _competitor_platform_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if not brand:
            continue
        rows.append(
            {
                "AI平台": _provider_label(item.get("engine")),
                "平台推荐排名": _format_rank(item.get("rank")),
                "品牌": brand,
                "搜索问题": item.get("question") or item.get("trend_term") or "",
                "推荐理由": str(item.get("reason") or "")[:260],
                "引用链接数": len(item.get("citation_urls") or []),
            }
        )
    order = {"Qwen": 1, "豆包": 2, "元宝": 3, "DeepSeek": 4}
    return sorted(rows, key=lambda item: (order.get(str(item.get("AI平台")), 99), _safe_int(item.get("平台推荐排名")), str(item.get("品牌"))))


def _render_competitor_platform_tables(rows: list[dict[str, Any]]) -> None:
    providers = [provider for provider in ("Qwen", "豆包", "元宝", "DeepSeek") if any(item.get("AI平台") == provider for item in rows)]
    if not providers:
        st.dataframe(rows, width="stretch", hide_index=True)
        return
    tabs = st.tabs(providers)
    for tab, provider in zip(tabs, providers):
        with tab:
            provider_rows = [item for item in rows if item.get("AI平台") == provider]
            st.dataframe(provider_rows, width="stretch", hide_index=True)


def _format_rank(value: Any) -> str:
    if value in (None, "", "None"):
        return "未获取"
    try:
        number = float(str(value).strip())
        if number <= 0:
            return "未获取"
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
    except Exception:
        return str(value)


def _stringify_rows(rows: list[dict[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for row in rows or []:
        clean: dict[str, str] = {}
        for key, value in (row or {}).items():
            if isinstance(value, (dict, list, tuple, set)):
                clean[str(key)] = json.dumps(value, ensure_ascii=False)
            elif value is None:
                clean[str(key)] = ""
            else:
                clean[str(key)] = str(value)
        result.append(clean)
    return result


def _format_count(value: Any, has_data: bool | None = None) -> str:
    if value in (None, "", "None"):
        return "未获取"
    number = _safe_int(value)
    if has_data is False and number == 0:
        return "未获取"
    return str(number)


def _search_visibility_display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows:
        has_data = item.get("search_visibility_rank") not in (None, "", "None") or _safe_int(item.get("mentioned_count")) > 0
        result.append(
            {
                "品牌": item.get("brand_name", ""),
                "品牌内容声量排名": _format_rank(item.get("search_visibility_rank")),
                "五平台内容数量估算": _format_count(item.get("mentioned_count"), has_data),
                "结果数估算": _format_count(item.get("result_count"), has_data),
                "查询词": item.get("query", ""),
                "数据口径": item.get("metric_type") or "五平台内容数量估算",
                "说明": item.get("warning") or "",
            }
        )
    return result


def _gap_display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows:
        has_visibility = item.get("search_visibility_rank") not in (None, "", "None") or _safe_int(item.get("mentioned_count")) > 0
        result.append(
            {
                "品牌": item.get("brand_name", ""),
                "AI排名": _format_rank(item.get("ai_recommendation_rank")),
                "品牌内容声量排名": _format_rank(item.get("search_visibility_rank")) if has_visibility else "未进入声量估算",
                "五平台内容数量估算": _format_count(item.get("mentioned_count"), has_visibility),
                "解读": item.get("gap_label") if has_visibility else "AI 推荐中出现，但本轮未拿到有效五平台声量估算；不是确认没有内容。",
            }
        )
    return result


def _provider_status_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    labels = {"qwen": "Qwen", "doubao": "豆包", "yuanbao": "元宝", "deepseek": "DeepSeek"}
    result = []
    for item in rows:
        provider = str(item.get("provider") or "")
        recommendation_ok = bool(item.get("recommendation_ok"))
        visibility_ok = bool(item.get("visibility_ok"))
        error = item.get("recommendation_error") or item.get("visibility_error") or ""
        result.append(
            {
                "AI平台": labels.get(provider.lower(), provider),
                "推荐排名": "OK" if recommendation_ok else "FAIL",
                "推荐条数": item.get("recommendation_count", 0),
                "声量估算": "OK" if visibility_ok else "FAIL",
                "声量品牌数": item.get("visibility_count", 0),
                "模型": item.get("model") or "",
                "接口": item.get("endpoint") or "",
                "超时秒数": item.get("timeout") or "",
                "错误信息": str(error)[:180],
            }
        )
    return result


def _prompt_run_display_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows:
        result.append(
            {
                "AI平台": _provider_label(item.get("provider", "")),
                "问题类型": _prompt_type_label(item.get("prompt_type", "")),
                "测试问题": item.get("prompt", ""),
                "客户品牌是否出现": "是" if item.get("brand_mentioned") else "否",
                "推荐位置": _format_rank(item.get("brand_position")) if item.get("brand_position") else "未出现",
                "情绪分": item.get("sentiment_score", 50),
                "共现竞品": "、".join(str(value) for value in (item.get("co_occurring_brands") or [])[:6]),
                "引用链接数": len(item.get("citation_urls") or []),
                "状态": "OK" if item.get("ok") else "FAIL",
                "错误": item.get("error", ""),
            }
        )
    return result


def _prompt_type_label(value: Any) -> str:
    return {
        "neutral_recommendation": "中立推荐",
        "brand_diagnostic": "品牌诊断",
        "comparison": "竞品对比",
    }.get(str(value or ""), str(value or ""))


def _provider_status_from_available_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    rec_results = data.get("multi_ai_recommendation_results") or []
    vis_results = data.get("multi_ai_visibility_results") or []
    names = list(dict.fromkeys([item.get("provider", "") for item in rec_results] + [item.get("provider", "") for item in vis_results]))
    rows = []
    for name in [item for item in names if item]:
        rec = next((item for item in rec_results if item.get("provider") == name), {})
        vis = next((item for item in vis_results if item.get("provider") == name), {})
        rec_rows = ((rec.get("parsed") or {}).get("recommendations") or []) if isinstance(rec.get("parsed"), dict) else []
        vis_rows = ((vis.get("parsed") or {}).get("brand_visibility") or []) if isinstance(vis.get("parsed"), dict) else []
        rows.append(
            {
                "provider": name,
                "recommendation_ok": bool(rec.get("ok")),
                "visibility_ok": bool(vis.get("ok")),
                "recommendation_error": rec.get("error", ""),
                "visibility_error": vis.get("error", ""),
                "recommendation_count": len(rec_rows),
                "visibility_count": len(vis_rows),
                "model": rec.get("model") or vis.get("model") or "",
                "endpoint": rec.get("endpoint") or vis.get("endpoint") or "",
                "timeout": rec.get("timeout") or vis.get("timeout") or "",
            }
        )
    if rows:
        return rows

    by_provider: dict[str, int] = {}
    for item in data.get("recommendation_items") or []:
        provider = str(item.get("engine") or "").strip()
        if provider:
            by_provider[provider] = by_provider.get(provider, 0) + 1
    return [
        {
            "provider": provider,
            "recommendation_ok": count > 0,
            "visibility_ok": False,
            "recommendation_error": "",
            "visibility_error": "历史数据缺少声量估算平台状态",
            "recommendation_count": count,
            "visibility_count": 0,
            "model": "",
            "endpoint": "",
            "timeout": "",
        }
        for provider, count in by_provider.items()
    ]


def _compact_recommendation_source_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows:
        source_parts = []
        for label in ("Qwen", "豆包", "元宝", "DeepSeek"):
            rank = item.get(label)
            if rank not in ("", None):
                source_parts.append(f"{label}#{rank}")
        result.append(
            {
                "品牌": item.get("brand_name", ""),
                "综合排名": item.get("综合排名", ""),
                "推荐来源": "；".join(source_parts) or "无",
                "来源链接数": item.get("来源链接数", 0),
                "主要推荐理由": str(item.get("主要推荐理由") or "")[:180],
            }
        )
    return result


def _recommendation_chart_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows[:20]:
        brand = item.get("brand_name", "")
        for provider in ("Qwen", "豆包", "元宝", "DeepSeek"):
            rank = item.get(provider)
            if rank in ("", None):
                continue
            try:
                rank_value = int(rank)
            except Exception:
                continue
            result.append(
                {
                    "品牌": brand,
                    "AI平台": provider,
                    "推荐名次": rank_value,
                    "推荐得分": max(1, 11 - rank_value),
                    "综合排名": item.get("综合排名", ""),
                }
            )
    return result


def _visibility_platform_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows:
        traditional = item.get("traditional_search") or {}
        new_media = item.get("new_media") or {}
        result.append(
            {
                "品牌": item.get("brand_name", ""),
                "总声量估算": item.get("estimated_result_count", 0),
                "百度": traditional.get("baidu", 0),
                "搜狗": traditional.get("sogou", 0),
                "360": traditional.get("so360", 0),
                "抖音": new_media.get("douyin", 0),
                "小红书": new_media.get("xiaohongshu", 0),
                "参与AI数": item.get("provider_count", 0),
                "消息来源/依据": _source_note(item),
            }
        )
    return result


def _source_note(item: dict[str, Any]) -> str:
    urls = item.get("source_urls") or []
    if urls:
        return "；".join(str(url) for url in urls[:3])
    notes = item.get("notes") or []
    if notes:
        return "；".join(str(note) for note in notes[:2])
    return str(item.get("warning") or "")


def _source_article_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows[:80]:
        ok = bool(item.get("text_excerpt")) and not item.get("error")
        result.append(
            {
                "品牌/来源": item.get("label", ""),
                "域名": item.get("domain", ""),
                "AI来源": item.get("engine", ""),
                "抓取状态": "成功" if ok else "失败",
                "正文长度": len(item.get("text_excerpt") or ""),
                "链接/错误": item.get("url") if ok else item.get("error") or item.get("url"),
            }
        )
    return result


def _content_analysis_meta_from_articles(rows: list[dict[str, Any]]) -> dict[str, Any]:
    success = len([item for item in rows if item.get("text_excerpt") and not item.get("error")])
    failed = len([item for item in rows if item.get("error") or not item.get("text_excerpt")])
    return {
        "analysis_provider": "qwen",
        "article_total": len(rows),
        "article_success_count": success,
        "article_failed_count": failed,
    }


def _derive_content_positioning_analysis(data: dict[str, Any]) -> dict[str, Any]:
    ranking = data.get("ai_recommendation_ranking") or []
    items = data.get("recommendation_items") or []
    articles = data.get("source_articles") or []
    by_brand: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if brand:
            by_brand.setdefault(brand, []).append(item)
    success_labels = {str(item.get("label") or "") for item in articles if item.get("text_excerpt") and not item.get("error")}
    analysis = {
        "category_boundary": [],
        "price_bands": [],
        "psychology_motives": [],
        "decision_heuristics": [],
        "personas": [],
        "selling_points": [],
        "digital_asset_scores": [],
    }
    for brand in ranking[:12]:
        name = str(brand.get("brand_name") or "")
        reasons = by_brand.get(name) or []
        text = " ".join(str(item.get("reason") or "") for item in reasons)
        analysis["category_boundary"].append(
            {"brand_name": name, "boundary_type": _infer_boundary_type(text), "positioning": text[:80], "evidence": text[:120]}
        )
        analysis["price_bands"].append({"brand_name": name, "price_band": _infer_price_band(text), "estimated_unit_price": "", "evidence": text[:120] or "依据不足"})
        for motive, score in _infer_motive_scores(text).items():
            analysis["psychology_motives"].append({"brand_name": name, "motive": motive, "score": score, "evidence": text[:120]})
        for heuristic, score in _infer_heuristic_scores(text).items():
            analysis["decision_heuristics"].append({"brand_name": name, "heuristic": heuristic, "score": score, "evidence": text[:120]})
        analysis["personas"].append(
            {
                "brand_name": name,
                "age": "25-45 或依据不足",
                "spending_power": _infer_price_band(text),
                "scenario": "项目对比/安全背书/案例验证/价格咨询",
                "concern": "安全、资质、医生、案例、价格",
                "content_preference": "榜单推荐、案例对比、医生资质、项目科普",
            }
        )
        for point in _selling_points_from_text(text)[:5]:
            analysis["selling_points"].append({"brand_name": name, "selling_point": point, "source_type": "AI推荐理由", "evidence": text[:120]})
        has_article = any(name in label or label in name for label in success_labels if label)
        analysis["digital_asset_scores"].append(
            {
                "brand_name": name,
                "search_asset_score": min(100, int(brand.get("recommendation_count") or 0) * 25),
                "content_platform_score": min(100, len(reasons) * 20),
                "website_access_score": 80 if has_article else 20,
                "proof_asset_score": min(100, len(_selling_points_from_text(text)) * 20),
                "gap": "补充可访问案例、价格带、资质、项目页和平台内容。",
            }
        )
    return analysis


def _render_content_positioning_charts(analysis: dict[str, Any], source_articles: list[dict[str, Any]]) -> None:
    try:
        import pandas as pd
        import plotly.express as px

        c1, c2 = st.columns(2)
        boundary = pd.DataFrame(analysis.get("category_boundary") or [])
        with c1:
            if not boundary.empty and "boundary_type" in boundary:
                counts = boundary.groupby("boundary_type", as_index=False).size().rename(columns={"boundary_type": "品类边界", "size": "品牌数"})
                fig = px.pie(counts, names="品类边界", values="品牌数", hole=0.35, title="品类边界分布", height=360)
                fig.update_traces(textinfo="label+percent+value")
                st.plotly_chart(fig, width="stretch")
        motives = pd.DataFrame(analysis.get("psychology_motives") or [])
        with c2:
            if not motives.empty and "motive" in motives:
                totals = motives.groupby("motive", as_index=False)["score"].sum().rename(columns={"motive": "消费动机", "score": "强度"})
                fig = px.bar(totals, x="消费动机", y="强度", color="消费动机", title="消费心理动机", height=360)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width="stretch")

        heuristics = pd.DataFrame(analysis.get("decision_heuristics") or [])
        selling_points = pd.DataFrame(analysis.get("selling_points") or [])
        c3, c4 = st.columns(2)
        with c3:
            if not heuristics.empty and "heuristic" in heuristics:
                totals = heuristics.groupby("heuristic", as_index=False)["score"].sum().rename(columns={"heuristic": "决策捷径", "score": "强度"})
                fig = px.bar(totals.sort_values("强度", ascending=True), x="强度", y="决策捷径", orientation="h", title="决策捷径/心理启发式", height=420)
                st.plotly_chart(fig, width="stretch")
        with c4:
            price = pd.DataFrame(analysis.get("price_bands") or [])
            if not price.empty and "price_band" in price:
                counts = price.groupby("price_band", as_index=False).size().rename(columns={"price_band": "价格带", "size": "品牌数"})
                fig = px.pie(counts, names="价格带", values="品牌数", hole=0.35, title="价格带/客单价定位", height=420)
                fig.update_traces(textinfo="label+percent+value")
                st.plotly_chart(fig, width="stretch")

        c5, c6 = st.columns(2)
        with c5:
            personas = pd.DataFrame(analysis.get("personas") or [])
            if not personas.empty and "spending_power" in personas:
                counts = personas.groupby("spending_power", as_index=False).size().rename(columns={"spending_power": "用户消费能力", "size": "品牌数"})
                fig = px.bar(counts, x="用户消费能力", y="品牌数", color="用户消费能力", title="用户画像：消费能力分布", height=360)
                fig.update_layout(showlegend=False)
                st.plotly_chart(fig, width="stretch")
        with c6:
            if not selling_points.empty:
                counts = selling_points.groupby("brand_name", as_index=False).size().rename(columns={"brand_name": "品牌", "size": "卖点数量"})
                fig = px.bar(counts.sort_values("卖点数量", ascending=True).tail(12), x="卖点数量", y="品牌", orientation="h", title="各品牌卖点数量", height=420)
                st.plotly_chart(fig, width="stretch")

        scores = pd.DataFrame(analysis.get("digital_asset_scores") or [])
        if not scores.empty:
            score_cols = ["search_asset_score", "content_platform_score", "website_access_score", "proof_asset_score"]
            score_df = scores[["brand_name", *[col for col in score_cols if col in scores.columns]]].rename(
                columns={
                    "brand_name": "品牌",
                    "search_asset_score": "搜索资产",
                    "content_platform_score": "内容平台资产",
                    "website_access_score": "官网可访问性",
                    "proof_asset_score": "信任证明资产",
                }
            )
            melted = score_df.melt(id_vars=["品牌"], var_name="资产类型", value_name="评分")
            fig = px.bar(melted, x="品牌", y="评分", color="资产类型", barmode="group", title="数字资产评分", height=460)
            fig.update_layout(margin=dict(l=20, r=20, t=50, b=100))
            st.plotly_chart(fig, width="stretch")

    except Exception:
        st.info("文章定位图表生成失败，已保留文字报告。")


def _platform_breakdown_chart_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows[:20]:
        traditional, new_media = _platform_values_from_volume_item(item)
        brand = item.get("brand_name", "")
        values = {
            "百度": traditional.get("baidu", 0),
            "搜狗": traditional.get("sogou", 0),
            "360搜索": traditional.get("so360", 0),
            "抖音": new_media.get("douyin", 0),
            "小红书": new_media.get("xiaohongshu", 0),
        }
        for platform, count in values.items():
            result.append(
                {
                    "品牌": brand,
                    "平台": platform,
                    "内容数量估算": _safe_int(count),
                    "品牌类型": "客户品牌" if item.get("is_user_brand") else "竞品",
                }
            )
    return result


def _platform_values_from_volume_item(item: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    traditional = {key: _safe_int(value) for key, value in (item.get("traditional_search") or {}).items()}
    new_media = {key: _safe_int(value) for key, value in (item.get("new_media") or {}).items()}
    if any(traditional.values()) or any(new_media.values()):
        return traditional, new_media

    estimates = [estimate for estimate in item.get("provider_estimates") or [] if isinstance(estimate, dict)]
    if not estimates:
        return traditional, new_media
    traditional_totals = {"baidu": 0, "sogou": 0, "so360": 0}
    new_media_totals = {"douyin": 0, "xiaohongshu": 0}
    for estimate in estimates:
        for key in traditional_totals:
            traditional_totals[key] += _safe_int((estimate.get("traditional_search") or {}).get(key, 0))
        for key in new_media_totals:
            new_media_totals[key] += _safe_int((estimate.get("new_media") or {}).get(key, 0))
    provider_count = max(len(estimates), 1)
    return (
        {key: round(value / provider_count) for key, value in traditional_totals.items()},
        {key: round(value / provider_count) for key, value in new_media_totals.items()},
    )


def _render_platform_breakdown_charts(rows: list[dict[str, Any]]) -> None:
    chart_rows = _platform_breakdown_chart_rows(rows)
    if not chart_rows:
        st.info("暂无五平台拆分数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(chart_rows)
        total = df.groupby("平台", as_index=False)["内容数量估算"].sum()
        fig = px.pie(total, names="平台", values="内容数量估算", hole=0.35, height=460, title="五平台总占比")
        fig.update_traces(textinfo="label+percent+value")
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20), legend_title_text="平台")
        st.plotly_chart(fig, width="stretch")

        total_sorted = total.sort_values("内容数量估算", ascending=True)
        fig_bar = px.bar(total_sorted, x="内容数量估算", y="平台", orientation="h", color="平台", height=360, title="五平台内容数量对比")
        fig_bar.update_layout(margin=dict(l=80, r=20, t=50, b=50), showlegend=False)
        fig_bar.update_xaxes(title_text="内容数量估算")
        fig_bar.update_yaxes(title_text="平台")
        st.plotly_chart(fig_bar, width="stretch")

        top_brands = (
            df.groupby("品牌", as_index=False)["内容数量估算"].sum()
            .sort_values("内容数量估算", ascending=False)
            .head(10)["品牌"]
            .tolist()
        )
        brand_df = df[df["品牌"].isin(top_brands)]
        fig2 = px.bar(brand_df, x="品牌", y="内容数量估算", color="平台", height=460, title="各品牌五平台拆分")
        fig2.update_layout(barmode="stack", margin=dict(l=20, r=20, t=50, b=100), legend_title_text="平台")
        fig2.update_xaxes(title_text="品牌")
        fig2.update_yaxes(title_text="内容数量估算")
        st.plotly_chart(fig2, width="stretch")
    except Exception:
        st.dataframe(chart_rows, width="stretch", hide_index=True)


def _provider_visibility_chart_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in data.get("search_volume_ranking") or []:
        brand = item.get("brand_name", "")
        for estimate in item.get("provider_estimates") or []:
            provider = _provider_label(estimate.get("provider", ""))
            traditional = estimate.get("traditional_search") or {}
            new_media = estimate.get("new_media") or {}
            values = {
                "百度": traditional.get("baidu", 0),
                "搜狗": traditional.get("sogou", 0),
                "360搜索": traditional.get("so360", 0),
                "抖音": new_media.get("douyin", 0),
                "小红书": new_media.get("xiaohongshu", 0),
            }
            for platform, count in values.items():
                result.append(
                    {
                        "AI平台": provider,
                        "品牌": brand,
                        "平台": platform,
                        "内容数量估算": _safe_int(count),
                    }
                )
    return result


def _render_provider_visibility_charts(data: dict[str, Any]) -> None:
    rows = _provider_visibility_chart_rows(data)
    if not rows:
        st.info("暂无分 AI 平台声量估算数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(rows)
        provider_platform = df.groupby(["AI平台", "平台"], as_index=False)["内容数量估算"].sum()
        fig = px.bar(
            provider_platform,
            x="AI平台",
            y="内容数量估算",
            color="平台",
            height=420,
            title="各 AI 平台对五平台声量的估算",
        )
        fig.update_layout(barmode="stack", margin=dict(l=20, r=20, t=50, b=70), legend_title_text="平台")
        fig.update_xaxes(title_text="AI平台")
        fig.update_yaxes(title_text="内容数量估算")
        st.plotly_chart(fig, width="stretch")

        provider_brand = df.groupby(["AI平台", "品牌"], as_index=False)["内容数量估算"].sum()
        top_brands = (
            provider_brand.groupby("品牌", as_index=False)["内容数量估算"].sum()
            .sort_values("内容数量估算", ascending=False)
            .head(10)["品牌"]
            .tolist()
        )
        fig2 = px.bar(
            provider_brand[provider_brand["品牌"].isin(top_brands)],
            x="品牌",
            y="内容数量估算",
            color="AI平台",
            barmode="group",
            height=440,
            title="各 AI 平台给出的品牌声量 Top 对比",
        )
        fig2.update_layout(margin=dict(l=20, r=20, t=50, b=100), legend_title_text="AI平台")
        fig2.update_xaxes(title_text="品牌")
        fig2.update_yaxes(title_text="内容数量估算")
        st.plotly_chart(fig2, width="stretch")

        with st.expander("查看分 AI 平台声量估算明细", expanded=False):
            st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_provider_status_chart(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    try:
        import pandas as pd
        import plotly.express as px

        chart_rows = []
        for item in rows:
            chart_rows.append({"AI平台": item["AI平台"], "任务": "推荐排名", "状态": item["推荐排名"], "返回数量": item["推荐条数"]})
            chart_rows.append({"AI平台": item["AI平台"], "任务": "声量估算", "状态": item["声量估算"], "返回数量": item["声量品牌数"]})
        df = pd.DataFrame(chart_rows)
        fig = px.bar(df, x="AI平台", y="返回数量", color="任务", pattern_shape="状态", height=360)
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=60), legend_title_text="任务")
        fig.update_xaxes(title_text="AI平台")
        fig.update_yaxes(title_text="返回数量")
        st.plotly_chart(fig, width="stretch")
    except Exception:
        pass


def _render_recommendation_source_charts(rows: list[dict[str, Any]]) -> None:
    chart_rows = _recommendation_chart_rows(rows)
    if not chart_rows:
        st.info("暂无可绘制的 AI 推荐来源数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(chart_rows)
        provider_share = df.groupby("AI平台", as_index=False).agg(推荐品牌数=("品牌", "nunique"), 推荐热度=("推荐得分", "sum"))
        fig = px.pie(
            provider_share,
            names="AI平台",
            values="推荐品牌数",
            hole=0.35,
            height=430,
            title="AI 推荐来源占比",
        )
        fig.update_traces(textinfo="label+percent+value")
        fig.update_layout(margin=dict(l=20, r=20, t=50, b=20), legend_title_text="AI平台")
        st.plotly_chart(fig, width="stretch")

        heatmap_df = df.copy()
        heatmap_df["名次热度"] = heatmap_df["推荐名次"].map(lambda value: max(1, 11 - int(value)))
        pivot = heatmap_df.pivot_table(index="品牌", columns="AI平台", values="名次热度", aggfunc="max", fill_value=0)
        fig2 = px.imshow(
            pivot.head(20),
            aspect="auto",
            height=460,
            color_continuous_scale="YlGnBu",
            labels=dict(x="AI平台", y="品牌", color="推荐热度"),
        )
        fig2.update_layout(margin=dict(l=140, r=20, t=20, b=80))
        st.plotly_chart(fig2, width="stretch")
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_article_status_charts(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("暂无数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(rows)
        status = df.groupby("抓取状态", as_index=False).size().rename(columns={"size": "链接数量"})
        c1, c2 = st.columns(2)
        with c1:
            fig = px.pie(status, names="抓取状态", values="链接数量", hole=0.35, height=360)
            fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, width="stretch")
        with c2:
            by_engine = df.groupby(["AI来源", "抓取状态"], as_index=False).size().rename(columns={"size": "链接数量"})
            fig2 = px.bar(by_engine, x="AI来源", y="链接数量", color="抓取状态", height=360)
            fig2.update_layout(margin=dict(l=20, r=20, t=20, b=60), legend_title_text="抓取状态")
            fig2.update_xaxes(title_text="AI来源")
            fig2.update_yaxes(title_text="链接数量")
            st.plotly_chart(fig2, width="stretch")
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _chart_label(name: str) -> str:
    return {
        "brand_name": "品牌",
        "mentioned_count": "传统搜索声量",
        "result_count": "全网声量估算",
        "estimated_result_count": "全网声量估算",
        "recommendation_count": "AI推荐次数",
        "gap_score": "排名差距",
        "is_user_brand": "品牌类型",
        "topic": "内容主题",
        "count": "次数",
        "resource_title": "媒介资源",
        "estimated_total_cost": "预估成本",
    }.get(name, name)


def _safe_int(value: Any) -> int:
    try:
        return max(int(float(str(value or 0).replace(",", "").strip() or 0)), 0)
    except Exception:
        return 0


def _provider_label(value: Any) -> str:
    key = str(value or "").strip().lower()
    return {"qwen": "Qwen", "doubao": "豆包", "yuanbao": "元宝", "deepseek": "DeepSeek"}.get(key, str(value or ""))


def _infer_boundary_type(text: str) -> str:
    if any(word in text for word in ("三甲", "医院", "医美", "整形", "皮肤", "医生", "科室")):
        return "卖服务"
    if any(word in text for word in ("场景", "体验", "空间", "生活方式")):
        return "卖场景"
    if any(word in text for word in ("解决方案", "一站式", "综合")):
        return "卖解决方案"
    if any(word in text for word in ("产品", "配件", "设备")):
        return "卖产品"
    return "混合/依据不足"


def _infer_price_band(text: str) -> str:
    if any(word in text for word in ("高端", "轻奢", "高价", "私享", "定制")):
        return "高"
    if any(word in text for word in ("收费合理", "性价比", "亲民", "低价")):
        return "中低"
    if any(word in text for word in ("连锁", "大型", "综合", "主流")):
        return "中"
    return "未知"


def _infer_motive_scores(text: str) -> dict[str, int]:
    result = {"功能价值": 1}
    if any(word in text for word in ("安全", "资质", "医生", "设备", "技术", "效果", "正规")):
        result["功能价值"] = 3
    if any(word in text for word in ("安心", "服务", "体验", "口碑", "信任", "环境")):
        result["情感价值"] = 2
    if any(word in text for word in ("高端", "轻奢", "审美", "定制", "身份")):
        result["自我实现"] = 2
    return result


def _infer_heuristic_scores(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    if any(word in text for word in ("排名", "前十", "知名", "主流", "老牌", "用户基数")):
        result["从众效应"] = 2
    if any(word in text for word in ("三甲", "资质", "专家", "博士", "医生", "权威")):
        result["权威背书"] = 3
    if any(word in text for word in ("案例", "对比", "口碑", "评价")):
        result["社会认同"] = 2
    if any(word in text for word in ("价格", "收费", "套餐")):
        result["锚定效应"] = 1
    return result or {"依据不足": 1}


def _selling_points_from_text(text: str) -> list[str]:
    parts = []
    for token in re.split(r"[，,。；;\n、]", str(text or "")):
        token = token.strip()
        if 4 <= len(token) <= 40:
            parts.append(token)
    return list(dict.fromkeys(parts))[:5] or ["资质背书", "服务项目覆盖", "医生/技术能力", "案例或口碑", "本地可达性"]


def _render_stacked_visibility(rows: list[dict[str, Any]]) -> None:
    if not rows:
        st.info("暂无数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        source = []
        for item in rows[:20]:
            source.append({"品牌": item.get("brand_name", ""), "平台类型": "传统搜索", "声量估算": item.get("traditional_search_count", 0)})
            source.append({"品牌": item.get("brand_name", ""), "平台类型": "新媒体", "声量估算": item.get("new_media_count", 0)})
        df = pd.DataFrame(source)
        fig = px.bar(df, x="品牌", y="声量估算", color="平台类型", height=440)
        fig.update_layout(barmode="stack", margin=dict(l=20, r=20, t=20, b=100), legend_title_text="平台类型")
        fig.update_xaxes(title_text="品牌")
        fig.update_yaxes(title_text="声量估算")
        st.plotly_chart(fig, width="stretch")
        with st.expander("查看声量估算原始数据", expanded=False):
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_bar(
    rows: list[dict[str, Any]],
    x: str,
    y: str,
    color: str | None = None,
    use_index_axis: bool = False,
    show_mapping_table: bool = False,
) -> None:
    if not rows:
        st.info("No data available.")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(rows)
        chart_df = df.head(20).copy()
        chart_x = _chart_label(x)
        chart_y = _chart_label(y)
        chart_color = None
        if color and color in chart_df.columns:
            chart_color = _chart_label(color)
            if color == "is_user_brand":
                chart_df[chart_color] = chart_df[color].map(lambda value: "Customer Brand" if bool(value) else "Competitor")
            else:
                chart_df[chart_color] = chart_df[color]
        if x in chart_df.columns:
            chart_df[chart_x] = chart_df[x]
        if y in chart_df.columns:
            chart_df[chart_y] = chart_df[y]

        mapping_df = None
        if use_index_axis and x in chart_df.columns:
            chart_df["Index"] = list(range(1, len(chart_df) + 1))
            mapping_df = pd.DataFrame({
                "No.": chart_df["Index"],
                "Brand": chart_df[x],
                "Brand Type": chart_df[chart_color] if chart_color and chart_color in chart_df.columns else "",
                "Sentiment Score": chart_df[y],
            })

        plot_x = "Index" if use_index_axis and "Index" in chart_df.columns else chart_x
        custom_data = [chart_x]
        if chart_color:
            custom_data.append(chart_color)
        fig = px.bar(chart_df, x=plot_x, y=chart_y, color=chart_color, height=420, custom_data=custom_data)
        hover_parts = ["No.: %{x}", "Brand: %{customdata[0]}"] if use_index_axis else [f"{chart_x}: %{{x}}"]
        if chart_color:
            hover_parts.append(f"{chart_color}: %{{customdata[1]}}")
        hover_parts.append(f"{chart_y}: %{{y}}")
        fig.update_traces(hovertemplate="<br>".join(hover_parts) + "<extra></extra>")
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=90), legend_title_text=chart_color or "")
        fig.update_xaxes(title_text=("No." if use_index_axis else chart_x), tickmode=("linear" if use_index_axis else None))
        fig.update_yaxes(title_text=chart_y)

        if show_mapping_table and mapping_df is not None:
            left_col, right_col = st.columns([3, 2])
            with left_col:
                st.plotly_chart(fig, width="stretch")
            with right_col:
                st.markdown("##### Brand Number Mapping")
                st.dataframe(mapping_df, width="stretch", hide_index=True)
        else:
            st.plotly_chart(fig, width="stretch")

        with st.expander("View detail data", expanded=False):
            st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_pie(rows: list[dict[str, Any]], names: str, values: str) -> None:
    if not rows:
        st.info("暂无数据。")
        return
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(rows)
        chart_names = _chart_label(names)
        chart_values = _chart_label(values)
        chart_df = df.head(12).copy()
        chart_df[chart_names] = chart_df[names]
        chart_df[chart_values] = chart_df[values]
        fig = px.pie(chart_df, names=chart_names, values=chart_values, hole=0.35, height=420)
        fig.update_layout(margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, width="stretch")
        with st.expander("查看详细数据", expanded=False):
            st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _render_heatmap(rows: list[dict[str, Any]]) -> None:
    try:
        import pandas as pd
        import plotly.express as px

        df = pd.DataFrame(rows)
        pivot = df.pivot_table(index="brand", columns="topic", values="count", aggfunc="sum", fill_value=0)
        fig = px.imshow(pivot.head(12), aspect="auto", height=520, labels=dict(x="内容主题", y="品牌", color="次数"))
        fig.update_layout(margin=dict(l=120, r=20, t=20, b=80))
        st.plotly_chart(fig, width="stretch")
        with st.expander("查看详细数据", expanded=False):
            st.dataframe(df, width="stretch", hide_index=True)
    except Exception:
        st.dataframe(rows, width="stretch", hide_index=True)


def _competitor_rows(competitor_discovery: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    group_labels = {
        "direct_competitors": "直接竞品",
        "local_competitors": "本地竞品",
        "national_competitors": "全国竞品",
        "adjacent_competitors": "相邻竞品",
    }
    for key, label in group_labels.items():
        for item in competitor_discovery.get(key) or []:
            if isinstance(item, str):
                rows.append({"brand_name": item, "type": label, "region": "", "reason": ""})
            elif isinstance(item, dict) and item.get("brand_name"):
                rows.append(
                    {
                        "brand_name": item.get("brand_name", ""),
                        "type": item.get("competitor_type") or label,
                        "region": item.get("region", ""),
                        "reason": item.get("reason", ""),
                    }
                )
    seen = set()
    deduped = []
    for item in rows:
        key = str(item.get("brand_name") or "").lower()
        if key and key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped


def _labels(language: str) -> dict[str, str]:
    if language == "en":
        return {
            "product": "Product",
            "brand": "Brand",
            "category": "Category",
            "ranking": "AI Recommendation Ranking",
            "baidu": "Baidu Mention Stats",
        }
    return {
        "product": "产品",
        "brand": "品牌",
        "category": "类目",
        "ranking": "AI 推荐排名",
        "baidu": "百度提及统计",
    }


def main() -> None:
    st.set_page_config(page_title="GEO 一键分析", layout="wide")
    inject_styles()
    st.title("GEO 一键分析")
    storage = get_storage()
    config = sidebar_config()
    render_console()
    render_history(storage)
    render_input_panel(storage, config)
    render_profile_confirmation(storage, config)
    render_result()


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        if exc.name == "streamlit":
            print("缺少 Streamlit，请先运行：python -m pip install -r requirements.txt", file=sys.stderr)
        raise
