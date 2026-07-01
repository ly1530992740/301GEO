from __future__ import annotations

import sys

import streamlit as st

from geo_app.config import AppConfig, BudgetConfig, MeijiekuConfig, QwenConfig, load_config, normalize_meijieku_base_url
from geo_app.storage import Storage
from geo_app.workflow import (
    create_task,
    generate_articles_for_matches,
    generate_platform_matches,
    get_publishable_matches,
    publish_articles,
    refresh_media_resources,
    run_search_and_analysis,
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
2. 在“新建任务”输入推广词条和客户产品，执行搜索分析。
3. 在“平台匹配与发布”刷新媒介库资源，生成平台匹配。
4. 模糊匹配需要批量确认，确认后选择本批平台生成文章。
5. 预览待发布文章，勾选扣费确认，再提交媒介库。
6. 下次启动或进入“文章与订单状态”刷新未完成订单。

如果真实媒介库 API 地址暂时不可用，可先在左侧开启“媒介库模拟模式”测试匹配和文章生成流程。
"""
    )
    st.code("python -m streamlit run app.py --server.headless true --server.port 8501", language="bash")
    st.caption("建议把 DASHSCOPE_API_KEY、MEIJIEKU_MOBILE、MEIJIEKU_PASSWORD 写入 .env。")


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

    tabs = st.tabs(["任务看板", "新建任务", "平台匹配与发布", "文章与订单状态", "说明"])
    with tabs[0]:
        render_dashboard(storage, config)
    with tabs[1]:
        render_create_task(storage, config)
    with tabs[2]:
        render_publish(storage, config)
    with tabs[3]:
        render_status(storage, config)
    with tabs[4]:
        render_help()


if __name__ == "__main__":
    try:
        main()
    except ModuleNotFoundError as exc:
        if exc.name == "streamlit":
            print("缺少 Streamlit，请先运行：python -m pip install -r requirements.txt", file=sys.stderr)
        raise


