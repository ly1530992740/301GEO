from __future__ import annotations

import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .action_planner import build_action_plan
from .content_monitoring import build_content_monitoring
from .geo_metrics import build_standard_geo_metrics
from .geo_visibility_metrics import (
    build_brand_visibility_metrics,
    build_geo_visibility_summary,
    build_prompt_visibility_rows,
    build_provider_visibility_matrix,
)
from .owned_asset_audit import audit_owned_assets
from .source_intelligence import build_source_intelligence
from .topic_analysis import derive_content_topic_analysis
from .utils import write_text


LABELS = {
    "zh": {
        "title": "GEO 一键分析报告",
        "product": "产品画像",
        "trend_terms": "AI 搜索探测主题",
        "strategy": "分析策略",
        "neutral_queries": "真实搜索中立查询",
        "ranking": "AI 推荐品牌排名",
        "search_volume": "全网搜索声量估算",
        "visibility_queries": "搜索声量查询方案",
        "search_ranking": "品牌内容声量排名",
        "gap_ranking": "AI 推荐与搜索声量差距",
        "competitors": "竞品校准",
        "mentions": "传统搜索声量合计",
        "patterns": "竞品内容特点",
        "media": "媒介库匹配",
        "term": "探测主题",
        "source": "来源",
        "reason": "相关原因",
        "brand": "品牌",
        "count": "推荐次数",
        "avg_rank": "平均排名",
        "engine": "AI 引擎",
        "articles": "提及篇数",
        "matched": "可匹配媒介",
        "fallback": "AI 搜索问题补齐说明",
    },
    "en": {
        "title": "GEO One-Click Analysis Report",
        "product": "Product Profile",
        "trend_terms": "AI Search Probe Topics",
        "strategy": "Analysis Strategy",
        "neutral_queries": "Neutral Search Queries",
        "ranking": "AI Recommendation Brand Ranking",
        "search_volume": "All-Web Search Volume Estimate",
        "visibility_queries": "Search Volume Query Strategy",
        "search_ranking": "Search Visibility Ranking",
        "gap_ranking": "AI Recommendation vs Search Visibility Gap",
        "competitors": "Competitor Calibration",
        "mentions": "Traditional Search Visibility Summary",
        "patterns": "Competitor Content Patterns",
        "media": "Media Library Matching",
        "term": "Probe Topic",
        "source": "Source",
        "reason": "Relevance Reason",
        "brand": "Brand",
        "count": "Recommendation Count",
        "avg_rank": "Average Rank",
        "engine": "AI Engine",
        "articles": "Mentioned Results",
        "matched": "Matched Media",
        "fallback": "AI Search Question Fallback Note",
    },
}


def render_integrated_outputs(run_dir: Path, analysis_data: dict[str, Any], report_language: str) -> dict[str, str]:
    analysis_data = enrich_analysis_data(analysis_data)
    labels = LABELS.get(report_language, LABELS["zh"])
    markdown = build_markdown_report(analysis_data, labels)
    html_report = build_html_report(analysis_data, labels, markdown)
    dashboard_html = build_dashboard_html_report(analysis_data, labels)
    md_path = run_dir / "integrated_report.md"
    html_path = run_dir / "integrated_report.html"
    dashboard_path = run_dir / "dashboard_report.html"
    data_path = run_dir / "integrated_data.json"
    write_text(md_path, markdown)
    write_text(html_path, html_report)
    write_text(dashboard_path, dashboard_html)
    write_text(data_path, json.dumps(analysis_data, ensure_ascii=False, indent=2))
    return {
        "report_md_path": str(md_path),
        "report_html_path": str(html_path),
        "dashboard_html_path": str(dashboard_path),
        "data_path": str(data_path),
        "report_md": markdown,
    }


