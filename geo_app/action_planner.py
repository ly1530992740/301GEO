from __future__ import annotations

from typing import Any


def build_action_plan(data: dict[str, Any]) -> dict[str, Any]:
    """Convert diagnostic modules into an executable GEO optimization todo list."""

    metrics = data.get("standard_geo_metrics") or {}
    source_intel = data.get("source_intelligence") or {}
    owned_audit = data.get("owned_asset_audit") or {}
    monitoring = data.get("content_monitoring") or {}
    media_cost = data.get("media_cost_analysis") or {}

    actions: list[dict[str, Any]] = []
    actions.extend(_metric_actions(metrics))
    actions.extend(_source_actions(source_intel))
    actions.extend(_owned_asset_actions(owned_audit))
    actions.extend(_monitoring_actions(monitoring))
    actions.extend(_media_actions(media_cost))

    priority_order = {"高": 0, "中": 1, "低": 2}
    module_order = {"GEO指标": 0, "Sources": 1, "Owned Assets": 2, "Content Monitoring": 3, "Media": 4}
    deduped = []
    seen = set()
    for item in actions:
        key = (item.get("module"), item.get("task"))
        if key in seen or not item.get("task"):
            continue
        seen.add(key)
        deduped.append(item)
    deduped.sort(key=lambda item: (priority_order.get(item.get("priority"), 9), module_order.get(item.get("module"), 9)))
    for idx, item in enumerate(deduped, start=1):
        item["rank"] = idx
    return {
        "action_plan_version": "geo_action_plan_v1",
        "actions": deduped[:30],
        "summary": {
            "high_priority_count": len([item for item in deduped if item.get("priority") == "高"]),
            "total_count": len(deduped),
        },
    }


def _metric_actions(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    visibility = (metrics.get("visibility") or {}).get("score", 0)
    sov = (metrics.get("sov") or {}).get("score", 0)
    position = (metrics.get("position") or {}).get("avg_rank")
    sentiment = (metrics.get("sentiment") or {}).get("score", 50)
    if visibility < 40:
        actions.append(_action("高", "GEO指标", "提升中立推荐可见度", "客户品牌在中立 AI 推荐中出现率偏低，需要优先补充第三方信源和官网结构化内容。", "Visibility"))
    if sov < 0.15:
        actions.append(_action("高", "GEO指标", "提升 AI 推荐 SOV", "客户品牌在所有品牌提及中的占比偏低，需要围绕主流推荐问题持续发布内容。", "SOV"))
    if position and float(position or 99) > 5:
        actions.append(_action("中", "GEO指标", "优化 AI 推荐位置", "客户品牌出现时排名靠后，需要强化差异化卖点、权威背书和对比内容。", "Position"))
    if sentiment < 60:
        actions.append(_action("高", "GEO指标", "修复品牌诊断情绪分", "AI 对品牌描述不够正面或存在风险词，需要补充资质、案例、价格透明度和服务流程说明。", "Sentiment"))
    return actions


def _source_actions(source_intel: dict[str, Any]) -> list[dict[str, Any]]:
    rows = source_intel.get("source_opportunities") or []
    actions = []
    for item in rows[:8]:
        actions.append(
            _action(
                item.get("priority", "中"),
                "Sources",
                f"补齐 {item.get('domain')} 信源内容",
                item.get("reason") or "AI 已引用该域名，但客户品牌未出现。",
                "Sources",
                target=item.get("domain", ""),
                suggested_channel=item.get("domain_type", ""),
            )
        )
    return actions


def _owned_asset_actions(owned_audit: dict[str, Any]) -> list[dict[str, Any]]:
    actions = []
    for item in owned_audit.get("structured_source_actions") or []:
        actions.append(
            _action(
                item.get("priority", "中"),
                "Owned Assets",
                item.get("action", ""),
                item.get("reason", ""),
                "Owned Asset Score",
            )
        )
    return actions


def _monitoring_actions(monitoring: dict[str, Any]) -> list[dict[str, Any]]:
    opinion = monitoring.get("opinion_monitoring") or {}
    content = monitoring.get("content_monitoring") or {}
    actions = []
    if opinion.get("negative_mentions"):
        actions.append(_action("高", "Content Monitoring", "处理 AI 负面/风险表达", "品牌诊断或竞品对比中出现高风险负面表达，需要发布澄清、案例、资质或服务流程内容。", "Sentiment"))
    for item in (content.get("articles_mentioning_competitors_only") or [])[:5]:
        actions.append(
            _action(
                "中",
                "Content Monitoring",
                f"进入竞品已出现的信源 {item.get('domain')}",
                "该信源出现竞品但未识别到客户品牌，适合做对比稿、榜单稿或问答内容。",
                "Brands Appear",
                target=item.get("domain", ""),
            )
        )
    return actions


def _media_actions(media_cost: dict[str, Any]) -> list[dict[str, Any]]:
    if not media_cost or not media_cost.get("target_articles"):
        return []
    return [
        _action(
            "中",
            "Media",
            f"按竞品声量至少补 {media_cost.get('target_articles', 0)} 篇内容",
            media_cost.get("planning_note") or "根据竞品声量差距估算需要补充发布数量。",
            "Content Volume",
            estimated_cost=media_cost.get("estimated_total_cost") or media_cost.get("avg_unit_price"),
        )
    ]


def _action(
    priority: str,
    module: str,
    task: str,
    reason: str,
    expected_metric: str,
    target: str = "",
    suggested_channel: str = "",
    estimated_cost: Any = None,
) -> dict[str, Any]:
    return {
        "priority": priority or "中",
        "module": module,
        "task": task,
        "reason": reason,
        "expected_metric": expected_metric,
        "target": target,
        "suggested_channel": suggested_channel,
        "estimated_cost": estimated_cost,
    }
