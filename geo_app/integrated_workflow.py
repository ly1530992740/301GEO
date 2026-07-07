from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from .config import AppConfig, OUTPUT_DIR
from .integrated_report_renderer import render_integrated_outputs
from .multi_ai_geo_workflow import run_multi_ai_geo_competition
from .platform_matcher import PlatformMatcher
from .product_ingestion import UploadedPdf, collect_product_sources, source_text_for_ai
from .qwen_client import QwenClient
from .storage import Storage
from .utils import domain_from_url, safe_filename, utc_now_iso, write_text


ProgressFn = Callable[[str], None]
INTEGRATED_DIR = OUTPUT_DIR / "integrated_reports"
WORKFLOW_VERSION = "integrated_geo_v5_multi_ai_consensus_20260707"


def create_product_profile_run(
    storage: Storage,
    config: AppConfig,
    website_url: str = "",
    uploaded_pdfs: list[UploadedPdf] | None = None,
    preferred_product_name: str = "",
    user_market_context: dict[str, Any] | None = None,
    report_language: str = "zh",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    del storage
    run_id = f"{utc_now_iso().replace(':', '').replace('-', '').replace('Z', '')}_{uuid.uuid4().hex[:6]}"
    subject = preferred_product_name or website_url or "uploaded_product"
    run_dir = INTEGRATED_DIR / f"{run_id}_{safe_filename(subject, 40)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    if progress:
        progress("收集产品资料：官网首页、同域链接和上传 PDF")
    sources = collect_product_sources(website_url, uploaded_pdfs or [], max_same_domain_links=5)
    write_text(run_dir / "product_sources.json", json.dumps(sources, ensure_ascii=False, indent=2))

    if progress:
        progress("调用 Qwen 生成产品画像、市场语言、服务地区、品牌名和类目")
    qwen = QwenClient(config.qwen)
    profile = qwen.generate_product_profile(
        source_text_for_ai(sources),
        preferred_product_name=preferred_product_name,
        report_language=report_language,
    )
    profile = _apply_user_market_context(profile, user_market_context or {})
    write_text(run_dir / "product_profile.md", profile.get("profile_md", ""))
    write_text(run_dir / "product_profile.json", json.dumps(profile, ensure_ascii=False, indent=2))
    if progress:
        progress(f"产品画像已保存：{run_dir / 'product_profile.md'}")
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "sources": sources,
        "product_profile": profile,
        "user_market_context": user_market_context or {},
        "workflow_version": WORKFLOW_VERSION,
        "report_language": report_language,
    }