def build_markdown_report(analysis_data: dict[str, Any], labels: dict[str, str]) -> str:
    analysis_data = enrich_analysis_data(analysis_data)
    profile = analysis_data.get("product_profile") or {}
    strategy = analysis_data.get("analysis_strategy") or {}
    question_discovery = analysis_data.get("question_discovery") or {}
    competitor_discovery = analysis_data.get("competitor_discovery") or {}
    trend = analysis_data.get("trend_discovery") or {}
    ai_ranking = analysis_data.get("ai_recommendation_ranking") or analysis_data.get("brand_ranking") or []
    search_ranking = analysis_data.get("search_visibility_ranking") or []
    search_volume = analysis_data.get("search_volume_ranking") or []
    visibility_strategy = analysis_data.get("visibility_query_strategy") or {}
    gap_ranking = analysis_data.get("competitive_gap_ranking") or []
    baidu = analysis_data.get("baidu_mentions") or []
    media = analysis_data.get("media_matches") or {}
    cost = analysis_data.get("media_cost_analysis") or {}
    topics = analysis_data.get("content_topic_analysis") or {}
    content_report = analysis_data.get("content_pattern_report") or ""
    article_format = analysis_data.get("article_generation_format") or ""
    provider_status = analysis_data.get("multi_ai_provider_status") or _provider_status_from_results(analysis_data)
    source_articles = analysis_data.get("source_articles") or []
    visibility_summary = analysis_data.get("geo_visibility_summary") or {}
    neutral_summary = analysis_data.get("neutral_visibility_summary") or visibility_summary
    diagnostic_summary = analysis_data.get("brand_diagnostic_summary") or {}
    comparison_summary = analysis_data.get("comparison_summary") or {}
    brand_visibility_metrics = analysis_data.get("brand_visibility_metrics") or []

    lines = [f"# {labels['title']}", ""]
    if analysis_data.get("workflow_version"):
        lines.extend([f"- Workflow version: {analysis_data.get('workflow_version')}", ""])
    lines.extend(
        [
            f"## {labels['product']}",
            "",
            profile.get("profile_md") or profile.get("summary") or "",
            "",
            f"- Product: {profile.get('product_name', '')}",
            f"- Brand: {profile.get('brand_name', '')}",
            f"- Category: {_display_category(profile)}",
            f"- Market language: {question_discovery.get('market_language') or profile.get('market_language', '')}",
            f"- Target market: {question_discovery.get('target_market') or profile.get('target_market', '')}",
            f"- Primary region: {question_discovery.get('primary_region') or profile.get('primary_region', '')}",
            f"- Business type: {question_discovery.get('business_type') or profile.get('business_type', '')}",
            "",
        ]
    )
    if strategy:
        lines.extend(
            [
                f"## {labels['strategy']}",
                "",
                f"- GEO target audience: {strategy.get('geo_audience') or strategy.get('analysis_goal', '')}",
                f"- Probe subject: {strategy.get('geo_probe_subject', '')}",
                f"- Service scope: {strategy.get('service_scope', '')}",
                f"- Service region: {strategy.get('service_region', '')}",
                f"- Topic taxonomy: {', '.join(str(item) for item in strategy.get('topic_taxonomy') or [])}",
                "",
            ]
        )
    if visibility_summary:
        lines.extend(
            [
                "## GEO 可见度总览",
                "",
                f"- GEO 可见度总分：{visibility_summary.get('visibility_score', 0)}%",
                f"- AI 提及次数：{visibility_summary.get('mention_count', 0)}",
                f"- 平均推荐位置：{_display_rank(visibility_summary.get('avg_position'))}",
                f"- AI 描述情绪分：{visibility_summary.get('sentiment_score', 50)}/100",
                f"- Prompt 成功率：{round(float(visibility_summary.get('prompt_success_rate') or 0) * 100, 1)}%",
                f"- AI 平台覆盖：{visibility_summary.get('provider_coverage_count', 0)}/{visibility_summary.get('provider_total_count', 0)}",
                "",
                "| 品牌 | AI提及次数 | 平均推荐位置 | 情绪分 | AI推荐份额 |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for item in brand_visibility_metrics[:12]:
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {item.get('mention_count', 0)} | {_cell(_display_rank(item.get('avg_position')))} | {item.get('sentiment_score', 50)} | {round(float(item.get('share_of_voice') or 0) * 100, 1)}% |"
            )
        lines.append("")
    standard_geo_metrics = analysis_data.get("standard_geo_metrics") or {}
    if standard_geo_metrics:
        lines.extend(_standard_geo_metrics_markdown(standard_geo_metrics))

    source_intelligence = analysis_data.get("source_intelligence") or {}
    if source_intelligence:
        lines.extend(_source_intelligence_markdown(source_intelligence))

    owned_asset_audit = analysis_data.get("owned_asset_audit") or {}
    if owned_asset_audit:
        lines.extend(_owned_asset_audit_markdown(owned_asset_audit))

    content_monitoring = analysis_data.get("content_monitoring") or {}
    if content_monitoring:
        lines.extend(_content_monitoring_markdown(content_monitoring))

    geo_actions = analysis_data.get("geo_actions") or {}
    if geo_actions:
        lines.extend(_geo_actions_markdown(geo_actions))

    if trend.get("fallback_used"):
        lines.extend([f"## {labels['fallback']}", "", trend.get("fallback_note") or "Fallback terms were used.", ""])

    lines.extend([f"## {labels['trend_terms']}", "", f"| {labels['term']} | {labels['source']} | {labels['reason']} |", "|---|---|---|"])
    for item in trend.get("terms") or []:
        lines.append(f"| {_cell(item.get('term'))} | {_cell(item.get('source'))} | {_cell(item.get('relevance_reason'))} |")
    lines.append("")

    probe_questions = trend.get("probe_questions") or _probe_questions_from_ai_probes(analysis_data.get("ai_probes") or [])
    if probe_questions:
        lines.extend(["## AI 搜索问题建议", "", "| 趋势词 | 建议问题 | 用户意图 |", "|---|---|---|"])
        for item in probe_questions:
            lines.append(f"| {_cell(item.get('term'))} | {_cell(item.get('question'))} | {_cell(item.get('intent'))} |")
        lines.append("")

    neutral_queries = strategy.get("neutral_search_queries") or question_discovery.get("neutral_search_queries") or []
    if neutral_queries:
        lines.extend([f"## {labels['neutral_queries']}", "", "| 查询词 |", "|---|"])
        for query in neutral_queries:
            lines.append(f"| {_cell(query)} |")
        lines.append("")

    if visibility_strategy.get("visibility_queries"):
        lines.extend([f"## {labels['visibility_queries']}", "", "| 品牌 | 查询词 | 指标目标 |", "|---|---|---|"])
        for item in visibility_strategy.get("visibility_queries") or []:
            lines.append(f"| {_cell(item.get('brand_name'))} | {_cell(item.get('query'))} | {_cell(item.get('metric_goal'))} |")
        lines.append("")

    if provider_status:
        lines.extend(["## 多 AI 平台调用状态", "", "| AI平台 | 推荐排名 | 推荐条数 | 声量估算 | 声量品牌数 | 模型 | 超时秒数 | 错误信息 |", "|---|---|---:|---|---:|---|---:|---|"])
        for item in provider_status:
            lines.append(
                f"| {_cell(item.get('provider'))} | {_ok_text(item.get('recommendation_ok'))} | {item.get('recommendation_count', 0)} | {_ok_text(item.get('visibility_ok'))} | {item.get('visibility_count', 0)} | {_cell(item.get('model'))} | {_cell(item.get('timeout'))} | {_cell(item.get('recommendation_error') or item.get('visibility_error'))} |"
            )
        lines.append("")

    competitor_platform_rows = _provider_recommendation_rows(analysis_data.get("recommendation_items") or [])
    if competitor_platform_rows:
        lines.extend(["## 竞品校准（按 AI 平台）", "", "| AI平台 | 平台推荐排名 | 品牌 | 搜索问题 | 引用链接数 | 推荐理由 |", "|---|---:|---|---|---:|---|"])
        for item in competitor_platform_rows:
            lines.append(
                f"| {_cell(item.get('provider'))} | {_cell(item.get('rank'))} | {_cell(item.get('brand_name'))} | {_cell(item.get('question'))} | {item.get('source_url_count', 0)} | {_cell(item.get('reason'))} |"
            )
        lines.append("")

    competitor_rows = _competitor_rows(competitor_discovery)
    if competitor_rows:
        lines.extend([f"## {labels['competitors']}（跨平台汇总）", "", "| 品牌 | 类型 | 地区 | 原因 |", "|---|---|---|---|"])
        for item in competitor_rows:
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {_cell(item.get('competitor_group'))} | {_cell(item.get('region'))} | {_cell(item.get('reason'))} |"
            )
        lines.append("")

    if search_volume:
        lines.extend([f"## {labels['search_volume']}", "", "| 品牌 | 排名 | 估算结果数 | 与客户差距 | 查询词 | 指标口径 | 说明 |", "|---|---:|---:|---:|---|---|---|"])
        for item in search_volume:
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {item.get('search_volume_rank', '')} | {item.get('estimated_result_count', 0)} | {item.get('gap_vs_user', 0)} | {_cell(item.get('query'))} | {_cell(item.get('metric_type'))} | {_cell(item.get('warning'))} |"
            )
        lines.append("")

    if search_ranking:
        lines.extend([f"## {labels['search_ranking']}", "", "含义：基于 AI 对百度、搜狗、360 搜索、抖音、小红书五个平台内容数量的估算，用来判断品牌在传统搜索与新媒体里的可见度。", "", "| 品牌 | 品牌内容声量排名 | 五平台内容数量估算 | 结果数估算 | 查询词 | 数据口径 |", "|---|---:|---:|---:|---|---|"])
        for item in search_ranking:
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {_cell(_display_rank(item.get('search_visibility_rank')))} | {_cell(_display_count(item.get('mentioned_count'), _has_visibility_data(item)))} | {_cell(_display_count(item.get('result_count'), _has_visibility_data(item)))} | {_cell(item.get('query'))} | {_cell(item.get('metric_type') or '五平台内容数量估算')} |"
            )
        lines.append("")

    lines.extend([f"## {labels['ranking']}（AI 可推荐度，不等于市场知名度）", "", f"| {labels['brand']} | {labels['count']} | {labels['avg_rank']} | {labels['engine']} |", "|---|---:|---:|---|"])
    for item in ai_ranking:
        lines.append(
            f"| {_cell(item.get('brand_name'))} | {item.get('recommendation_count', 0)} | {item.get('avg_rank', '')} | {_cell(item.get('engine'))} |"
        )
    lines.append("")

    recommendation_source_rows = _recommendation_source_rows(analysis_data.get("recommendation_items") or [], ai_ranking)
    if recommendation_source_rows:
        lines.extend(["## AI 推荐来源明细", "", "| 品牌 | 综合排名 | Qwen | 豆包 | 元宝 | DeepSeek | 来源链接数 | 主要推荐理由 |", "|---|---:|---:|---:|---:|---:|---:|---|"])
        for item in recommendation_source_rows:
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {item.get('ai_recommendation_rank', '')} | {_cell(item.get('qwen_rank'))} | {_cell(item.get('doubao_rank'))} | {_cell(item.get('yuanbao_rank'))} | {_cell(item.get('deepseek_rank'))} | {item.get('source_url_count', 0)} | {_cell(item.get('reason'))} |"
            )
        lines.append("")

    if search_volume:
        lines.extend(["## 全网声量平台拆分", "", "| 品牌 | 总声量估算 | 百度 | 搜狗 | 360 | 抖音 | 小红书 | 参与AI数 | 消息来源/依据 |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"])
        for item in search_volume:
            traditional = item.get("traditional_search") or {}
            new_media = item.get("new_media") or {}
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {item.get('estimated_result_count', 0)} | {traditional.get('baidu', 0)} | {traditional.get('sogou', 0)} | {traditional.get('so360', 0)} | {new_media.get('douyin', 0)} | {new_media.get('xiaohongshu', 0)} | {item.get('provider_count', 0)} | {_cell(_source_note(item))} |"
            )
        lines.append("")

    if gap_ranking:
        lines.extend([f"## {labels['gap_ranking']}", "", "| 品牌 | AI排名 | 品牌内容声量排名 | 五平台内容数量估算 | 解读 |", "|---|---:|---|---|---|"])
        for item in gap_ranking:
            has_visibility = _has_visibility_data(item)
            lines.append(
                f"| {_cell(item.get('brand_name'))} | {_cell(_display_rank(item.get('ai_recommendation_rank')))} | {_cell(_display_rank(item.get('search_visibility_rank')) if has_visibility else '未进入声量估算')} | {_cell(_display_count(item.get('mentioned_count'), has_visibility))} | {_cell(item.get('gap_label') if has_visibility else 'AI 推荐中出现，但本轮未拿到有效五平台声量估算；不是确认没有内容。')} |"
            )
        lines.append("")

    lines.extend([f"## {labels['mentions']}", "", f"| {labels['brand']} | {labels['articles']} |", "|---|---:|"])
    for item in baidu:
        lines.append(f"| {_cell(item.get('brand_name'))} | {item.get('mentioned_count', 0)} |")
    lines.append("")

    if source_articles:
        lines.extend(["## 文章链接与抓取状态", "", "| 品牌/来源 | 域名 | AI来源 | 抓取状态 | 正文长度 | 链接/错误 |", "|---|---|---|---|---:|---|"])
        for item in source_articles[:40]:
            status = "成功" if item.get("text_excerpt") and not item.get("error") else "失败"
            url_or_error = item.get("url") if status == "成功" else item.get("error") or item.get("url")
            lines.append(
                f"| {_cell(item.get('label'))} | {_cell(item.get('domain'))} | {_cell(item.get('engine'))} | {status} | {len(item.get('text_excerpt') or '')} | {_cell(url_or_error)} |"
            )
        lines.append("")

    lines.extend([f"## {labels['patterns']}", "", content_report, ""])
    lines.extend(["## 内容主题分布", "", "| 主题 | 出现次数 |", "|---|---:|"])
    for item in topics.get("topics") or []:
        lines.append(f"| {_cell(item.get('topic'))} | {item.get('count', 0)} |")
    lines.append("")

    lines.extend(
        [
            "## 媒介库成本测算",
            "",
            f"- 对标竞品：{cost.get('benchmark_brand', '')}",
            f"- 对标提及篇数：{cost.get('benchmark_mentioned_count', 0)}",
            f"- 客户当前声量：{cost.get('user_brand_count', 0)}",
            f"- 内容资产差距：{cost.get('content_asset_gap', 0)}",
            f"- 建议至少发布篇数：{cost.get('target_articles', 0)}",
            f"- 规划说明：{cost.get('planning_note', '')}",
            f"- 单篇报价区间：{cost.get('min_unit_price', 0)} - {cost.get('max_unit_price', 0)} {cost.get('currency', 'CNY')}",
            "",
            "| Domain | Resource | 单篇报价 | 建议篇数 | 预计总成本 |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for item in cost.get("rows") or []:
        lines.append(
            f"| {_cell(item.get('source_domain'))} | {_cell(item.get('resource_title'))} | {item.get('unit_price', 0)} | {item.get('target_articles', 0)} | {item.get('estimated_total_cost', 0)} |"
        )
    lines.append("")

    lines.extend([f"## {labels['media']}", "", f"| Domain | {labels['matched']} | Resource | price_1 | price_2 | price_3 |", "|---|---|---|---:|---:|---:|"])
    for item in media.get("matches") or []:
        lines.append(
            f"| {_cell(item.get('source_domain'))} | {_cell(item.get('match_type'))} | {_cell(item.get('resource_title'))} | {item.get('price_1', 0)} | {item.get('price_2', 0)} | {item.get('price_3', 0)} |"
        )
    lines.extend(["", "## article_generation_format.md", "", article_format])
    return "\n".join(lines)


def build_html_report(analysis_data: dict[str, Any], labels: dict[str, str], markdown: str) -> str:
    analysis_data = enrich_analysis_data(analysis_data)
    profile = analysis_data.get("product_profile") or {}
    strategy = analysis_data.get("analysis_strategy") or {}
    question_discovery = analysis_data.get("question_discovery") or {}
    competitor_discovery = analysis_data.get("competitor_discovery") or {}
    trend = analysis_data.get("trend_discovery") or {}
    ranking = analysis_data.get("ai_recommendation_ranking") or analysis_data.get("brand_ranking") or []
    brand_visibility_metrics = analysis_data.get("brand_visibility_metrics") or []
    search_ranking = analysis_data.get("search_visibility_ranking") or []
    search_volume = analysis_data.get("search_volume_ranking") or []
    visibility_strategy = analysis_data.get("visibility_query_strategy") or {}
    gap_ranking = analysis_data.get("competitive_gap_ranking") or []
    baidu = analysis_data.get("baidu_mentions") or []
    media = analysis_data.get("media_matches") or {}
    cost = analysis_data.get("media_cost_analysis") or {}
    topics = analysis_data.get("content_topic_analysis") or {}
    provider_status = analysis_data.get("multi_ai_provider_status") or _provider_status_from_results(analysis_data)
    source_articles = analysis_data.get("source_articles") or []
    recommendation_source_rows = _recommendation_source_rows(analysis_data.get("recommendation_items") or [], ranking)
    competitor_platform_rows = _provider_recommendation_rows(analysis_data.get("recommendation_items") or [])
    probe_questions = trend.get("probe_questions") or _probe_questions_from_ai_probes(analysis_data.get("ai_probes") or [])
    charts = _chart_payload(ranking, baidu, media.get("matches") or [], topics, cost, search_ranking, gap_ranking, search_volume)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(labels['title'])}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin: 0; font-family: Arial, "Microsoft YaHei", sans-serif; color: #1f2937; background: #f8fafc; }}
    main {{ max-width: 1160px; margin: 0 auto; padding: 32px 20px 56px; }}
    section {{ margin: 24px 0; padding: 20px; background: #fff; border: 1px solid #e5e7eb; border-radius: 8px; }}
    h1 {{ font-size: 30px; margin: 0 0 20px; }}
    h2 {{ font-size: 20px; margin: 0 0 14px; }}
    .chart {{ min-height: 360px; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }}
    .metric {{ padding: 14px; border: 1px solid #e5e7eb; border-radius: 8px; background: #fbfdff; }}
    .metric strong {{ display: block; font-size: 24px; }}
    pre {{ white-space: pre-wrap; background: #111827; color: #e5e7eb; padding: 16px; border-radius: 8px; overflow: auto; }}
  </style>
</head>
<body>
<main>
  <h1>{html.escape(labels['title'])}</h1>
  <p>Workflow version: {html.escape(str(analysis_data.get('workflow_version', 'unknown')))}</p>
  <section>
    <h2>{html.escape(labels['product'])}</h2>
    <div class="grid">
      <div class="metric">Product<strong>{html.escape(str(profile.get('product_name', '')))}</strong></div>
      <div class="metric">Brand<strong>{html.escape(str(profile.get('brand_name', '')))}</strong></div>
      <div class="metric">Category<strong>{html.escape(_display_category(profile))}</strong></div>
      <div class="metric">Market<strong>{html.escape(str(question_discovery.get('target_market') or profile.get('target_market', '')))}</strong></div>
      <div class="metric">Region<strong>{html.escape(str(question_discovery.get('primary_region') or profile.get('primary_region', '')))}</strong></div>
      <div class="metric">Business<strong>{html.escape(str(question_discovery.get('business_type') or profile.get('business_type', '')))}</strong></div>
    </div>
    <p>{html.escape(str(profile.get('summary', '')))}</p>
  </section>
  <section><h2>{html.escape(labels['trend_terms'])}</h2>{_trend_table(trend.get('terms') or [], labels)}</section>
  <section><h2>AI 搜索问题建议</h2>{_probe_question_table(probe_questions)}</section>
  <section><h2>{html.escape(labels['neutral_queries'])}</h2>{_neutral_query_table(strategy.get('neutral_search_queries') or question_discovery.get('neutral_search_queries') or [])}</section>
  <section><h2>{html.escape(labels['visibility_queries'])}</h2>{_visibility_query_table(visibility_strategy.get('visibility_queries') or [])}</section>
  <section><h2>{html.escape(labels['strategy'])}</h2>{_strategy_table(strategy)}</section>
  <section><h2>多 AI 平台调用状态</h2>{_provider_status_table(provider_status)}</section>
  <section><h2>竞品校准（按 AI 平台）</h2>{_provider_recommendation_table(competitor_platform_rows)}</section>
  <section><h2>{html.escape(labels['competitors'])}（跨平台汇总）</h2>{_competitor_table(_competitor_rows(competitor_discovery))}</section>
  <section><h2>{html.escape(labels['search_volume'])}</h2><div id="searchVolumeChart" class="chart"></div>{_search_volume_table(search_volume)}<h3>全网声量平台拆分</h3>{_visibility_platform_table(search_volume)}</section>
  <section><h2>{html.escape(labels['search_ranking'])}</h2><div id="searchVisibilityChart" class="chart"></div>{_search_visibility_table(search_ranking)}</section>
  <section><h2>{html.escape(labels['gap_ranking'])}</h2><div id="gapChart" class="chart"></div>{_gap_table(gap_ranking)}</section>
  <section><h2>{html.escape(labels['ranking'])}（AI 可推荐度，不等于市场知名度）</h2><div id="rankingChart" class="chart"></div>{_ranking_table(ranking, labels)}</section>
  <section><h2>AI 推荐来源明细</h2>{_recommendation_source_table(recommendation_source_rows)}</section>
  <section><h2>{html.escape(labels['mentions'])}</h2><div id="baiduChart" class="chart"></div>{_mentions_table(baidu, labels)}</section>
  <section><h2>文章链接与抓取状态</h2>{_source_article_table(source_articles)}</section>
  <section><h2>内容主题分析</h2><div id="topicChart" class="chart"></div><div id="topicMatrixChart" class="chart"></div>{_topic_table(topics.get('topics') or [])}</section>
  <section><h2>媒介库成本测算</h2>{_cost_summary(cost)}<div id="costChart" class="chart"></div>{_cost_table(cost.get('rows') or [])}</section>
  <section><h2>{html.escape(labels['media'])}</h2><div id="mediaChart" class="chart"></div>{_media_warning(media)}{_media_table(media.get('matches') or [], labels)}</section>
  <section><h2>Markdown</h2><pre>{html.escape(markdown)}</pre></section>
</main>
<script>
const chartData = {_script_json(charts)};
const commonLayout = {{ margin: {{ l: 50, r: 20, t: 20, b: 110 }}, paper_bgcolor: "white", plot_bgcolor: "white" }};
if (chartData.ranking.x.length) {{
  Plotly.newPlot("rankingChart", [{{ type: "bar", x: chartData.ranking.x, y: chartData.ranking.y, marker: {{ color: chartData.ranking.colors }} }}], {{ ...commonLayout, yaxis: {{ title: "{html.escape(labels['count'])}" }} }}, {{ responsive: true }});
}}
if (chartData.baidu.x.length) {{
  Plotly.newPlot("baiduChart", [{{ type: "bar", x: chartData.baidu.x, y: chartData.baidu.y, marker: {{ color: "#2563eb" }} }}], {{ ...commonLayout, yaxis: {{ title: "{html.escape(labels['articles'])}" }} }}, {{ responsive: true }});
}}
if (chartData.searchVisibility.x.length) {{
  Plotly.newPlot("searchVisibilityChart", [{{ type: "bar", x: chartData.searchVisibility.x, y: chartData.searchVisibility.y, marker: {{ color: "#0f766e" }} }}], {{ ...commonLayout, yaxis: {{ title: "{html.escape(labels['articles'])}" }} }}, {{ responsive: true }});
}}
if (chartData.searchVolume.x.length) {{
  Plotly.newPlot("searchVolumeChart", [
    {{ type: "bar", name: "传统搜索", x: chartData.searchVolume.x, y: chartData.searchVolume.traditional, marker: {{ color: "#0891b2" }} }},
    {{ type: "bar", name: "新媒体", x: chartData.searchVolume.x, y: chartData.searchVolume.newMedia, marker: {{ color: "#f59e0b" }} }}
  ], {{ ...commonLayout, barmode: "stack", yaxis: {{ title: "Estimated results" }} }}, {{ responsive: true }});
}}
if (chartData.gap.x.length) {{
  Plotly.newPlot("gapChart", [{{ type: "bar", x: chartData.gap.x, y: chartData.gap.y, marker: {{ color: chartData.gap.colors }} }}], {{ ...commonLayout, yaxis: {{ title: "Gap score" }} }}, {{ responsive: true }});
}}
if (chartData.media.x.length) {{
  Plotly.newPlot("mediaChart", [{{ type: "bar", x: chartData.media.x, y: chartData.media.y, marker: {{ color: "#059669" }} }}], {{ ...commonLayout, yaxis: {{ title: "Confidence" }} }}, {{ responsive: true }});
}}
if (chartData.topics.labels.length) {{
  Plotly.newPlot("topicChart", [{{ type: "pie", labels: chartData.topics.labels, values: chartData.topics.values, hole: 0.35 }}], {{ margin: {{ l: 20, r: 20, t: 20, b: 20 }} }}, {{ responsive: true }});
}}
if (chartData.topicMatrix.x.length) {{
  Plotly.newPlot("topicMatrixChart", [{{ type: "heatmap", x: chartData.topicMatrix.x, y: chartData.topicMatrix.y, z: chartData.topicMatrix.z, colorscale: "Blues" }}], {{ ...commonLayout }}, {{ responsive: true }});
}}
if (chartData.cost.x.length) {{
  Plotly.newPlot("costChart", [{{ type: "bar", x: chartData.cost.x, y: chartData.cost.y, marker: {{ color: "#d97706" }} }}], {{ ...commonLayout, yaxis: {{ title: "Estimated total cost" }} }}, {{ responsive: true }});
}}
</script>
</body>
</html>"""


def build_dashboard_html_report(analysis_data: dict[str, Any], labels: dict[str, str]) -> str:
    analysis_data = enrich_analysis_data(analysis_data)
    profile = analysis_data.get("product_profile") or {}
    question_discovery = analysis_data.get("question_discovery") or {}
    payload = _dashboard_payload(analysis_data)
    visibility_summary = analysis_data.get("geo_visibility_summary") or {}
    ranking = analysis_data.get("ai_recommendation_ranking") or analysis_data.get("brand_ranking") or []
    brand_visibility_metrics = analysis_data.get("brand_visibility_metrics") or []
    search_ranking = analysis_data.get("search_visibility_ranking") or []
    search_volume = analysis_data.get("search_volume_ranking") or []
    gap_ranking = analysis_data.get("competitive_gap_ranking") or []
    provider_status = analysis_data.get("multi_ai_provider_status") or _provider_status_from_results(analysis_data)
    source_articles = analysis_data.get("source_articles") or []
    topics = analysis_data.get("content_topic_analysis") or {}
    charts = _chart_payload(
        ranking,
        analysis_data.get("baidu_mentions") or [],
        (analysis_data.get("media_matches") or {}).get("matches") or [],
        topics,
        analysis_data.get("media_cost_analysis") or {},
        search_ranking,
        gap_ranking,
        search_volume,
    )
    question_table = _dashboard_question_groups_html(analysis_data)
    prompt_metrics_html = _dashboard_prompt_metrics_groups_html(analysis_data.get("prompt_runs") or [])
    competitor_table = _provider_recommendation_table(_provider_recommendation_rows(analysis_data.get("recommendation_items") or []))
    diagnostic_table = _prompt_run_table(analysis_data.get("brand_diagnostic_prompt_runs") or [])
    brand_profile_table = _dashboard_brand_profile_table(analysis_data)
    mention_mapping_table = _brand_mapping_table(brand_visibility_metrics[:20], "mention_count")
    sentiment_mapping_table = _brand_mapping_table(brand_visibility_metrics[:20], "sentiment_score")
    ranking_mapping_table = _brand_mapping_table(ranking[:20], "recommendation_count")
    comparison_table = _prompt_run_table(analysis_data.get("comparison_prompt_runs") or [])
    search_visibility_table = _search_visibility_table(search_ranking)
    gap_table = _gap_table(gap_ranking)
    platform_detail_table = _visibility_platform_table(search_volume)
    article_table = _source_article_table(source_articles)
    topic_table = _topic_table(topics.get("topics") or [])
    standard_geo_metrics = analysis_data.get("standard_geo_metrics") or {}
    source_intelligence = analysis_data.get("source_intelligence") or {}
    owned_asset_audit = analysis_data.get("owned_asset_audit") or {}
    content_monitoring = analysis_data.get("content_monitoring") or {}
    geo_actions = analysis_data.get("geo_actions") or {}
    geo_metrics_table = _dashboard_geo_metrics_table(standard_geo_metrics)
    source_intelligence_table = _dashboard_source_intelligence_table(source_intelligence)
    owned_asset_table = _dashboard_owned_asset_table(owned_asset_audit)
    content_monitoring_table = _dashboard_content_monitoring_table(content_monitoring)
    geo_actions_table = _dashboard_geo_actions_table(geo_actions)
    reports_todo_table = _dashboard_reports_todo_table()
    content_report = analysis_data.get("content_pattern_report") or ""
    content_report_block = (
        f'<details class="details"><summary>查看完整品牌调研与市场定位文字报告</summary><pre class="markdown">{html.escape(content_report)}</pre></details>'
        if content_report
        else '<p class="note">暂无品牌调研与市场定位文字报告。</p>'
    )
    neutral_summary = analysis_data.get("neutral_visibility_summary") or visibility_summary
    diagnostic_summary = analysis_data.get("brand_diagnostic_summary") or {}
    comparison_summary = analysis_data.get("comparison_summary") or {}
    visibility_score = neutral_summary.get("visibility_score", 0)
    avg_position = neutral_summary.get("avg_position")
    sentiment_score = diagnostic_summary.get("sentiment_score", neutral_summary.get("sentiment_score", 50))
    prompt_success = round(float(neutral_summary.get("prompt_success_rate") or 0) * 100, 1)
    provider_coverage = f"{neutral_summary.get('provider_coverage_count', 0)}/{neutral_summary.get('provider_total_count', 0)}"
    title = "GEO 可视化看板"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body {{ margin:0; background:#0e1117; color:#f8fafc; font-family: Arial, "Microsoft YaHei", sans-serif; }}
    main {{ max-width: 1480px; margin: 0 auto; padding: 26px 28px 60px; }}
    .hero {{ display:none; }}
    .hero h1 {{ margin:0 0 10px; font-size:30px; }}
    .meta {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(180px,1fr)); gap:10px; margin-top:18px; }}
    .metric {{ background:#0e1117; border:0; border-radius:8px; padding:10px 0; }}
    .metric span {{ color:#f8fafc; font-size:15px; font-weight:700; }}
    .metric strong {{ display:block; margin-top:8px; font-size:38px; line-height:1.08; color:#fff; font-weight:500; }}
    .kpi strong {{ font-size:30px; }}
    .toc {{ display:flex; flex-wrap:wrap; gap:10px; margin:18px 0; }}
    .toc a {{ color:#0f766e; background:white; border:1px solid #d9e2ec; border-radius:8px; padding:9px 12px; text-decoration:none; font-size:14px; }}
    .pe-shell {{ display:grid; grid-template-columns: 340px minmax(0,1fr); gap:28px; align-items:start; }}
    .pe-side {{ position:sticky; top:16px; background:#0e1117; border:0; border-radius:10px; padding:4px 0; }}
    .pe-side h2 {{ font-size:22px; margin:0 0 12px; }}
    .pe-side a {{ display:block; color:#f8fafc; text-decoration:none; padding:7px 8px 7px 28px; border-radius:6px; font-size:16px; line-height:1.28; font-weight:700; position:relative; }}
    .pe-side a::before {{ content:""; position:absolute; left:0; top:9px; width:17px; height:17px; border:1px solid #334155; border-radius:50%; }}
    .pe-side a:first-of-type::before {{ background:#ff4b4b; border-color:#ff4b4b; box-shadow:inset 0 0 0 5px #ff4b4b; }}
    .pe-side a:hover {{ background:#111827; color:#fff; }}
    .pe-content {{ min-width:0; }}
    section {{ background:#0e1117; border:0; border-radius:0; padding:0; margin:0 0 36px; }}
    h2 {{ margin:0 0 14px; font-size:30px; color:#fff; }}
    h3 {{ margin:22px 0 12px; font-size:22px; color:#fff; }}
    .grid2 {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(460px,1fr)); gap:14px; }}
    .chart {{ min-height:420px; }}
    .chart-with-table {{ display:grid; grid-template-columns: minmax(0, 3fr) minmax(280px, 2fr); gap:12px; align-items:start; }}
    .chart-inner {{ min-height:420px; }}
    .sentiment-map-wrap {{ margin-top:0; max-height:420px; overflow:auto; }}
    .mapping-scroll {{ height:400px; overflow-y:auto; overflow-x:hidden; border:1px solid #374151; border-radius:0; }}
    .mapping-scroll table {{ table-layout:fixed; }}
    .mapping-scroll th {{ position:sticky; top:0; z-index:1; }}
    .mapping-scroll th:nth-child(1), .mapping-scroll td:nth-child(1) {{ width:48px; text-align:right; }}
    .mapping-scroll th:nth-child(3), .mapping-scroll td:nth-child(3) {{ width:74px; text-align:right; }}
    .mapping-scroll td:nth-child(2) {{ white-space:normal; word-break:break-word; line-height:1.45; }}
    .wide {{ min-height:480px; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ border:1px solid #374151; padding:10px 12px; text-align:left; vertical-align:top; color:#f8fafc; }}
    th {{ background:#1f232b; }}
    .table-wrap {{ overflow:auto; border:1px solid #374151; border-radius:8px; margin-top:10px; }}
    .note {{ color:#8aa0bd; font-size:14px; line-height:1.7; }}
    .details {{ margin-top:12px; border:1px solid #374151; border-radius:8px; padding:12px 14px; }}
    .details summary {{ cursor:pointer; font-weight:700; color:#f8fafc; }}
    .markdown {{ white-space:pre-wrap; line-height:1.75; color:#f8fafc; background:#111827; border-radius:8px; padding:12px; overflow:auto; }}
    .prompt-group {{ margin:12px 0; border:1px solid #374151; border-radius:8px; padding:10px 12px; }}
    .prompt-group summary {{ cursor:pointer; font-weight:700; }}
    @media (max-width: 980px) {{ .pe-shell {{ grid-template-columns: 1fr; }} .pe-side {{ position:relative; top:auto; }} }}
  </style>
</head>
<body>
<main>
  <div class="hero">
    <h1>{html.escape(title)}</h1>
    <div>{html.escape(str(profile.get("brand_name") or profile.get("product_name") or ""))} · {html.escape(_display_category(profile))} · {html.escape(str(question_discovery.get("primary_region") or profile.get("primary_region") or ""))}</div>
    <div class="meta">
      <div class="metric"><span>产品/服务</span><strong>{html.escape(str(profile.get("product_name", "")))}</strong></div>
      <div class="metric"><span>品牌</span><strong>{html.escape(str(profile.get("brand_name", "")))}</strong></div>
      <div class="metric"><span>类目</span><strong>{html.escape(_display_category(profile))}</strong></div>
      <div class="metric"><span>目标市场</span><strong>{html.escape(str(question_discovery.get("target_market") or profile.get("target_market") or ""))}</strong></div>
    </div>
  </div>

  <div class="pe-shell">
  <aside class="pe-side">
    <h2>Prompt Edge</h2>
    <a href="#overview">01 Overview 总览</a>
    <a href="#brand">02 Brand 品牌初始化</a>
    <a href="#prompts">03 Prompts 问题设计</a>
    <a href="#models">04 Models 模型状态</a>
    <a href="#metrics">05 Metrics 指标体系</a>
    <a href="#competitors">06 Competitors 竞品排名</a>
    <a href="#step2">07 Voice 五平台声量</a>
    <a href="#sources">08 Sources 引用来源</a>
    <a href="#step3">09 Research 品牌调研</a>
    <a href="#assets">10 Assets 数字资产</a>
    <a href="#structured">11 Structured 官网信源</a>
    <a href="#monitoring">12 Monitoring 内容监控</a>
    <a href="#actions">13 Actions 优化建议</a>
    <a href="#reports">14 Reports 后续接口</a>
  </aside>
  <div class="pe-content">
  <section id="overview">
    <h2>GEO 可见度总览</h2>
    <p class="note">主 GEO 可见度只统计不含客户品牌名的中立推荐问题；品牌诊断和竞品直接对比单独展示，不参与主推荐排名。</p>
    <div class="meta">
      <div class="metric kpi"><span>中立推荐可见度</span><strong>{html.escape(str(visibility_score))}%</strong></div>
      <div class="metric kpi"><span>中立推荐提及</span><strong>{html.escape(str(neutral_summary.get("mention_count", 0)))}</strong></div>
      <div class="metric kpi"><span>平均推荐位置</span><strong>{html.escape("#" + str(avg_position) if avg_position else "未出现")}</strong></div>
      <div class="metric kpi"><span>品牌诊断情绪分</span><strong>{html.escape(str(sentiment_score))}/100</strong></div>
      <div class="metric kpi"><span>中立 Prompt 成功率</span><strong>{html.escape(str(prompt_success))}%</strong></div>
      <div class="metric kpi"><span>AI 平台覆盖</span><strong>{html.escape(provider_coverage)}</strong></div>
      <div class="metric kpi"><span>竞品对比提及</span><strong>{html.escape(str(comparison_summary.get("brand_mentioned_responses", 0)))}</strong></div>
    </div>
    <h3>AI 提及次数</h3>
    <div class="chart-with-table">
      <div id="mentionChart" class="chart-inner"></div>
      <div>
        <h3>品牌序号 Mapping</h3>
        {mention_mapping_table}
      </div>
    </div>
    <h3>AI 描述情绪分</h3>
    <div class="chart-with-table">
      <div id="sentimentChart" class="chart-inner"></div>
      <div>
        <h3>品牌序号 Mapping</h3>
        {sentiment_mapping_table}
      </div>
    </div>
    <div class="grid2">
      <div id="promptSuccessPie" class="chart"></div>
      <div id="providerMentionHeatmap" class="chart"></div>
    </div>
    <div class="grid2">
      <div id="actionPriorityPie" class="chart"></div>
      <div id="actionModuleBar" class="chart"></div>
    </div>
  </section>

  <section id="brand">
    <h2>Brand 品牌初始化</h2>
    <p class="note">展示本次分析识别到的品牌、类目、服务地区、目标市场和官网来源。</p>
    <div class="table-wrap">{brand_profile_table}</div>
  </section>

  <section id="prompts">
    <h2>Prompts 问题设计</h2>
    <p class="note">按中立推荐、品牌诊断、竞品对比和客户自定义分组展示，避免所有问题挤在一个长表里。</p>
    <div id="promptTypePie" class="chart"></div>
    {question_table}
  </section>

  <section id="models">
    <h2>Models 模型状态</h2>
    <div class="grid2">
      <div id="modelStatusPie" class="chart"></div>
      <div id="modelCountBar" class="chart"></div>
    </div>
    <details class="details"><summary>查看模型调用明细</summary><div class="table-wrap">{_provider_status_table(provider_status)}</div></details>
  </section>

  <section id="metrics">
    <h2>Metrics 指标体系</h2>
    <h3>GEO 指标定义</h3>
    <div class="table-wrap">{geo_metrics_table}</div>
    <h3>Prompt 级指标</h3>
    <div class="grid2">
      <div id="promptMetricPie" class="chart"></div>
      <div id="promptMentionBar" class="chart"></div>
    </div>
    {prompt_metrics_html}
  </section>

  <section id="competitors">
    <h2>Competitors 竞品排名</h2>
    <div class="chart-with-table">
      <div id="rankingChart" class="chart-inner"></div>
      <div>
        <h3>品牌序号 Mapping</h3>
        {ranking_mapping_table}
      </div>
    </div>
    <details class="details"><summary>查看竞品排名明细</summary><div class="table-wrap">{_ranking_table(ranking, labels)}</div></details>
    <h3>分 AI 平台推荐来源</h3>
    <div class="grid2">
      <div id="recommendationSourcePie" class="chart"></div>
      <div id="recommendationHeatmap" class="chart"></div>
    </div>
    <details class="details"><summary>查看 AI 平台推荐来源明细</summary><div class="table-wrap">{competitor_table}</div></details>
    <h3>品牌诊断（不参与主推荐排名）</h3>
    <div class="table-wrap">{diagnostic_table}</div>
    <h3>竞品直接对比（不参与主推荐排名）</h3>
    <div class="table-wrap">{comparison_table}</div>
  </section>

  <section id="sources">
    <h2>Sources 引用来源</h2>
    <h3>AI 推荐引用信源</h3>
    <div class="grid2">
      <div id="sourceTypePie" class="chart"></div>
      <div id="sourceCitationBar" class="chart"></div>
    </div>
    <div class="table-wrap">{source_intelligence_table}</div>
  </section>

  <section id="step2">
    <h2>第二步：五平台声量</h2>
    <div id="platformPie" class="chart wide"></div>
    <div id="platformBar" class="chart"></div>
    <div id="brandPlatformStack" class="chart wide"></div>
    <h3>分 AI 平台五平台声量估算</h3>
    <div id="providerPlatformStack" class="chart wide"></div>
    <div id="providerBrandCompare" class="chart wide"></div>
    <h3>品牌内容声量排名</h3>
    <p class="note">含义：基于 AI 对百度、搜狗、360 搜索、抖音、小红书五个平台内容数量的估算，用来判断品牌在传统搜索与新媒体里的可见度；不是单一百度提及数。</p>
    <div id="searchVisibilityChart" class="chart wide"></div>
    <div class="table-wrap">{search_visibility_table}</div>
    <h3>AI 推荐与内容声量差异</h3>
    <div id="gapChart" class="chart wide"></div>
    <div class="table-wrap">{gap_table}</div>
    <h3>五平台拆分明细</h3>
    <div class="table-wrap">{platform_detail_table}</div>
  </section>

  <section id="step3">
    <h2>第三步：品牌调研与市场定位分析</h2>
    <p class="note">下列图表基于 AI 推荐理由、可访问文章正文与链接抓取状态生成。抓取失败只代表本次自动抓取不可用，不代表品牌没有内容资产。</p>
    <div class="grid2">
      <div id="boundaryPie" class="chart"></div>
      <div id="motiveBar" class="chart"></div>
      <div id="heuristicBar" class="chart"></div>
      <div id="pricePie" class="chart"></div>
      <div id="personaBar" class="chart"></div>
      <div id="sellingPointBar" class="chart"></div>
    </div>
  </section>

  <section id="assets">
    <h2>Assets 数字资产</h2>
    <div id="assetScoreChart" class="chart wide"></div>
  </section>

  <section id="structured">
    <h2>Structured 官网信源</h2>
    <p class="note">检查官网是否具备 AI 可解析、可引用的品牌事实块：FAQ、价格、案例、资质、对比、联系方式、Schema。</p>
    <div id="articleStatusPie" class="chart"></div>
    <h3>官网结构化信源审计</h3>
    <div id="ownedAssetBar" class="chart"></div>
    <div class="table-wrap">{owned_asset_table}</div>
    <h3>文章抓取明细</h3>
    <div class="table-wrap">{article_table}</div>
  </section>

  <section id="monitoring">
    <h2>Monitoring 内容监控</h2>
    <p class="note">第一版为手动监控快照：舆情风险、内容缺口、竞品优势。自动定时监控后续再做。</p>
    <h3>内容监控与舆情监控</h3>
    <div class="grid2">
      <div id="riskTopicBar" class="chart"></div>
      <div id="competitorAdvantageBar" class="chart"></div>
    </div>
    <div class="table-wrap">{content_monitoring_table}</div>
  </section>

  <section id="topics">
    <h3>内容主题分布</h3>
    <div class="grid2">
      <div id="topicChart" class="chart"></div>
      <div id="topicMatrixChart" class="chart"></div>
    </div>
    <div class="table-wrap">{topic_table}</div>
    {content_report_block}
  </section>
  <section id="actions">
    <h2>Actions 优化建议</h2>
    <h3>Actions 优化待办清单</h3>
    <div class="table-wrap">{geo_actions_table}</div>
  </section>
  <section id="reports">
    <h2>Reports 后续接口</h2>
    <p class="note">这里展示已明确要后续接入、当前不应伪装成真实数据的能力。</p>
    <div class="table-wrap">{reports_todo_table}</div>
  </section>
  </div>
  </div>
</main>
<script>
const D = {_script_json(payload)};
const C = {_script_json(charts)};
const axisBase = {{ gridcolor:"#374151", zerolinecolor:"#4b5563", linecolor:"#4b5563", tickfont:{{color:"#f8fafc"}}, titlefont:{{color:"#f8fafc"}} }};
const layout = {{ margin: {{ l: 60, r: 24, t: 54, b: 110 }}, paper_bgcolor: "#0e1117", plot_bgcolor: "#0e1117", font:{{color:"#f8fafc"}}, legend:{{font:{{color:"#f8fafc"}}}} }};
const compact = {{ margin: {{ l: 30, r: 20, t: 54, b: 30 }}, paper_bgcolor: "#0e1117", plot_bgcolor: "#0e1117", font:{{color:"#f8fafc"}}, legend:{{font:{{color:"#f8fafc"}}}} }};
function plot(id, traces, extra={{}}) {{
  const el = document.getElementById(id);
  if (!el || !traces || !traces.length) return;
  const merged = {{...layout, ...extra, xaxis:{{...axisBase, ...(extra.xaxis || {{}})}}, yaxis:{{...axisBase, ...(extra.yaxis || {{}})}}}};
  Plotly.newPlot(id, traces, merged, {{responsive:true, displaylogo:false}});
}}
plot("rankingChart", [{{type:"bar", x:D.ranking.index, y:D.ranking.y, marker:{{color:D.ranking.colors}}, customdata:D.ranking.x, hovertemplate:"序号: %{{x}}<br>品牌: %{{customdata}}<br>AI推荐次数: %{{y}}<extra></extra>"}}], {{title:"综合 AI 推荐排名", yaxis:{{title:"AI推荐次数"}}, xaxis:{{title:"序号", dtick:1}}}});
plot("recommendationSourcePie", [{{type:"pie", labels:D.recommendationSource.labels, values:D.recommendationSource.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"AI 推荐来源占比"}});
plot("recommendationHeatmap", [{{type:"heatmap", x:D.recommendationHeatmap.x, y:D.recommendationHeatmap.y, z:D.recommendationHeatmap.z, colorscale:"YlGnBu"}}], {{title:"AI 推荐热度矩阵"}});
plot("mentionChart", [{{type:"bar", x:D.mentions.index, y:D.mentions.y, marker:{{color:D.mentions.colors}}, customdata:D.mentions.x, hovertemplate:"序号: %{{x}}<br>品牌: %{{customdata}}<br>AI提及次数: %{{y}}<extra></extra>"}}], {{title:"AI 提及次数", yaxis:{{title:"AI提及次数"}}, xaxis:{{title:"序号", dtick:1}}}});
plot("sentimentChart", [{{type:"bar", x:D.sentiment.x, y:D.sentiment.y, marker:{{color:D.sentiment.colors}}, customdata:D.sentiment.customdata, hovertemplate:"序号: %{{x}}<br>品牌: %{{customdata[0]}}<br>情绪分: %{{y}}<extra></extra>"}}], {{title:"AI 描述情绪分", yaxis:{{title:"情绪分", range:[0,100]}}, xaxis:{{title:"序号", dtick:1}}}});
plot("promptSuccessPie", [{{type:"pie", labels:D.promptSuccess.labels, values:D.promptSuccess.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"Prompt 触发表现"}});
plot("promptTypePie", [{{type:"pie", labels:D.promptTypes.labels, values:D.promptTypes.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"问题类型占比"}});
plot("promptMetricPie", [{{type:"pie", labels:D.promptMetricTypes.labels, values:D.promptMetricTypes.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"Prompt 回答类型占比"}});
plot("promptMentionBar", [{{type:"bar", x:D.promptMentionByType.labels, y:D.promptMentionByType.values, marker:{{color:"#2563eb"}}}}], {{title:"各问题类型提及客户次数", yaxis:{{title:"提及客户次数"}}, xaxis:{{title:"问题类型"}}}});
plot("modelStatusPie", [{{type:"pie", labels:D.modelStatus.labels, values:D.modelStatus.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"模型调用状态占比"}});
plot("modelCountBar", D.modelCounts.traces, {{title:"各模型返回数量", barmode:"group", yaxis:{{title:"数量"}}, xaxis:{{title:"AI平台"}}}});
plot("providerMentionHeatmap", [{{type:"heatmap", x:D.providerMentionHeatmap.x, y:D.providerMentionHeatmap.y, z:D.providerMentionHeatmap.z, colorscale:"Blues"}}], {{title:"AI 平台 x 品牌提及矩阵"}});
plot("platformPie", [{{type:"pie", labels:D.platformTotals.labels, values:D.platformTotals.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"五平台总占比"}});
plot("platformBar", [{{type:"bar", x:D.platformTotals.values, y:D.platformTotals.labels, orientation:"h", marker:{{color:"#0f766e"}}}}], {{title:"五平台内容数量对比", xaxis:{{title:"内容数量估算"}}, yaxis:{{title:"平台"}}}});
plot("brandPlatformStack", D.brandPlatform.traces, {{title:"各品牌五平台拆分", barmode:"stack", yaxis:{{title:"内容数量估算"}}, xaxis:{{title:"品牌"}}}});
plot("providerPlatformStack", D.providerPlatform.traces, {{title:"各 AI 平台对五平台声量的估算", barmode:"stack", yaxis:{{title:"内容数量估算"}}, xaxis:{{title:"AI平台"}}}});
plot("providerBrandCompare", D.providerBrand.traces, {{title:"各 AI 平台给出的品牌声量 Top 对比", barmode:"group", yaxis:{{title:"内容数量估算"}}, xaxis:{{title:"品牌"}}}});
plot("searchVisibilityChart", [{{type:"bar", x:C.searchVisibility.x, y:C.searchVisibility.y, marker:{{color:"#0f766e"}}}}], {{title:"品牌内容声量排名", yaxis:{{title:"五平台内容数量估算"}}, xaxis:{{title:"品牌"}}}});
plot("gapChart", [{{type:"bar", x:C.gap.x, y:C.gap.y, marker:{{color:C.gap.colors}}}}], {{title:"AI 推荐与内容声量差异", yaxis:{{title:"差异评分"}}, xaxis:{{title:"品牌"}}}});
plot("boundaryPie", [{{type:"pie", labels:D.boundary.labels, values:D.boundary.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"品类边界分布"}});
plot("motiveBar", [{{type:"bar", x:D.motives.labels, y:D.motives.values, marker:{{color:"#2563eb"}}}}], {{title:"消费心理动机", yaxis:{{title:"强度"}}}});
plot("heuristicBar", [{{type:"bar", x:D.heuristics.values, y:D.heuristics.labels, orientation:"h", marker:{{color:"#7c3aed"}}}}], {{title:"决策捷径/心理启发式", xaxis:{{title:"强度"}}}});
plot("pricePie", [{{type:"pie", labels:D.priceBands.labels, values:D.priceBands.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"价格带/客单价定位"}});
plot("personaBar", [{{type:"bar", x:D.personas.labels, y:D.personas.values, marker:{{color:"#f59e0b"}}}}], {{title:"用户画像：消费能力分布", yaxis:{{title:"品牌数"}}}});
plot("sellingPointBar", [{{type:"bar", x:D.sellingPoints.values, y:D.sellingPoints.labels, orientation:"h", marker:{{color:"#059669"}}}}], {{title:"各品牌卖点数量", xaxis:{{title:"卖点数量"}}}});
plot("assetScoreChart", D.assetScores.traces, {{title:"数字资产评分", barmode:"group", yaxis:{{title:"评分"}}, xaxis:{{title:"品牌"}}}});
plot("articleStatusPie", [{{type:"pie", labels:D.articleStatus.labels, values:D.articleStatus.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"文章链接抓取状态"}});
plot("topicChart", [{{type:"pie", labels:C.topics.labels, values:C.topics.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"内容主题分布"}});
plot("topicMatrixChart", [{{type:"heatmap", x:C.topicMatrix.x, y:C.topicMatrix.y, z:C.topicMatrix.z, colorscale:"Blues"}}], {{title:"品牌内容重点矩阵"}});
plot("actionPriorityPie", [{{type:"pie", labels:D.actionPriority.labels, values:D.actionPriority.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"Actions 优先级占比"}});
plot("actionModuleBar", [{{type:"bar", x:D.actionModules.values, y:D.actionModules.labels, orientation:"h", marker:{{color:"#475569"}}}}], {{title:"Actions 模块分布", xaxis:{{title:"任务数"}}}});
plot("sourceTypePie", [{{type:"pie", labels:D.sourceTypes.labels, values:D.sourceTypes.values, hole:0.35, textinfo:"label+percent+value"}}], {{...compact, title:"AI 引用信源类型"}});
plot("sourceCitationBar", [{{type:"bar", x:D.sourceCitations.values, y:D.sourceCitations.labels, orientation:"h", marker:{{color:"#0ea5e9"}}}}], {{title:"AI 引用域名次数 Top", xaxis:{{title:"引用次数"}}}});
plot("ownedAssetBar", [{{type:"bar", x:D.ownedAssets.values, y:D.ownedAssets.labels, orientation:"h", marker:{{color:D.ownedAssets.colors}}}}], {{title:"官网结构化信源资产检查", xaxis:{{title:"是否具备", range:[0,1]}}, yaxis:{{automargin:true}}}});
plot("riskTopicBar", [{{type:"bar", x:D.riskTopics.values, y:D.riskTopics.labels, orientation:"h", marker:{{color:"#dc2626"}}}}], {{title:"舆情风险问题", xaxis:{{title:"风险强度"}}}});
plot("competitorAdvantageBar", [{{type:"bar", x:D.competitorAdvantages.values, y:D.competitorAdvantages.labels, orientation:"h", marker:{{color:"#2563eb"}}}}], {{title:"竞品优势提及", xaxis:{{title:"AI提及次数"}}}});
</script>
</body>
</html>"""


def _chart_payload(
    ranking: list[dict[str, Any]],
    baidu: list[dict[str, Any]],
    media: list[dict[str, Any]],
    topics: dict[str, Any],
    cost: dict[str, Any],
    search_ranking: list[dict[str, Any]] | None = None,
    gap_ranking: list[dict[str, Any]] | None = None,
    search_volume: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ranking_top = ranking[:20]
    baidu_top = baidu[:20]
    media_top = media[:20]
    search_top = (search_ranking or [])[:20]
    volume_top = (search_volume or [])[:20]
    gap_top = (gap_ranking or [])[:20]
    topic_rows = (topics.get("topics") or [])[:12]
    matrix_rows = topics.get("brand_topic_matrix") or []
    matrix_brands = list(dict.fromkeys(str(item.get("brand", "")) for item in matrix_rows if item.get("brand")))[:12]
    matrix_topics = list(dict.fromkeys(str(item.get("topic", "")) for item in matrix_rows if item.get("topic")))[:12]
    matrix_lookup = {(item.get("brand"), item.get("topic")): item.get("count", 0) for item in matrix_rows}
    cost_rows = (cost.get("rows") or [])[:20]
    return {
        "ranking": {
            "x": [item.get("brand_name", "") for item in ranking_top],
            "y": [item.get("recommendation_count", 0) for item in ranking_top],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#64748b" for item in ranking_top],
        },
        "baidu": {
            "x": [item.get("brand_name", "") for item in baidu_top],
            "y": [item.get("mentioned_count", 0) for item in baidu_top],
        },
        "searchVisibility": {
            "x": [item.get("brand_name", "") for item in search_top],
            "y": [item.get("mentioned_count", 0) for item in search_top],
        },
        "searchVolume": {
            "x": [item.get("brand_name", "") for item in volume_top],
            "y": [item.get("estimated_result_count", 0) for item in volume_top],
            "traditional": [item.get("traditional_search_count", 0) for item in volume_top],
            "newMedia": [item.get("new_media_count", 0) for item in volume_top],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#0891b2" for item in volume_top],
        },
        "gap": {
            "x": [item.get("brand_name", "") for item in gap_top],
            "y": [item.get("gap_score", 0) for item in gap_top],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#7c3aed" for item in gap_top],
        },
        "media": {
            "x": [item.get("source_domain", "") or item.get("resource_title", "") for item in media_top],
            "y": [item.get("confidence", 0) for item in media_top],
        },
        "topics": {
            "labels": [item.get("topic", "") for item in topic_rows],
            "values": [item.get("count", 0) for item in topic_rows],
        },
        "topicMatrix": {
            "x": matrix_topics,
            "y": matrix_brands,
            "z": [[matrix_lookup.get((brand, topic), 0) for topic in matrix_topics] for brand in matrix_brands],
        },
        "cost": {
            "x": [item.get("resource_title", "") or item.get("source_domain", "") for item in cost_rows],
            "y": [item.get("estimated_total_cost", 0) for item in cost_rows],
        },
    }



def _brand_mapping_table(rows: list[dict[str, Any]], value_key: str) -> str:
    if not rows:
        return '<p class="note">暂无品牌序号 Mapping。</p>'
    body = []
    for index, item in enumerate(rows[:20], start=1):
        brand = html.escape(str(item.get("brand_name", "")))
        value = html.escape(str(item.get(value_key, "")))
        body.append(f"<tr><td>{index}</td><td>{brand}</td><td>{value}</td></tr>")
    return '<div class="mapping-scroll"><table><thead><tr><th>序号</th><th>品牌</th><th>指标值</th></tr></thead><tbody>' + ''.join(body) + '</tbody></table></div>'


def _sentiment_mapping_table(rows: list[dict[str, Any]]) -> str:
    return _brand_mapping_table(rows, "sentiment_score")


def _dashboard_geo_metrics_table(metrics: dict[str, Any]) -> str:
    rows = [
        ("Visibility", metrics.get("visibility") or {}),
        ("Sentiment", metrics.get("sentiment") or {}),
        ("Position", metrics.get("position") or {}),
        ("SOV", metrics.get("sov") or {}),
        ("Prompt 成功率", metrics.get("prompt_success") or {}),
    ]
    body = []
    for name, item in rows:
        value = item.get("value_label") or item.get("score") or item.get("avg_rank") or ""
        body.append(
            f"<tr><td>{html.escape(str(name))}</td><td>{html.escape(str(value))}</td><td>{html.escape(str(item.get('formula') or ''))}</td><td>{html.escape(str(item.get('business_meaning') or ''))}</td></tr>"
        )
    return "<table><thead><tr><th>指标</th><th>当前值</th><th>计算方式</th><th>业务含义</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _dashboard_brand_profile_table(data: dict[str, Any]) -> str:
    profile = data.get("product_profile") or {}
    sources = data.get("sources") or {}
    rows = [
        ("产品/服务名", profile.get("product_name", "")),
        ("品牌名", profile.get("brand_name", "")),
        ("别名", ", ".join(profile.get("brand_aliases") or [])),
        ("类目", _display_category(profile)),
        ("目标市场", profile.get("target_market", "")),
        ("服务地区", profile.get("primary_region", "")),
        ("业务类型", profile.get("business_type", "")),
        ("官网", sources.get("website_url") or profile.get("website_url", "")),
    ]
    body = "".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value or ''))}</td></tr>" for label, value in rows)
    return "<table><tbody>" + body + "</tbody></table>"


def _dashboard_reports_todo_table() -> str:
    rows = [
        ("真实用户搜索词热度/概率", "AI 生成/规则补齐", "百度指数、5118/爱站、搜索平台或第三方关键词 API"),
        ("国外 AI 模型", "未调用", "ChatGPT / Gemini / Grok provider"),
        ("五平台真实声量", "多 AI 估算", "百度、搜狗、360、抖音、小红书真实搜索/内容数据 API"),
        ("自动监控", "手动快照", "定时任务、重跑、趋势对比、提醒通知"),
    ]
    body = "".join(f"<tr><td>{html.escape(module)}</td><td>{html.escape(status)}</td><td>{html.escape(api)}</td></tr>" for module, status, api in rows)
    return "<table><thead><tr><th>模块</th><th>当前状态</th><th>后续接口</th></tr></thead><tbody>" + body + "</tbody></table>"


def _dashboard_source_intelligence_table(source_intelligence: dict[str, Any]) -> str:
    rows = source_intelligence.get("domain_summary") or []
    if not rows:
        return '<p class="note">暂无 AI 引用信源数据。</p>'
    body = []
    for item in rows[:15]:
        body.append(
            f"<tr><td>{html.escape(str(item.get('rank', '')))}</td><td>{html.escape(str(item.get('domain', '')))}</td><td>{html.escape(str(item.get('domain_type', '')))}</td><td>{html.escape(str(item.get('citation_count', 0)))}</td><td>{round(float(item.get('used_rate') or 0) * 100, 1)}%</td><td>{'是' if item.get('mentioned_user_brand') else '否'}</td><td>{html.escape(', '.join(item.get('brands_appear') or []))}</td><td>{html.escape(str(item.get('action') or ''))}</td></tr>"
        )
    return "<table><thead><tr><th>排名</th><th>域名</th><th>类型</th><th>引用次数</th><th>Used %</th><th>客户出现</th><th>出现品牌</th><th>建议动作</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _dashboard_owned_asset_table(audit: dict[str, Any]) -> str:
    rows = audit.get("asset_checks") or []
    if not rows:
        return '<p class="note">暂无官网结构化信源审计数据。</p>'
    summary = f"<p class=\"note\">官网 AI 可读性评分：{html.escape(str(audit.get('ai_readability_score', 0)))}/100；页面抓取成功：{html.escape(str(audit.get('crawl_success_count', 0)))}/{html.escape(str(audit.get('crawl_total_count', 0)))}</p>"
    body = []
    for item in rows:
        body.append(
            f"<tr><td>{html.escape(str(item.get('asset_name', '')))}</td><td>{'是' if item.get('present') else '否'}</td><td>{html.escape(str(item.get('recommendation') or ''))}</td></tr>"
        )
    return summary + "<table><thead><tr><th>资产项</th><th>是否具备</th><th>建议</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _dashboard_content_monitoring_table(monitoring: dict[str, Any]) -> str:
    opinion = monitoring.get("opinion_monitoring") or {}
    risks = opinion.get("risk_topics") or []
    advantages = opinion.get("competitor_advantages") or []
    if not risks and not advantages:
        return '<p class="note">暂无内容监控与舆情监控数据。</p>'
    risk_rows = "".join(
        f"<tr><td>{html.escape(str(item.get('severity', '')))}</td><td>{html.escape(str(item.get('provider', '')))}</td><td>{html.escape(str(item.get('sentiment_score', 50)))}</td><td>{html.escape(', '.join(item.get('risk_terms') or []))}</td><td>{html.escape(str(item.get('evidence') or ''))}</td></tr>"
        for item in risks[:10]
    )
    advantage_rows = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{html.escape(str(item.get('mention_count', 0)))}</td><td>{html.escape(str(item.get('sentiment_score', 50)))}</td><td>{html.escape('；'.join(item.get('advantage_evidence') or []))}</td></tr>"
        for item in advantages[:10]
    )
    return (
        "<h4>舆情风险</h4><table><thead><tr><th>严重度</th><th>AI平台</th><th>情绪分</th><th>风险词</th><th>证据</th></tr></thead><tbody>"
        + risk_rows
        + "</tbody></table><h4>竞品优势</h4><table><thead><tr><th>品牌</th><th>AI提及</th><th>情绪分</th><th>证据摘要</th></tr></thead><tbody>"
        + advantage_rows
        + "</tbody></table>"
    )


def _dashboard_geo_actions_table(plan: dict[str, Any]) -> str:
    rows = plan.get("actions") or []
    if not rows:
        return '<p class="note">暂无 Actions 待办数据。</p>'
    body = []
    for item in rows[:20]:
        body.append(
            f"<tr><td>{html.escape(str(item.get('rank', '')))}</td><td>{html.escape(str(item.get('priority', '')))}</td><td>{html.escape(str(item.get('module', '')))}</td><td>{html.escape(str(item.get('task', '')))}</td><td>{html.escape(str(item.get('reason', '')))}</td></tr>"
        )
    return "<table><thead><tr><th>排名</th><th>优先级</th><th>模块</th><th>任务</th><th>原因</th></tr></thead><tbody>" + "".join(body) + "</tbody></table>"


def _source_citation_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    top = sorted(rows, key=lambda item: int(item.get("citation_count") or 0), reverse=True)[:12]
    return {"labels": [str(item.get("domain") or "") for item in top], "values": [int(item.get("citation_count") or 0) for item in top]}


def _owned_asset_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    labels = [str(item.get("asset_name") or "") for item in rows]
    values = [1 if item.get("present") else 0 for item in rows]
    colors = ["#059669" if value else "#dc2626" for value in values]
    return {"labels": labels, "values": values, "colors": colors}


def _risk_topic_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    top = rows[:12]
    return {
        "labels": [str(item.get("prompt") or item.get("provider") or "风险项")[:36] for item in top],
        "values": [max(1, 100 - int(item.get("sentiment_score") or 50)) for item in top],
    }


def _competitor_advantage_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    top = sorted(rows, key=lambda item: int(item.get("mention_count") or 0), reverse=True)[:12]
    return {"labels": [str(item.get("brand_name") or "") for item in top], "values": [int(item.get("mention_count") or 0) for item in top]}


def _dashboard_payload(data: dict[str, Any]) -> dict[str, Any]:
    ranking = data.get("ai_recommendation_ranking") or data.get("brand_ranking") or []
    brand_metrics = data.get("brand_visibility_metrics") or []
    prompt_runs = data.get("prompt_runs") or []
    provider_matrix = data.get("provider_visibility_matrix") or []
    rec_rows = _recommendation_source_rows(data.get("recommendation_items") or [], ranking)
    rec_chart = _recommendation_chart_rows(rec_rows)
    platform_rows = _platform_breakdown_rows(data.get("search_volume_ranking") or [])
    provider_rows = _provider_visibility_rows(data)
    content = data.get("content_positioning_analysis") or _derive_content_positioning_analysis(data)
    articles = data.get("source_articles") or []
    provider_status = data.get("multi_ai_provider_status") or _provider_status_from_results(data)
    source_intelligence = data.get("source_intelligence") or {}
    owned_asset_audit = data.get("owned_asset_audit") or {}
    content_monitoring = data.get("content_monitoring") or {}
    geo_actions = data.get("geo_actions") or {}
    return {
        "providerStatusRows": provider_status,
        "actionPriority": _count_payload(geo_actions.get("actions") or [], "priority", "task"),
        "actionModules": _count_payload(geo_actions.get("actions") or [], "module", "task"),
        "sourceTypes": _sum_payload(source_intelligence.get("domain_type_distribution") or [], "domain_type", "count"),
        "sourceCitations": _source_citation_payload(source_intelligence.get("domain_summary") or []),
        "ownedAssets": _owned_asset_payload(owned_asset_audit.get("asset_checks") or []),
        "riskTopics": _risk_topic_payload((content_monitoring.get("opinion_monitoring") or {}).get("risk_topics") or []),
        "competitorAdvantages": _competitor_advantage_payload((content_monitoring.get("opinion_monitoring") or {}).get("competitor_advantages") or []),
        "ranking": {
            "index": list(range(1, len(ranking[:20]) + 1)),
            "x": [item.get("brand_name", "") for item in ranking[:20]],
            "y": [item.get("recommendation_count", 0) for item in ranking[:20]],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#64748b" for item in ranking[:20]],
        },
        "promptTypes": _prompt_type_count_payload(data),
        "promptMetricTypes": _prompt_metric_type_payload(prompt_runs, mentioned_only=False),
        "promptMentionByType": _prompt_metric_type_payload(prompt_runs, mentioned_only=True),
        "modelStatus": _model_status_payload(provider_status),
        "modelCounts": _model_count_payload(provider_status),
        "recommendationSource": _count_payload(rec_chart, "AI平台", "品牌"),
        "recommendationHeatmap": _heatmap_payload(rec_chart, row_key="品牌", col_key="AI平台", value_key="推荐热度", limit=20),
        "avgPosition": {
            "index": list(range(1, len(brand_metrics[:15]) + 1)),
            "x": [item.get("brand_name", "") for item in brand_metrics[:15]],
            "y": [item.get("avg_position") or 0 for item in brand_metrics[:15]],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#2563eb" for item in brand_metrics[:15]],
        },
        "mentions": {
            "index": list(range(1, len(brand_metrics[:20]) + 1)),
            "x": [item.get("brand_name", "") for item in brand_metrics[:20]],
            "y": [item.get("mention_count", 0) for item in brand_metrics[:20]],
            "colors": ["#0b70c9" if item.get("is_user_brand") else "#7cc4f8" for item in brand_metrics[:20]],
        },
        "sentiment": {
            "x": list(range(1, len(brand_metrics[:15]) + 1)),
            "y": [item.get("sentiment_score", 50) for item in brand_metrics[:15]],
            "colors": ["#dc2626" if item.get("is_user_brand") else "#f59e0b" for item in brand_metrics[:15]],
            "customdata": [[item.get("brand_name", ""), "Customer Brand" if item.get("is_user_brand") else "Competitor"] for item in brand_metrics[:15]],
        },
        "promptSuccess": _prompt_success_payload(prompt_runs),
        "providerMentionHeatmap": _heatmap_payload(
            [
                {
                    "品牌": item.get("brand_name", ""),
                    "AI平台": _provider_label(item.get("provider", "")),
                    "提及次数": item.get("mention_count", 0),
                }
                for item in provider_matrix
            ],
            row_key="品牌",
            col_key="AI平台",
            value_key="提及次数",
            limit=20,
        ),
        "platformTotals": _sum_payload(platform_rows, "平台", "内容数量估算"),
        "brandPlatform": _stacked_payload(platform_rows, x_key="品牌", stack_key="平台", value_key="内容数量估算", limit=10),
        "providerPlatform": _stacked_payload(provider_rows, x_key="AI平台", stack_key="平台", value_key="内容数量估算"),
        "providerBrand": _stacked_payload(provider_rows, x_key="品牌", stack_key="AI平台", value_key="内容数量估算", limit=10),
        "boundary": _count_payload(content.get("category_boundary") or [], "boundary_type", "brand_name"),
        "motives": _sum_payload(content.get("psychology_motives") or [], "motive", "score"),
        "heuristics": _sum_payload(content.get("decision_heuristics") or [], "heuristic", "score"),
        "priceBands": _count_payload(content.get("price_bands") or [], "price_band", "brand_name"),
        "personas": _count_payload(content.get("personas") or [], "spending_power", "brand_name"),
        "sellingPoints": _count_payload(content.get("selling_points") or [], "brand_name", "selling_point", limit=12),
        "assetScores": _asset_score_payload(content.get("digital_asset_scores") or []),
        "articleStatus": _article_status_payload(articles),
    }


def _recommendation_chart_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows[:30]:
        brand = item.get("brand_name", "")
        for provider, key in (("Qwen", "qwen_rank"), ("豆包", "doubao_rank"), ("元宝", "yuanbao_rank"), ("DeepSeek", "deepseek_rank")):
            rank = item.get(key)
            if rank in ("", None):
                continue
            rank_value = _safe_int(rank)
            if not rank_value:
                continue
            result.append({"品牌": brand, "AI平台": provider, "推荐名次": rank_value, "推荐热度": max(1, 11 - rank_value)})
    return result


def _platform_breakdown_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for item in rows[:20]:
        traditional, new_media = _platform_values(item)
        values = {
            "百度": traditional.get("baidu", 0),
            "搜狗": traditional.get("sogou", 0),
            "360搜索": traditional.get("so360", 0),
            "抖音": new_media.get("douyin", 0),
            "小红书": new_media.get("xiaohongshu", 0),
        }
        for platform, value in values.items():
            result.append({"品牌": item.get("brand_name", ""), "平台": platform, "内容数量估算": _safe_int(value)})
    return result


def _platform_values(item: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
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


def _provider_visibility_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for item in data.get("search_volume_ranking") or []:
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
            for platform, value in values.items():
                result.append({"AI平台": provider, "品牌": item.get("brand_name", ""), "平台": platform, "内容数量估算": _safe_int(value)})
    return result


def _count_payload(rows: list[dict[str, Any]], label_key: str, value_key: str, limit: int | None = None) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for item in rows:
        label = str(item.get(label_key) or "未知")
        if value_key:
            counts[label] += 1 if item.get(value_key) is not None else 0
        else:
            counts[label] += 1
    items = counts.most_common(limit)
    return {"labels": [item[0] for item in items], "values": [item[1] for item in items]}


def _sum_payload(rows: list[dict[str, Any]], label_key: str, value_key: str) -> dict[str, Any]:
    totals: defaultdict[str, int] = defaultdict(int)
    for item in rows:
        totals[str(item.get(label_key) or "未知")] += _safe_int(item.get(value_key))
    items = sorted(totals.items(), key=lambda pair: pair[1], reverse=True)
    return {"labels": [item[0] for item in items], "values": [item[1] for item in items]}


def _prompt_success_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"labels": [], "values": []}
    success = len([item for item in rows if item.get("brand_mentioned")])
    failed = len(rows) - success
    return {"labels": ["客户品牌被推荐", "客户品牌未出现"], "values": [success, failed]}


def _prompt_type_count_payload(data: dict[str, Any]) -> dict[str, Any]:
    question_discovery = data.get("question_discovery") or {}
    strategy = data.get("analysis_strategy") or {}
    prompt_groups = question_discovery.get("prompt_groups") or strategy.get("prompt_groups") or {}
    counts: Counter[str] = Counter()
    if isinstance(prompt_groups, dict) and prompt_groups:
        for group, items in prompt_groups.items():
            counts[_prompt_type_label(group)] += len(items or [])
    else:
        questions = question_discovery.get("questions") or (data.get("trend_discovery") or {}).get("probe_questions") or []
        if questions:
            counts["中立推荐"] += len(questions)
    items = counts.most_common()
    return {"labels": [item[0] for item in items], "values": [item[1] for item in items]}


def _prompt_metric_type_payload(rows: list[dict[str, Any]], mentioned_only: bool = False) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for item in rows:
        if mentioned_only and not item.get("brand_mentioned"):
            continue
        counts[_prompt_type_label(item.get("prompt_type")) or "未分类"] += 1
    items = counts.most_common()
    return {"labels": [item[0] for item in items], "values": [item[1] for item in items]}


def _model_status_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    for item in rows:
        counts["推荐排名 OK" if item.get("recommendation_ok") else "推荐排名 FAIL"] += 1
        counts["声量估算 OK" if item.get("visibility_ok") else "声量估算 FAIL"] += 1
    items = counts.most_common()
    return {"labels": [item[0] for item in items], "values": [item[1] for item in items]}


def _model_count_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    providers = [_provider_label(item.get("provider", "")) for item in rows]
    return {
        "traces": [
            {"type": "bar", "name": "推荐条数", "x": providers, "y": [_safe_int(item.get("recommendation_count")) for item in rows]},
            {"type": "bar", "name": "声量品牌数", "x": providers, "y": [_safe_int(item.get("visibility_count")) for item in rows]},
        ]
    }


def _stacked_payload(rows: list[dict[str, Any]], x_key: str, stack_key: str, value_key: str, limit: int | None = None) -> dict[str, Any]:
    totals: defaultdict[str, int] = defaultdict(int)
    for item in rows:
        totals[str(item.get(x_key) or "")] += _safe_int(item.get(value_key))
    xs = [key for key, _ in sorted(totals.items(), key=lambda pair: pair[1], reverse=True) if key]
    if limit:
        xs = xs[:limit]
    stacks = list(dict.fromkeys(str(item.get(stack_key) or "") for item in rows if item.get(stack_key)))
    traces = []
    for stack in stacks:
        traces.append(
            {
                "type": "bar",
                "name": stack,
                "x": xs,
                "y": [
                    sum(_safe_int(item.get(value_key)) for item in rows if str(item.get(x_key) or "") == x and str(item.get(stack_key) or "") == stack)
                    for x in xs
                ],
            }
        )
    return {"x": xs, "traces": traces}


def _heatmap_payload(rows: list[dict[str, Any]], row_key: str, col_key: str, value_key: str, limit: int | None = None) -> dict[str, Any]:
    row_totals: defaultdict[str, int] = defaultdict(int)
    for item in rows:
        row_totals[str(item.get(row_key) or "")] += _safe_int(item.get(value_key))
    y = [key for key, _ in sorted(row_totals.items(), key=lambda pair: pair[1], reverse=True) if key]
    if limit:
        y = y[:limit]
    x = list(dict.fromkeys(str(item.get(col_key) or "") for item in rows if item.get(col_key)))
    lookup = {(str(item.get(row_key) or ""), str(item.get(col_key) or "")): _safe_int(item.get(value_key)) for item in rows}
    return {"x": x, "y": y, "z": [[lookup.get((row, col), 0) for col in x] for row in y]}


def _asset_score_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    brands = [str(item.get("brand_name") or "") for item in rows[:12]]
    specs = [
        ("搜索资产", "search_asset_score"),
        ("内容平台资产", "content_platform_score"),
        ("官网可访问性", "website_access_score"),
        ("信任证明资产", "proof_asset_score"),
    ]
    traces = []
    for label, key in specs:
        traces.append({"type": "bar", "name": label, "x": brands, "y": [_safe_int(item.get(key)) for item in rows[:12]]})
    return {"traces": traces}


def _article_status_payload(rows: list[dict[str, Any]]) -> dict[str, Any]:
    success = len([item for item in rows if item.get("text_excerpt") and not item.get("error")])
    failed = len([item for item in rows if item.get("error") or not item.get("text_excerpt")])
    return {"labels": ["成功", "失败"], "values": [success, failed]}


def _derive_content_positioning_analysis(data: dict[str, Any]) -> dict[str, Any]:
    ranking = data.get("ai_recommendation_ranking") or []
    items = data.get("recommendation_items") or []
    by_brand: dict[str, list[dict[str, Any]]] = {}
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if brand:
            by_brand.setdefault(brand, []).append(item)
    analysis = {"category_boundary": [], "price_bands": [], "psychology_motives": [], "decision_heuristics": [], "personas": [], "selling_points": [], "digital_asset_scores": []}
    for brand in ranking[:12]:
        name = str(brand.get("brand_name") or "")
        text = " ".join(str(item.get("reason") or "") for item in by_brand.get(name, []))
        analysis["category_boundary"].append({"brand_name": name, "boundary_type": _infer_boundary_type(text), "positioning": text[:80], "evidence": text[:120]})
        analysis["price_bands"].append({"brand_name": name, "price_band": _infer_price_band(text), "evidence": text[:120]})
        for motive, score in _infer_motive_scores(text).items():
            analysis["psychology_motives"].append({"brand_name": name, "motive": motive, "score": score})
        for heuristic, score in _infer_heuristic_scores(text).items():
            analysis["decision_heuristics"].append({"brand_name": name, "heuristic": heuristic, "score": score})
        analysis["personas"].append({"brand_name": name, "spending_power": _infer_price_band(text)})
        points = _selling_points_from_text(text)
        for point in points:
            analysis["selling_points"].append({"brand_name": name, "selling_point": point})
        analysis["digital_asset_scores"].append({"brand_name": name, "search_asset_score": min(100, int(brand.get("recommendation_count") or 0) * 25), "content_platform_score": min(100, len(by_brand.get(name, [])) * 20), "website_access_score": 30, "proof_asset_score": min(100, len(points) * 20)})
    return analysis


def _provider_label(value: Any) -> str:
    return {"qwen": "Qwen", "doubao": "豆包", "yuanbao": "元宝", "deepseek": "DeepSeek"}.get(str(value or "").lower(), str(value or ""))


def _infer_boundary_type(text: str) -> str:
    if any(word in text for word in ("医院", "医美", "整形", "医生", "科室", "服务")):
        return "卖服务"
    if any(word in text for word in ("场景", "体验", "空间", "生活方式")):
        return "卖场景"
    if any(word in text for word in ("解决方案", "一站式", "综合")):
        return "卖解决方案"
    return "混合/依据不足"


def _infer_price_band(text: str) -> str:
    if any(word in text for word in ("高端", "轻奢", "定制")):
        return "高"
    if any(word in text for word in ("合理", "性价比", "亲民")):
        return "中低"
    if any(word in text for word in ("连锁", "大型", "主流")):
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
    if any(word in text for word in ("排名", "前十", "知名", "主流", "老牌")):
        result["从众效应"] = 2
    if any(word in text for word in ("三甲", "资质", "专家", "博士", "医生", "权威")):
        result["权威背书"] = 3
    if any(word in text for word in ("案例", "对比", "口碑", "评价")):
        result["社会认同"] = 2
    return result or {"依据不足": 1}


def _selling_points_from_text(text: str) -> list[str]:
    parts = []
    for token in re.split(r"[，,。；;\n、]", str(text or "")):
        token = token.strip()
        if 4 <= len(token) <= 40:
            parts.append(token)
    return list(dict.fromkeys(parts))[:5] or ["资质背书", "服务项目覆盖", "医生/技术能力", "案例或口碑", "本地可达性"]


def _script_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def _media_warning(media: dict[str, Any]) -> str:
    warning = media.get("warning")
    if not warning:
        return ""
    return f'<p style="color:#b45309;background:#fffbeb;border:1px solid #fde68a;padding:10px;border-radius:8px;">{html.escape(str(warning))}</p>'


def _provider_status_from_results(data: dict[str, Any]) -> list[dict[str, Any]]:
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
    return rows


def _ok_text(value: Any) -> str:
    return "OK" if bool(value) else "FAIL"


def _provider_status_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('provider', '')))}</td><td>{_ok_text(item.get('recommendation_ok'))}</td><td>{item.get('recommendation_count', 0)}</td><td>{_ok_text(item.get('visibility_ok'))}</td><td>{item.get('visibility_count', 0)}</td><td>{html.escape(str(item.get('model', '')))}</td><td>{html.escape(str(item.get('timeout', '')))}</td><td>{html.escape(str(item.get('recommendation_error') or item.get('visibility_error') or ''))}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>AI平台</th><th>推荐排名</th><th>推荐条数</th><th>声量估算</th><th>声量品牌数</th><th>模型</th><th>超时秒数</th><th>错误信息</th></tr></thead><tbody>" + body + "</tbody></table>"


def _prompt_type_label(value: Any) -> str:
    return {
        "neutral_recommendation": "中立推荐",
        "mainstream_recommendation": "中立推荐",
        "brand_diagnostic": "品牌诊断",
        "brand_reputation": "品牌诊断",
        "comparison": "竞品对比",
        "direct_competitor_comparison": "竞品对比",
        "custom": "客户自定义",
    }.get(str(value or ""), str(value or ""))


def _dashboard_question_groups_html(data: dict[str, Any]) -> str:
    question_discovery = data.get("question_discovery") or {}
    strategy = data.get("analysis_strategy") or {}
    prompt_groups = question_discovery.get("prompt_groups") or strategy.get("prompt_groups") or {}
    rows: list[dict[str, str]] = []
    if isinstance(prompt_groups, dict) and prompt_groups:
        for group, items in prompt_groups.items():
            for item in items or []:
                rows.append(
                    {
                        "type": _prompt_type_label(group),
                        "question": str(item.get("question") or item.get("query") or ""),
                        "intent": str(item.get("intent") or ""),
                        "reason": str(item.get("reason") or ""),
                    }
                )
    else:
        for item in question_discovery.get("questions") or (data.get("trend_discovery") or {}).get("probe_questions") or []:
            if isinstance(item, dict):
                rows.append({"type": "中立推荐", "question": str(item.get("question") or item.get("term") or ""), "intent": str(item.get("intent") or ""), "reason": str(item.get("reason") or "")})
            else:
                rows.append({"type": "中立推荐", "question": str(item), "intent": "", "reason": ""})
    if not rows:
        return "<p class='note'>暂无 Prompt 设计数据。</p>"
    parts = []
    for group in ["中立推荐", "品牌诊断", "竞品对比", "客户自定义"]:
        group_rows = [row for row in rows if row["type"] == group]
        if not group_rows:
            continue
        body = "".join(
            f"<tr><td>{html.escape(row['question'])}</td><td>{html.escape(row['intent'])}</td><td>{html.escape(row['reason'][:260])}</td></tr>"
            for row in group_rows
        )
        parts.append(f"<details class='prompt-group' {'open' if group == '中立推荐' else ''}><summary>{group}（{len(group_rows)} 个问题）</summary><div class='table-wrap'><table><thead><tr><th>问题</th><th>意图</th><th>说明</th></tr></thead><tbody>{body}</tbody></table></div></details>")
    return "".join(parts)


def _dashboard_prompt_metrics_groups_html(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='note'>暂无 Prompt 级指标。</p>"
    parts = []
    for group in ["中立推荐", "品牌诊断", "竞品对比", "客户自定义"]:
        group_rows = [item for item in rows if _prompt_type_label(item.get("prompt_type")) == group]
        if not group_rows:
            continue
        body = "".join(
            f"<tr><td>{html.escape(str(item.get('prompt', '')))}</td><td>{html.escape(_provider_label(item.get('provider', '')))}</td><td>{'是' if item.get('brand_mentioned') else '否'}</td><td>{html.escape(str(item.get('brand_position') or '未出现'))}</td><td>{html.escape(str(item.get('sentiment_score', 50)))}</td><td>{len(item.get('co_occurring_brands') or [])}</td><td>{len(item.get('citation_urls') or [])}</td></tr>"
            for item in group_rows
        )
        parts.append(f"<details class='prompt-group' {'open' if group == '中立推荐' else ''}><summary>{group} Prompt 指标（{len(group_rows)} 条回答）</summary><div class='table-wrap'><table><thead><tr><th>Prompt</th><th>AI平台</th><th>是否提及客户</th><th>Position</th><th>Sentiment</th><th>Mentions</th><th>引用链接数</th></tr></thead><tbody>{body}</tbody></table></div></details>")
    return "".join(parts)


def _prompt_run_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "<p class='note'>暂无数据。</p>"
    body = "".join(
        f"<tr><td>{html.escape(_provider_label(item.get('provider', '')))}</td><td>{html.escape(_prompt_type_label(item.get('prompt_type', '')))}</td><td>{html.escape(str(item.get('prompt', '')))}</td><td>{'是' if item.get('brand_mentioned') else '否'}</td><td>{html.escape(str(item.get('brand_position') or '未出现'))}</td><td>{html.escape(str(item.get('sentiment_score', 50)))}</td><td>{html.escape('、'.join(str(value) for value in (item.get('co_occurring_brands') or [])[:6]))}</td><td>{'OK' if item.get('ok') else 'FAIL'}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>AI平台</th><th>问题类型</th><th>测试问题</th><th>客户品牌出现</th><th>位置</th><th>情绪分</th><th>共现竞品</th><th>状态</th></tr></thead><tbody>" + body + "</tbody></table>"


def _dashboard_question_table(data: dict[str, Any]) -> str:
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
                        "module": group_labels.get(group_key, group_key),
                        "subject": item.get("intent") or "",
                        "query": item.get("question") or "",
                        "purpose": "主排名" if group_key == "neutral_recommendation" else "诊断展示，不参与主排名",
                        "note": item.get("reason") or "",
                    }
                )
    else:
        for item in questions:
            rows.append(
                {
                    "module": "中立推荐排名",
                    "subject": item.get("term") or item.get("question") or "",
                    "query": item.get("question") or item.get("term") or "",
                    "purpose": item.get("intent") or item.get("question_type") or "AI 推荐排名",
                    "note": item.get("reason") or "",
                }
            )
    for query in neutral_queries:
        rows.append(
            {
                "module": "中立推荐问题",
                "subject": query,
                "query": query,
                "purpose": "AI 推荐排名",
                "note": "不包含客户品牌名，用于统计主流竞争排名。",
            }
        )
    for query in diagnostic_queries:
        rows.append(
            {
                "module": "品牌诊断问题",
                "subject": query,
                "query": query,
                "purpose": "品牌口碑/情绪分析",
                "note": "允许包含客户品牌名，不参与主推荐排名。",
            }
        )
    for query in comparison_queries:
        rows.append(
            {
                "module": "竞品直接对比问题",
                "subject": query,
                "query": query,
                "purpose": "客户品牌 vs 头部竞品表现",
                "note": "基于中立推荐排名选取竞品，不参与主推荐排名。",
            }
        )
    for item in visibility_queries[:12]:
        rows.append(
            {
                "module": "品牌声量查询词",
                "subject": item.get("brand_name", ""),
                "query": item.get("query", ""),
                "purpose": item.get("metric_goal", "五平台内容数量估算"),
                "note": "",
            }
        )
    if not rows:
        return "<p class='note'>暂无 AI 搜索问题设计数据。</p>"
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('module', '')))}</td><td>{html.escape(str(item.get('subject', '')))}</td><td>{html.escape(str(item.get('query', '')))}</td><td>{html.escape(str(item.get('purpose', '')))}</td><td>{html.escape(str(item.get('note', ''))[:220])}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>模块</th><th>输入/探测主题</th><th>实际问题/查询词</th><th>用途</th><th>说明</th></tr></thead><tbody>" + body + "</tbody></table>"


