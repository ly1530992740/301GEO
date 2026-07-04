from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from geo_app.config import (
    AppConfig,
    BudgetConfig,
    MeijiekuConfig,
    QwenConfig,
    SerpApiConfig,
    load_config,
    normalize_meijieku_base_url,
)
from geo_app.storage import Storage
from geo_app.strategy_workflow import (
    run_ai_visibility_diagnosis,
    run_brand_strategy,
    run_competitor_analysis,
    run_geo_monitor,
)
from geo_app.workflow import (
    create_task,
    generate_articles_for_matches,
    generate_platform_matches,
    get_publishable_matches,
    publish_articles,
    refresh_media_resources,
    run_search_and_analysis,
    run_trend_analysis,
    sync_pending_orders,
)


STATUS_LABELS = {
    None: "未发布",
    0: "待处理",
    1: "已收稿",
    2: "已发布",
    4: "已退款/失败",
    9: "售后中",
}


@st.cache_resource
def get_storage() -> Storage:
    return Storage()


def sidebar_config() -> AppConfig:
    base = load_config()
    qwen_api_host_value = getattr(base.qwen, "api_host", "")
    with st.sidebar:
        st.header("配置")
        st.caption("可先用 .env 配置，界面输入只对当前运行生效。")

        qwen_api_key = st.text_input("Qwen API Key", value=base.qwen.api_key, type="password")
        qwen_api_host = st.text_input(
            "Qwen API Host（可选）",
            value=qwen_api_host_value,
            placeholder="例如 https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/api/v1",
        )
        search_model = st.text_input("搜索模型", value=base.qwen.search_model)
        analysis_model = st.text_input("链接分析/网页抓取模型", value=base.qwen.analysis_model)
        writing_model = st.text_input("写作模型", value=base.qwen.writing_model)

        st.divider()
        serpapi_key = st.text_input("SerpApi API Key", value=base.serpapi.api_key, type="password")
        serpapi_geo = st.text_input("Trends 默认地区 geo", value=base.serpapi.default_geo)
        serpapi_hl = st.text_input("SerpApi 语言 hl", value=base.serpapi.default_hl)
        serpapi_gl = st.text_input("Google 搜索地区 gl", value=base.serpapi.default_gl)

        st.divider()
        meijieku_base_url = st.text_input("媒介库 API 地址", value=base.meijieku.base_url)
        meijieku_mobile = st.text_input("媒介库手机号", value=base.meijieku.mobile)
        meijieku_password = st.text_input("媒介库密码", value=base.meijieku.password, type="password")
        meijieku_token = st.text_input("媒介库 Token（可选）", value=base.meijieku.token, type="password")
        meijieku_mock_mode = st.checkbox("媒介库模拟模式（不请求真实接口）", value=base.meijieku.mock_mode)
        page_size = st.number_input("资源每页数量", min_value=20, max_value=200, value=base.meijieku.resource_page_size, step=10)
        max_pages = st.number_input("资源最大页数", min_value=1, max_value=200, value=base.meijieku.resource_max_pages, step=1)

        st.divider()
        max_price = st.number_input("单平台最高价（0 不限制）", min_value=0.0, value=base.budget.max_price_per_platform, step=10.0)
        max_total = st.number_input("单次总预算（0 不限制）", min_value=0.0, value=base.budget.max_total_budget, step=50.0)

    return AppConfig(
        qwen=QwenConfig(
            api_key=qwen_api_key.strip(),
            api_host=qwen_api_host.strip().rstrip("/"),
            search_model=search_model.strip() or "qwen-plus",
            analysis_model=analysis_model.strip() or "qwen3.7-max",
            writing_model=writing_model.strip() or "qwen-plus",
            search_strategy=base.qwen.search_strategy,
            analysis_strategy=base.qwen.analysis_strategy,
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
        serpapi=SerpApiConfig(
            api_key=serpapi_key.strip(),
            default_geo=serpapi_geo.strip() or "CN",
            default_hl=serpapi_hl.strip() or "zh-CN",
            default_gl=serpapi_gl.strip() or "cn",
            timeout_seconds=base.serpapi.timeout_seconds,
        ),
        budget=BudgetConfig(
            max_price_per_platform=float(max_price),
            max_total_budget=float(max_total),
            require_fuzzy_confirmation=True,
        ),
    )


def require_qwen(config: AppConfig) -> bool:
    if config.qwen.api_key:
        lowered = config.qwen.api_key.lower()
        if config.qwen.api_key in {"sk-your-qwen-key", "YOUR_API_KEY"} or "your-qwen-key" in lowered:
            st.error("当前 Qwen API Key 还是示例占位值，请填写阿里云百炼控制台生成的完整明文 API Key。")
            return False
        return True
    st.error("请先在左侧配置 Qwen API Key，或在 .env 中设置 DASHSCOPE_API_KEY。")
    return False


def require_meijieku(config: AppConfig) -> bool:
    if config.meijieku.mock_mode:
        return True
    if config.meijieku.token or (config.meijieku.mobile and config.meijieku.password):
        return True
    st.error("请先在左侧配置媒介库手机号/密码，或填写媒介库 Token。")
    return False


def require_serpapi(config: AppConfig) -> bool:
    if config.serpapi.api_key:
        return True
    st.error("请先在左侧配置 SerpApi API Key，或在 .env 中设置 SERPAPI_API_KEY。")
    return False


def show_action_error(title: str, exc: Exception) -> None:
    st.error(f"{title}失败：{exc}")
    if "InvalidApiKey" in str(exc):
        st.info(
            "根据阿里云百炼文档，程序需要使用完整的百炼 API Key。请检查："
            "不要填控制台列表里复制的脱敏 Key；Key 是否被重置、删除、禁用；"
            "如果 Key 属于特定业务空间/地域，请把创建 Key 时显示的 API Host 填到左侧 Qwen API Host。"
        )
    if "api.meijieku.com" in str(exc) or "HTTP 404" in str(exc):
        st.info(
            "当前程序会使用 `https://api.meijieku.com`，并且接口路径不带 `/api` 前缀，"
            "例如登录会请求 `POST https://api.meijieku.com/System/login_long_token`。"
            "如果仍失败，请检查媒介库账号、Token、接口权限或服务端返回内容；也可以先开启“媒介库模拟模式”继续测试流程。"
        )


def render_file_downloads(paths: list[tuple[str, str, str]]) -> None:
    existing = [(label, Path(path), mime) for label, path, mime in paths if path and Path(path).exists()]
    if not existing:
        return
    cols = st.columns(min(4, len(existing)))
    for idx, (label, path, mime) in enumerate(existing):
        cols[idx % len(cols)].download_button(
            label,
            data=path.read_bytes(),
            file_name=path.name,
            mime=mime,
            key=f"download_{path}",
        )


def render_trend_visual_preview(report_path: str, report_md: str = "", html_path: str = "") -> None:
    report_file = Path(report_path) if report_path else None
    trend_dir = report_file.parent if report_file else None
    visual_path = trend_dir / "visual_data.json" if trend_dir else None
    if not visual_path or not visual_path.exists():
        if html_path and Path(html_path).exists():
            components.html(Path(html_path).read_text(encoding="utf-8"), height=900, scrolling=True)
        elif report_md:
            st.markdown(report_md[:8000])
        return

    try:
        import pandas as pd
        import plotly.express as px
    except ModuleNotFoundError as exc:
        st.warning(f"缺少图表依赖：{exc.name}。请运行 `python -m pip install -r requirements.txt`。")
        if html_path and Path(html_path).exists():
            components.html(Path(html_path).read_text(encoding="utf-8"), height=900, scrolling=True)
        return

    visual_data = json.loads(visual_path.read_text(encoding="utf-8"))
    cards = visual_data.get("comparison_cards") or []
    if cards:
        metric_cols = st.columns(min(5, len(cards)))
        for idx, card in enumerate(cards[:5]):
            metric_cols[idx].metric(
                str(card.get("keyword", "")),
                card.get("avg_heat", 0),
                delta=f"峰值 {card.get('peak_heat', 0)} / 相关查询 {card.get('related_query_count', 0)}",
            )

    tab_trend, tab_related, tab_geo, tab_data, tab_html = st.tabs(
        ["热度趋势", "常见搜索查询", "地域热度", "完整数据", "HTML报告"]
    )

    with tab_trend:
        interest_df = pd.DataFrame(visual_data.get("interest_over_time") or [])
        if interest_df.empty:
            st.info("暂无热度随时间变化数据。")
        else:
            interest_df["date_axis"] = pd.to_datetime(interest_df.get("timestamp"), unit="s", errors="coerce")
            if interest_df["date_axis"].isna().all():
                interest_df["date_axis"] = interest_df["date"]
            fig = px.line(
                interest_df,
                x="date_axis",
                y="value",
                color="keyword",
                markers=True,
                labels={"date_axis": "", "value": "Search interest", "keyword": "关键词"},
                height=460,
            )
            fig.update_yaxes(range=[0, 100])
            fig.update_layout(legend_orientation="h", margin=dict(l=40, r=20, t=20, b=40))
            st.plotly_chart(fig, width="stretch")

        monthly_df = pd.DataFrame(visual_data.get("monthly_interest") or [])
        if not monthly_df.empty:
            fig = px.bar(
                monthly_df,
                x="month",
                y="avg_value",
                color="keyword",
                barmode="group",
                labels={"month": "月份", "avg_value": "月均热度", "keyword": "关键词"},
                height=360,
            )
            fig.update_yaxes(range=[0, 100])
            fig.update_layout(legend_orientation="h", margin=dict(l=40, r=20, t=20, b=40))
            st.plotly_chart(fig, width="stretch")

    with tab_related:
        related_df = pd.DataFrame(visual_data.get("related_queries") or [])
        if related_df.empty:
            st.info("暂无相关查询数据。")
        else:
            top_df = related_df[related_df["type"].eq("top")].head(20)
            rising_df = related_df[related_df["type"].eq("rising")].head(20)
            c1, c2 = st.columns(2)
            c1.markdown("**重点常见搜索查询 Top queries**")
            c1.dataframe(top_df, width="stretch", hide_index=True)
            c2.markdown("**搜索用户还在增长搜索的 Rising queries**")
            c2.dataframe(rising_df, width="stretch", hide_index=True)

            chart_df = related_df.dropna(subset=["extracted_value"]).head(25)
            if not chart_df.empty:
                fig = px.bar(
                    chart_df.sort_values("extracted_value"),
                    x="extracted_value",
                    y="query",
                    color="type",
                    orientation="h",
                    hover_data=["source_keyword"],
                    labels={"extracted_value": "热度/涨幅", "query": "查询"},
                    height=560,
                )
                fig.update_layout(margin=dict(l=180, r=20, t=20, b=40))
                st.plotly_chart(fig, width="stretch")

    with tab_geo:
        geo_df = pd.DataFrame(visual_data.get("geo_interest") or [])
        if geo_df.empty:
            st.info("暂无地域热度数据。")
        else:
            chart_df = geo_df.dropna(subset=["extracted_value"]).head(25)
            if not chart_df.empty:
                fig = px.bar(
                    chart_df.sort_values("extracted_value"),
                    x="extracted_value",
                    y="location",
                    color="keyword",
                    orientation="h",
                    labels={"extracted_value": "地域热度", "location": "地区"},
                    height=520,
                )
                fig.update_xaxes(range=[0, 100])
                fig.update_layout(margin=dict(l=160, r=20, t=20, b=40))
                st.plotly_chart(fig, width="stretch")
            st.dataframe(geo_df, width="stretch", hide_index=True)

    with tab_data:
        data_tabs = st.tabs(["热度时间序列", "相关查询", "月度趋势", "地域热度", "关键词评分"])
        datasets = [
            visual_data.get("interest_over_time") or [],
            visual_data.get("related_queries") or [],
            visual_data.get("monthly_interest") or [],
            visual_data.get("geo_interest") or [],
            visual_data.get("keyword_scores") or [],
        ]
        for data_tab, rows in zip(data_tabs, datasets):
            with data_tab:
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

    with tab_html:
        if html_path and Path(html_path).exists():
            components.html(Path(html_path).read_text(encoding="utf-8"), height=900, scrolling=True)
        elif report_md:
            st.markdown(report_md[:8000])


def money(value: object) -> str:
    try:
        return f"{float(value or 0):.2f}"
    except Exception:
        return "0.00"


def task_options(storage: Storage) -> list[dict]:
    return storage.query("select * from tasks order by created_at desc")


def render_dashboard(storage: Storage, config: AppConfig) -> None:
    cols = st.columns(4)
    task_count = storage.get_one("select count(*) as c from tasks")["c"]
    article_count = storage.get_one("select count(*) as c from articles")["c"]
    published_count = storage.get_one("select count(*) as c from articles where publish_status=2")["c"]
    pending_count = storage.get_one(
        "select count(*) as c from articles where order_id is not null and (publish_status is null or publish_status in (0,1,9))"
    )["c"]
    cols[0].metric("GEO任务", task_count)
    cols[1].metric("生成文章", article_count)
    cols[2].metric("已发布", published_count)
    cols[3].metric("待跟进", pending_count)

    if st.button("查询未完成订单状态", type="primary"):
        if require_meijieku(config):
            with st.status("正在查询媒介库订单状态", expanded=True) as status:
                try:
                    updated = sync_pending_orders(storage, config, progress=st.write)
                    status.update(label=f"状态同步完成，更新 {updated} 条", state="complete")
                except Exception as exc:
                    status.update(label="状态同步失败", state="error")
                    show_action_error("状态同步", exc)

    tasks = task_options(storage)
    st.subheader("任务列表")
    if not tasks:
        st.info("还没有 GEO 任务。去“新建任务”创建第一个。")
        return
    st.dataframe(
        [
            {
                "任务ID": item["id"],
                "推广词条": item["keyword"],
                "客户产品": item["customer_product"],
                "状态": item["status"],
                "创建时间": item["created_at"],
            }
            for item in tasks
        ],
        width="stretch",
        hide_index=True,
    )


def render_create_task(storage: Storage, config: AppConfig) -> None:
    st.subheader("新建 GEO 任务")
    with st.form("create_task"):
        keyword = st.text_input("推广词条", value="推荐20岁成年人的复合维生素")
        customer_product = st.text_input("客户产品/品牌", value="XX牌维生素")
        c1, c2 = st.columns(2)
        search_count = c1.number_input("搜索次数", min_value=1, max_value=10, value=3, step=1)
        links_per_search = c2.number_input("每次取前 N 条链接", min_value=1, max_value=30, value=10, step=1)
        query_templates = st.text_area(
            "搜索问法模板（可选，每行一个，支持 {keyword}）",
            value="{keyword}\n{keyword} 哪些值得推荐\n{keyword} 排行榜 评测 推荐",
            height=110,
        )
        submitted = st.form_submit_button("创建任务并执行搜索分析", type="primary")

    if submitted:
        if not keyword.strip() or not customer_product.strip():
            st.error("推广词条和客户产品都不能为空。")
            return
        if not require_qwen(config):
            return
        task = create_task(
            storage,
            keyword.strip(),
            customer_product.strip(),
            int(search_count),
            int(links_per_search),
            query_templates,
        )
        with st.status("正在创建 GEO 分析任务", expanded=True) as status:
            try:
                run_search_and_analysis(storage, config, task, progress=st.write)
                status.update(label="搜索分析完成，已生成文章生成格式.md", state="complete")
                st.success(f"任务已创建：{task['id']}")
            except Exception as exc:
                status.update(label="搜索分析失败", state="error")
                show_action_error("搜索分析", exc)


def render_trend_analysis(storage: Storage, config: AppConfig) -> None:
    st.subheader("趋势与同行分析")
    st.caption("用于 GEO 前置分析：先判断用户在搜什么、同行在做什么，再决定优先写哪些内容。")
    with st.form("trend_analysis"):
        c1, c2 = st.columns(2)
        city = c1.text_input("城市", value="福州")
        industry = c2.text_input("行业", value="家装公司")
        seed_keyword = st.text_input("核心词", value="福州家装公司推荐")
        customer_product = st.text_input("客户/品牌", value="XX家装公司")
        competitors = st.text_area("同行名称（可选，每行一个）", value="", height=90)
        c3, c4 = st.columns(2)
        trend_date = c3.selectbox("趋势时间范围", ["today 12-m", "today 5-y", "now 7-d", "now 30-d", "all"], index=0)
        max_search_queries = c4.number_input("SERP 搜索问题数", min_value=1, max_value=8, value=4, step=1)
        submitted = st.form_submit_button("创建任务并生成趋势报告", type="primary")

    if submitted:
        if not city.strip() or not industry.strip() or not seed_keyword.strip() or not customer_product.strip():
            st.error("城市、行业、核心词、客户/品牌都不能为空。")
            return
        if not require_serpapi(config) or not require_qwen(config):
            return
        task = create_task(
            storage,
            seed_keyword.strip(),
            customer_product.strip(),
            search_count=3,
            links_per_search=10,
            query_templates="",
        )
        with st.status("正在生成趋势与同行分析报告", expanded=True) as status:
            try:
                result = run_trend_analysis(
                    storage=storage,
                    config=config,
                    task=task,
                    city=city.strip(),
                    industry=industry.strip(),
                    competitors=competitors.strip(),
                    trend_date=trend_date,
                    max_search_queries=int(max_search_queries),
                    progress=st.write,
                )
                status.update(label="趋势报告生成完成", state="complete")
                st.success(f"Markdown 报告：{result['report_path']}")
                st.success(f"HTML 可视化报告：{result.get('report_html_path', '')}")
                st.caption(f"热度 CSV：{result.get('interest_csv_path', '')}")
                st.caption(f"相关查询 CSV：{result.get('related_csv_path', '')}")
                st.caption(f"月度趋势 CSV：{result.get('monthly_csv_path', '')}")
                if result.get("pdf_path"):
                    st.caption(f"PDF 报告：{result['pdf_path']}")
                else:
                    st.caption("PDF 未自动导出；可打开 HTML 报告后使用浏览器打印为 PDF。")
                if result.get("screenshot_path"):
                    st.caption(f"报告截图：{result['screenshot_path']}")
                render_file_downloads(
                    [
                        ("下载 HTML 报告", result.get("report_html_path", ""), "text/html"),
                        ("下载 PDF 报告", result.get("pdf_path", ""), "application/pdf"),
                        ("下载热度 CSV", result.get("interest_csv_path", ""), "text/csv"),
                        ("下载相关查询 CSV", result.get("related_csv_path", ""), "text/csv"),
                        ("下载完整 JSON", str(Path(result["report_path"]).with_name("trend_data.json")), "application/json"),
                    ]
                )
                render_trend_visual_preview(
                    result["report_path"],
                    report_md=result["report_md"],
                    html_path=result.get("report_html_path", ""),
                )
            except Exception as exc:
                status.update(label="趋势报告生成失败", state="error")
                show_action_error("趋势分析", exc)

    reports = storage.query("select * from trend_reports order by created_at desc limit 10")
    if reports:
        st.markdown("**最近趋势报告**")
        st.dataframe(
            [
                {
                    "报告ID": item["id"],
                    "任务ID": item["task_id"],
                    "城市": item["city"],
                    "行业": item["industry"],
                    "核心词": item["seed_keyword"],
                    "Markdown": item["file_path"],
                    "HTML": str(Path(item["file_path"]).with_name("trend_report.html")),
                    "生成时间": item["created_at"],
                }
                for item in reports
            ],
            width="stretch",
            hide_index=True,
        )
        with st.expander("预览最新趋势报告"):
            html_path = Path(reports[0]["file_path"]).with_name("trend_report.html")
            render_file_downloads(
                [
                    ("下载 HTML 报告", str(html_path), "text/html"),
                    ("下载 PDF 报告", str(Path(reports[0]["file_path"]).with_name("trend_report.pdf")), "application/pdf"),
                    ("下载热度 CSV", str(Path(reports[0]["file_path"]).with_name("interest_over_time.csv")), "text/csv"),
                    ("下载相关查询 CSV", str(Path(reports[0]["file_path"]).with_name("related_queries.csv")), "text/csv"),
                    ("下载完整 JSON", str(Path(reports[0]["file_path"]).with_name("trend_data.json")), "application/json"),
                ]
            )
            render_trend_visual_preview(
                reports[0]["file_path"],
                report_md=reports[0]["report_md"],
                html_path=str(html_path),
            )


def render_strategy_tools(storage: Storage, config: AppConfig) -> None:
    st.subheader("GEO 策略工具")
    st.caption("第一版：竞品分析、AI 可见度诊断、品牌定位策略、手动 GEO 监控，全部输出 Markdown。")

    tool_tabs = st.tabs(["竞品分析", "AI可见度诊断", "品牌定位策略", "手动监控", "历史报告"])

    with tool_tabs[0]:
        with st.form("competitor_analysis"):
            c1, c2 = st.columns(2)
            city = c1.text_input("城市/市场", value="Los Angeles", key="ca_city")
            industry = c2.text_input("行业", value="LED Sign", key="ca_industry")
            customer_product = st.text_input("客户/品牌", value="LED Sign Company", key="ca_customer")
            seed_keyword = st.text_input("核心词/商品名", value="Led Sign Company recommend", key="ca_seed")
            competitors = st.text_area("竞品名称/商品名（可选，每行一个）", height=90, key="ca_competitors")
            competitor_urls = st.text_area("竞品官网 URL（可选，每行一个）", height=90, key="ca_urls")
            pdf_paths = st.text_area("竞品 PDF 路径（可选，每行一个）", height=90, key="ca_pdfs")
            submitted = st.form_submit_button("生成竞品分析报告", type="primary")
        if submitted:
            if not require_qwen(config) or not require_serpapi(config):
                return
            with st.status("正在生成竞品分析报告", expanded=True) as status:
                try:
                    result = run_competitor_analysis(
                        storage,
                        config,
                        city.strip(),
                        industry.strip(),
                        customer_product.strip(),
                        seed_keyword.strip(),
                        competitors.strip(),
                        competitor_urls.strip(),
                        pdf_paths.strip(),
                        progress=st.write,
                    )
                    status.update(label="竞品分析报告已生成", state="complete")
                    st.success(result["report_path"])
                    st.markdown(result["report_md"])
                except Exception as exc:
                    status.update(label="竞品分析失败", state="error")
                    show_action_error("竞品分析", exc)

    with tool_tabs[1]:
        with st.form("visibility_diagnosis"):
            c1, c2 = st.columns(2)
            city = c1.text_input("城市/市场", value="Los Angeles", key="vd_city")
            industry = c2.text_input("行业", value="LED Sign", key="vd_industry")
            customer_product = st.text_input("客户/品牌", value="LED Sign Company", key="vd_customer")
            seed_keyword = st.text_input("核心词/商品名", value="LED sign company", key="vd_seed")
            competitors = st.text_area("竞品名称（可选，每行一个）", height=90, key="vd_competitors")
            question_count = st.number_input("测试问题数", min_value=3, max_value=20, value=8, step=1, key="vd_count")
            submitted = st.form_submit_button("执行 AI 可见度诊断", type="primary")
        if submitted:
            if not require_qwen(config):
                return
            with st.status("正在执行 AI 可见度诊断", expanded=True) as status:
                try:
                    result = run_ai_visibility_diagnosis(
                        storage,
                        config,
                        city.strip(),
                        industry.strip(),
                        customer_product.strip(),
                        seed_keyword.strip(),
                        competitors.strip(),
                        int(question_count),
                        progress=st.write,
                    )
                    status.update(label="AI 可见度诊断完成", state="complete")
                    st.success(result["report_path"])
                    st.markdown(result["report_md"])
                except Exception as exc:
                    status.update(label="AI 可见度诊断失败", state="error")
                    show_action_error("AI 可见度诊断", exc)

    with tool_tabs[2]:
        with st.form("brand_strategy"):
            c1, c2 = st.columns(2)
            city = c1.text_input("城市/市场", value="Los Angeles", key="bs_city")
            industry = c2.text_input("行业", value="LED Sign", key="bs_industry")
            customer_product = st.text_input("客户/品牌", value="LED Sign Company", key="bs_customer")
            seed_keyword = st.text_input("核心词/商品名", value="LED sign company", key="bs_seed")
            customer_advantages = st.text_area("客户优势/已有资料（可不完整）", height=120, key="bs_advantages")
            competitors = st.text_area("竞品名称（可选，每行一个）", height=90, key="bs_competitors")
            website_url = st.text_input("客户官网 URL（可选）", key="bs_website")
            pdf_paths = st.text_area("客户/竞品资料 PDF 路径（可选，每行一个）", height=90, key="bs_pdfs")
            submitted = st.form_submit_button("生成品牌定位与内容策略报告", type="primary")
        if submitted:
            if not require_qwen(config) or not require_serpapi(config):
                return
            with st.status("正在生成品牌定位与内容策略报告", expanded=True) as status:
                try:
                    result = run_brand_strategy(
                        storage,
                        config,
                        city.strip(),
                        industry.strip(),
                        customer_product.strip(),
                        seed_keyword.strip(),
                        customer_advantages.strip(),
                        competitors.strip(),
                        website_url.strip(),
                        pdf_paths.strip(),
                        progress=st.write,
                    )
                    status.update(label="品牌策略报告已生成", state="complete")
                    st.success(result["report_path"])
                    st.markdown(result["report_md"])
                except Exception as exc:
                    status.update(label="品牌策略生成失败", state="error")
                    show_action_error("品牌策略", exc)

    with tool_tabs[3]:
        with st.form("geo_monitor"):
            monitor_name = st.text_input("监控名称", value="LED Sign LA 手动监控", key="gm_name")
            c1, c2 = st.columns(2)
            city = c1.text_input("城市/市场", value="Los Angeles", key="gm_city")
            industry = c2.text_input("行业", value="LED Sign", key="gm_industry")
            customer_product = st.text_input("客户/品牌", value="LED Sign Company", key="gm_customer")
            seed_keyword = st.text_input("核心词/商品名", value="LED sign company", key="gm_seed")
            competitors = st.text_area("竞品名称（可选，每行一个）", height=90, key="gm_competitors")
            question_count = st.number_input("监控问题数", min_value=3, max_value=20, value=8, step=1, key="gm_count")
            submitted = st.form_submit_button("立即执行一次手动监控", type="primary")
        if submitted:
            if not require_qwen(config):
                return
            with st.status("正在执行 GEO 手动监控", expanded=True) as status:
                try:
                    result = run_geo_monitor(
                        storage,
                        config,
                        monitor_name.strip(),
                        city.strip(),
                        industry.strip(),
                        customer_product.strip(),
                        seed_keyword.strip(),
                        competitors.strip(),
                        int(question_count),
                        progress=st.write,
                    )
                    status.update(label="GEO 手动监控完成", state="complete")
                    st.success(result["report_path"])
                    st.markdown(result["report_md"])
                except Exception as exc:
                    status.update(label="GEO 手动监控失败", state="error")
                    show_action_error("GEO 手动监控", exc)

    with tool_tabs[4]:
        reports = storage.query("select * from strategy_reports order by created_at desc limit 50")
        if not reports:
            st.info("还没有策略报告。")
        else:
            st.dataframe(
                [
                    {
                        "ID": item["id"],
                        "类型": item["report_type"],
                        "主题": item["subject"],
                        "客户": item["customer_product"],
                        "城市": item["city"],
                        "行业": item["industry"],
                        "文件": item["file_path"],
                        "时间": item["created_at"],
                    }
                    for item in reports
                ],
                width="stretch",
                hide_index=True,
            )
            with st.expander("预览最新策略报告"):
                st.markdown(reports[0]["report_md"][:8000])


def render_publish(storage: Storage, config: AppConfig) -> None:
    st.subheader("平台匹配与发布")
    tasks = task_options(storage)
    if not tasks:
        st.info("请先创建任务。")
        return
    labels = {f"{item['keyword']} | {item['customer_product']} | {item['id']}": item["id"] for item in tasks}
    selected_label = st.selectbox("选择任务", list(labels.keys()))
    task_id = labels[selected_label]
    task = storage.get_one("select * from tasks where id=?", (task_id,))
    if not task:
        return

    c1, c2, c3 = st.columns(3)
    if c1.button("刷新媒介库资源"):
        if require_meijieku(config):
            with st.status("正在同步媒介库网站媒体和自媒体", expanded=True) as status:
                try:
                    counts = refresh_media_resources(storage, config, progress=st.write)
                    status.update(label=f"资源同步完成：网站 {counts.get('website', 0)}，自媒体 {counts.get('wemedia', 0)}", state="complete")
                except Exception as exc:
                    status.update(label="资源同步失败", state="error")
                    show_action_error("媒介库资源同步", exc)
    if c2.button("生成/刷新平台匹配"):
        if require_qwen(config):
            with st.status("正在匹配来源平台和媒介库资源", expanded=True) as status:
                try:
                    matches = generate_platform_matches(storage, config, task_id, use_ai_fuzzy=True)
                    status.update(label=f"平台匹配完成，共 {len(matches)} 条", state="complete")
                except Exception as exc:
                    status.update(label="平台匹配失败", state="error")
                    show_action_error("平台匹配", exc)
    if c3.button("批量确认所有模糊匹配"):
        fuzzy = storage.query("select id from platform_matches where task_id=? and match_type='fuzzy'", (task_id,))
        storage.update_match_confirmation([item["id"] for item in fuzzy], True)
        st.success(f"已确认 {len(fuzzy)} 条模糊匹配。")

    matches = storage.query("select * from platform_matches where task_id=? order by link_count desc, confidence desc", (task_id,))
    if matches:
        st.markdown("**匹配结果**")
        st.dataframe(
            [
                {
                    "ID": item["id"],
                    "来源平台": item["source_site_name"],
                    "域名": item["source_domain"],
                    "链接次数": item["link_count"],
                    "媒介库类型": item["resource_type"],
                    "媒介库资源": item["resource_title"],
                    "匹配": item["match_type"],
                    "确认": "是" if item["confirmed"] else "否",
                    "price_1": money(item["price_1"]),
                    "price_2": money(item["price_2"]),
                    "price_3": money(item["price_3"]),
                    "提示": item["warning"],
                }
                for item in matches
            ],
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("还没有平台匹配结果。请先刷新媒介库资源，再生成平台匹配。")
        return

    publishable = get_publishable_matches(storage, task_id)
    st.markdown("**生成本批文章**")
    if not publishable:
        st.warning("没有已确认且可发布的平台。完全匹配会自动确认，模糊匹配需要批量确认后才能发布。")
        return

    default_count = min(10, len(publishable))
    batch_count = st.number_input("本批默认选择前 N 个平台", min_value=1, max_value=len(publishable), value=default_count, step=1)
    option_labels = {
        f"{item['id']} | {item['resource_title']} | {item['resource_type']} | price_1={money(item['price_1'])} | {item['match_type']}": item["id"]
        for item in publishable
    }
    defaults = list(option_labels.keys())[: int(batch_count)]
    selected = st.multiselect("选择本批平台", list(option_labels.keys()), default=defaults)
    selected_ids = [option_labels[label] for label in selected]
    selected_matches = [item for item in publishable if item["id"] in selected_ids]
    total_price = sum(float(item.get("price_1") or 0) for item in selected_matches)
    over_single = [
        item for item in selected_matches if config.budget.max_price_per_platform and float(item.get("price_1") or 0) > config.budget.max_price_per_platform
    ]
    over_total = bool(config.budget.max_total_budget and total_price > config.budget.max_total_budget)
    st.caption(f"本批预计 price_1 合计：{money(total_price)}")
    if over_single:
        st.error("有平台超过单个平台最高价，请调整选择或预算。")
    if over_total:
        st.error("本批预计费用超过单次总预算，请调整选择或预算。")
    can_generate = bool(selected_ids) and not over_single and not over_total
    if st.button("为所选平台生成不同文章", type="primary", disabled=not can_generate):
        if require_qwen(config):
            with st.status("正在按平台生成不同文章", expanded=True) as status:
                try:
                    articles = generate_articles_for_matches(storage, config, task_id, selected_ids, progress=st.write)
                    status.update(label=f"文章生成完成，共 {len(articles)} 篇", state="complete")
                except Exception as exc:
                    status.update(label="文章生成失败", state="error")
                    show_action_error("文章生成", exc)

    unpublished = storage.query(
        """
        select * from articles
        where task_id=? and order_id is null
        order by created_at desc
        """,
        (task_id,),
    )
    st.markdown("**待发布文章**")
    if not unpublished:
        st.info("当前没有待发布文章。")
        return
    st.dataframe(
        [
            {
                "文章ID": item["id"],
                "平台": item["resource_title"],
                "类型": item["resource_type"],
                "标题": item["title"],
                "原稿": item["file_path"],
            }
            for item in unpublished
        ],
        width="stretch",
        hide_index=True,
    )
    with st.expander("预览最新一篇原稿"):
        st.markdown(unpublished[0]["content_md"][:4000])
    confirm = st.checkbox("我确认将以上待发布文章提交到媒介库，提交后会按媒介库规则扣费。")
    if st.button("确认发布待发布文章", type="primary", disabled=not confirm):
        if require_meijieku(config):
            with st.status("正在提交媒介库发布", expanded=True) as status:
                try:
                    article_ids = [item["id"] for item in unpublished]
                    published = publish_articles(storage, config, article_ids, progress=st.write)
                    status.update(label=f"已提交 {len(published)} 篇文章", state="complete")
                except Exception as exc:
                    status.update(label="提交发布失败", state="error")
                    show_action_error("媒介库发布", exc)


def render_status(storage: Storage, config: AppConfig) -> None:
    st.subheader("文章与订单状态")
    if st.button("刷新未完成订单"):
        if require_meijieku(config):
            with st.status("正在刷新订单状态", expanded=True) as status:
                try:
                    updated = sync_pending_orders(storage, config, progress=st.write)
                    status.update(label=f"刷新完成，更新 {updated} 条", state="complete")
                except Exception as exc:
                    status.update(label="刷新失败", state="error")
                    show_action_error("订单状态刷新", exc)
    rows = storage.query("select * from articles order by created_at desc")
    if not rows:
        st.info("还没有生成文章。")
        return
    st.dataframe(
        [
            {
                "文章ID": item["id"],
                "任务ID": item["task_id"],
                "平台": item["resource_title"],
                "标题": item["title"],
                "订单号": item["order_id"],
                "状态": STATUS_LABELS.get(item["publish_status"], item["publish_status"]),
                "发布链接": item["link"],
                "失败/退款原因": item["refund_info"] or item["rejection_info"],
                "原稿": item["file_path"],
            }
            for item in rows
        ],
        width="stretch",
        hide_index=True,
    )


def render_help() -> None:
    st.subheader("第一版使用顺序")
    st.markdown(
        """
1. 在左侧配置 Qwen API Key、媒介库账号和预算。
2. 可先在“趋势与同行分析”输入城市、行业、核心词，生成客户前置分析报告。
3. 在“GEO 策略工具”生成竞品分析、AI 可见度诊断、品牌定位策略和手动监控报告。
4. 在“新建任务”输入推广词条和客户产品，执行搜索分析。
5. 在“平台匹配与发布”刷新媒介库资源，生成平台匹配。
6. 模糊匹配需要批量确认，确认后选择本批平台生成文章。
7. 预览待发布文章，勾选扣费确认，再提交媒介库。
8. 下次启动或进入“文章与订单状态”刷新未完成订单。

如果真实媒介库 API 地址暂时不可用，可先在左侧开启“媒介库模拟模式”测试匹配和文章生成流程。
"""
    )
    st.code("python -m streamlit run app.py --server.headless true --server.port 8501", language="bash")
    st.caption("建议把 DASHSCOPE_API_KEY、SERPAPI_API_KEY、MEIJIEKU_MOBILE、MEIJIEKU_PASSWORD 写入 .env。")


def main() -> None:
    st.set_page_config(page_title="GEO 文章生成与媒介库发布", layout="wide")
    st.title("GEO 文章生成与媒介库发布")
    storage = get_storage()
    config = sidebar_config()

    if "startup_sync_done" not in st.session_state:
        st.session_state.startup_sync_done = True
        if not config.meijieku.mock_mode and (config.meijieku.token or (config.meijieku.mobile and config.meijieku.password)):
            try:
                updated = sync_pending_orders(storage, config)
                if updated:
                    st.toast(f"启动时已同步 {updated} 条未完成订单")
            except Exception as exc:
                st.toast(f"启动状态同步失败：{exc}")

    tabs = st.tabs(["任务看板", "趋势与同行分析", "GEO 策略工具", "新建任务", "平台匹配与发布", "文章与订单状态", "说明"])
    with tabs[0]:
        render_dashboard(storage, config)
    with tabs[1]:
        render_trend_analysis(storage, config)
    with tabs[2]:
        render_strategy_tools(storage, config)
    with tabs[3]:
        render_create_task(storage, config)
    with tabs[4]:
        render_publish(storage, config)
    with tabs[5]:
        render_status(storage, config)
    with tabs[6]:
        render_help()


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        if exc.name == "streamlit":
            print("缺少 Streamlit，请先运行：python -m pip install -r requirements.txt", file=sys.stderr)
        raise


