from __future__ import annotations

import json
import uuid
from csv import DictWriter
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from .config import AppConfig, TASKS_DIR
from .meijieku_client import MeijiekuClient
from .platform_matcher import PlatformMatcher
from .qwen_client import QwenClient
from .serpapi_client import SerpApiClient
from .storage import Storage
from .trend_report_renderer import render_trend_outputs
from .trend_analyzer import (
    build_candidate_keywords,
    build_market_queries,
    extract_related_queries,
    extract_timeseries_scores,
    score_keywords,
    summarize_search_result,
    unique_strings,
)
from .utils import markdown_to_html, safe_filename, utc_now_iso, write_text


ProgressFn = Callable[[str], None]


def build_query_list(keyword: str, search_count: int, query_templates: str = "") -> list[str]:
    templates = [line.strip() for line in query_templates.splitlines() if line.strip()]
    if not templates:
        templates = [
            "{keyword}",
            "{keyword} 哪些值得推荐",
            "{keyword} 排行榜 评测 推荐",
            "AI搜索 {keyword} 信息来源",
            "{keyword} 选购指南 推荐清单",
        ]
    queries = []
    for idx in range(search_count):
        template = templates[idx % len(templates)]
        queries.append(template.replace("{keyword}", keyword))
    return queries


def create_task(
    storage: Storage,
    keyword: str,
    customer_product: str,
    search_count: int,
    links_per_search: int,
    query_templates: str,
) -> dict[str, Any]:
    task_id = f"{utc_now_iso().replace(':', '').replace('-', '').replace('Z', '')}_{uuid.uuid4().hex[:6]}"
    task_dir = TASKS_DIR / f"{task_id}_{safe_filename(keyword, 40)}"
    task_dir.mkdir(parents=True, exist_ok=True)
    task = {
        "id": task_id,
        "keyword": keyword,
        "customer_product": customer_product,
        "status": "draft",
        "search_count": search_count,
        "links_per_search": links_per_search,
        "query_templates": query_templates,
        "task_dir": str(task_dir),
        "format_md_path": str(task_dir / "文章生成格式.md"),
        "created_at": utc_now_iso(),
    }
    storage.upsert_task(task)
    return task