def _provider_recommendation_rows(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    provider_order = {"qwen": 1, "doubao": 2, "yuanbao": 3, "deepseek": 4}
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        provider = str(item.get("engine") or "").strip().lower()
        if not brand or not provider:
            continue
        rows.append(
            {
                "provider": _provider_label(provider),
                "provider_key": provider,
                "rank": _display_rank(item.get("rank")),
                "brand_name": brand,
                "question": item.get("question") or item.get("trend_term") or "",
                "source_url_count": len(item.get("citation_urls") or []),
                "reason": str(item.get("reason") or "")[:260],
            }
        )
    return sorted(rows, key=lambda item: (provider_order.get(str(item.get("provider_key")), 99), _safe_int(item.get("rank")), str(item.get("brand_name"))))


def _display_rank(value: Any) -> str:
    if value in (None, "", "None"):
        return "未获取"
    try:
        number = float(str(value).strip())
        if number <= 0:
            return "未获取"
        return str(int(number)) if number.is_integer() else f"{number:.1f}"
    except Exception:
        return str(value)


def _has_visibility_data(item: dict[str, Any]) -> bool:
    return item.get("search_visibility_rank") not in (None, "", "None") or _safe_int(item.get("mentioned_count")) > 0 or _safe_int(item.get("result_count")) > 0


def _display_count(value: Any, has_data: bool | None = None) -> str:
    if value in (None, "", "None"):
        return "未获取"
    number = _safe_int(value)
    if has_data is False and number == 0:
        return "未获取"
    return str(number)


def _recommendation_source_rows(items: list[dict[str, Any]], ranking: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_brand: dict[str, dict[str, Any]] = {}
    rank_lookup = {str(item.get("brand_key") or _brand_key(item.get("brand_name", ""))): item for item in ranking}
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if not brand:
            continue
        key = _brand_key(brand)
        row = by_brand.setdefault(
            key,
            {
                "brand_name": brand,
                "ai_recommendation_rank": (rank_lookup.get(key) or {}).get("ai_recommendation_rank", ""),
                "source_urls": [],
                "reasons": [],
            },
        )
        provider = str(item.get("engine") or "").lower()
        if provider:
            current = row.get(f"{provider}_rank")
            rank = item.get("rank", "")
            row[f"{provider}_rank"] = min([value for value in [current, rank] if isinstance(value, int)], default=rank) if current else rank
        row["source_urls"].extend(item.get("citation_urls") or [])
        if item.get("reason"):
            row["reasons"].append(str(item.get("reason")))
    rows = []
    for row in by_brand.values():
        row["source_url_count"] = len(list(dict.fromkeys(row.get("source_urls") or [])))
        row["reason"] = (row.get("reasons") or [""])[0]
        rows.append(row)
    return sorted(rows, key=lambda item: (int(item.get("ai_recommendation_rank") or 999), str(item.get("brand_name", ""))))[:30]


def _recommendation_source_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{item.get('ai_recommendation_rank', '')}</td><td>{item.get('qwen_rank', '')}</td><td>{item.get('doubao_rank', '')}</td><td>{item.get('yuanbao_rank', '')}</td><td>{item.get('deepseek_rank', '')}</td><td>{item.get('source_url_count', 0)}</td><td>{html.escape(str(item.get('reason', ''))[:220])}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>品牌</th><th>综合排名</th><th>Qwen</th><th>豆包</th><th>元宝</th><th>DeepSeek</th><th>来源链接数</th><th>主要推荐理由</th></tr></thead><tbody>" + body + "</tbody></table>"


def _provider_recommendation_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('provider', '')))}</td><td>{html.escape(str(item.get('rank', '')))}</td><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{html.escape(str(item.get('question', '')))}</td><td>{item.get('source_url_count', 0)}</td><td>{html.escape(str(item.get('reason', ''))[:220])}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>AI平台</th><th>平台推荐排名</th><th>品牌</th><th>搜索问题</th><th>引用链接数</th><th>推荐理由</th></tr></thead><tbody>" + body + "</tbody></table>"


