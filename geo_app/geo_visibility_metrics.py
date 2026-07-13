from __future__ import annotations

from collections import defaultdict
from typing import Any

from .brand_normalizer import brand_key
from .sentiment_scoring import average_sentiment, score_text_sentiment


def build_prompt_visibility_rows(results: list[Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    own_keys = _own_alias_keys(profile)
    own_display = profile.get("brand_name") or profile.get("product_name") or ""
    for result in results:
        raw = result if isinstance(result, dict) else (getattr(result, "raw", {}) or {})
        parsed = raw.get("parsed") if isinstance(raw.get("parsed"), dict) else getattr(result, "parsed", None)
        if not isinstance(parsed, dict):
            parsed = raw.get("parsed") if isinstance(raw.get("parsed"), dict) else {}
        recommendations = parsed.get("recommendations") if isinstance(parsed.get("recommendations"), list) else []
        question = raw.get("question") or parsed.get("question") or getattr(result, "question", "")
        answer = str(parsed.get("answer") or raw.get("content") or "")
        brand_position = None
        reason_texts = [answer]
        co_brands: list[str] = []
        citation_urls: list[str] = []
        for idx, rec in enumerate(recommendations or [], start=1):
            if not isinstance(rec, dict):
                continue
            brand = str(rec.get("brand_name") or rec.get("name") or "").strip()
            rank = _safe_int(rec.get("rank")) or idx
            if brand:
                co_brands.append(brand)
            if rec.get("reason"):
                reason_texts.append(str(rec.get("reason") or ""))
            for url in rec.get("citation_urls") or []:
                if isinstance(url, str) and url.startswith("http"):
                    citation_urls.append(url)
            if brand_key(brand) in own_keys and brand_position is None:
                brand_position = rank
        sentiment = score_text_sentiment(" ".join(reason_texts))
        rows.append(
            {
                "prompt": question,
                "prompt_type": raw.get("prompt_type", "") if isinstance(result, dict) else getattr(result, "prompt_type", raw.get("prompt_type", "")),
                "intent": raw.get("intent", "") if isinstance(result, dict) else getattr(result, "intent", raw.get("intent", "")),
                "provider": raw.get("provider", "") if isinstance(result, dict) else getattr(result, "provider", raw.get("provider", "")),
                "ok": bool(raw.get("ok", False) if isinstance(result, dict) else getattr(result, "ok", raw.get("ok", False))),
                "error": raw.get("error", "") if isinstance(result, dict) else getattr(result, "error", raw.get("error", "")),
                "brand_name": own_display,
                "brand_mentioned": brand_position is not None,
                "brand_position": brand_position,
                "sentiment_score": sentiment["sentiment_score"] if brand_position is not None else 50,
                "sentiment_label": sentiment["sentiment_label"] if brand_position is not None else "neutral",
                "positive_terms": sentiment["positive_terms"] if brand_position is not None else [],
                "risk_terms": sentiment["risk_terms"] if brand_position is not None else [],
                "co_occurring_brands": list(dict.fromkeys(co_brands))[:10],
                "citation_urls": list(dict.fromkeys(citation_urls))[:10],
                "answer_excerpt": answer[:500],
            }
        )
    return rows


def build_brand_visibility_metrics(recommendation_items: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    own_keys = _own_alias_keys(profile)
    grouped: dict[str, dict[str, Any]] = {}
    ranks: defaultdict[str, list[int]] = defaultdict(list)
    providers: defaultdict[str, set[str]] = defaultdict(set)
    prompts: defaultdict[str, set[str]] = defaultdict(set)
    reasons: defaultdict[str, list[str]] = defaultdict(list)

    for item in recommendation_items:
        brand = str(item.get("brand_name") or "").strip()
        key = brand_key(brand)
        if not key:
            continue
        if key in own_keys:
            brand = profile.get("brand_name") or profile.get("product_name") or brand
            key = brand_key(brand)
        grouped.setdefault(key, {"brand_name": brand, "brand_key": key, "is_user_brand": key in own_keys or brand_key(brand) in own_keys})
        ranks[key].append(_safe_int(item.get("rank")) or 99)
        providers[key].add(str(item.get("engine") or ""))
        prompts[key].add(str(item.get("question") or item.get("trend_term") or ""))
        if item.get("reason"):
            reasons[key].append(str(item.get("reason") or ""))

    total_mentions = sum(len(values) for values in ranks.values()) or 1
    rows: list[dict[str, Any]] = []
    for key, meta in grouped.items():
        mention_count = len(ranks[key])
        avg_position = round(sum(ranks[key]) / mention_count, 2) if mention_count else None
        sentiment = score_text_sentiment(" ".join(reasons[key]))
        rows.append(
            {
                **meta,
                "mention_count": mention_count,
                "avg_position": avg_position,
                "provider_coverage_count": len([item for item in providers[key] if item]),
                "prompt_coverage_count": len([item for item in prompts[key] if item]),
                "sentiment_score": sentiment["sentiment_score"],
                "sentiment_label": sentiment["sentiment_label"],
                "positive_terms": sentiment["positive_terms"],
                "risk_terms": sentiment["risk_terms"],
                "share_of_voice": round(mention_count / total_mentions, 4),
            }
        )
    rows.sort(key=lambda item: (-item["mention_count"], float(item["avg_position"] or 99), item["brand_name"]))
    for idx, row in enumerate(rows, start=1):
        row["visibility_rank"] = idx
    return rows


def build_provider_visibility_matrix(recommendation_items: list[dict[str, Any]], limit: int = 20) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    ranks: defaultdict[tuple[str, str], list[int]] = defaultdict(list)
    for item in recommendation_items:
        provider = str(item.get("engine") or "")
        brand = str(item.get("brand_name") or "").strip()
        if not provider or not brand:
            continue
        key = (provider, brand)
        grouped.setdefault(key, {"provider": provider, "brand_name": brand})
        ranks[key].append(_safe_int(item.get("rank")) or 99)
    rows = []
    for key, meta in grouped.items():
        values = ranks[key]
        rows.append(
            {
                **meta,
                "mention_count": len(values),
                "avg_position": round(sum(values) / len(values), 2) if values else None,
                "recommendation_heat": sum(max(1, 11 - rank) for rank in values),
            }
        )
    rows.sort(key=lambda item: (-item["mention_count"], item["provider"], item["brand_name"]))
    return rows[:limit * 4]


def build_geo_visibility_summary(data: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    prompt_rows = data.get("prompt_runs") or []
    brand_metrics = data.get("brand_visibility_metrics") or []
    provider_total = len({row.get("provider") for row in prompt_rows if row.get("provider")}) or len(
        {item.get("engine") for item in data.get("recommendation_items") or [] if item.get("engine")}
    )
    total_ai_responses = len([row for row in prompt_rows if row.get("ok")]) or len(prompt_rows)
    brand_rows = [row for row in prompt_rows if row.get("brand_mentioned")]
    unique_prompts = {row.get("prompt") for row in prompt_rows if row.get("prompt")}
    successful_prompts = {row.get("prompt") for row in brand_rows if row.get("prompt")}
    own_metric = next((item for item in brand_metrics if item.get("is_user_brand")), {})

    positions = [_safe_int(row.get("brand_position")) for row in brand_rows if _safe_int(row.get("brand_position"))]
    provider_coverage = len({row.get("provider") for row in brand_rows if row.get("provider")})
    visibility_score = round((len(brand_rows) / total_ai_responses) * 100, 1) if total_ai_responses else 0.0
    if visibility_score >= 70:
        level = "high"
    elif visibility_score >= 40:
        level = "medium"
    else:
        level = "low"

    return {
        "visibility_score": visibility_score,
        "visibility_level": level,
        "total_ai_responses": total_ai_responses,
        "brand_mentioned_responses": len(brand_rows),
        "mention_count": own_metric.get("mention_count", len(brand_rows)),
        "avg_position": round(sum(positions) / len(positions), 2) if positions else None,
        "sentiment_score": average_sentiment([row.get("answer_excerpt") for row in brand_rows]),
        "prompt_success_rate": round(len(successful_prompts) / len(unique_prompts), 4) if unique_prompts else 0.0,
        "successful_prompt_count": len(successful_prompts),
        "prompt_count": len(unique_prompts),
        "provider_coverage_count": provider_coverage,
        "provider_total_count": provider_total,
        "share_of_voice": own_metric.get("share_of_voice", 0),
    }


def build_visibility_metric_bundle(
    recommendation_results: list[Any],
    recommendation_items: list[dict[str, Any]],
    profile: dict[str, Any],
) -> dict[str, Any]:
    prompt_rows = build_prompt_visibility_rows(recommendation_results, profile)
    brand_metrics = build_brand_visibility_metrics(recommendation_items, profile)
    provider_matrix = build_provider_visibility_matrix(recommendation_items)
    summary = build_geo_visibility_summary(
        {"prompt_runs": prompt_rows, "brand_visibility_metrics": brand_metrics, "recommendation_items": recommendation_items},
        profile,
    )
    return {
        "prompt_runs": prompt_rows,
        "brand_visibility_metrics": brand_metrics,
        "provider_visibility_matrix": provider_matrix,
        "geo_visibility_summary": summary,
    }


def _own_alias_keys(profile: dict[str, Any]) -> set[str]:
    return {
        brand_key(value)
        for value in [profile.get("brand_name"), profile.get("product_name"), *(profile.get("brand_aliases") or [])]
        if value
    }


def _safe_int(value: Any) -> int:
    try:
        if value in (None, "", "None"):
            return 0
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return 0