def run_search_and_analysis(
    storage: Storage,
    config: AppConfig,
    task: dict[str, Any],
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    task_dir = Path(task["task_dir"])
    queries = build_query_list(task["keyword"], int(task["search_count"]), task.get("query_templates", ""))
    all_results: list[dict[str, Any]] = []
    storage.update_task(task["id"], status="searching")
    for idx, query in enumerate(queries, start=1):
        if progress:
            progress(f"第 {idx}/{len(queries)} 次搜索：{query}")
        result = qwen.search_sources(query, int(task["links_per_search"]))
        storage.add_search_results(task["id"], idx, query, result.search_results or [])
        all_results.extend(result.search_results or [])
    write_text(task_dir / "search_results.json", json.dumps(all_results, ensure_ascii=False, indent=2))

    if progress:
        progress("正在生成文章生成格式.md")
    storage.update_task(task["id"], status="analyzing")
    format_md = qwen.analyze_sources(task["keyword"], task["customer_product"], all_results)
    write_text(Path(task["format_md_path"]), format_md)
    storage.update_task(task["id"], status="analyzed", format_md_path=task["format_md_path"])
    return {**task, "status": "analyzed"}


def run_trend_analysis(
    storage: Storage,
    config: AppConfig,
    task: dict[str, Any],
    city: str,
    industry: str,
    competitors: str = "",
    trend_date: str = "today 12-m",
    max_search_queries: int = 4,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    storage.update_task(task["id"], status="trend_analyzing")
    task_dir = Path(task["task_dir"])
    serpapi = SerpApiClient(config.serpapi)
    qwen = QwenClient(config.qwen)

    seed_keyword = task["keyword"]
    if progress:
        progress("正在用 Qwen 生成目标市场搜索词")
    query_plan = _safe_qwen_query_plan(
        qwen=qwen,
        city=city,
        industry=industry,
        customer_product=task["customer_product"],
        seed_keyword=seed_keyword,
        competitors=competitors,
        max_search_queries=max_search_queries,
    )
    queries = unique_strings(query_plan.get("search_queries", []))[:max_search_queries]
    if not queries:
        queries = build_market_queries(city, industry, seed_keyword, competitors)[:max_search_queries]
        query_plan["fallback_used"] = True

    search_summaries: list[dict[str, Any]] = []
    search_raw: list[dict[str, Any]] = []
    for idx, query in enumerate(queries, start=1):
        if progress:
            progress(f"SerpApi Search {idx}/{len(queries)}：{query}")
        raw = serpapi.google_search(query=query, location="", num=10)
        search_raw.append({"query": query, "raw": raw})
        search_summaries.append(summarize_search_result(query, raw))

    planned_trend_keywords = unique_strings(query_plan.get("trend_keywords", []), max_length=72)[:5]
    candidates = build_candidate_keywords(
        seed_keyword,
        search_summaries,
        extra_keywords=planned_trend_keywords,
        limit=12,
    )
    trend_keywords = unique_strings(planned_trend_keywords + candidates, max_length=72)[:5]
    if not trend_keywords:
        trend_keywords = [seed_keyword]

    if progress:
        progress(f"Google Trends 时间序列：{', '.join(trend_keywords)}")
    timeseries_raw = _safe_serpapi_call(
        lambda: serpapi.trends_timeseries(trend_keywords, date=trend_date),
        "timeseries",
    )
    timeseries_scores = {}
    if "error" not in timeseries_raw:
        timeseries_scores = extract_timeseries_scores(timeseries_raw)

    related_queries: dict[str, Any] = {}
    for idx, keyword in enumerate(trend_keywords, start=1):
        if progress:
            progress(f"Google Trends 相关查询 {idx}/{len(trend_keywords)}：{keyword}")
        raw = _safe_serpapi_call(
            lambda keyword=keyword: serpapi.trends_related_queries(keyword, date=trend_date),
            f"related_queries:{keyword}",
        )
        related_queries[keyword] = raw if "error" in raw else extract_related_queries(raw)

    if progress:
        progress(f"Google Trends 地域热度：{seed_keyword}")
    geo_map_raw = _safe_serpapi_call(
        lambda: serpapi.trends_geo_map(seed_keyword, date=trend_date),
        "geo_map",
    )

    keyword_scores = score_keywords(candidates, timeseries_scores, local_terms=[city])
    analysis_data = {
        "input": {
            "city": city,
            "industry": industry,
            "customer_product": task["customer_product"],
            "seed_keyword": seed_keyword,
            "competitors": competitors,
            "trend_date": trend_date,
        },
        "query_plan": query_plan,
        "search_queries": queries,
        "search_summaries": search_summaries,
        "candidate_keywords": candidates,
        "trend_keywords": trend_keywords,
        "timeseries_scores": timeseries_scores,
        "related_queries": related_queries,
        "geo_map": geo_map_raw,
        "keyword_scores": keyword_scores,
    }

    if progress:
        progress("正在生成客户趋势分析报告")
    report_md = qwen.generate_trend_report(
        city=city,
        industry=industry,
        customer_product=task["customer_product"],
        seed_keyword=seed_keyword,
        analysis_data=analysis_data,
    )

    trend_dir = task_dir / "trend_analysis"
    report_path = trend_dir / "trend_report.md"
    data_path = trend_dir / "trend_data.json"
    csv_path = trend_dir / "keyword_scores.csv"
    write_text(report_path, report_md)
    full_data = {**analysis_data, "search_raw": search_raw, "timeseries_raw": timeseries_raw}
    write_text(
        data_path,
        json.dumps(full_data, ensure_ascii=False, indent=2),
    )
    write_text(csv_path, _keyword_scores_csv(keyword_scores))
    if progress:
        progress("正在生成 Google Trends 可视化 HTML、CSV 和可选 PDF")
    trend_outputs = render_trend_outputs(
        trend_dir=trend_dir,
        analysis_data=analysis_data,
        timeseries_raw=timeseries_raw,
        report_md=report_md,
    )
    full_data["trend_outputs"] = trend_outputs
    write_text(data_path, json.dumps(full_data, ensure_ascii=False, indent=2))
    storage.add_trend_report(
        {
            "task_id": task["id"],
            "city": city,
            "industry": industry,
            "seed_keyword": seed_keyword,
            "report_md": report_md,
            "raw_json": full_data,
            "file_path": str(report_path),
        }
    )
    storage.replace_trend_keywords(task["id"], keyword_scores)
    storage.update_task(task["id"], status="trend_analyzed")
    return {
        "task_id": task["id"],
        "report_path": str(report_path),
        "data_path": str(data_path),
        "csv_path": str(csv_path),
        **trend_outputs,
        "keyword_scores": keyword_scores,
        "report_md": report_md,
    }


def _safe_qwen_query_plan(
    qwen: QwenClient,
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    competitors: str,
    max_search_queries: int,
) -> dict[str, Any]:
    try:
        return qwen.generate_trend_query_plan(
            city=city,
            industry=industry,
            customer_product=customer_product,
            seed_keyword=seed_keyword,
            competitors=competitors,
            max_search_queries=max_search_queries,
        )
    except Exception as exc:
        return {"search_queries": [], "trend_keywords": [], "error": str(exc)}


def _safe_serpapi_call(fn: Callable[[], dict[str, Any]], label: str) -> dict[str, Any]:
    try:
        return fn()
    except Exception as exc:
        return {"error": str(exc), "label": label}


def _keyword_scores_csv(items: list[dict[str, Any]]) -> str:
    output = StringIO()
    fieldnames = [
        "keyword",
        "trend_score",
        "growth_score",
        "commercial_score",
        "local_score",
        "final_score",
        "reason",
    ]
    writer = DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for item in items:
        writer.writerow({key: item.get(key, "") for key in fieldnames})
    return output.getvalue()


def refresh_media_resources(
    storage: Storage,
    config: AppConfig,
    progress: ProgressFn | None = None,
) -> dict[str, int]:
    if config.meijieku.mock_mode:
        counts: dict[str, int] = {}
        for resource_type, items in _mock_media_resources().items():
            if progress:
                progress(f"模拟同步 {resource_type} 资源")
            storage.upsert_media_resources(resource_type, items)
            counts[resource_type] = len(items)
        return counts

    client = MeijiekuClient(config.meijieku)
    counts: dict[str, int] = {}
    for resource_type, label in [("website", "网站媒体"), ("wemedia", "自媒体")]:
        if progress:
            progress(f"正在同步{label}资源")
        items = client.list_resources(resource_type)
        for item in items:
            item["resource_type"] = resource_type
        storage.upsert_media_resources(resource_type, items)
        counts[resource_type] = len(items)
    return counts


def _mock_media_resources() -> dict[str, list[dict[str, Any]]]:
    return {
        "website": [
            {
                "resource_type": "website",
                "resource_id": 900101,
                "title": "搜狐健康",
                "case_link": "https://www.sohu.com/a/mock",
                "entrance_link": "https://www.sohu.com",
                "price_1": "120.00",
                "price_2": "130.00",
                "price_3": "140.00",
                "remarks": "模拟网站媒体资源，仅用于测试流程",
            },
            {
                "resource_type": "website",
                "resource_id": 900102,
                "title": "网易健康",
                "case_link": "https://www.163.com/health/mock",
                "entrance_link": "https://www.163.com",
                "price_1": "150.00",
                "price_2": "160.00",
                "price_3": "170.00",
                "remarks": "模拟网站媒体资源，仅用于测试流程",
            },
        ],
        "wemedia": [
            {
                "resource_type": "wemedia",
                "resource_id": 910201,
                "title": "百家号健康",
                "case_link": "https://baijiahao.baidu.com/s?id=mock",
                "entrance_link": "https://baijiahao.baidu.com",
                "price_1": "80.00",
                "price_2": "90.00",
                "price_3": "100.00",
                "remarks": "模拟自媒体资源，仅用于测试流程",
            },
            {
                "resource_type": "wemedia",
                "resource_id": 910202,
                "title": "头条健康",
                "case_link": "https://www.toutiao.com/article/mock",
                "entrance_link": "https://www.toutiao.com",
                "price_1": "95.00",
                "price_2": "105.00",
                "price_3": "115.00",
                "remarks": "模拟自媒体资源，仅用于测试流程",
            },
        ],
    }


def generate_platform_matches(
    storage: Storage,
    config: AppConfig,
    task_id: str,
    use_ai_fuzzy: bool = True,
) -> list[dict[str, Any]]:
    task = storage.get_one("select * from tasks where id=?", (task_id,))
    if not task:
        raise RuntimeError("任务不存在")
    search_results = storage.query("select * from search_results where task_id=? order by run_index, rank", (task_id,))
    resources = storage.query("select * from media_resources")
    if not resources:
        raise RuntimeError("媒介库资源为空，请先刷新媒介库资源")
    qwen = QwenClient(config.qwen) if use_ai_fuzzy and config.qwen.api_key else None
    matcher = PlatformMatcher(qwen=qwen)
    matches = matcher.match(search_results, resources)
    storage.clear_task_matches(task_id)
    for item in matches:
        storage.add_platform_match({**item, "task_id": task_id})
    storage.update_task(task_id, status="matched")
    task_dir = Path(task["task_dir"])
    write_text(task_dir / "platform_matches.json", json.dumps(matches, ensure_ascii=False, indent=2))
    return storage.query("select * from platform_matches where task_id=? order by link_count desc, confidence desc", (task_id,))


def get_publishable_matches(storage: Storage, task_id: str) -> list[dict[str, Any]]:
    return storage.query(
        """
        select * from platform_matches
        where task_id=? and confirmed=1 and resource_id is not null
        order by link_count desc, price_1 asc, confidence desc
        """,
        (task_id,),
    )


def generate_articles_for_matches(
    storage: Storage,
    config: AppConfig,
    task_id: str,
    match_ids: list[int],
    progress: ProgressFn | None = None,
) -> list[dict[str, Any]]:
    task = storage.get_one("select * from tasks where id=?", (task_id,))
    if not task:
        raise RuntimeError("任务不存在")
    format_path = Path(task["format_md_path"])
    if not format_path.exists():
        raise RuntimeError("文章生成格式.md 不存在，请先完成搜索分析")
    format_md = format_path.read_text(encoding="utf-8")
    matches = []
    for match_id in match_ids:
        item = storage.get_one("select * from platform_matches where id=?", (match_id,))
        if item:
            matches.append(item)
    existing_titles = [row["title"] for row in storage.query("select title from articles where task_id=?", (task_id,)) if row.get("title")]
    qwen = QwenClient(config.qwen)
    articles_dir = Path(task["task_dir"]) / "articles"
    created = []
    for idx, match in enumerate(matches, start=1):
        if progress:
            progress(f"正在生成 {idx}/{len(matches)}：{match.get('resource_title')}")
        article = qwen.generate_article(
            keyword=task["keyword"],
            customer_product=task["customer_product"],
            format_md=format_md,
            platform=match,
            existing_titles=existing_titles,
        )
        existing_titles.append(article["title"])
        content_html = markdown_to_html(article["content_md"])
        filename = f"{safe_filename(match.get('resource_title') or match.get('source_site_name'))}_{safe_filename(article['title'], 60)}.md"
        file_path = articles_dir / filename
        write_text(file_path, article["content_md"])
        article_id = storage.add_article(
            {
                "task_id": task_id,
                "platform_match_id": match["id"],
                "resource_type": match["resource_type"],
                "resource_id": match["resource_id"],
                "resource_title": match["resource_title"],
                "title": article["title"],
                "content_md": article["content_md"],
                "content_html": content_html,
                "file_path": str(file_path),
                "publish_status": None,
            }
        )
        created.append(storage.get_one("select * from articles where id=?", (article_id,)))
    storage.update_task(task_id, status="articles_ready")
    return created


def publish_articles(
    storage: Storage,
    config: AppConfig,
    article_ids: list[int],
    remark: str = "GEO自动发布",
    progress: ProgressFn | None = None,
) -> list[dict[str, Any]]:
    client = MeijiekuClient(config.meijieku)
    published = []
    for idx, article_id in enumerate(article_ids, start=1):
        article = storage.get_one("select * from articles where id=?", (article_id,))
        if not article:
            continue
        if progress:
            progress(f"正在发布 {idx}/{len(article_ids)}：{article.get('resource_title')}")
        response = client.submit_article(
            resource_type=article["resource_type"],
            title=article["title"],
            content_html=article["content_html"],
            resource_id=int(article["resource_id"]),
            resource_name=article["resource_title"],
            customer=article["task_id"],
            remark=remark,
        )
        result_items = response.get("result") or []
        result = result_items[0] if result_items else {}
        storage.update_article(
            article_id,
            article_id=result.get("article_id"),
            order_id=result.get("order_id"),
            publish_status=0,
        )
        published.append(storage.get_one("select * from articles where id=?", (article_id,)))
    return published


def sync_pending_orders(
    storage: Storage,
    config: AppConfig,
    progress: ProgressFn | None = None,
) -> int:
    pending = storage.query(
        """
        select * from articles
        where order_id is not null and (publish_status is null or publish_status in (0, 1, 9))
        order by updated_at asc
        """
    )
    if not pending:
        return 0
    client = MeijiekuClient(config.meijieku)
    updated = 0
    for idx, article in enumerate(pending, start=1):
        if progress:
            progress(f"正在查询 {idx}/{len(pending)}：{article.get('order_id')}")
        remote = client.query_article(article["resource_type"], article["order_id"])
        if not remote:
            continue
        storage.update_article(
            article["id"],
            publish_status=remote.get("status"),
            link=remote.get("link"),
            refund_info=remote.get("refund_info"),
            rejection_info=remote.get("rejection_info"),
        )
        updated += 1
    return updated