def _source_note(item: dict[str, Any]) -> str:
    urls = item.get("source_urls") or []
    notes = item.get("notes") or []
    if urls:
        return "链接：" + "；".join(str(url) for url in urls[:3])
    if notes:
        return "；".join(str(note) for note in notes[:2])
    return item.get("warning", "")


def _visibility_platform_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{item.get('estimated_result_count', 0)}</td><td>{(item.get('traditional_search') or {}).get('baidu', 0)}</td><td>{(item.get('traditional_search') or {}).get('sogou', 0)}</td><td>{(item.get('traditional_search') or {}).get('so360', 0)}</td><td>{(item.get('new_media') or {}).get('douyin', 0)}</td><td>{(item.get('new_media') or {}).get('xiaohongshu', 0)}</td><td>{item.get('provider_count', 0)}</td><td>{html.escape(_source_note(item)[:260])}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>品牌</th><th>总声量估算</th><th>百度</th><th>搜狗</th><th>360</th><th>抖音</th><th>小红书</th><th>参与AI数</th><th>消息来源/依据</th></tr></thead><tbody>" + body + "</tbody></table>"


def _source_article_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('label', '')))}</td><td>{html.escape(str(item.get('domain', '')))}</td><td>{html.escape(str(item.get('engine', '')))}</td><td>{'成功' if item.get('text_excerpt') and not item.get('error') else '失败'}</td><td>{len(item.get('text_excerpt') or '')}</td><td>{html.escape(str((item.get('url') if item.get('text_excerpt') and not item.get('error') else item.get('error') or item.get('url') or ''))[:320])}</td></tr>"
        for item in rows[:40]
    )
    return "<table><thead><tr><th>品牌/来源</th><th>域名</th><th>AI来源</th><th>抓取状态</th><th>正文长度</th><th>链接/错误</th></tr></thead><tbody>" + body + "</tbody></table>"


