from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_content_monitoring(data: dict[str, Any]) -> dict[str, Any]:
    """Build manual-monitoring style opinion and content signals."""

    prompt_runs = data.get("prompt_runs") or []
    diagnostic_runs = data.get("brand_diagnostic_prompt_runs") or []
    comparison_runs = data.get("comparison_prompt_runs") or []
    brand_metrics = data.get("brand_visibility_metrics") or []
    source_intelligence = data.get("source_intelligence") or {}
    source_domains = source_intelligence.get("domain_summary") or []
    content_positioning = data.get("content_positioning_analysis") or {}

    watched_rows = [*prompt_runs, *diagnostic_runs, *comparison_runs]
    risk_rows = _risk_rows(watched_rows)
    positive_rows = _positive_rows(watched_rows)
    competitor_advantages = _competitor_advantages(brand_metrics, data.get("recommendation_items") or [])
    domains_missing_brand = [item for item in source_domains if not item.get("mentioned_user_brand")][:12]
    selling_point_counts = Counter(
        str(item.get("brand_name") or "")
        for item in content_positioning.get("selling_points") or []
        if item.get("brand_name")
    )

    return {
        "content_monitoring_version": "content_monitoring_v1",
        "opinion_monitoring": {
            "positive_topics": positive_rows[:12],
            "risk_topics": risk_rows[:12],
            "negative_mentions": [item for item in risk_rows if item.get("severity") == "高"][:8],
            "competitor_advantages": competitor_advantages[:12],
        },
        "content_monitoring": {
            "cited_domains": source_domains[:20],
            "domains_missing_user_brand": domains_missing_brand,
            "articles_mentioning_competitors_only": [
                {
                    "domain": item.get("domain"),
                    "brands_appear": item.get("brands_appear") or [],
                    "action": item.get("action"),
                }
                for item in domains_missing_brand
                if item.get("brands_appear")
            ][:12],
            "selling_point_coverage": [
                {"brand_name": brand, "selling_point_count": count}
                for brand, count in selling_point_counts.most_common(20)
            ],
        },
        "definitions": {
            "opinion_monitoring": "基于 AI 回答、诊断问题和对比问题识别品牌正负面表达与风险。",
            "content_monitoring": "基于 AI 引用来源、抓取文章和竞品内容识别投放缺口。",
        },
    }


def _risk_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        risk_terms = row.get("risk_terms") or []
        score = int(row.get("sentiment_score") or 50)
        if risk_terms or score < 45 or row.get("error"):
            result.append(
                {
                    "provider": row.get("provider", ""),
                    "prompt": row.get("prompt", ""),
                    "sentiment_score": score,
                    "risk_terms": risk_terms,
                    "severity": "高" if score <= 35 or len(risk_terms) >= 2 else "中",
                    "evidence": str(row.get("answer_excerpt") or row.get("error") or "")[:240],
                }
            )
    result.sort(key=lambda item: (0 if item["severity"] == "高" else 1, item["sentiment_score"]))
    return result


def _positive_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in rows:
        positive_terms = row.get("positive_terms") or []
        score = int(row.get("sentiment_score") or 50)
        if positive_terms or score >= 65:
            result.append(
                {
                    "provider": row.get("provider", ""),
                    "prompt": row.get("prompt", ""),
                    "sentiment_score": score,
                    "positive_terms": positive_terms,
                    "evidence": str(row.get("answer_excerpt") or "")[:240],
                }
            )
    result.sort(key=lambda item: -item["sentiment_score"])
    return result


def _competitor_advantages(metrics: list[dict[str, Any]], recommendation_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reasons: defaultdict[str, list[str]] = defaultdict(list)
    for item in recommendation_items:
        brand = str(item.get("brand_name") or "")
        if brand and item.get("reason"):
            reasons[brand].append(str(item.get("reason"))[:160])
    rows = []
    for metric in metrics:
        if metric.get("is_user_brand"):
            continue
        brand = str(metric.get("brand_name") or "")
        rows.append(
            {
                "brand_name": brand,
                "mention_count": metric.get("mention_count", 0),
                "avg_position": metric.get("avg_position"),
                "sentiment_score": metric.get("sentiment_score", 50),
                "advantage_evidence": reasons.get(brand, [])[:3],
            }
        )
    rows.sort(key=lambda item: (-int(item.get("mention_count") or 0), float(item.get("avg_position") or 99)))
    return rows
