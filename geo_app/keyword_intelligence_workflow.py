from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import asdict
from typing import Any, Callable

from .brand_normalizer import brand_key
from .client_5118 import Client5118
from .config import AppConfig
from .keyword_intelligence import KeywordMetric, KeywordSuggestion


ProgressFn = Callable[[str], None]


ZH_CATEGORY_SEEDS: list[tuple[tuple[str, ...], list[str]]] = [
    (("医美", "医疗美容", "整形", "美容医院"), ["医美", "医疗美容", "美容医院", "整形医院", "双眼皮", "隆鼻", "皮肤管理"]),
    (("口腔", "牙科", "看牙", "种植牙", "牙齿"), ["口腔医院", "牙科医院", "看牙哪家好", "种植牙", "牙齿矫正", "儿童口腔"]),
    (("奶茶", "茶饮", "饮品"), ["奶茶品牌", "奶茶推荐", "奶茶店", "奶茶加盟", "茶饮品牌"]),
    (("火锅",), ["火锅推荐", "火锅店", "火锅哪家好", "特色火锅"]),
    (("洗发水", "护发", "防脱"), ["洗发水推荐", "防脱洗发水", "控油洗发水", "去屑洗发水"]),
    (("耳机", "音频"), ["耳机推荐", "蓝牙耳机推荐", "降噪耳机推荐"]),
    (("法律", "律师", "法务"), ["法律咨询", "律师事务所", "法律顾问", "律师推荐"]),
    (("保健品", "营养品"), ["保健品推荐", "营养品推荐", "保健品品牌"]),
    (("汽车零部件", "汽车配件", "auto parts"), ["汽车零部件购买网站", "汽车配件购买网站", "汽车配件推荐"]),
]

COMMERCIAL_INTENT_TERMS = ["推荐", "哪家好", "排名", "排行", "价格", "多少钱", "口碑", "品牌", "医院", "机构", "购买", "加盟"]
NOISE_TERMS = ["招聘", "地址电话", "电话", "怎么走", "营业时间", "地图", "团购", "优惠券"]