def _probe_question_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('term', '')))}</td><td>{html.escape(str(item.get('question', '')))}</td><td>{html.escape(str(item.get('intent', '')))}</td><td>{html.escape(str(item.get('reason', '')))}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>探测主题</th><th>建议问题</th><th>用户意图</th><th>原因</th></tr></thead><tbody>{body}</tbody></table>"


def _neutral_query_table(rows: list[str]) -> str:
    body = "".join(f"<tr><td>{html.escape(str(item))}</td></tr>" for item in rows)
    return "<table><thead><tr><th>查询词</th></tr></thead><tbody>" + body + "</tbody></table>"


def _visibility_query_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{html.escape(str(item.get('query', '')))}</td><td>{html.escape(str(item.get('metric_goal', '')))}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>品牌</th><th>查询词</th><th>指标目标</th></tr></thead><tbody>" + body + "</tbody></table>"


def _search_volume_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{item.get('search_volume_rank', '')}</td><td>{item.get('estimated_result_count', 0)}</td><td>{item.get('gap_vs_user', 0)}</td><td>{html.escape(str(item.get('query', '')))}</td><td>{html.escape(str(item.get('metric_type', '')))}</td><td>{html.escape(str(item.get('warning', '')))}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>品牌</th><th>排名</th><th>估算结果数</th><th>与客户差距</th><th>查询词</th><th>指标口径</th><th>说明</th></tr></thead><tbody>" + body + "</tbody></table>"


