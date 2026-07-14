from __future__ import annotations

import json
import re
from collections import defaultdict
from typing import Any, Callable

from .brand_normalizer import brand_key, canonicalize_brand_name
from .config import AppConfig
from .geo_visibility_metrics import build_visibility_metric_bundle
from .keyword_intelligence_workflow import build_keyword_prompt_items, run_5118_keyword_intelligence
from .multi_ai_clients import build_default_providers
from .product_ingestion import collect_website_pages
from .qwen_client import QwenClient
from .topic_analysis import derive_content_topic_analysis
from .utils import domain_from_url, extract_json


ProgressFn = Callable[[str], None]


def run_multi_ai_geo_competition(
    config: AppConfig,
    profile: dict[str, Any],
    report_language: str = "zh",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    recommendation_question = build_recommendation_question(profile)
    prompt_count = max(1, int(getattr(config.geo_ai, "prompt_count", 5) or 5))
    diagnostic_count = max(0, int(getattr(config.geo_ai, "brand_diagnostic_prompt_count", 3) or 0))
    comparison_count = max(0, int(getattr(config.geo_ai, "comparison_prompt_count", 2) or 0))
    recommendations_per_prompt = max(3, int(getattr(config.geo_ai, "recommendations_per_prompt", 10) or 10))
    prompt_groups = build_prompt_groups(
        config,
        profile,
        recommendation_question,
        report_language,
        prompt_count,
        diagnostic_count,
        progress,
    )
    keyword_intelligence = prompt_groups.pop("_keyword_intelligence", {}) if isinstance(prompt_groups, dict) else {}
    prompt_questions = [item["question"] for item in prompt_groups["neutral_recommendation"]]
    diagnostic_questions = [item["question"] for item in prompt_groups["brand_diagnostic"]]
    if progress:
        progress(
            f"多 AI 中立推荐问题组：{len(prompt_questions)} 个问题；"
            f"品牌诊断问题：{len(diagnostic_questions)} 个；每题最多返回 {recommendations_per_prompt} 个品牌"
        )

    providers = build_default_providers(config.qwen)
    recommendation_results = []
    total_calls = len(prompt_questions) * len(providers)
    call_idx = 0
    for prompt_item in prompt_groups["neutral_recommendation"]:
        question = prompt_item["question"]
        for provider in providers:
            call_idx += 1
            if progress:
                progress(f"调用 {provider.name} 获取中立推荐排名 {call_idx}/{total_calls}：{question}")
            recommendation_results.append(
                _ask_recommendations(
                    provider,
                    profile,
                    question,
                    report_language,
                    recommendations_per_prompt,
                    prompt_type="neutral_recommendation",
                    intent=prompt_item.get("intent", "mainstream_recommendation"),
                )
            )

    recommendation_items = _flatten_recommendations(recommendation_results, profile)
    ai_ranking = _build_multi_ai_ranking(recommendation_items, profile)
    metric_bundle = build_visibility_metric_bundle(recommendation_results, recommendation_items, profile)
    top_brands = _top_brand_pool(ai_ranking, profile, limit=max(3, int(getattr(config.geo_ai, "visibility_brand_limit", 10) or 10)))
    competitor_discovery = _competitor_discovery_from_ranking(ai_ranking, profile)
    source_links = _collect_source_links(recommendation_results, recommendation_items, limit=int(getattr(config.geo_ai, "source_link_limit", 80) or 80))

    diagnostic_results = []
    diagnostic_items: list[dict[str, Any]] = []
    diagnostic_metric_bundle = build_visibility_metric_bundle([], [], profile)
    if diagnostic_questions:
        total_diag_calls = len(diagnostic_questions) * len(providers)
        diag_idx = 0
        for prompt_item in prompt_groups["brand_diagnostic"]:
            question = prompt_item["question"]
            for provider in providers:
                diag_idx += 1
                if progress:
                    progress(f"调用 {provider.name} 获取品牌诊断 {diag_idx}/{total_diag_calls}：{question}")
                diagnostic_results.append(
                    _ask_recommendations(
                        provider,
                        profile,
                        question,
                        report_language,
                        recommendations_per_prompt,
                        prompt_type="brand_diagnostic",
                        intent=prompt_item.get("intent", "brand_reputation"),
                    )
                )
        diagnostic_items = _flatten_recommendations(diagnostic_results, profile)
        diagnostic_metric_bundle = build_visibility_metric_bundle(diagnostic_results, diagnostic_items, profile)

    comparison_prompt_items = build_comparison_prompt_set(profile, top_brands, report_language, comparison_count)
    prompt_groups["comparison"] = comparison_prompt_items
    comparison_questions = [item["question"] for item in comparison_prompt_items]
    comparison_results = []
    comparison_items: list[dict[str, Any]] = []
    comparison_metric_bundle = build_visibility_metric_bundle([], [], profile)
    if comparison_questions:
        total_cmp_calls = len(comparison_questions) * len(providers)
        cmp_idx = 0
        for prompt_item in comparison_prompt_items:
            question = prompt_item["question"]
            for provider in providers:
                cmp_idx += 1
                if progress:
                    progress(f"调用 {provider.name} 获取竞品直接对比 {cmp_idx}/{total_cmp_calls}：{question}")
                comparison_results.append(
                    _ask_recommendations(
                        provider,
                        profile,
                        question,
                        report_language,
                        recommendations_per_prompt,
                        prompt_type="comparison",
                        intent=prompt_item.get("intent", "direct_comparison"),
                    )
                )
        comparison_items = _flatten_recommendations(comparison_results, profile)
        comparison_metric_bundle = build_visibility_metric_bundle(comparison_results, comparison_items, profile)

    if progress:
        progress("调用 Qwen/元宝/豆包/DeepSeek 估算传统搜索和新媒体内容声量")
    visibility_results = []
    visibility_prompt = build_visibility_prompt(top_brands, profile, report_language)
    for provider in providers:
        if progress:
            progress(f"调用 {provider.name} 估算品牌声量")
        visibility_results.append(_ask_visibility(provider, profile, top_brands, visibility_prompt, report_language))

    provider_status = _provider_status(recommendation_results + diagnostic_results + comparison_results, visibility_results)
    search_volume_ranking = _aggregate_visibility(visibility_results, top_brands, profile)
    search_visibility_ranking = _search_visibility_from_volume(search_volume_ranking)
    competitive_gap_ranking = _build_gap(ai_ranking, search_visibility_ranking)

    if progress:
        progress("抓取 AI 返回的文章链接正文")
    source_articles = _collect_source_articles(source_links, progress, limit=int(getattr(config.geo_ai, "article_fetch_limit", 40) or 40))

    if progress:
        progress("调用 Qwen 提炼各品牌文章宣传重点")
    content_analysis = _extract_content_features_with_qwen(config, profile, top_brands, source_articles, recommendation_items, report_language)
    content_report = content_analysis.get("markdown_report") or _fallback_content_report(top_brands, recommendation_items, source_articles)
    topic_analysis = derive_content_topic_analysis(
        recommendation_items,
        source_articles,
        content_report,
        topic_taxonomy=_default_topic_taxonomy(profile),
    )

    question_discovery = {
        "source_language": profile.get("source_language") or profile.get("market_language") or "",
        "market_language": profile.get("market_language") or ("zh" if report_language == "zh" else "en"),
        "target_market": profile.get("target_market") or "",
        "primary_region": profile.get("primary_region") or "",
        "region_level": profile.get("region_level") or "",
        "business_type": profile.get("business_type") or "",
        "geo_probe_subject": _probe_subject(profile),
        "business_type_reason": "Generated by multi-AI GEO flow with separated neutral, diagnostic, and comparison prompts.",
        "market_reason": profile.get("market_reason") or "",
        "questions": [
            {
                "term": question,
                "question": question,
                "intent": profile.get("geo_audience") or "mainstream_recommendation",
                "question_type": "neutral_recommendation",
                "prompt_type": "neutral_recommendation",
                "reason": "中立推荐问题，用于 Qwen、豆包、元宝、DeepSeek 主排名；不包含客户品牌名。",
            }
            for question in prompt_questions
        ],
        "neutral_search_queries": prompt_questions,
        "brand_diagnostic_questions": diagnostic_questions,
        "comparison_questions": comparison_questions,
        "prompt_groups": prompt_groups,
        "keyword_intelligence": keyword_intelligence,
    }
    question_discovery["prompt_generation"] = {
        "prompt_count": len(prompt_questions),
        "brand_diagnostic_prompt_count": len(diagnostic_questions),
        "comparison_prompt_count": len(comparison_questions),
        "configured_prompt_count": prompt_count,
        "configured_brand_diagnostic_prompt_count": diagnostic_count,
        "configured_comparison_prompt_count": comparison_count,
        "ai_prompt_discovery_enabled": bool(getattr(config.geo_ai, "enable_ai_prompt_discovery", True)),
        "recommendations_per_prompt": recommendations_per_prompt,
    }
    analysis_strategy = {
        "strategy_version": "multi_ai_consensus_v1",
        "market_language": question_discovery["market_language"],
        "target_market": question_discovery["target_market"],
        "service_scope": profile.get("service_scope") or "",
        "service_region": profile.get("primary_region") or "",
        "business_type": profile.get("business_type") or "",
        "geo_audience": profile.get("geo_audience") or profile.get("analysis_goal") or "mixed",
        "analysis_goal": profile.get("analysis_goal") or profile.get("geo_audience") or "mixed",
        "category_local": profile.get("category_local") or "",
        "category_en": profile.get("category_en") or "",
        "geo_probe_subject": _probe_subject(profile),
        "mainstream_competition_only": True,
        "multi_ai_providers": [item.provider for item in recommendation_results],
        "recommendation_question": recommendation_question,
        "recommendation_questions": prompt_questions,
        "brand_diagnostic_questions": diagnostic_questions,
        "comparison_questions": comparison_questions,
        "search_intents": [
            {
                "intent": "multi_ai_mainstream_recommendation",
                "neutral_queries": prompt_questions,
                "ai_probe_question": recommendation_question,
                "reason": "Prompt group uses mainstream user questions across multiple AI models.",
            }
        ],
        "neutral_search_queries": prompt_questions,
        "ai_probe_questions": question_discovery["questions"],
        "prompt_groups": prompt_groups,
        "keyword_intelligence": keyword_intelligence,
        "competitor_types": ["multi_ai_recommended"],
        "topic_taxonomy": _default_topic_taxonomy(profile),
        "validation_notes": [
            "主排名只使用不含客户品牌名的中立推荐问题；品牌诊断和竞品直接对比单独展示，不参与主推荐排名。",
            "声量数据由 AI 估算，字段使用 estimated_count，不等同于真实平台接口统计。",
        ],
    }
    trend_discovery = {
        "terms": [{"term": question, "source": "multi_ai_prompt_group", "relevance_reason": "主流 GEO 推荐问题"} for question in prompt_questions],
        "probe_questions": question_discovery["questions"],
        "fallback_used": False,
    }
    visibility_query_strategy = {
        "strategy_version": "multi_ai_visibility_estimate_v1",
        "visibility_prompt": visibility_prompt,
        "visibility_queries": [
            {
                "brand_name": item["brand_name"],
                "brand_key": item["brand_key"],
                "query": f"{item['brand_name']} 百度 搜狗 360 抖音 小红书 内容声量",
                "metric_goal": "AI estimated traditional search and new media content volume",
                "is_user_brand": item.get("is_user_brand", False),
            }
            for item in top_brands
        ],
    }
    article_format = _build_article_format(profile, recommendation_question, content_report, report_language)

    return {
        "analysis_strategy": analysis_strategy,
        "competitor_discovery": competitor_discovery,
        "question_discovery": question_discovery,
        "keyword_intelligence": keyword_intelligence,
        "trend_discovery": trend_discovery,
        "multi_ai_recommendation_results": [item.raw for item in recommendation_results],
        "brand_diagnostic_results": [item.raw for item in diagnostic_results],
        "brand_diagnostic_items": diagnostic_items,
        "brand_diagnostic_prompt_runs": diagnostic_metric_bundle["prompt_runs"],
        "brand_diagnostic_brand_metrics": diagnostic_metric_bundle["brand_visibility_metrics"],
        "brand_diagnostic_provider_matrix": diagnostic_metric_bundle["provider_visibility_matrix"],
        "brand_diagnostic_summary": diagnostic_metric_bundle["geo_visibility_summary"],
        "comparison_results": [item.raw for item in comparison_results],
        "comparison_items": comparison_items,
        "comparison_prompt_runs": comparison_metric_bundle["prompt_runs"],
        "comparison_brand_metrics": comparison_metric_bundle["brand_visibility_metrics"],
        "comparison_provider_matrix": comparison_metric_bundle["provider_visibility_matrix"],
        "comparison_summary": comparison_metric_bundle["geo_visibility_summary"],
        "multi_ai_visibility_results": [item.raw for item in visibility_results],
        "multi_ai_provider_status": provider_status,
        "prompt_runs": metric_bundle["prompt_runs"],
        "brand_visibility_metrics": metric_bundle["brand_visibility_metrics"],
        "provider_visibility_matrix": metric_bundle["provider_visibility_matrix"],
        "geo_visibility_summary": metric_bundle["geo_visibility_summary"],
        "neutral_visibility_summary": metric_bundle["geo_visibility_summary"],
        "recommendation_items": recommendation_items,
        "ai_recommendation_ranking": ai_ranking,
        "brand_ranking": ai_ranking,
        "top_brand_pool": top_brands,
        "visibility_query_strategy": visibility_query_strategy,
        "search_volume_ranking": search_volume_ranking,
        "search_volume_queries": [item.raw for item in visibility_results],
        "search_visibility_ranking": search_visibility_ranking,
        "baidu_mentions": search_visibility_ranking,
        "competitive_gap_ranking": competitive_gap_ranking,
        "source_links": source_links,
        "source_articles": source_articles,
        "content_pattern_report": content_report,
        "content_positioning_analysis": content_analysis,
        "content_analysis_meta": {
            "analysis_provider": "qwen",
            "article_total": len(source_articles),
            "article_success_count": len([item for item in source_articles if item.get("text_excerpt") and not item.get("error")]),
            "article_failed_count": len([item for item in source_articles if item.get("error") or not item.get("text_excerpt")]),
        },
        "article_generation_format": article_format,
        "content_topic_analysis": topic_analysis,
    }


def build_recommendation_question(profile: dict[str, Any]) -> str:
    market_language = str(profile.get("market_language") or "").lower()
    category = _category(profile)
    region = str(profile.get("primary_region") or "").strip()
    scope = str(profile.get("service_scope") or "").strip()
    business_type = str(profile.get("business_type") or "").lower()
    is_local = scope in {"local_city", "regional"} or bool(region and region.lower() not in {"global", "unknown"})
    if market_language.startswith("en") or scope == "global":
        if "ecommerce" in business_type or any(word in category.lower() for word in ("parts", "website", "platform")):
            return f"Recommend {category} websites"
        return f"Recommend {category} brands"
    if "ecommerce" in business_type or "购物" in category or "零部件" in category or "配件" in category:
        return f"推荐一下{category}购买网站"
    if is_local and region:
        return f"推荐一下{region}的{category}"
    return f"推荐一下{category}品牌"


def build_prompt_set(
    config: AppConfig,
    profile: dict[str, Any],
    base_question: str,
    report_language: str,
    prompt_count: int,
    progress: ProgressFn | None = None,
) -> list[str]:
    groups = build_prompt_groups(config, profile, base_question, report_language, prompt_count, 0, progress)
    return [item["question"] for item in groups.get("neutral_recommendation") or []]


def build_prompt_groups(
    config: AppConfig,
    profile: dict[str, Any],
    base_question: str,
    report_language: str,
    prompt_count: int,
    diagnostic_count: int,
    progress: ProgressFn | None = None,
) -> dict[str, list[dict[str, str]]]:
    neutral_rows: list[dict[str, str]] = []
    diagnostic_rows: list[dict[str, str]] = []
    keyword_intelligence = run_5118_keyword_intelligence(config, profile, report_language, progress)
    keyword_rows = build_keyword_prompt_items(keyword_intelligence, profile, prompt_count)
    if getattr(config.geo_ai, "enable_ai_prompt_discovery", True):
        try:
            if progress:
                progress(f"调用 Qwen 生成 {prompt_count} 个中立推荐问题和 {diagnostic_count} 个品牌诊断问题")
            qwen = QwenClient(config.qwen)
            language = "中文" if report_language == "zh" else "English"
            own_terms = _own_brand_terms(profile)
            prompt = f"""
请根据产品画像，为 GEO 可见度测试生成两组真实用户会问 AI 的问题。

基础问题：{base_question}
客户品牌/产品黑名单：{json.dumps(own_terms, ensure_ascii=False)}
产品画像：
{json.dumps(_compact_profile_for_prompt(profile), ensure_ascii=False, indent=2)}

要求：
1. neutral_recommendation 只生成主流品类/服务推荐问题，用于统计“AI 会推荐谁”。严禁包含客户品牌、产品名、别名或黑名单中的任何词。
2. neutral_recommendation 不生成长尾特色词，不用非常小众的单品词；本地服务必须包含服务地区。
3. brand_diagnostic 用于分析客户品牌口碑/情绪，可以包含客户品牌名，但不参与主推荐排名。
4. 如果面向国内用户，使用中文；如果面向海外用户，使用英文。
5. 问题要像真实用户向 AI 提问，不要像 SEO 关键词。
6. 返回 JSON，不要 Markdown。

JSON schema:
{{
  "neutral_recommendation": [{{"question": "问题", "intent": "用户意图", "reason": "为什么需要测试这个问题"}}],
  "brand_diagnostic": [{{"question": "问题", "intent": "用户意图", "reason": "为什么需要测试这个问题"}}]
}}

数量要求：
- neutral_recommendation：{prompt_count} 个。
- brand_diagnostic：{diagnostic_count} 个。

输出语言：{language}
"""
            result = qwen._call(
                [{"role": "user", "content": prompt}],
                model=config.qwen.search_model,
                enable_search=False,
            )
            parsed = extract_json(result.content, fallback={})
            if isinstance(parsed, dict):
                neutral_rows = _normalize_prompt_rows(parsed.get("neutral_recommendation") or parsed.get("questions") or [], "neutral_recommendation")
                diagnostic_rows = _normalize_prompt_rows(parsed.get("brand_diagnostic") or [], "brand_diagnostic")
        except Exception as exc:
            if progress:
                progress(f"AI 搜索问题生成失败，使用规则兜底：{exc}")

    neutral_questions = _filter_neutral_questions(
        [*[item["question"] for item in keyword_rows], base_question, *[item["question"] for item in neutral_rows]],
        profile,
        prompt_count,
    )
    if len(neutral_questions) < prompt_count:
        neutral_questions = _unique_questions(
            [
                *neutral_questions,
                *_fallback_prompt_set(profile, base_question, prompt_count, report_language),
            ],
            prompt_count,
        )
    neutral_items = [
        _prompt_item(
            question,
            "neutral_recommendation",
            _prompt_intent_for(question, keyword_rows + neutral_rows) or "mainstream_recommendation",
            _prompt_reason_for(question, keyword_rows + neutral_rows) or "中立主流推荐问题，不包含客户品牌名。",
        )
        for question in neutral_questions[:prompt_count]
    ]
    for item in neutral_items:
        meta = _prompt_meta_for(item["question"], keyword_rows)
        if meta:
            item.update(meta)

    diagnostic_questions = _unique_questions([item["question"] for item in diagnostic_rows], diagnostic_count)
    if len(diagnostic_questions) < diagnostic_count:
        diagnostic_questions = _unique_questions(
            [
                *diagnostic_questions,
                *_fallback_brand_diagnostic_prompt_set(profile, diagnostic_count, report_language),
            ],
            diagnostic_count,
        )
    diagnostic_items = [
        _prompt_item(question, "brand_diagnostic", "brand_reputation", _prompt_reason_for(question, diagnostic_rows) or "品牌诊断问题，用于口碑和情绪分析，不参与主推荐排名。")
        for question in diagnostic_questions[:diagnostic_count]
    ]
    return {
        "neutral_recommendation": neutral_items,
        "brand_diagnostic": diagnostic_items,
        "comparison": [],
        "_keyword_intelligence": keyword_intelligence,
    }


def build_comparison_prompt_set(
    profile: dict[str, Any],
    top_brands: list[dict[str, Any]],
    report_language: str,
    prompt_count: int,
) -> list[dict[str, str]]:
    if prompt_count <= 0:
        return []
    own = str(profile.get("brand_name") or profile.get("product_name") or "").strip()
    if not own:
        return []
    market_language = str(profile.get("market_language") or "").lower()
    category = _category(profile)
    region = str(profile.get("primary_region") or "").strip()
    competitors = [item.get("brand_name", "") for item in top_brands if item.get("brand_name") and not item.get("is_user_brand")]
    rows: list[dict[str, str]] = []
    for competitor in competitors[:prompt_count]:
        if market_language.startswith("en") or report_language == "en":
            question = f"{own} vs {competitor}: which {category} option is better?"
        else:
            prefix = f"{region}" if region and region not in own and region not in str(competitor) else ""
            question = f"{prefix}{own}和{competitor}哪个更值得选？"
        rows.append(_prompt_item(question, "comparison", "direct_competitor_comparison", "基于中立推荐排名选取头部竞品，诊断客户品牌与竞品的直接对比表现。"))
    return rows


def build_visibility_prompt(brands: list[dict[str, Any]], profile: dict[str, Any], report_language: str) -> str:
    language = "中文" if report_language == "zh" else "English"
    brand_names = [item["brand_name"] for item in brands]
    category = _category(profile)
    region = profile.get("primary_region") or ""
    return f"""
请估算以下品牌在传统搜索引擎和新媒体平台的内容声量。

产品类目：{category}
服务地区：{region}
品牌列表：{json.dumps(brand_names, ensure_ascii=False)}

请只返回 JSON，不要输出 Markdown。
要求：
1. 每个品牌都要返回。
2. 传统搜索引擎包括：百度、搜狗、360搜索。
3. 新媒体包括：抖音、小红书。
4. 数量可以是估算，但必须标注 confidence 和 notes。
5. 尽量给出消息来源、参考链接或你判断的依据。
6. 输出语言使用{language}。

JSON schema:
{{
  "brand_visibility": [
    {{
      "brand_name": "品牌名",
      "traditional_search": {{
        "baidu": 0,
        "sogou": 0,
        "so360": 0
      }},
      "new_media": {{
        "douyin": 0,
        "xiaohongshu": 0
      }},
      "source_urls": ["https://..."],
      "confidence": 0.0,
      "notes": "数据依据和不确定性说明"
    }}
  ]
}}
"""


def _ask_recommendations(
    provider: Any,
    profile: dict[str, Any],
    question: str,
    report_language: str,
    max_recommendations: int,
    prompt_type: str = "neutral_recommendation",
    intent: str = "mainstream_recommendation",
) -> Any:
    language = "中文" if report_language == "zh" else "English"
    prompt_profile = _compact_profile_for_prompt(profile)
    prompt_type_instruction = {
        "neutral_recommendation": "这是中立推荐排名测试。只能按用户问题和真实主流竞争格局推荐，不要因为画像里出现被分析品牌就优先推荐它。",
        "brand_diagnostic": "这是品牌诊断测试。允许围绕被分析品牌讨论口碑、风险、优势和竞品共现，但结果不得写入主推荐排名。",
        "comparison": "这是竞品直接对比测试。请公平比较被分析品牌与题目中的竞品，指出优势、弱点和选择场景。",
    }.get(prompt_type, "请按真实普通用户视角回答。")
    prompt = f"""
请像普通用户正在使用 AI 搜索一样回答这个问题：

{question}

被分析品牌画像：
{json.dumps(prompt_profile, ensure_ascii=False, indent=2)}

请只返回 JSON，不要输出 Markdown。
要求：
1. 返回最多 {max_recommendations} 个推荐品牌/商家/网站。
2. 排名必须符合正常用户视角，不要因为被分析品牌在画像里出现就优先推荐它。
3. 如果是本地服务或本地品牌，优先考虑服务地区的真实主流竞争。
4. 不要推荐长尾特色词，只推荐主流品类竞争者。
5. 如有可参考的文章链接、榜单链接、官网链接、媒体链接，请放入 citation_urls。
6. 输出语言使用{language}。
7. {prompt_type_instruction}

JSON schema:
{{
  "question": "{question}",
  "answer": "简短回答",
  "recommendations": [
    {{
      "rank": 1,
      "brand_name": "品牌名",
      "product_name": "具体产品或门店，可为空",
      "reason": "推荐理由",
      "citation_urls": ["https://..."]
    }}
  ]
}}
"""
    result = provider.ask_json(prompt, system="You are a GEO competitor ranking analyst. Return strict JSON.", enable_search=True)
    if not result.ok and result.provider == "doubao":
        result = provider.ask_json(_compact_recommendation_prompt(prompt_profile, question, language), system="Return strict JSON only.", enable_search=False)
    parsed = result.parsed if isinstance(result.parsed, dict) else {}
    recommendations = parsed.get("recommendations") if isinstance(parsed.get("recommendations"), list) else []
    return _Obj(
        provider=result.provider,
        ok=result.ok,
        error=result.error,
        parsed=parsed,
        raw={
            "provider": result.provider,
            "ok": result.ok,
            "error": result.error,
            "model": getattr(provider, "model", ""),
            "endpoint": getattr(provider, "endpoint", ""),
            "timeout": getattr(provider, "timeout", ""),
            "question": question,
            "prompt_type": prompt_type,
            "intent": intent,
            "parsed": parsed,
            "content": result.content,
            "search_results": result.search_results or [],
        },
        recommendations=recommendations,
        search_results=result.search_results or [],
    )


def _ask_visibility(provider: Any, profile: dict[str, Any], brands: list[dict[str, Any]], prompt: str, report_language: str) -> Any:
    result = provider.ask_json(prompt, system="You estimate brand visibility and return strict JSON.", enable_search=True)
    if not result.ok and result.provider == "doubao":
        result = provider.ask_json(
            _compact_visibility_prompt(brands, profile, report_language),
            system="Return strict JSON only.",
            enable_search=False,
        )
    parsed = result.parsed if isinstance(result.parsed, dict) else {}
    return _Obj(
        provider=result.provider,
        ok=result.ok,
        error=result.error,
        parsed=parsed,
        raw={
            "provider": result.provider,
            "ok": result.ok,
            "error": result.error,
            "model": getattr(provider, "model", ""),
            "endpoint": getattr(provider, "endpoint", ""),
            "timeout": getattr(provider, "timeout", ""),
            "parsed": parsed,
            "content": result.content,
        },
    )


def _compact_visibility_prompt(brands: list[dict[str, Any]], profile: dict[str, Any], report_language: str) -> str:
    language = "中文" if report_language == "zh" else "English"
    brand_names = [item.get("brand_name", "") for item in brands[:10]]
    return f"""
请估算这些品牌在 5 个平台的内容数量：百度、搜狗、360搜索、抖音、小红书。
类目：{_category(profile)}
地区：{profile.get("primary_region") or ""}
品牌：{json.dumps(brand_names, ensure_ascii=False)}

只返回 JSON：
{{
  "brand_visibility": [
    {{
      "brand_name": "品牌名",
      "traditional_search": {{"baidu": 0, "sogou": 0, "so360": 0}},
      "new_media": {{"douyin": 0, "xiaohongshu": 0}},
      "source_urls": [],
      "confidence": 0.6,
      "notes": "估算依据"
    }}
  ]
}}
输出语言：{language}
"""


def _flatten_recommendations(results: list[Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for result in results:
        question = (result.raw or {}).get("question") or ""
        prompt_type = (result.raw or {}).get("prompt_type") or "neutral_recommendation"
        intent = (result.raw or {}).get("intent") or ""
        for idx, rec in enumerate(result.recommendations or [], start=1):
            if not isinstance(rec, dict):
                continue
            brand = str(rec.get("brand_name") or rec.get("name") or "").strip()
            if not brand:
                continue
            rows.append(
                {
                    "engine": result.provider,
                    "trend_term": question,
                    "question": question,
                    "prompt_type": prompt_type,
                    "intent": intent,
                    "rank": int(rec.get("rank") or idx),
                    "brand_name": brand,
                    "product_name": str(rec.get("product_name") or "").strip(),
                    "reason": str(rec.get("reason") or "").strip(),
                    "citation_urls": _url_list(rec.get("citation_urls")),
                    "is_user_brand": _is_user_brand(brand, profile),
                }
            )
    return rows


def _build_multi_ai_ranking(items: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    aliases = _own_alias_keys(profile)
    grouped: dict[str, dict[str, Any]] = {}
    ranks: defaultdict[str, list[int]] = defaultdict(list)
    engines: defaultdict[str, set[str]] = defaultdict(set)
    urls: defaultdict[str, list[str]] = defaultdict(list)
    reasons: defaultdict[str, list[str]] = defaultdict(list)
    for item in items:
        brand = item.get("brand_name", "")
        key = brand_key(brand)
        if key in aliases:
            brand = profile.get("brand_name") or profile.get("product_name") or brand
            key = brand_key(brand)
        if not key:
            continue
        grouped.setdefault(key, {"brand_name": brand, "brand_key": key, "is_user_brand": key == brand_key(profile.get("brand_name") or profile.get("product_name"))})
        ranks[key].append(int(item.get("rank") or 99))
        engines[key].add(str(item.get("engine") or ""))
        urls[key].extend(item.get("citation_urls") or [])
        if item.get("reason"):
            reasons[key].append(str(item.get("reason")))
    rows = []
    for key, meta in grouped.items():
        rows.append(
            {
                **meta,
                "recommendation_count": len(ranks[key]),
                "avg_rank": round(sum(ranks[key]) / len(ranks[key]), 2) if ranks[key] else "",
                "engine_count": len([item for item in engines[key] if item]),
                "engine": ", ".join(sorted(item for item in engines[key] if item)),
                "source_urls": list(dict.fromkeys(urls[key]))[:10],
                "reasons": reasons[key][:8],
            }
        )
    rows.sort(key=lambda item: (-item["recommendation_count"], -item["engine_count"], float(item["avg_rank"] or 99), item["brand_name"]))
    for idx, row in enumerate(rows, start=1):
        row["ai_recommendation_rank"] = idx
    return rows


def _top_brand_pool(ranking: list[dict[str, Any]], profile: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    rows = [{**item, "is_user_brand": bool(item.get("is_user_brand"))} for item in ranking[:limit]]
    own = profile.get("brand_name") or profile.get("product_name") or ""
    own_key = brand_key(own)
    if own and own_key not in {item.get("brand_key") for item in rows}:
        rows.append({"brand_name": own, "brand_key": own_key, "is_user_brand": True, "recommendation_count": 0, "avg_rank": ""})
    return rows


def _competitor_discovery_from_ranking(ranking: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    region = profile.get("primary_region") or ""
    direct = []
    local = []
    national = []
    for item in ranking:
        if item.get("is_user_brand"):
            continue
        row = {"brand_name": item.get("brand_name", ""), "reason": f"多 AI 主流推荐中出现；来源：{item.get('engine', '')}"}
        if region:
            local.append({**row, "region": region})
        else:
            national.append(row)
        direct.append({**row, "competitor_type": "multi_ai_recommended"})
    return {
        "direct_competitors": direct[:10],
        "local_competitors": local[:10],
        "national_competitors": national[:10],
        "adjacent_competitors": [],
        "calibration_note": "由 Qwen、豆包、元宝、DeepSeek 对同一个主流推荐问题的回答聚合生成。",
    }


def _provider_status(recommendation_results: list[Any], visibility_results: list[Any]) -> list[dict[str, Any]]:
    names = list(dict.fromkeys([item.provider for item in recommendation_results] + [item.provider for item in visibility_results]))
    rows = []
    for name in names:
        rec_items = [item for item in recommendation_results if item.provider == name]
        vis = next((item for item in visibility_results if item.provider == name), None)
        rec = rec_items[0] if rec_items else None
        rec_raw = rec.raw if rec else {}
        vis_raw = vis.raw if vis else {}
        rec_ok_count = len([item for item in rec_items if item.ok])
        rec_errors = [item.error for item in rec_items if item.error]
        rows.append(
            {
                "provider": name,
                "recommendation_ok": bool(rec_ok_count) if rec_items else False,
                "visibility_ok": bool(vis.ok) if vis else False,
                "recommendation_error": "; ".join(dict.fromkeys(rec_errors))[:500] if rec_errors else ("" if rec_items else "not called"),
                "visibility_error": vis.error if vis else "not called",
                "recommendation_count": sum(len(item.recommendations or []) for item in rec_items),
                "recommendation_prompt_count": len(rec_items),
                "recommendation_success_count": rec_ok_count,
                "visibility_count": len((vis.parsed or {}).get("brand_visibility") or []) if vis and isinstance(vis.parsed, dict) else 0,
                "model": rec_raw.get("model") or vis_raw.get("model") or "",
                "endpoint": rec_raw.get("endpoint") or vis_raw.get("endpoint") or "",
                "timeout": rec_raw.get("timeout") or vis_raw.get("timeout") or "",
            }
        )
    return rows


def _aggregate_visibility(results: list[Any], brands: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    brand_meta = {item["brand_key"]: item for item in brands}
    grouped: dict[str, dict[str, Any]] = {
        item["brand_key"]: {
            "brand_name": item["brand_name"],
            "brand_key": item["brand_key"],
            "is_user_brand": bool(item.get("is_user_brand")),
            "traditional_search_count": 0,
            "new_media_count": 0,
            "traditional_search": {"baidu": 0, "sogou": 0, "so360": 0},
            "new_media": {"douyin": 0, "xiaohongshu": 0},
            "estimated_result_count": 0,
            "provider_count": 0,
            "source_urls": [],
            "provider_estimates": [],
            "notes": [],
        }
        for item in brands
    }
    for result in results:
        rows = (result.parsed or {}).get("brand_visibility") if isinstance(result.parsed, dict) else []
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _match_brand_key(row.get("brand_name", ""), brand_meta)
            if not key:
                continue
            target = grouped[key]
            traditional = row.get("traditional_search") or {}
            new_media = row.get("new_media") or {}
            traditional_count = _sum_counts(traditional)
            new_media_count = _sum_counts(new_media)
            target["traditional_search_count"] += traditional_count
            target["new_media_count"] += new_media_count
            _add_count_dict(target["traditional_search"], traditional)
            _add_count_dict(target["new_media"], new_media)
            target["estimated_result_count"] += traditional_count + new_media_count
            target["provider_count"] += 1
            target["source_urls"].extend(_url_list(row.get("source_urls")))
            if row.get("notes"):
                target["notes"].append(f"{result.provider}: {row.get('notes')}")
            target["provider_estimates"].append(
                {
                    "provider": result.provider,
                    "traditional_search": traditional,
                    "new_media": new_media,
                    "confidence": row.get("confidence"),
                    "notes": row.get("notes", ""),
                }
            )
    rows = []
    own_count = 0
    for item in grouped.values():
        provider_count = max(int(item.get("provider_count") or 0), 1)
        item["traditional_search_count"] = round(item["traditional_search_count"] / provider_count)
        item["new_media_count"] = round(item["new_media_count"] / provider_count)
        item["traditional_search"] = {key: round(value / provider_count) for key, value in (item.get("traditional_search") or {}).items()}
        item["new_media"] = {key: round(value / provider_count) for key, value in (item.get("new_media") or {}).items()}
        item["estimated_result_count"] = item["traditional_search_count"] + item["new_media_count"]
        item["total_count"] = None
        item["top_k_result_count"] = 0
        item["metric_type"] = "multi_ai_estimated_count"
        item["warning"] = "AI 估算声量，不等同于真实搜索/平台接口统计。"
        item["query"] = f"{item['brand_name']} {_category(profile)} 内容声量"
        item["source_urls"] = list(dict.fromkeys(item["source_urls"]))[:10]
        item["notes"] = item["notes"][:8]
        if item.get("is_user_brand"):
            own_count = int(item["estimated_result_count"])
        rows.append(item)
    rows.sort(key=lambda item: (-int(item.get("estimated_result_count") or 0), item["brand_name"]))
    for idx, item in enumerate(rows, start=1):
        item["search_volume_rank"] = idx
        item["gap_vs_user"] = int(item.get("estimated_result_count") or 0) - int(own_count or 0)
    return rows


def _search_visibility_from_volume(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for idx, item in enumerate(rows, start=1):
        result.append(
            {
                "brand_name": item.get("brand_name", ""),
                "brand_key": item.get("brand_key", ""),
                "is_user_brand": bool(item.get("is_user_brand")),
                "search_visibility_rank": idx,
                "mentioned_count": int(item.get("traditional_search_count") or 0),
                "result_count": int(item.get("estimated_result_count") or 0),
                "new_media_count": int(item.get("new_media_count") or 0),
                "traditional_search": item.get("traditional_search") or {},
                "new_media": item.get("new_media") or {},
                "query": item.get("query", ""),
                "metric_type": item.get("metric_type", ""),
                "warning": item.get("warning", ""),
                "source_urls": item.get("source_urls") or [],
            }
        )
    return result


def _build_gap(ai_ranking: list[dict[str, Any]], visibility: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ai_pos = {item.get("brand_key"): idx for idx, item in enumerate(ai_ranking, start=1)}
    ai_by_key = {item.get("brand_key"): item for item in ai_ranking}
    vis_by_key = {item.get("brand_key"): item for item in visibility}
    keys = [key for key in dict.fromkeys([*ai_by_key.keys(), *vis_by_key.keys()]) if key]
    missing_rank = len(keys) + 1
    rows = []
    for key in keys:
        ai = ai_by_key.get(key, {})
        vis = vis_by_key.get(key, {})
        ai_rank = ai_pos.get(key)
        search_rank = vis.get("search_visibility_rank")
        if ai_rank and search_rank:
            gap_score = int(search_rank) - int(ai_rank)
        elif ai_rank:
            gap_score = missing_rank - int(ai_rank)
        elif search_rank:
            gap_score = int(search_rank) - missing_rank
        else:
            gap_score = 0
        rows.append(
            {
                "brand_name": ai.get("brand_name") or vis.get("brand_name") or "",
                "brand_key": key,
                "ai_recommendation_rank": ai_rank,
                "ai_recommendation_count": ai.get("recommendation_count", 0),
                "avg_ai_rank": ai.get("avg_rank", ""),
                "search_visibility_rank": search_rank,
                "mentioned_count": vis.get("mentioned_count", 0),
                "result_count": vis.get("result_count", 0),
                "is_user_brand": bool(ai.get("is_user_brand") or vis.get("is_user_brand")),
                "gap_score": gap_score,
                "gap_label": _gap_label(gap_score, ai_rank, search_rank),
            }
        )
    return sorted(rows, key=lambda item: (-abs(int(item.get("gap_score") or 0)), item.get("brand_name", "")))


def _collect_source_links(results: list[Any], items: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    links = []
    seen = set()

    def add(url: str, label: str, provider: str, source_type: str) -> None:
        url = _normalize_url(url)
        if not url or url in seen:
            return
        seen.add(url)
        links.append({"url": url, "domain": domain_from_url(url), "label": label, "engine": provider, "source_type": source_type, "trend_term": ""})

    for item in items:
        for url in item.get("citation_urls") or []:
            add(url, item.get("brand_name", ""), item.get("engine", ""), "citation")
    for result in results:
        for source in result.search_results or []:
            add(source.get("url", ""), source.get("site_name") or source.get("title") or "", result.provider, "ai_search_result")
    return links[:limit]


def _collect_source_articles(source_links: list[dict[str, Any]], progress: ProgressFn | None, limit: int = 40) -> list[dict[str, Any]]:
    articles = []
    fetch_limit = max(0, int(limit or 0))
    for idx, item in enumerate(source_links[:fetch_limit], start=1):
        if progress and (idx == 1 or idx % 10 == 0 or idx == min(len(source_links), fetch_limit)):
            progress(f"抓取 AI 文章链接正文 {idx}/{min(len(source_links), fetch_limit)}")
        pages = collect_website_pages(item["url"], max_same_domain_links=0)
        page = pages[0] if pages else {"url": item["url"], "error": "no page"}
        articles.append({**item, "text_excerpt": (page.get("text") or "")[:5000], "error": page.get("error", "")})
    return articles


def _extract_content_features_with_qwen(
    config: AppConfig,
    profile: dict[str, Any],
    brands: list[dict[str, Any]],
    articles: list[dict[str, Any]],
    recommendation_items: list[dict[str, Any]],
    report_language: str,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    payload = {
        "product_profile": profile,
        "brands": brands,
        "articles": [
            {
                "url": item.get("url"),
                "domain": item.get("domain"),
                "label": item.get("label"),
                "text_excerpt": (item.get("text_excerpt") or "")[:1600],
                "error": item.get("error", ""),
            }
            for item in articles[:30]
        ],
        "recommendations": recommendation_items[:80],
    }
    language = "中文" if report_language == "zh" else "English"
    prompt = f"""
请根据以下 AI 推荐理由、可访问文章正文和链接抓取状态，输出一份“基于 GEO 导向的品牌调研与市场定位分析”。

分析目标：
这不是普通竞品简介，而是为了帮助客户理解：为什么 AI 会推荐这些竞品、竞品内容在宣传什么、客户品牌应该补哪些数字资产和内容资产，最终服务于 GEO 优化。

请只返回 JSON，不要输出 Markdown 代码块。

JSON schema:
{{
  "markdown_report": "给客户看的完整 Markdown 报告",
  "category_boundary": [
    {{"brand_name": "品牌", "boundary_type": "卖产品/卖场景/卖服务/卖解决方案/混合", "positioning": "品类心智", "evidence": "依据"}}
  ],
  "price_bands": [
    {{"brand_name": "品牌", "price_band": "低/中/高/未知", "estimated_unit_price": "", "evidence": "依据"}}
  ],
  "psychology_motives": [
    {{"brand_name": "品牌", "motive": "功能价值/情感价值/自我实现", "score": 1, "evidence": "依据"}}
  ],
  "decision_heuristics": [
    {{"brand_name": "品牌", "heuristic": "从众效应/权威背书/锚定效应/稀缺性/损失规避/社会认同/案例对比", "score": 1, "evidence": "依据"}}
  ],
  "personas": [
    {{"brand_name": "品牌", "age": "年龄", "spending_power": "消费能力", "scenario": "需求场景", "concern": "决策顾虑", "content_preference": "内容偏好"}}
  ],
  "selling_points": [
    {{"brand_name": "品牌", "selling_point": "卖点", "source_type": "AI推荐理由/文章正文/官网媒体链接/可见标题", "evidence": "依据"}}
  ],
  "digital_asset_scores": [
    {{"brand_name": "品牌", "search_asset_score": 0, "content_platform_score": 0, "website_access_score": 0, "proof_asset_score": 0, "gap": "内容缺口"}}
  ]
}}

markdown_report 必须按以下结构：

## 1. 品类边界界定
- 判断客户品牌到底属于哪个品类边界：卖产品、卖场景/生活方式、卖服务、卖解决方案，或混合类型。
- 说明 AI 推荐出的竞品分别在文章内容里把自己归入什么品类/心智位置。
- 如果资料不足，必须标注“依据不足”，不要编造。

## 2. 客单价与价格带
- 提炼 AI 排名前 3 品牌的客单价、套餐价、项目价或价格带。
- 对比客户品牌自身客单价/价格带。
- 如果文章没有价格，允许给“低/中/高端价格带”判断，但必须说明依据来自内容表达、品牌定位或服务项目，不得伪造具体金额。

## 3. 消费心理学深层动机
- 分析用户购买的是功能价值（安全/便捷/效果）、情感价值（归属/信任/爱美/安心），还是自我实现价值（身份标签/审美表达/圈层）。
- 分析文章中使用了哪些决策捷径或心理启发式：从众效应、锚定效应、权威背书、稀缺性、损失规避、社会认同、案例对比等。
- 每个判断都要说明来自 AI 推荐理由、文章正文、或链接可见信息。

## 4. 用户画像
- 归纳 AI 排名前列品牌吸引的用户画像。
- 至少从年龄/消费能力/需求场景/决策顾虑/内容偏好五个角度描述。
- 如数据不足，给出“可能用户画像”，并标明是推断。

## 5. 卖点解析
- 对每个主要品牌至少提炼 5 个卖点。
- 每个卖点尽量标注来源类型：AI 推荐理由、文章正文、官网/媒体链接、或可见链接标题。
- 对客户品牌也要提炼现有卖点，并指出缺失卖点。

## 6. 客户自身数字资产与内容资产分析
- 数字资产：综合分析搜索引擎与内容平台可见内容、抓取成功/失败、链接质量、内容覆盖度。
- 品牌内容：客户品牌当前在 AI 推荐中呈现的品牌心智、信任背书和内容弱点。
- 产品/服务内容：客户当前内容是否说清楚品类边界、价格带、核心项目/产品、案例、风险控制、售后/服务流程。
- 给出面向 GEO 的补强建议：应该补什么页面、什么文章、什么问答、什么案例、什么平台内容。

通用要求：
1. 输出语言使用{language}。
2. 明确说明信息来自 AI 推荐理由、文章正文或可见链接；不要伪造无法验证的数据。
3. 对抓取失败的链接，只能作为“数据可用性问题”说明，不能当作该品牌没有内容。
4. 报告要给客户看，少写技术报错，多写业务含义。

数据：
{json.dumps(payload, ensure_ascii=False, indent=2)}
"""
    try:
        result = qwen._call(
            [{"role": "user", "content": prompt}],
            model=config.qwen.analysis_model,
            enable_search=True,
            search_options={"search_strategy": config.qwen.analysis_strategy},
        )
        parsed = extract_json(result.content, fallback=None)
        if isinstance(parsed, dict):
            parsed.setdefault("markdown_report", parsed.get("report") or result.content)
            return parsed
        if result.content:
            return {"markdown_report": result.content}
    except Exception:
        pass
    return _fallback_content_analysis(brands, recommendation_items, articles)


def _build_article_format(profile: dict[str, Any], question: str, content_report: str, report_language: str) -> str:
    if report_language != "zh":
        return f"""# GEO Article Format

Main query: {question}
Brand: {profile.get('brand_name') or profile.get('product_name') or ''}
Category: {_category(profile)}

Use the competitor content patterns below as reference, cite reliable sources, compare mainstream competitors fairly, and position the tracked brand with verifiable evidence.

{content_report[:4000]}
"""
    return f"""# GEO 文章生产格式

主流推荐问题：{question}
客户品牌：{profile.get('brand_name') or profile.get('product_name') or ''}
产品类目：{_category(profile)}

写作要求：
1. 围绕主流推荐问题写，不写细分长尾机会词。
2. 公平对比主流竞品，不无依据把客户品牌排第一。
3. 优先使用可验证文章链接、官网、媒体、平台内容作为证据。
4. 结构建议：用户问题 -> 主流选择标准 -> 竞品对比 -> 客户品牌可补强点 -> GEO 优化建议。
5. 禁止夸大无法验证的销量、排名、功效和资质。

竞品内容特点参考：

{content_report[:4000]}
"""


def _fallback_content_report(brands: list[dict[str, Any]], items: list[dict[str, Any]], articles: list[dict[str, Any]]) -> str:
    lines = ["# 竞品内容特点提炼", "", "Qwen 提炼失败，以下为基于 AI 推荐理由和抓取文章的规则化摘要。", ""]
    by_brand: defaultdict[str, list[str]] = defaultdict(list)
    for item in items:
        if item.get("reason"):
            by_brand[item.get("brand_name", "")].append(item.get("reason", ""))
    for brand in brands:
        name = brand.get("brand_name", "")
        lines.extend([f"## {name}", ""])
        for reason in by_brand.get(name, [])[:5]:
            lines.append(f"- {reason}")
        related = [item for item in articles if name and name.lower() in str(item.get("label", "")).lower()]
        if related:
            lines.append(f"- 可参考链接数量：{len(related)}")
        lines.append("")
    return "\n".join(lines)


def _fallback_content_analysis(brands: list[dict[str, Any]], items: list[dict[str, Any]], articles: list[dict[str, Any]]) -> dict[str, Any]:
    markdown = _fallback_content_report(brands, items, articles)
    by_brand: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        brand = str(item.get("brand_name") or "").strip()
        if brand:
            by_brand[brand].append(item)
    article_success_by_brand: defaultdict[str, int] = defaultdict(int)
    for article in articles:
        if article.get("text_excerpt") and not article.get("error"):
            article_success_by_brand[str(article.get("label") or "")] += 1

    category_boundary = []
    price_bands = []
    psychology_motives = []
    decision_heuristics = []
    personas = []
    selling_points = []
    digital_asset_scores = []
    for brand in brands[:12]:
        name = str(brand.get("brand_name") or "")
        reasons = by_brand.get(name) or []
        reason_text = " ".join(str(item.get("reason") or "") for item in reasons)
        category_boundary.append(
            {
                "brand_name": name,
                "boundary_type": "卖服务",
                "positioning": "基于 AI 推荐理由推断的本地服务品牌",
                "evidence": reason_text[:160] or "依据不足",
            }
        )
        price_bands.append({"brand_name": name, "price_band": "未知", "estimated_unit_price": "", "evidence": "当前可访问文章未提供明确价格。"})
        for motive, score in _infer_motives(reason_text).items():
            psychology_motives.append({"brand_name": name, "motive": motive, "score": score, "evidence": reason_text[:120]})
        for heuristic, score in _infer_heuristics(reason_text).items():
            decision_heuristics.append({"brand_name": name, "heuristic": heuristic, "score": score, "evidence": reason_text[:120]})
        personas.append(
            {
                "brand_name": name,
                "age": "依据不足",
                "spending_power": "中高",
                "scenario": "需要医美服务/项目对比/安全背书的用户",
                "concern": "安全、资质、医生、案例、价格",
                "content_preference": "排名榜单、案例对比、资质说明、项目科普",
            }
        )
        points = _extract_selling_points(reason_text)
        for point in points[:5]:
            selling_points.append({"brand_name": name, "selling_point": point, "source_type": "AI推荐理由", "evidence": reason_text[:120]})
        digital_asset_scores.append(
            {
                "brand_name": name,
                "search_asset_score": min(100, int(brand.get("recommendation_count") or 0) * 25),
                "content_platform_score": min(100, len(reasons) * 20),
                "website_access_score": 80 if article_success_by_brand.get(name) else 20,
                "proof_asset_score": 50 if points else 20,
                "gap": "需要补充可访问的案例、价格带、资质、项目页和平台内容。",
            }
        )
    return {
        "markdown_report": markdown,
        "category_boundary": category_boundary,
        "price_bands": price_bands,
        "psychology_motives": psychology_motives,
        "decision_heuristics": decision_heuristics,
        "personas": personas,
        "selling_points": selling_points,
        "digital_asset_scores": digital_asset_scores,
    }


def _infer_motives(text: str) -> dict[str, int]:
    lowered = text.lower()
    result = {"功能价值": 1}
    if any(word in text for word in ("安全", "资质", "医生", "设备", "技术", "效果", "正规")):
        result["功能价值"] = 3
    if any(word in text for word in ("安心", "服务", "体验", "口碑", "信任", "环境")):
        result["情感价值"] = 2
    if any(word in text for word in ("高端", "轻奢", "审美", "定制", "明星", "身份")) or "premium" in lowered:
        result["自我实现"] = 2
    return result


def _infer_heuristics(text: str) -> dict[str, int]:
    result: dict[str, int] = {}
    if any(word in text for word in ("排名", "前十", "知名", "主流", "老牌", "用户基数")):
        result["从众效应"] = 2
    if any(word in text for word in ("三甲", "资质", "专家", "博士", "医生", "权威")):
        result["权威背书"] = 3
    if any(word in text for word in ("案例", "对比", "口碑", "评价")):
        result["社会认同"] = 2
    if any(word in text for word in ("价格", "收费", "套餐")):
        result["锚定效应"] = 1
    return result or {"依据不足": 1}


def _extract_selling_points(text: str) -> list[str]:
    candidates = []
    for token in re.split(r"[，,。；;\n、]", text):
        token = token.strip()
        if 4 <= len(token) <= 40:
            candidates.append(token)
    return list(dict.fromkeys(candidates))[:5] or ["资质背书", "服务项目覆盖", "医生/技术能力", "案例或口碑", "本地可达性"]


def _default_topic_taxonomy(profile: dict[str, Any]) -> list[str]:
    text = f"{profile.get('category_local','')} {profile.get('category_en','')} {profile.get('business_type','')}".lower()
    if any(word in text for word in ("奶茶", "茶饮", "火锅", "餐厅", "restaurant", "hotpot")):
        return ["口味/特色", "价格/性价比", "门店/地理位置", "服务/体验", "口碑/评价", "外卖/便利"]
    if any(word in text for word in ("医美", "法律", "顾问", "咨询", "medical", "legal")):
        return ["资质/专业性", "案例/口碑", "服务范围", "价格/收费", "合规/风险", "响应速度"]
    if any(word in text for word in ("零部件", "配件", "ecommerce", "parts")):
        return ["品类覆盖", "价格/性价比", "正品/品质", "适配/兼容", "物流/退换", "客服/售后"]
    return ["价格/性价比", "品质/特色", "服务/售后", "口碑/评价", "信任/资质"]


def _fallback_prompt_set(profile: dict[str, Any], base_question: str, prompt_count: int, report_language: str) -> list[str]:
    category = _category(profile)
    region = str(profile.get("primary_region") or "").strip()
    scope = str(profile.get("service_scope") or "").strip()
    audience = str(profile.get("geo_audience") or profile.get("analysis_goal") or "").strip()
    is_english = report_language != "zh" or str(profile.get("market_language") or "").lower().startswith("en")
    is_local = scope in {"local_city", "regional"} and bool(region)
    questions = [base_question]
    if is_english:
        subject = f"{region} {category}".strip() if is_local else category
        questions.extend(
            [
                f"What are the best {subject} brands?",
                f"Which {subject} should I choose?",
                f"Recommend reliable {subject} options",
                f"What is the best {subject} for customers?",
                f"{subject} comparison and recommendations",
            ]
        )
    else:
        subject = f"{region}{category}" if is_local else category
        if audience == "franchise":
            questions.extend(
                [
                    f"{subject}加盟品牌推荐",
                    f"想开一家{category}店选什么品牌",
                    f"{subject}招商品牌哪家靠谱",
                    f"{category}加盟品牌对比",
                ]
            )
        elif audience == "b2b_purchase":
            questions.extend(
                [
                    f"{subject}供应商推荐",
                    f"{category}采购选哪家",
                    f"{subject}服务商对比",
                    f"{category}企业采购怎么选",
                ]
            )
        else:
            questions.extend(
                [
                    f"{subject}推荐",
                    f"{subject}哪家好",
                    f"{subject}品牌排名",
                    f"{subject}怎么选",
                    f"{subject}口碑好的有哪些",
                ]
            )
    return _unique_questions(questions, prompt_count)


def _fallback_brand_diagnostic_prompt_set(profile: dict[str, Any], prompt_count: int, report_language: str) -> list[str]:
    own = str(profile.get("brand_name") or profile.get("product_name") or "").strip()
    if not own or prompt_count <= 0:
        return []
    category = _category(profile)
    region = str(profile.get("primary_region") or "").strip()
    is_english = report_language != "zh" or str(profile.get("market_language") or "").lower().startswith("en")
    if is_english:
        subject = f"{own} {category}".strip()
        questions = [
            f"How is {subject} reviewed by customers?",
            f"Is {own} a reliable {category} option?",
            f"What are the strengths and risks of {own}?",
            f"What do users say about {own} compared with competitors?",
        ]
    else:
        prefix = f"{region}" if region and region not in own else ""
        questions = [
            f"{prefix}{own}怎么样？",
            f"{prefix}{own}做{category}靠谱吗？",
            f"{prefix}{own}口碑和评价怎么样？",
            f"{prefix}{own}价格、案例和服务透明吗？",
        ]
    return _unique_questions(questions, prompt_count)


def _normalize_prompt_rows(rows: Any, prompt_type: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    if not isinstance(rows, list):
        return result
    for item in rows:
        if isinstance(item, str):
            question = item.strip()
            intent = ""
            reason = ""
        elif isinstance(item, dict):
            question = str(item.get("question") or item.get("query") or item.get("term") or "").strip()
            intent = str(item.get("intent") or item.get("question_type") or "").strip()
            reason = str(item.get("reason") or "").strip()
        else:
            continue
        if not question:
            continue
        result.append(_prompt_item(question, prompt_type, intent or prompt_type, reason))
    return result


def _prompt_item(question: str, prompt_type: str, intent: str, reason: str) -> dict[str, str]:
    return {
        "question": re.sub(r"\s+", " ", str(question or "").strip()),
        "prompt_type": prompt_type,
        "intent": intent,
        "reason": reason,
    }


def _prompt_reason_for(question: str, rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("question") == question:
            return row.get("reason", "")
    return ""


def _prompt_intent_for(question: str, rows: list[dict[str, str]]) -> str:
    for row in rows:
        if row.get("question") == question:
            return row.get("intent", "")
    return ""


def _prompt_meta_for(question: str, rows: list[dict[str, str]]) -> dict[str, str]:
    for row in rows:
        if row.get("question") == question:
            return {
                key: str(row.get(key) or "")
                for key in ("keyword_source", "source_keyword")
                if row.get(key)
            }
    return {}


def _own_brand_terms(profile: dict[str, Any]) -> list[str]:
    terms = [
        profile.get("brand_name"),
        profile.get("product_name"),
        *(profile.get("brand_aliases") or []),
    ]
    result = []
    for term in terms:
        clean = str(term or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _contains_own_brand_term(question: str, profile: dict[str, Any]) -> bool:
    text = str(question or "").lower().replace(" ", "")
    text_key = brand_key(question)
    for term in _own_brand_terms(profile):
        clean = str(term or "").strip().lower().replace(" ", "")
        key = brand_key(term)
        if clean and clean in text:
            return True
        if key and (key in text_key or text_key in key):
            return True
    return False


def _filter_neutral_questions(questions: list[str], profile: dict[str, Any], limit: int) -> list[str]:
    return _unique_questions(
        [question for question in questions if question and not _contains_own_brand_term(question, profile)],
        limit,
    )


def _unique_questions(questions: list[str], limit: int) -> list[str]:
    result = []
    seen = set()
    for question in questions:
        clean = re.sub(r"\s+", " ", str(question or "").strip())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        result.append(clean)
        if len(result) >= limit:
            break
    return result


def _compact_profile_for_prompt(profile: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "product_name",
        "brand_name",
        "brand_aliases",
        "category_local",
        "category_en",
        "market_language",
        "target_market",
        "primary_region",
        "region_level",
        "service_scope",
        "business_type",
        "geo_audience",
        "analysis_goal",
        "geo_probe_subject",
        "known_competitor_hints",
        "summary",
        "selling_points",
        "target_audience",
        "market_reason",
    ]
    compact = {key: profile.get(key) for key in keys if profile.get(key) not in (None, "", [])}
    if profile.get("profile_md"):
        compact["profile_md_excerpt"] = str(profile.get("profile_md") or "")[:1200]
    return compact


def _compact_recommendation_prompt(profile: dict[str, Any], question: str, language: str) -> str:
    return f"""
请回答这个用户问题：{question}

产品/品牌背景：
{json.dumps(profile, ensure_ascii=False)}

只返回 JSON，不要 Markdown。按真实普通用户视角推荐主流竞争品牌，不要因为背景里出现被分析品牌就优先推荐它。
输出语言：{language}
JSON:
{{
  "question": "{question}",
  "answer": "简短回答",
  "recommendations": [
    {{"rank": 1, "brand_name": "品牌名", "product_name": "", "reason": "推荐理由", "citation_urls": []}}
  ]
}}
"""


def _category(profile: dict[str, Any]) -> str:
    market_language = str(profile.get("market_language") or "").lower()
    if market_language.startswith("en"):
        return str(profile.get("category_en") or profile.get("category_local") or profile.get("geo_probe_subject") or "product").strip()
    return str(profile.get("category_local") or profile.get("category_en") or profile.get("geo_probe_subject") or "产品").strip()


def _probe_subject(profile: dict[str, Any]) -> str:
    region = str(profile.get("primary_region") or "").strip()
    category = _category(profile)
    return f"{region}{category}".strip() if region else category


def _sum_counts(value: Any) -> int:
    if not isinstance(value, dict):
        return 0
    total = 0
    for item in value.values():
        total += _parse_int(item)
    return total


def _add_count_dict(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, dict):
        return
    for key, raw in value.items():
        clean_key = str(key or "").strip()
        if not clean_key:
            continue
        target[clean_key] = int(target.get(clean_key) or 0) + _parse_int(raw)


def _parse_int(value: Any) -> int:
    if value is None or isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return max(int(value), 0)
    text = str(value).replace(",", "").replace("，", "").strip()
    multiplier = 1
    if text.endswith("万"):
        multiplier = 10000
        text = text[:-1]
    elif text.endswith("亿"):
        multiplier = 100000000
        text = text[:-1]
    match = re.search(r"\d+(?:\.\d+)?", text)
    if not match:
        return 0
    return max(int(float(match.group(0)) * multiplier), 0)


def _url_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        if isinstance(value, str):
            value = re.findall(r"https?://[^\s\]\)\"']+", value)
        else:
            return []
    return [_normalize_url(str(item)) for item in value if _normalize_url(str(item))][:10]


def _normalize_url(url: str) -> str:
    url = str(url or "").strip().strip("<>").rstrip(".,;，。；)")
    if url.startswith("//"):
        url = f"https:{url}"
    if not re.match(r"https?://", url, flags=re.I):
        return ""
    return url


def _own_alias_keys(profile: dict[str, Any]) -> set[str]:
    return {
        brand_key(value)
        for value in [profile.get("brand_name"), profile.get("product_name"), *(profile.get("brand_aliases") or [])]
        if value
    }


def _is_user_brand(brand: str, profile: dict[str, Any]) -> bool:
    return brand_key(brand) in _own_alias_keys(profile)


def _match_brand_key(name: Any, brand_meta: dict[str, dict[str, Any]]) -> str:
    key = brand_key(name)
    if key in brand_meta:
        return key
    for candidate_key, meta in brand_meta.items():
        candidate = brand_key(meta.get("brand_name"))
        if key and candidate and (key in candidate or candidate in key):
            return candidate_key
    return ""


def _gap_label(gap_score: int, ai_rank: int | None, search_rank: int | None) -> str:
    if ai_rank and not search_rank:
        return "AI 推荐较高但声量估算不足"
    if search_rank and not ai_rank:
        return "声量估算较高但 AI 推荐不足"
    if gap_score >= 3:
        return "AI 排名高于声量估算"
    if gap_score <= -3:
        return "声量估算高于 AI 排名"
    return "AI 推荐与声量估算相对一致"


class _Obj:
    def __init__(self, **kwargs: Any):
        self.__dict__.update(kwargs)