def run_5118_keyword_intelligence(
    config: AppConfig,
    profile: dict[str, Any],
    report_language: str = "zh",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    keyword_config = getattr(config, "keyword_intelligence", None)
    if not keyword_config or not getattr(keyword_config, "enable_5118", True):
        return {"enabled": False, "status": "disabled", "source": "5118"}
    if not _is_domestic_zh(profile, report_language):
        return {
            "enabled": False,
            "status": "skipped",
            "source": "5118",
            "reason": "5118 is used only for Chinese/domestic keyword demand in the current workflow.",
        }

    longtail_key = getattr(keyword_config, "api_5118_longtail_v2", "") or ""
    kw_param_key = getattr(keyword_config, "api_5118_kw_param_v2", "") or ""
    suggest_key = getattr(keyword_config, "api_5118_suggest", "") or ""
    if not longtail_key and not kw_param_key and not suggest_key:
        return {
            "enabled": True,
            "status": "missing_keys",
            "source": "5118",
            "reason": "Missing API_5118_LONGTAIL_V2 / API_5118_KW_PARAM_V2 / API_5118_SUGGEST.",
            "seed_terms": build_seed_terms(profile, max_terms=getattr(keyword_config, "max_seed_terms", 9)),
        }

    client = Client5118(timeout_seconds=int(getattr(keyword_config, "timeout_seconds", 30) or 30))
    seed_terms = build_seed_terms(profile, max_terms=int(getattr(keyword_config, "max_seed_terms", 9) or 9))
    result: dict[str, Any] = {
        "enabled": True,
        "status": "ok",
        "source": "5118",
        "seed_terms": seed_terms,
        "longtail": [],
        "suggest": [],
        "keyword_metrics": [],
        "ranked_terms": [],
        "neutral_prompt_candidates": [],
        "competitor_or_brand_candidates": [],
        "errors": [],
    }

    interval = float(getattr(keyword_config, "request_interval_seconds", 1.2) or 0)
    page_size = int(getattr(keyword_config, "longtail_page_size", 10) or 10)

    if longtail_key:
        for seed in seed_terms:
            if progress:
                progress(f"调用 5118 长尾词：{seed}")
            try:
                rows = client.longtail_keywords(seed, page_size=page_size, api_key=longtail_key)
                result["longtail"].append({"seed": seed, "count": len(rows), "items": [_metric_dict(item) for item in rows]})
            except Exception as exc:
                _append_error(result, "longtail", seed, exc)
            _sleep(interval)

    if kw_param_key:
        try:
            if progress:
                progress("调用 5118 关键词搜索量信息")
            taskid = client.submit_keyword_params(seed_terms, api_key=kw_param_key)
            result["keyword_param_taskid"] = taskid
            for attempt in range(1, 4):
                _sleep(2 if attempt == 1 else max(8, interval))
                try:
                    rows = client.get_keyword_params(taskid, api_key=kw_param_key)
                    result["keyword_metrics"] = [_metric_dict(item) for item in rows]
                    result["keyword_param_attempts"] = attempt
                    break
                except Exception as exc:
                    _append_error(result, "keyword_param_poll", f"attempt={attempt}", exc)
        except Exception as exc:
            _append_error(result, "keyword_param_submit", "|".join(seed_terms), exc)

    if getattr(keyword_config, "enable_suggest", False) and suggest_key:
        for seed in seed_terms[:4]:
            try:
                rows = client.suggest_words(seed, platform="baidu", api_key=suggest_key)
                result["suggest"].append({"seed": seed, "count": len(rows), "items": [_suggestion_dict(item) for item in rows]})
            except Exception as exc:
                _append_error(result, "suggest", seed, exc)
            _sleep(max(interval, 3.0))

    ranked_terms = _rank_terms(result, profile)
    result["ranked_terms"] = ranked_terms[:60]
    result["neutral_prompt_candidates"] = [item for item in ranked_terms if item.get("classification") == "neutral"][:20]
    result["competitor_or_brand_candidates"] = [item for item in ranked_terms if item.get("classification") == "brand_or_competitor"][:20]
    if not result["longtail"] and not result["keyword_metrics"] and not result["suggest"]:
        result["status"] = "no_data"
    return result


def build_seed_terms(profile: dict[str, Any], max_terms: int = 9) -> list[str]:
    region = str(profile.get("primary_region") or profile.get("service_region") or "").strip()
    category = str(profile.get("category_local") or profile.get("geo_probe_subject") or profile.get("category_en") or "").strip()
    own = str(profile.get("brand_name") or profile.get("product_name") or "").strip()

    seeds: list[str] = []
    if own:
        seeds.append(_with_region(region, own))
        seeds.append(own)

    category_seeds = _category_seed_phrases(category)
    if not category_seeds and category:
        category_seeds = [category]
    if region:
        seeds.extend(_with_region(region, item) for item in category_seeds)
    seeds.extend(category_seeds)

    subject = str(profile.get("geo_probe_subject") or "").strip()
    if subject:
        seeds.append(subject)

    return _unique_terms([_clean_term(item) for item in seeds if item], max_terms)


def build_keyword_prompt_items(keyword_intelligence: dict[str, Any], profile: dict[str, Any], limit: int) -> list[dict[str, str]]:
    rows = keyword_intelligence.get("neutral_prompt_candidates") or []
    questions: list[dict[str, str]] = []
    for row in rows:
        keyword = str(row.get("keyword") or "").strip()
        question = question_from_keyword(keyword, profile)
        if not question or _contains_own_brand(question, profile):
            continue
        questions.append(
            {
                "question": question,
                "prompt_type": "neutral_recommendation",
                "intent": "real_user_keyword_demand",
                "reason": f"来自 5118 真实用户搜索词：{keyword}；长尾词数 {row.get('longtail_count', 0)}，竞价公司数 {row.get('bid_company_count', 0)}，SEM参考 {row.get('sem_price', '')}",
                "keyword_source": "5118",
                "source_keyword": keyword,
            }
        )
        if len(questions) >= limit:
            break
    return questions


def question_from_keyword(keyword: str, profile: dict[str, Any]) -> str:
    keyword = _clean_term(keyword)
    if not keyword:
        return ""
    if any(term in keyword for term in ("哪家好", "排名", "排行")):
        return f"{keyword}？"
    if "双眼皮" in keyword:
        region = _extract_region(profile, keyword)
        return f"{region}做双眼皮哪家医院比较推荐？" if region else f"{keyword}哪家比较推荐？"
    if "隆鼻" in keyword:
        region = _extract_region(profile, keyword)
        return f"{region}隆鼻哪家机构比较靠谱？" if region else f"{keyword}哪家比较靠谱？"
    if "种植牙" in keyword:
        region = _extract_region(profile, keyword)
        return f"{region}种植牙哪家医院比较靠谱？" if region else f"{keyword}哪家比较靠谱？"
    if "牙齿矫正" in keyword:
        region = _extract_region(profile, keyword)
        return f"{region}牙齿矫正哪家机构口碑好？" if region else f"{keyword}哪家口碑好？"
    if any(term in keyword for term in ("医院", "机构", "中心", "店", "品牌", "网站")):
        return f"{keyword}哪家比较好？"
    return f"推荐一下{keyword}"


def _rank_terms(result: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    source_map: defaultdict[str, set[str]] = defaultdict(set)
    for block in result.get("longtail") or []:
        seed = str(block.get("seed") or "")
        for item in block.get("items") or []:
            keyword = str(item.get("keyword") or "").strip()
            if not keyword:
                continue
            row = grouped.setdefault(keyword, {"keyword": keyword})
            source_map[keyword].add(seed)
            _merge_metric(row, item)
    for item in result.get("keyword_metrics") or []:
        keyword = str(item.get("keyword") or "").strip()
        if not keyword:
            continue
        row = grouped.setdefault(keyword, {"keyword": keyword})
        source_map[keyword].add("keyword_param")
        _merge_metric(row, item)

    rows = []
    for keyword, row in grouped.items():
        row["sources"] = sorted(source_map[keyword])
        row["is_own_brand"] = _contains_own_brand(keyword, profile)
        row["is_noise"] = _is_noise(keyword)
        row["is_brand_like"] = _is_competitor_or_brand_keyword(keyword, profile)
        row["is_category_relevant"] = _is_category_relevant(keyword, profile)
        row["score"] = _keyword_score(row)
        if row["is_noise"] or not row["is_category_relevant"]:
            row["classification"] = "excluded"
        elif row["is_own_brand"] or row["is_brand_like"]:
            row["classification"] = "brand_or_competitor"
        else:
            row["classification"] = "neutral"
        rows.append(row)
    rows.sort(key=lambda item: (-int(item.get("score") or 0), -int(item.get("longtail_count") or 0), item.get("keyword", "")))
    return rows


def _merge_metric(target: dict[str, Any], source: dict[str, Any]) -> None:
    for field in (
        "pc_index",
        "mobile_index",
        "so360_index",
        "douyin_index",
        "toutiao_index",
        "daily_pc_search",
        "daily_mobile_search",
        "longtail_count",
        "bid_company_count",
    ):
        target[field] = max(int(target.get(field) or 0), int(source.get(field) or 0))
    if source.get("sem_price") and not target.get("sem_price"):
        target["sem_price"] = source.get("sem_price")


def _keyword_score(row: dict[str, Any]) -> int:
    score = (
        int(row.get("pc_index") or 0) * 3
        + int(row.get("mobile_index") or 0) * 3
        + int(row.get("daily_pc_search") or 0) * 2
        + int(row.get("daily_mobile_search") or 0) * 2
        + min(int(row.get("longtail_count") or 0), 30000) // 20
        + int(row.get("bid_company_count") or 0) * 2
    )
    keyword = str(row.get("keyword") or "")
    if any(term in keyword for term in COMMERCIAL_INTENT_TERMS):
        score += 20
    return score


def _category_seed_phrases(category: str) -> list[str]:
    lower = category.lower()
    for triggers, seeds in ZH_CATEGORY_SEEDS:
        if any(trigger.lower() in lower or trigger in category for trigger in triggers):
            return seeds
    return [category] if category else []


def _is_category_relevant(keyword: str, profile: dict[str, Any]) -> bool:
    text = str(keyword or "")
    category = str(profile.get("category_local") or profile.get("geo_probe_subject") or profile.get("category_en") or "")
    seeds = _category_seed_phrases(category)
    tokens = set()
    for seed in seeds:
        tokens.add(seed)
        for part in ("推荐", "哪家好", "排名", "排行", "价格", "多少钱"):
            tokens.add(seed.replace(part, ""))
    category_compact = category.replace("推荐", "").replace("品牌", "").strip()
    if category_compact:
        tokens.add(category_compact)
    return any(token and token in text for token in tokens)


def _is_competitor_or_brand_keyword(keyword: str, profile: dict[str, Any]) -> bool:
    text_key = brand_key(keyword)
    for term in profile.get("known_competitor_hints") or []:
        key = brand_key(term)
        if key and (key in text_key or text_key in key):
            return True
    # Organization names with a specific non-category name before the category are usually competitor leads.
    category_words = ["医美", "医疗美容", "整形", "美容医院", "口腔", "牙科", "律师", "火锅", "奶茶"]
    generic_prefixes = ["福州", "北京", "上海", "广州", "深圳", "重庆", "杭州", "成都", "南京", "厦门", "台江", "鼓楼"]
    clean = str(keyword or "")
    if any(word in clean for word in category_words):
        stripped = clean
        for prefix in generic_prefixes:
            stripped = stripped.replace(prefix, "")
        for word in category_words:
            stripped = stripped.replace(word, "")
        stripped = stripped.replace("医院", "").replace("机构", "").replace("中心", "").replace("哪家好", "").replace("排名", "").strip()
        return len(stripped) >= 2
    return False


def _is_noise(keyword: str) -> bool:
    return any(term in str(keyword or "") for term in NOISE_TERMS)


def _contains_own_brand(text: str, profile: dict[str, Any]) -> bool:
    text_key = brand_key(text)
    for term in [profile.get("brand_name"), profile.get("product_name"), *(profile.get("brand_aliases") or [])]:
        key = brand_key(term)
        if key and (key in text_key or text_key in key):
            return True
    return False


def _is_domestic_zh(profile: dict[str, Any], report_language: str) -> bool:
    market_language = str(profile.get("market_language") or "").lower()
    target_market = str(profile.get("target_market") or "").lower()
    if report_language != "zh" and market_language.startswith("en"):
        return False
    if target_market in {"overseas", "global", "international"}:
        return False
    return True


def _extract_region(profile: dict[str, Any], keyword: str) -> str:
    region = str(profile.get("primary_region") or "").strip()
    if region and region in keyword:
        return region
    return region


def _with_region(region: str, term: str) -> str:
    term = str(term or "").strip()
    region = str(region or "").strip()
    if not region or region in term:
        return term
    return f"{region}{term}"


def _clean_term(value: Any) -> str:
    return " ".join(str(value or "").replace("_", " ").split()).strip()


def _unique_terms(items: list[str], limit: int) -> list[str]:
    result = []
    seen = set()
    for item in items:
        clean = _clean_term(item)
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def _metric_dict(item: KeywordMetric) -> dict[str, Any]:
    return asdict(item)


def _suggestion_dict(item: KeywordSuggestion) -> dict[str, Any]:
    return asdict(item)


def _append_error(result: dict[str, Any], stage: str, seed: str, exc: Exception) -> None:
    result.setdefault("errors", []).append({"stage": stage, "seed": seed, "error": str(exc)})


def _sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