def _strategy_table(strategy: dict[str, Any]) -> str:
    if not strategy:
        return "<p>暂无策略数据。</p>"
    rows = [
        ("GEO target audience", strategy.get("geo_audience") or strategy.get("analysis_goal", "")),
        ("Probe subject", strategy.get("geo_probe_subject", "")),
        ("Service scope", strategy.get("service_scope", "")),
        ("Service region", strategy.get("service_region", "")),
        ("Topic taxonomy", ", ".join(str(item) for item in strategy.get("topic_taxonomy") or [])),
    ]
    body = "".join(f"<tr><th>{html.escape(label)}</th><td>{html.escape(str(value))}</td></tr>" for label, value in rows)
    return "<table><tbody>" + body + "</tbody></table>"


def _display_category(profile: dict[str, Any]) -> str:
    market_language = str(profile.get("market_language") or "").lower()
    if market_language.startswith("zh"):
        return str(profile.get("category_local") or profile.get("category_en") or "")
    return str(profile.get("category_en") or profile.get("category_local") or "")


def _competitor_rows(competitor_discovery: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    group_labels = {
        "direct_competitors": "直接竞品",
        "local_competitors": "本地竞品",
        "national_competitors": "全国竞品",
        "adjacent_competitors": "相邻竞品",
    }
    for key, label in group_labels.items():
        for item in competitor_discovery.get(key) or []:
            if isinstance(item, str):
                rows.append({"brand_name": item, "competitor_group": label, "region": "", "reason": ""})
            elif isinstance(item, dict) and item.get("brand_name"):
                rows.append(
                    {
                        "brand_name": item.get("brand_name", ""),
                        "competitor_group": item.get("competitor_type") or label,
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


def _competitor_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{html.escape(str(item.get('competitor_group', '')))}</td><td>{html.escape(str(item.get('region', '')))}</td><td>{html.escape(str(item.get('reason', '')))}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>品牌</th><th>类型</th><th>地区</th><th>原因</th></tr></thead><tbody>{body}</tbody></table>"


def _topic_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('topic', '')))}</td><td>{item.get('count', 0)}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>内容主题</th><th>出现次数</th></tr></thead><tbody>{body}</tbody></table>"


