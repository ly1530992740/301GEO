from __future__ import annotations

import re
from statistics import mean
from typing import Any


def build_market_queries(city: str, industry: str, seed_keyword: str, competitors: str = "") -> list[str]:
    city = city.strip()
    industry = industry.strip()
    seed_keyword = seed_keyword.strip()
    base = [
        seed_keyword,
        f"{city}{industry}推荐",
        f"{city}{industry}哪家好",
        f"{city}{industry}排名",
        f"{city}{industry}价格",
        f"{city}{industry}避坑",
    ]
    for competitor in [item.strip() for item in re.split(r"[,，\n]", competitors or "") if item.strip()]:
        base.append(f"{city}{industry} {competitor}")
    return list(dict.fromkeys(item for item in base if item))


def summarize_search_result(query: str, raw: dict[str, Any]) -> dict[str, Any]:
    organic = raw.get("organic_results") or []
    related_searches = raw.get("related_searches") or []
    related_questions = raw.get("related_questions") or []
    return {
        "query": query,
        "organic_results": [
            {
                "position": item.get("position"),
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "source": item.get("source", ""),
                "snippet": item.get("snippet", ""),
            }
            for item in organic[:10]
        ],
        "related_searches": [
            item.get("query") or item.get("title") or ""
            for item in related_searches[:10]
            if item.get("query") or item.get("title")
        ],
        "related_questions": [
            item.get("question") or item.get("title") or ""
            for item in related_questions[:10]
            if item.get("question") or item.get("title")
        ],
    }


def build_candidate_keywords(seed_keyword: str, search_summaries: list[dict[str, Any]], limit: int = 12) -> list[str]:
    candidates = [seed_keyword.strip()]
    for summary in search_summaries:
        candidates.extend(summary.get("related_searches") or [])
        candidates.extend(summary.get("related_questions") or [])
        for item in summary.get("organic_results") or []:
            title = item.get("title", "")
            if title and len(title) <= 36:
                candidates.append(title)
    cleaned: list[str] = []
    for item in candidates:
        value = re.sub(r"\s+", " ", str(item)).strip(" -_|，,。")
        if not value or len(value) > 48:
            continue
        if value not in cleaned:
            cleaned.append(value)
    return cleaned[:limit]


def extract_timeseries_scores(raw: dict[str, Any]) -> dict[str, dict[str, float]]:
    timeline = raw.get("interest_over_time", {}).get("timeline_data") or raw.get("timeline_data") or []
    scores: dict[str, list[float]] = {}
    for point in timeline:
        for value_item in point.get("values") or []:
            keyword = value_item.get("query") or value_item.get("keyword") or ""
            extracted = value_item.get("extracted_value")
            if keyword and isinstance(extracted, (int, float)):
                scores.setdefault(keyword, []).append(float(extracted))

    result: dict[str, dict[str, float]] = {}
    for keyword, values in scores.items():
        if not values:
            continue
        recent = values[-4:] if len(values) >= 4 else values
        early = values[:4] if len(values) >= 4 else values
        average = mean(values)
        growth = mean(recent) - mean(early)
        result[keyword] = {
            "avg_heat": round(average, 2),
            "recent_heat": round(mean(recent), 2),
            "growth": round(growth, 2),
            "trend_score": round(min(100.0, max(0.0, average * 0.7 + max(growth, 0) * 1.2)), 2),
        }
    return result


def extract_related_queries(raw: dict[str, Any]) -> list[dict[str, Any]]:
    related = raw.get("related_queries") or {}
    items: list[dict[str, Any]] = []
    for group_name in ("rising", "top"):
        for item in related.get(group_name) or []:
            query = item.get("query") or item.get("title") or ""
            if query:
                items.append(
                    {
                        "query": query,
                        "type": group_name,
                        "value": item.get("value"),
                        "extracted_value": item.get("extracted_value"),
                    }
                )
    return items[:20]


def score_keywords(candidates: list[str], timeseries_scores: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    scored = []
    for keyword in candidates:
        trend = timeseries_scores.get(keyword, {})
        commercial_score = _commercial_score(keyword)
        local_score = _local_score(keyword)
        trend_score = float(trend.get("trend_score", 20 if keyword else 0))
        final_score = round(trend_score * 0.45 + commercial_score * 0.3 + local_score * 0.25, 2)
        scored.append(
            {
                "keyword": keyword,
                "trend_score": trend_score,
                "growth_score": float(trend.get("growth", 0)),
                "commercial_score": commercial_score,
                "local_score": local_score,
                "final_score": final_score,
                "reason": _reason(keyword, trend_score, commercial_score, local_score),
                "raw_trend": trend,
            }
        )
    return sorted(scored, key=lambda item: item["final_score"], reverse=True)


def _commercial_score(keyword: str) -> float:
    score = 35.0
    for token in ("推荐", "哪家好", "价格", "报价", "费用", "排名", "公司", "维修", "装修", "保养", "附近", "电话"):
        if token in keyword:
            score += 8
    return min(score, 100.0)


def _local_score(keyword: str) -> float:
    score = 45.0
    for token in ("福州", "厦门", "杭州", "广州", "深圳", "上海", "北京", "附近", "本地", "同城"):
        if token in keyword:
            score += 14
    return min(score, 100.0)


def _reason(keyword: str, trend_score: float, commercial_score: float, local_score: float) -> str:
    parts = []
    if trend_score >= 60:
        parts.append("趋势热度较好")
    if commercial_score >= 70:
        parts.append("商业意图明显")
    if local_score >= 70:
        parts.append("本地 GEO 属性强")
    if not parts:
        parts.append("可作为补充选题观察")
    return "，".join(parts)