def run_integrated_geo_analysis(
    storage: Storage,
    config: AppConfig,
    profile_run: dict[str, Any],
    confirmed_profile: dict[str, Any],
    report_language: str = "zh",
    trend_count: int = 10,
    recommendations_per_term: int = 10,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    """Run the one-click GEO analysis with the simplified multi-AI consensus flow."""

    del trend_count, recommendations_per_term
    run_dir = Path(profile_run["run_dir"])
    confirmed_profile = _apply_user_market_context(
        confirmed_profile,
        confirmed_profile.get("user_market_context") or profile_run.get("user_market_context") or {},
    )

    if progress:
        progress("启动多 AI 共识流程：Qwen、豆包、元宝、DeepSeek 使用同一个主流推荐问题")
    multi_ai = run_multi_ai_geo_competition(
        config=config,
        profile=confirmed_profile,
        report_language=report_language,
        progress=progress,
    )

    analysis_strategy = multi_ai["analysis_strategy"]
    competitor_discovery = multi_ai["competitor_discovery"]
    question_discovery = multi_ai["question_discovery"]
    trend_discovery = multi_ai["trend_discovery"]
    recommendation_items = multi_ai["recommendation_items"]
    ai_recommendation_ranking = multi_ai["ai_recommendation_ranking"]
    brand_ranking = multi_ai["brand_ranking"]
    visibility_query_strategy = multi_ai["visibility_query_strategy"]
    search_volume_ranking = multi_ai["search_volume_ranking"]
    search_volume_queries = multi_ai["search_volume_queries"]
    search_visibility_ranking = multi_ai["search_visibility_ranking"]
    baidu_mentions = multi_ai["baidu_mentions"]
    baidu_query_results = multi_ai.get("multi_ai_visibility_results") or []
    competitive_gap_ranking = multi_ai["competitive_gap_ranking"]
    source_links = multi_ai["source_links"]
    source_articles = multi_ai["source_articles"]
    content_pattern_report = multi_ai["content_pattern_report"]
    content_positioning_analysis = multi_ai.get("content_positioning_analysis") or {}
    content_analysis_meta = multi_ai.get("content_analysis_meta") or {}
    article_generation_format = multi_ai["article_generation_format"]
    content_topic_analysis = multi_ai["content_topic_analysis"]
    probes = [
        {
            "engine": item.get("engine", ""),
            "trend_term": item.get("trend_term", ""),
            "question_meta": {"question": item.get("question", ""), "intent": "multi_ai_mainstream_recommendation"},
            "result": {"question": item.get("question", ""), "recommendations": [item], "search_results": []},
        }
        for item in recommendation_items
    ]

    write_text(run_dir / "competitor_discovery.json", json.dumps(competitor_discovery, ensure_ascii=False, indent=2))
    write_text(run_dir / "analysis_strategy.json", json.dumps(analysis_strategy, ensure_ascii=False, indent=2))
    write_text(run_dir / "question_discovery.json", json.dumps(question_discovery, ensure_ascii=False, indent=2))
    write_text(run_dir / "trend_discovery.json", json.dumps(trend_discovery, ensure_ascii=False, indent=2))
    write_text(run_dir / "probe_questions.json", json.dumps(question_discovery.get("questions") or [], ensure_ascii=False, indent=2))
    write_text(run_dir / "ai_probe_results.json", json.dumps(probes, ensure_ascii=False, indent=2))
    write_text(run_dir / "recommendation_items.json", json.dumps(recommendation_items, ensure_ascii=False, indent=2))
    write_text(run_dir / "ai_recommendation_ranking.json", json.dumps(ai_recommendation_ranking, ensure_ascii=False, indent=2))
    write_text(run_dir / "brand_ranking.json", json.dumps(brand_ranking, ensure_ascii=False, indent=2))
    write_text(run_dir / "visibility_query_strategy.json", json.dumps(visibility_query_strategy, ensure_ascii=False, indent=2))
    write_text(run_dir / "search_volume_ranking.json", json.dumps(search_volume_ranking, ensure_ascii=False, indent=2))
    write_text(run_dir / "search_volume_queries.json", json.dumps(search_volume_queries, ensure_ascii=False, indent=2))
    write_text(run_dir / "source_links.json", json.dumps(source_links, ensure_ascii=False, indent=2))
    write_text(run_dir / "source_articles.json", json.dumps(source_articles, ensure_ascii=False, indent=2))
    write_text(run_dir / "baidu_mentions.json", json.dumps(baidu_mentions, ensure_ascii=False, indent=2))
    write_text(run_dir / "baidu_query_results.json", json.dumps(baidu_query_results, ensure_ascii=False, indent=2))
    write_text(run_dir / "search_visibility_ranking.json", json.dumps(search_visibility_ranking, ensure_ascii=False, indent=2))
    write_text(run_dir / "competitive_gap_ranking.json", json.dumps(competitive_gap_ranking, ensure_ascii=False, indent=2))
    write_text(run_dir / "content_pattern_report.md", content_pattern_report)
    write_text(run_dir / "article_generation_format.md", article_generation_format)

    if progress:
        progress("用 AI 返回的来源链接匹配媒介库资源和报价")
    media_matches = _match_media_sources(storage, config, source_links, progress)
    media_cost_analysis = _derive_media_cost_analysis(media_matches, search_volume_ranking or search_visibility_ranking)
    write_text(run_dir / "media_matches.json", json.dumps(media_matches, ensure_ascii=False, indent=2))
    write_text(run_dir / "content_topic_analysis.json", json.dumps(content_topic_analysis, ensure_ascii=False, indent=2))
    write_text(run_dir / "media_cost_analysis.json", json.dumps(media_cost_analysis, ensure_ascii=False, indent=2))

    analysis_data = {
        "workflow_version": WORKFLOW_VERSION,
        "run_id": profile_run["run_id"],
        "run_dir": str(run_dir),
        "report_language": report_language,
        "product_profile": confirmed_profile,
        "analysis_strategy": analysis_strategy,
        "sources": profile_run.get("sources") or {},
        "competitor_discovery": competitor_discovery,
        "question_discovery": question_discovery,
        "trend_discovery": trend_discovery,
        "ai_probes": probes,
        "recommendation_items": recommendation_items,
        "ai_recommendation_ranking": ai_recommendation_ranking,
        "search_visibility_ranking": search_visibility_ranking,
        "search_volume_ranking": search_volume_ranking,
        "search_volume_queries": search_volume_queries,
        "visibility_query_strategy": visibility_query_strategy,
        "competitive_gap_ranking": competitive_gap_ranking,
        "brand_ranking": brand_ranking,
        "source_links": source_links,
        "source_articles": source_articles,
        "baidu_mentions": baidu_mentions,
        "baidu_query_results": baidu_query_results,
        "content_topic_analysis": content_topic_analysis,
        "content_pattern_report": content_pattern_report,
        "content_positioning_analysis": content_positioning_analysis,
        "content_analysis_meta": content_analysis_meta,
        "article_generation_format": article_generation_format,
        "media_matches": media_matches,
        "media_cost_analysis": media_cost_analysis,
        "multi_ai_recommendation_results": multi_ai.get("multi_ai_recommendation_results") or [],
        "multi_ai_visibility_results": multi_ai.get("multi_ai_visibility_results") or [],
        "multi_ai_provider_status": multi_ai.get("multi_ai_provider_status") or [],
    }
    outputs = render_integrated_outputs(run_dir, analysis_data, report_language)
    report_id = storage.add_strategy_report(
        {
            "report_type": "integrated_geo",
            "subject": confirmed_profile.get("product_name") or confirmed_profile.get("brand_name") or profile_run["run_id"],
            "city": question_discovery.get("primary_region") or confirmed_profile.get("primary_region") or question_discovery.get("target_market") or "",
            "industry": _search_category(confirmed_profile),
            "customer_product": confirmed_profile.get("product_name") or "",
            "competitors": ", ".join(item.get("brand_name", "") for item in search_visibility_ranking[:10] or ai_recommendation_ranking[:10]),
            "report_md": outputs["report_md"],
            "raw_json": analysis_data,
            "file_path": outputs["report_md_path"],
        }
    )
    if progress:
        progress(f"多 AI 一键分析完成，报告已保存：{outputs['report_md_path']}")
    return {**outputs, "report_id": report_id, "analysis_data": analysis_data}


def _apply_user_market_context(profile: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    if not context:
        return dict(profile)
    merged = dict(profile)
    service_scope = str(context.get("service_scope") or merged.get("service_scope") or "").strip()
    service_region = str(context.get("service_region") or merged.get("primary_region") or "").strip()
    category_local = str(context.get("category_local") or merged.get("category_local") or "").strip()
    geo_audience = str(context.get("geo_audience") or context.get("analysis_goal") or merged.get("geo_audience") or merged.get("analysis_goal") or "").strip()
    target_market = str(context.get("target_market") or "").strip()
    market_language = str(context.get("market_language") or "").strip()

    if category_local:
        merged["category_local"] = category_local
    if service_region:
        merged["primary_region"] = service_region
    if service_scope:
        merged["service_scope"] = service_scope
        merged["region_level"] = {
            "local_city": "city",
            "regional": "province",
            "national": "country",
            "global": "global",
        }.get(service_scope, merged.get("region_level") or "unknown")
    if target_market:
        merged["target_market"] = target_market
    if market_language:
        merged["market_language"] = market_language
    if geo_audience:
        merged["geo_audience"] = geo_audience
        merged["analysis_goal"] = geo_audience
    if market_language == "zh" or target_market == "domestic":
        merged["source_language"] = merged.get("source_language") or "zh"
        merged["target_market"] = "domestic"
        merged["market_language"] = "zh"
        if category_local:
            merged["geo_probe_subject"] = f"{service_region}{category_local}品牌推荐".strip() if service_region else f"{category_local}品牌推荐"
            merged["category_en"] = merged.get("category_en") or category_local
    merged["user_market_context"] = context
    return merged


def _search_category(profile: dict[str, Any]) -> str:
    market_language = str(profile.get("market_language") or "").lower()
    if market_language.startswith("zh"):
        return profile.get("category_local") or profile.get("category_en") or ""
    return profile.get("category_en") or profile.get("category_local") or ""


def _match_media_sources(
    storage: Storage,
    config: AppConfig,
    source_links: list[dict[str, Any]],
    progress: ProgressFn | None,
) -> dict[str, Any]:
    resources = storage.query("select * from media_resources")
    refresh_counts: dict[str, int] = {}
    can_refresh = bool(
        config.meijieku.mock_mode
        or config.meijieku.token
        or (config.meijieku.mobile and config.meijieku.password)
    )
    if not resources and can_refresh:
        from .workflow import refresh_media_resources

        try:
            if progress:
                progress("媒介库本地资源为空，正在自动同步媒介库资源")
            refresh_counts = refresh_media_resources(storage, config, progress=progress)
        except Exception as exc:
            return {
                "matches": [],
                "resource_count": 0,
                "refresh_counts": refresh_counts,
                "warning": f"media resources refresh failed: {exc}",
                "refresh_error": str(exc),
            }
        resources = storage.query("select * from media_resources")
    if not resources:
        return {
            "matches": [],
            "resource_count": 0,
            "refresh_counts": refresh_counts,
            "warning": "media resources are empty; configure Meijieku credentials or refresh media library first",
        }

    search_results = [
        {
            "site_name": item.get("label") or item.get("domain") or "",
            "title": item.get("label") or "",
            "url": item.get("url") or "",
            "domain": item.get("domain") or domain_from_url(item.get("url", "")),
        }
        for item in source_links
    ]
    matches = PlatformMatcher().match(search_results, resources)
    return {
        "source_link_count": len(source_links),
        "resource_count": len(resources),
        "refresh_counts": refresh_counts,
        "matches": matches,
    }


def _derive_media_cost_analysis(media_matches: dict[str, Any], visibility_rows: list[dict[str, Any]]) -> dict[str, Any]:
    competitors = [item for item in visibility_rows if not item.get("is_user_brand")]
    count_key = "estimated_result_count" if any("estimated_result_count" in item for item in visibility_rows) else "mentioned_count"
    benchmark = max(competitors, key=lambda item: int(item.get(count_key) or 0), default={})
    user = next((item for item in visibility_rows if item.get("is_user_brand")), {})
    benchmark_count = int(benchmark.get(count_key) or 0)
    user_count = int(user.get(count_key) or 0)
    raw_gap = max(benchmark_count - user_count, benchmark_count, 1)
    target_articles = max(min(raw_gap, 300), 1)
    rows = []
    for item in media_matches.get("matches") or []:
        if item.get("match_type") == "unmatched" or not item.get("resource_title"):
            continue
        price_1 = _safe_float(item.get("price_1"))
        price_2 = _safe_float(item.get("price_2"))
        price_3 = _safe_float(item.get("price_3"))
        unit_price = next((price for price in (price_1, price_2, price_3) if price > 0), 0.0)
        rows.append(
            {
                "source_domain": item.get("source_domain", ""),
                "resource_title": item.get("resource_title", ""),
                "resource_type": item.get("resource_type", ""),
                "match_type": item.get("match_type", ""),
                "confidence": item.get("confidence", 0),
                "price_1": price_1,
                "price_2": price_2,
                "price_3": price_3,
                "unit_price": unit_price,
                "target_articles": target_articles,
                "estimated_total_cost": round(unit_price * target_articles, 2),
            }
        )
    prices = [item["unit_price"] for item in rows if item["unit_price"] > 0]
    return {
        "benchmark_brand": benchmark.get("brand_name", ""),
        "benchmark_mentioned_count": benchmark_count,
        "benchmark_metric_type": benchmark.get("metric_type", "multi_ai_estimated_count"),
        "user_brand_count": user_count,
        "content_asset_gap": max(benchmark_count - user_count, 0),
        "planning_note": "发布篇数为阶段性追赶目标，上限 300 篇；完整内容资产差距见 content_asset_gap。",
        "target_articles": target_articles,
        "currency": "CNY",
        "matched_media_count": len(rows),
        "min_unit_price": min(prices) if prices else 0,
        "avg_unit_price": round(sum(prices) / len(prices), 2) if prices else 0,
        "max_unit_price": max(prices) if prices else 0,
        "rows": rows,
    }


def _safe_float(value: Any) -> float:
    try:
        return float(str(value or 0).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0