def _cost_summary(cost: dict[str, Any]) -> str:
    return (
        '<div class="grid">'
        f'<div class="metric">对标竞品<strong>{html.escape(str(cost.get("benchmark_brand", "")))}</strong></div>'
        f'<div class="metric">对标提及篇数<strong>{cost.get("benchmark_mentioned_count", 0)}</strong></div>'
        f'<div class="metric">客户当前声量<strong>{cost.get("user_brand_count", 0)}</strong></div>'
        f'<div class="metric">内容资产差距<strong>{cost.get("content_asset_gap", 0)}</strong></div>'
        f'<div class="metric">建议发布篇数<strong>{cost.get("target_articles", 0)}</strong></div>'
        f'<div class="metric">平均单篇成本<strong>{cost.get("avg_unit_price", 0)} {html.escape(str(cost.get("currency", "CNY")))}</strong></div>'
        "</div>"
    )


def _cost_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('source_domain', '')))}</td><td>{html.escape(str(item.get('resource_title', '')))}</td><td>{item.get('price_1', 0)}</td><td>{item.get('price_2', 0)}</td><td>{item.get('price_3', 0)}</td><td>{item.get('target_articles', 0)}</td><td>{item.get('estimated_total_cost', 0)}</td></tr>"
        for item in rows
    )
    return "<table><thead><tr><th>Domain</th><th>媒介</th><th>price_1</th><th>price_2</th><th>price_3</th><th>建议篇数</th><th>预计总成本</th></tr></thead><tbody>" + body + "</tbody></table>"


def _trend_table(rows: list[dict[str, Any]], labels: dict[str, str]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('term', '')))}</td><td>{html.escape(str(item.get('source', '')))}</td><td>{html.escape(str(item.get('relevance_reason', '')))}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>{labels['term']}</th><th>{labels['source']}</th><th>{labels['reason']}</th></tr></thead><tbody>{body}</tbody></table>"


def _ranking_table(rows: list[dict[str, Any]], labels: dict[str, str]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{item.get('recommendation_count', 0)}</td><td>{item.get('avg_rank', '')}</td><td>{html.escape(str(item.get('engine', '')))}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>{labels['brand']}</th><th>{labels['count']}</th><th>{labels['avg_rank']}</th><th>{labels['engine']}</th></tr></thead><tbody>{body}</tbody></table>"


def _search_visibility_table(rows: list[dict[str, Any]]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{html.escape(_display_rank(item.get('search_visibility_rank')))}</td><td>{html.escape(_display_count(item.get('mentioned_count'), _has_visibility_data(item)))}</td><td>{html.escape(_display_count(item.get('result_count'), _has_visibility_data(item)))}</td><td>{html.escape(str(item.get('query', '')))}</td><td>{html.escape(str(item.get('metric_type') or '五平台内容数量估算'))}</td></tr>"
        for item in rows
    )
    return "<p>含义：基于 AI 对百度、搜狗、360 搜索、抖音、小红书五个平台内容数量的估算，用来判断品牌在传统搜索与新媒体里的可见度。</p><table><thead><tr><th>品牌</th><th>品牌内容声量排名</th><th>五平台内容数量估算</th><th>结果数估算</th><th>查询词</th><th>数据口径</th></tr></thead><tbody>" + body + "</tbody></table>"


def _gap_table(rows: list[dict[str, Any]]) -> str:
    body = ""
    for item in rows:
        has_visibility = _has_visibility_data(item)
        body += (
            f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td>"
            f"<td>{html.escape(_display_rank(item.get('ai_recommendation_rank')))}</td>"
            f"<td>{html.escape(_display_rank(item.get('search_visibility_rank')) if has_visibility else '未进入声量估算')}</td>"
            f"<td>{html.escape(_display_count(item.get('mentioned_count'), has_visibility))}</td>"
            f"<td>{html.escape(str(item.get('gap_label') if has_visibility else 'AI 推荐中出现，但本轮未拿到有效五平台声量估算；不是确认没有内容。'))}</td></tr>"
        )
    return "<table><thead><tr><th>品牌</th><th>AI排名</th><th>品牌内容声量排名</th><th>五平台内容数量估算</th><th>解读</th></tr></thead><tbody>" + body + "</tbody></table>"


def _mentions_table(rows: list[dict[str, Any]], labels: dict[str, str]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('brand_name', '')))}</td><td>{item.get('mentioned_count', 0)}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>{labels['brand']}</th><th>{labels['articles']}</th></tr></thead><tbody>{body}</tbody></table>"


def _media_table(rows: list[dict[str, Any]], labels: dict[str, str]) -> str:
    body = "".join(
        f"<tr><td>{html.escape(str(item.get('source_domain', '')))}</td><td>{html.escape(str(item.get('match_type', '')))}</td><td>{html.escape(str(item.get('resource_title', '')))}</td><td>{item.get('price_1', 0)}</td><td>{item.get('price_2', 0)}</td><td>{item.get('price_3', 0)}</td></tr>"
        for item in rows
    )
    return f"<table><thead><tr><th>Domain</th><th>{labels['matched']}</th><th>Resource</th><th>price_1</th><th>price_2</th><th>price_3</th></tr></thead><tbody>{body}</tbody></table>"


CONTENT_TOPIC_RULES = [
    ("价格/性价比", ["price", "cost", "discount", "affordable", "value", "cheap", "deal", "性价比", "价格", "折扣"]),
    ("品质/OEM", ["quality", "oem", "oe", "reliable", "durable", "warranty", "specification", "品质", "质保", "耐用"]),
    ("适配/兼容", ["fit", "compatibility", "compatible", "vin", "vehicle-specific", "replacement", "适配", "兼容", "车型"]),
    ("物流/退换", ["shipping", "delivery", "return", "warehouse", "free shipping", "物流", "发货", "退货"]),
    ("安装/DIY", ["install", "installation", "diy", "guide", "repair", "mechanic", "安装", "维修", "教程"]),
    ("品类覆盖", ["brake", "battery", "engine", "suspension", "rotor", "spark plug", "catalog", "parts", "品类", "覆盖"]),
    ("信任/评价", ["review", "rating", "trusted", "certified", "support", "service", "评价", "信任", "认证", "客服"]),
]


def _ensure_visibility_platform_splits(data: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for item in data.get("search_volume_ranking") or []:
        row = dict(item)
        if not row.get("traditional_search") and row.get("provider_estimates"):
            traditional: defaultdict[str, int] = defaultdict(int)
            new_media: defaultdict[str, int] = defaultdict(int)
            estimates = [estimate for estimate in row.get("provider_estimates") or [] if isinstance(estimate, dict)]
            provider_count = max(len(estimates), 1)
            for estimate in estimates:
                for key, value in (estimate.get("traditional_search") or {}).items():
                    traditional[str(key)] += _safe_int(value)
                for key, value in (estimate.get("new_media") or {}).items():
                    new_media[str(key)] += _safe_int(value)
            row["traditional_search"] = {key: round(value / provider_count) for key, value in traditional.items()}
            row["new_media"] = {key: round(value / provider_count) for key, value in new_media.items()}
            row["provider_count"] = row.get("provider_count") or provider_count
        rows.append(row)
    if rows:
        data["search_volume_ranking"] = rows
        split_by_key = {str(item.get("brand_key") or _brand_key(item.get("brand_name", ""))): item for item in rows}
        visibility_rows = []
        for item in data.get("search_visibility_ranking") or []:
            row = dict(item)
            split = split_by_key.get(str(row.get("brand_key") or _brand_key(row.get("brand_name", "")))) or {}
            row.setdefault("traditional_search", split.get("traditional_search") or {})
            row.setdefault("new_media", split.get("new_media") or {})
            visibility_rows.append(row)
        if visibility_rows:
            data["search_visibility_ranking"] = visibility_rows
    return data


def enrich_analysis_data(analysis_data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(analysis_data, dict):
        return {}
    data = dict(analysis_data)
    data = _ensure_visibility_platform_splits(data)
    if not data.get("multi_ai_provider_status"):
        data["multi_ai_provider_status"] = _provider_status_from_results(data)
    trend = dict(data.get("trend_discovery") or {})
    if not trend.get("probe_questions"):
        trend["probe_questions"] = _probe_questions_from_ai_probes(data.get("ai_probes") or [])
    else:
        trend["probe_questions"] = _normalize_probe_questions(trend.get("probe_questions") or [])
    data["trend_discovery"] = trend
    if not data.get("ai_recommendation_ranking"):
        data["ai_recommendation_ranking"] = data.get("brand_ranking") or []
    if not data.get("search_visibility_ranking"):
        data["search_visibility_ranking"] = _build_search_visibility_ranking(data.get("baidu_mentions") or [])
    if not data.get("competitive_gap_ranking"):
        data["competitive_gap_ranking"] = _build_competitive_gap_ranking(
            data.get("ai_recommendation_ranking") or [],
            data.get("search_visibility_ranking") or [],
        )
    if not data.get("brand_visibility_metrics"):
        data["brand_visibility_metrics"] = build_brand_visibility_metrics(
            data.get("recommendation_items") or [],
            data.get("product_profile") or {},
        )
    if not data.get("provider_visibility_matrix"):
        data["provider_visibility_matrix"] = build_provider_visibility_matrix(data.get("recommendation_items") or [])
    if not data.get("prompt_runs"):
        data["prompt_runs"] = build_prompt_visibility_rows(
            data.get("multi_ai_recommendation_results") or [],
            data.get("product_profile") or {},
        )
    summary = data.get("geo_visibility_summary") or {}
    if not summary or (not summary.get("total_ai_responses") and data.get("prompt_runs")):
        data["geo_visibility_summary"] = build_geo_visibility_summary(data, data.get("product_profile") or {})
    if not data.get("neutral_visibility_summary"):
        data["neutral_visibility_summary"] = data.get("geo_visibility_summary") or {}
    if not data.get("brand_diagnostic_prompt_runs") and data.get("brand_diagnostic_results"):
        data["brand_diagnostic_prompt_runs"] = build_prompt_visibility_rows(
            data.get("brand_diagnostic_results") or [],
            data.get("product_profile") or {},
        )
    if not data.get("brand_diagnostic_summary") and data.get("brand_diagnostic_prompt_runs"):
        diagnostic_items = data.get("brand_diagnostic_items") or []
        diagnostic_metrics = data.get("brand_diagnostic_brand_metrics") or build_brand_visibility_metrics(
            diagnostic_items,
            data.get("product_profile") or {},
        )
        data["brand_diagnostic_summary"] = build_geo_visibility_summary(
            {
                "prompt_runs": data.get("brand_diagnostic_prompt_runs") or [],
                "brand_visibility_metrics": diagnostic_metrics,
                "recommendation_items": diagnostic_items,
            },
            data.get("product_profile") or {},
        )
    if not data.get("comparison_prompt_runs") and data.get("comparison_results"):
        data["comparison_prompt_runs"] = build_prompt_visibility_rows(
            data.get("comparison_results") or [],
            data.get("product_profile") or {},
        )
    if not data.get("comparison_summary") and data.get("comparison_prompt_runs"):
        comparison_items = data.get("comparison_items") or []
        comparison_metrics = data.get("comparison_brand_metrics") or build_brand_visibility_metrics(
            comparison_items,
            data.get("product_profile") or {},
        )
        data["comparison_summary"] = build_geo_visibility_summary(
            {
                "prompt_runs": data.get("comparison_prompt_runs") or [],
                "brand_visibility_metrics": comparison_metrics,
                "recommendation_items": comparison_items,
            },
            data.get("product_profile") or {},
        )
    if not data.get("content_topic_analysis"):
        data["content_topic_analysis"] = derive_content_topic_analysis(
            data.get("recommendation_items") or [],
            data.get("source_articles") or [],
            data.get("content_pattern_report") or "",
            topic_taxonomy=(data.get("analysis_strategy") or {}).get("topic_taxonomy") or [],
        )
    if not data.get("media_cost_analysis"):
        data["media_cost_analysis"] = _derive_media_cost_analysis(
            data.get("media_matches") or {},
            data.get("search_volume_ranking") or data.get("baidu_mentions") or [],
        )
    if not data.get("standard_geo_metrics"):
        data["standard_geo_metrics"] = build_standard_geo_metrics(
            {
                "neutral_visibility_summary": data.get("neutral_visibility_summary") or {},
                "geo_visibility_summary": data.get("geo_visibility_summary") or {},
                "brand_diagnostic_summary": data.get("brand_diagnostic_summary") or {},
                "prompt_runs": data.get("prompt_runs") or [],
                "brand_visibility_metrics": data.get("brand_visibility_metrics") or [],
                "recommendation_items": data.get("recommendation_items") or [],
            }
        )
    if not data.get("source_intelligence"):
        data["source_intelligence"] = build_source_intelligence(
            source_links=data.get("source_links") or [],
            source_articles=data.get("source_articles") or [],
            recommendation_items=data.get("recommendation_items") or [],
            top_brands=data.get("ai_recommendation_ranking") or data.get("brand_ranking") or [],
            profile=data.get("product_profile") or {},
        )
    if not data.get("owned_asset_audit"):
        data["owned_asset_audit"] = audit_owned_assets(data.get("sources") or {}, data.get("product_profile") or {})
    if not data.get("content_monitoring"):
        data["content_monitoring"] = build_content_monitoring(
            {
                "prompt_runs": data.get("prompt_runs") or [],
                "brand_diagnostic_prompt_runs": data.get("brand_diagnostic_prompt_runs") or [],
                "comparison_prompt_runs": data.get("comparison_prompt_runs") or [],
                "brand_visibility_metrics": data.get("brand_visibility_metrics") or [],
                "recommendation_items": data.get("recommendation_items") or [],
                "source_intelligence": data.get("source_intelligence") or {},
                "content_positioning_analysis": data.get("content_positioning_analysis") or {},
            }
        )
    if not data.get("geo_actions"):
        data["geo_actions"] = build_action_plan(
            {
                "standard_geo_metrics": data.get("standard_geo_metrics") or {},
                "source_intelligence": data.get("source_intelligence") or {},
                "owned_asset_audit": data.get("owned_asset_audit") or {},
                "content_monitoring": data.get("content_monitoring") or {},
                "media_cost_analysis": data.get("media_cost_analysis") or {},
            }
        )
    return data


def _standard_geo_metrics_markdown(metrics: dict[str, Any]) -> list[str]:
    rows = [
        ("Visibility 可见度", metrics.get("visibility") or {}),
        ("Sentiment 情绪分", metrics.get("sentiment") or {}),
        ("Position 平均位置", metrics.get("position") or {}),
        ("SOV 推荐份额", metrics.get("sov") or {}),
        ("Prompt 成功率", metrics.get("prompt_success") or {}),
    ]
    lines = [
        "## GEO 指标定义",
        "",
        "| 指标 | 当前值 | 计算方式 | 业务含义 |",
        "|---|---:|---|---|",
    ]
    for name, item in rows:
        lines.append(
            f"| {_cell(name)} | {_cell(item.get('value_label') or item.get('score') or item.get('avg_rank') or '')} | {_cell(item.get('formula'))} | {_cell(item.get('business_meaning'))} |"
        )
    lines.append("")
    return lines


def _source_intelligence_markdown(source_intelligence: dict[str, Any]) -> list[str]:
    lines = [
        "## Sources AI 信源分析",
        "",
        "| 排名 | 域名 | 类型 | 引用次数 | Used % | Avg Citations | 客户品牌出现 | 出现品牌 | 建议动作 |",
        "|---:|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in (source_intelligence.get("domain_summary") or [])[:12]:
        lines.append(
            f"| {item.get('rank', '')} | {_cell(item.get('domain'))} | {_cell(item.get('domain_type'))} | {item.get('citation_count', 0)} | {round(float(item.get('used_rate') or 0) * 100, 1)}% | {item.get('avg_citations', 0)} | {'是' if item.get('mentioned_user_brand') else '否'} | {_cell(', '.join(item.get('brands_appear') or []))} | {_cell(item.get('action'))} |"
        )
    lines.extend(["", "### 信源机会", "", "| 优先级 | 域名 | 类型 | 原因 |", "|---|---|---|---|"])
    for item in (source_intelligence.get("source_opportunities") or [])[:10]:
        lines.append(f"| {_cell(item.get('priority'))} | {_cell(item.get('domain'))} | {_cell(item.get('domain_type'))} | {_cell(item.get('reason'))} |")
    lines.append("")
    return lines


def _owned_asset_audit_markdown(audit: dict[str, Any]) -> list[str]:
    lines = [
        "## 官网结构化信源审计",
        "",
        f"- 官网 AI 可读性评分：{audit.get('ai_readability_score', 0)}/100",
        f"- 页面抓取成功：{audit.get('crawl_success_count', 0)}/{audit.get('crawl_total_count', 0)}",
        f"- 结构化信号：{', '.join(audit.get('schema_signals') or []) or '暂未识别'}",
        "",
        "| 资产项 | 是否具备 | 建议 |",
        "|---|---|---|",
    ]
    for item in audit.get("asset_checks") or []:
        lines.append(f"| {_cell(item.get('asset_name'))} | {'是' if item.get('present') else '否'} | {_cell(item.get('recommendation'))} |")
    lines.extend(["", "### 官网待补动作", "", "| 优先级 | 动作 | 原因 |", "|---|---|---|"])
    for item in audit.get("structured_source_actions") or []:
        lines.append(f"| {_cell(item.get('priority'))} | {_cell(item.get('action'))} | {_cell(item.get('reason'))} |")
    lines.append("")
    return lines


def _content_monitoring_markdown(monitoring: dict[str, Any]) -> list[str]:
    opinion = monitoring.get("opinion_monitoring") or {}
    content = monitoring.get("content_monitoring") or {}
    lines = [
        "## 内容监控与舆情监控",
        "",
        "### 舆情风险",
        "",
        "| 严重度 | AI平台 | 情绪分 | 风险词 | 证据 |",
        "|---|---|---:|---|---|",
    ]
    for item in opinion.get("risk_topics") or []:
        lines.append(
            f"| {_cell(item.get('severity'))} | {_cell(item.get('provider'))} | {item.get('sentiment_score', 50)} | {_cell(', '.join(item.get('risk_terms') or []))} | {_cell(item.get('evidence'))} |"
        )
    lines.extend(["", "### 竞品优势", "", "| 品牌 | AI提及次数 | 平均位置 | 情绪分 | 证据摘要 |", "|---|---:|---:|---:|---|"])
    for item in opinion.get("competitor_advantages") or []:
        lines.append(
            f"| {_cell(item.get('brand_name'))} | {item.get('mention_count', 0)} | {_cell(_display_rank(item.get('avg_position')))} | {item.get('sentiment_score', 50)} | {_cell('；'.join(item.get('advantage_evidence') or []))} |"
        )
    lines.extend(["", "### 内容缺口", "", "| 域名 | 已出现品牌 | 建议 |", "|---|---|---|"])
    for item in content.get("articles_mentioning_competitors_only") or []:
        lines.append(f"| {_cell(item.get('domain'))} | {_cell(', '.join(item.get('brands_appear') or []))} | {_cell(item.get('action'))} |")
    lines.append("")
    return lines


def _geo_actions_markdown(plan: dict[str, Any]) -> list[str]:
    lines = [
        "## Actions 优化待办清单",
        "",
        f"- 高优先级任务：{(plan.get('summary') or {}).get('high_priority_count', 0)}",
        f"- 任务总数：{(plan.get('summary') or {}).get('total_count', 0)}",
        "",
        "| 排名 | 优先级 | 模块 | 任务 | 原因 | 目标指标 | 预估成本 |",
        "|---:|---|---|---|---|---|---:|",
    ]
    for item in plan.get("actions") or []:
        lines.append(
            f"| {item.get('rank', '')} | {_cell(item.get('priority'))} | {_cell(item.get('module'))} | {_cell(item.get('task'))} | {_cell(item.get('reason'))} | {_cell(item.get('expected_metric'))} | {_cell(item.get('estimated_cost') or '')} |"
        )
    lines.append("")
    return lines


def _build_search_visibility_ranking(baidu_mentions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in baidu_mentions:
        brand = str(item.get("brand_name") or "").strip()
        if not brand:
            continue
        rows.append(
            {
                "brand_name": brand,
                "brand_key": _brand_key(brand),
                "mentioned_count": int(item.get("mentioned_count") or 0),
                "result_count": int(item.get("result_count") or 0),
                "query": item.get("query", ""),
                "is_user_brand": bool(item.get("is_user_brand")),
                "error": item.get("error", ""),
            }
        )
    rows.sort(key=lambda item: (-item["mentioned_count"], -item["result_count"], item["brand_name"]))
    for idx, item in enumerate(rows, start=1):
        item["search_visibility_rank"] = idx
    return rows


def _build_competitive_gap_ranking(
    ai_recommendation_ranking: list[dict[str, Any]],
    search_visibility_ranking: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    ai_by_key = {_brand_key(item.get("brand_name", "")): item for item in ai_recommendation_ranking if item.get("brand_name")}
    search_by_key = {_brand_key(item.get("brand_name", "")): item for item in search_visibility_ranking if item.get("brand_name")}
    ai_positions = {_brand_key(item.get("brand_name", "")): idx for idx, item in enumerate(ai_recommendation_ranking, start=1)}
    keys = [key for key in dict.fromkeys([*ai_by_key.keys(), *search_by_key.keys()]) if key]
    missing_rank = max(len(keys), 1) + 1
    rows = []
    for key in keys:
        ai = ai_by_key.get(key, {})
        search = search_by_key.get(key, {})
        ai_rank = ai_positions.get(key)
        search_rank = search.get("search_visibility_rank")
        if ai_rank and search_rank:
            gap_score = int(search_rank) - int(ai_rank)
        elif ai_rank and not search_rank:
            gap_score = missing_rank - int(ai_rank)
        elif search_rank and not ai_rank:
            gap_score = int(search_rank) - missing_rank
        else:
            gap_score = 0
        rows.append(
            {
                "brand_name": ai.get("brand_name") or search.get("brand_name") or "",
                "brand_key": key,
                "ai_recommendation_rank": ai_rank,
                "ai_recommendation_count": ai.get("recommendation_count", 0),
                "avg_ai_rank": ai.get("avg_rank", ""),
                "search_visibility_rank": search_rank,
                "mentioned_count": search.get("mentioned_count", 0),
                "result_count": search.get("result_count", 0),
                "is_user_brand": bool(ai.get("is_user_brand") or search.get("is_user_brand")),
                "gap_score": gap_score,
                "gap_label": _gap_label(gap_score, ai_rank, search_rank),
            }
        )
    return sorted(rows, key=lambda item: (-abs(int(item.get("gap_score") or 0)), item.get("brand_name", "")))


def _gap_label(gap_score: int, ai_rank: int | None, search_rank: int | None) -> str:
    if ai_rank and not search_rank:
        return "AI 推荐较高但搜索声量不足"
    if search_rank and not ai_rank:
        return "搜索声量较高但 AI 推荐不足"
    if gap_score >= 3:
        return "AI 排名高于搜索声量"
    if gap_score <= -3:
        return "搜索声量高于 AI 排名"
    return "AI 推荐与搜索声量相对一致"


def _probe_questions_from_ai_probes(probes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    seen = set()
    for probe in probes:
        term = str(probe.get("trend_term") or "").strip()
        meta = probe.get("question_meta") or {}
        result = probe.get("result") or {}
        question = str(meta.get("question") or result.get("question") or "").strip()
        if not question or question.lower().startswith("recommend "):
            question = _fallback_probe_question(term)
        if term and term not in seen:
            seen.add(term)
            rows.append(
                {
                    "term": term,
                    "question": question,
                    "intent": meta.get("intent") or "历史数据回放：原始探测问题",
                    "reason": meta.get("reason") or "该问题来自历史 AI 推荐探测结果。",
                }
            )
    return rows


def _normalize_probe_questions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        term = str(item.get("term") or "").strip()
        question = str(item.get("question") or "").strip()
        if not question or question.lower().startswith("recommend "):
            question = _fallback_probe_question(term)
        normalized.append({**item, "term": term, "question": question})
    return normalized


def _fallback_probe_question(term: str) -> str:
    clean = str(term or "").strip()
    lower = clean.lower()
    if "vin" in lower:
        return "How can I find the right car replacement parts by VIN?"
    if "free shipping" in lower:
        return f"Where can I buy reliable {clean} with free shipping?"
    if "discount" in lower:
        return f"Which {clean} are reliable and worth buying online?"
    if any(word in lower for word in ("brake", "rotor", "suspension", "engine", "battery", "spark plug")):
        return f"Which {clean} are best for my car and easy to replace?"
    if "oem" in lower or "replacement" in lower:
        return f"What are the best OEM-quality {clean} for my vehicle?"
    return f"What are the best {clean} to buy online for my car?"


def _derive_content_topic_analysis(
    recommendation_items: list[dict[str, Any]],
    source_articles: list[dict[str, Any]],
    content_pattern_report: str,
) -> dict[str, Any]:
    topic_counts: Counter[str] = Counter()
    brand_topics: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for item in recommendation_items:
        brand = str(item.get("brand_name") or "").strip() or "Unknown"
        text = " ".join(str(item.get(key, "")) for key in ("brand_name", "product_name", "reason", "trend_term")).lower()
        for topic in _match_content_topics(text):
            topic_counts[topic] += 1
            brand_topics[brand][topic] += 1
    for item in source_articles[:30]:
        text = str(item.get("text_excerpt") or "").lower()
        for topic in _match_content_topics(text):
            topic_counts[topic] += 1
    for topic in _match_content_topics(str(content_pattern_report or "").lower()):
        topic_counts[topic] += 1
    matrix = []
    for brand, counts in brand_topics.items():
        for topic, count in counts.items():
            matrix.append({"brand": brand, "topic": topic, "count": count})
    return {
        "topics": [{"topic": topic, "count": count} for topic, count in topic_counts.most_common()],
        "brand_topic_matrix": sorted(matrix, key=lambda item: (-item["count"], item["brand"], item["topic"])),
    }


def _match_content_topics(text: str) -> list[str]:
    matched = []
    for topic, keywords in CONTENT_TOPIC_RULES:
        if any(keyword in text for keyword in keywords):
            matched.append(topic)
    return matched or ["综合推荐"]


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
        "benchmark_metric_type": benchmark.get("metric_type", "top_k_mentions"),
        "user_brand_count": user_count,
        "content_asset_gap": max(benchmark_count - user_count, 0),
        "planning_note": "建议发布篇数为阶段性追赶目标，上限 300 篇；完整内容资产差距见 content_asset_gap。",
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


def _safe_int(value: Any) -> int:
    try:
        return max(int(float(str(value or 0).replace(",", "").strip() or 0)), 0)
    except ValueError:
        return 0


def _brand_key(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").lower())


def _cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
