from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Callable

from .config import AppConfig, OUTPUT_DIR
from .qwen_client import QwenClient
from .serpapi_client import SerpApiClient
from .storage import Storage
from .trend_analyzer import (
    extract_related_queries,
    extract_timeseries_scores,
    summarize_search_result,
    unique_strings,
)
from .utils import safe_filename, utc_now_iso, write_text


ProgressFn = Callable[[str], None]
STRATEGY_DIR = OUTPUT_DIR / "strategy_reports"


def run_competitor_analysis(
    storage: Storage,
    config: AppConfig,
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    competitors: str = "",
    competitor_urls: str = "",
    pdf_paths: str = "",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    serpapi = SerpApiClient(config.serpapi)
    if progress:
        progress("正在生成竞品研究计划")
    plan = qwen.generate_competitor_research_plan(city, industry, customer_product, seed_keyword, competitors)
    queries = unique_strings(plan.get("search_queries", []), max_length=120)[:8]
    if not queries:
        queries = unique_strings([seed_keyword, f"{industry} {city}", competitors], max_length=120)[:5]

    search_summaries, search_raw = _run_serp_searches(serpapi, queries, progress)
    trend_keywords = unique_strings(plan.get("trend_keywords", []), max_length=72)[:5]
    trends = _run_trends(serpapi, trend_keywords, progress)
    pdf_summaries = _read_pdf_inputs(pdf_paths)

    analysis_data = {
        "input": _base_input(city, industry, customer_product, seed_keyword, competitors),
        "competitor_urls": _split_multiline(competitor_urls),
        "plan": plan,
        "search_queries": queries,
        "search_summaries": search_summaries,
        "trend_keywords": trend_keywords,
        "trends": trends,
        "pdf_summaries": pdf_summaries,
        "search_raw": search_raw,
    }
    if progress:
        progress("正在生成竞品 GEO 分析报告")
    report_md = qwen.generate_competitor_analysis_report(analysis_data)
    return _save_strategy_report(
        storage,
        report_type="competitor",
        subject=seed_keyword,
        city=city,
        industry=industry,
        customer_product=customer_product,
        competitors=competitors,
        report_md=report_md,
        raw_json=analysis_data,
        filename_prefix="competitor_analysis",
    )


def run_ai_visibility_diagnosis(
    storage: Storage,
    config: AppConfig,
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    competitors: str = "",
    question_count: int = 8,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    if progress:
        progress("正在生成 AI 可见度测试问题")
    plan = qwen.generate_visibility_question_plan(city, industry, customer_product, seed_keyword, competitors, question_count)
    questions = unique_strings(plan.get("questions", []), max_length=200)[:question_count]
    answers = []
    for idx, question in enumerate(questions, start=1):
        if progress:
            progress(f"正在模拟用户提问 {idx}/{len(questions)}：{question}")
        answers.append(
            {
                "question": question,
                "result": qwen.answer_visibility_question(question, customer_product, competitors),
            }
        )

    analysis_data = {
        "input": _base_input(city, industry, customer_product, seed_keyword, competitors),
        "question_plan": plan,
        "answers": answers,
        "summary_metrics": _visibility_metrics(customer_product, competitors, answers),
    }
    if progress:
        progress("正在生成 AI 可见度诊断报告")
    report_md = qwen.generate_visibility_report(analysis_data)
    return _save_strategy_report(
        storage,
        report_type="visibility",
        subject=seed_keyword,
        city=city,
        industry=industry,
        customer_product=customer_product,
        competitors=competitors,
        report_md=report_md,
        raw_json=analysis_data,
        filename_prefix="ai_visibility",
    )


def run_brand_strategy(
    storage: Storage,
    config: AppConfig,
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    customer_advantages: str = "",
    competitors: str = "",
    website_url: str = "",
    pdf_paths: str = "",
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    serpapi = SerpApiClient(config.serpapi)
    queries = unique_strings(
        [
            f"{customer_product} {industry}",
            f"{seed_keyword} {city}",
            f"{industry} competitors {city}",
            f"{industry} reviews {city}",
        ],
        max_length=120,
    )
    search_summaries, search_raw = _run_serp_searches(serpapi, queries, progress)
    analysis_data = {
        "input": _base_input(city, industry, customer_product, seed_keyword, competitors),
        "customer_advantages": customer_advantages,
        "website_url": website_url,
        "pdf_summaries": _read_pdf_inputs(pdf_paths),
        "search_queries": queries,
        "search_summaries": search_summaries,
        "search_raw": search_raw,
    }
    if progress:
        progress("正在生成品牌定位与内容策略报告")
    report_md = qwen.generate_brand_strategy_report(analysis_data)
    return _save_strategy_report(
        storage,
        report_type="brand_strategy",
        subject=seed_keyword,
        city=city,
        industry=industry,
        customer_product=customer_product,
        competitors=competitors,
        report_md=report_md,
        raw_json=analysis_data,
        filename_prefix="brand_strategy",
    )


def run_geo_monitor(
    storage: Storage,
    config: AppConfig,
    monitor_name: str,
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    competitors: str = "",
    question_count: int = 8,
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    qwen = QwenClient(config.qwen)
    if progress:
        progress("正在生成本次手动监控问题")
    plan = qwen.generate_visibility_question_plan(city, industry, customer_product, seed_keyword, competitors, question_count)
    questions = unique_strings(plan.get("questions", []), max_length=200)[:question_count]
    answers = []
    for idx, question in enumerate(questions, start=1):
        if progress:
            progress(f"正在执行监控问题 {idx}/{len(questions)}：{question}")
        answers.append(
            {
                "question": question,
                "result": qwen.answer_visibility_question(question, customer_product, competitors),
            }
        )
    previous_runs = storage.query(
        """
        select id, created_at, file_path from strategy_reports
        where report_type='geo_monitor' and customer_product=?
        order by created_at desc limit 5
        """,
        (customer_product,),
    )
    analysis_data = {
        "monitor_name": monitor_name,
        "input": _base_input(city, industry, customer_product, seed_keyword, competitors),
        "question_plan": plan,
        "answers": answers,
        "summary_metrics": _visibility_metrics(customer_product, competitors, answers),
        "previous_runs": previous_runs,
    }
    if progress:
        progress("正在生成 GEO 手动监控报告")
    report_md = qwen.generate_geo_monitor_report(analysis_data)
    return _save_strategy_report(
        storage,
        report_type="geo_monitor",
        subject=monitor_name or seed_keyword,
        city=city,
        industry=industry,
        customer_product=customer_product,
        competitors=competitors,
        report_md=report_md,
        raw_json=analysis_data,
        filename_prefix="geo_monitor",
    )


def _run_serp_searches(
    serpapi: SerpApiClient,
    queries: list[str],
    progress: ProgressFn | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    summaries: list[dict[str, Any]] = []
    raw_items: list[dict[str, Any]] = []
    for idx, query in enumerate(queries, start=1):
        if progress:
            progress(f"SerpApi Search {idx}/{len(queries)}：{query}")
        try:
            raw = serpapi.google_search(query=query, location="", num=10)
            raw_items.append({"query": query, "raw": raw})
            summaries.append(summarize_search_result(query, raw))
        except Exception as exc:
            raw_items.append({"query": query, "error": str(exc)})
    return summaries, raw_items


def _run_trends(
    serpapi: SerpApiClient,
    keywords: list[str],
    progress: ProgressFn | None = None,
) -> dict[str, Any]:
    if not keywords:
        return {}
    if progress:
        progress(f"Google Trends 对比：{', '.join(keywords)}")
    try:
        timeseries = serpapi.trends_timeseries(keywords, date="today 12-m")
        related = {}
        for keyword in keywords[:3]:
            try:
                related[keyword] = extract_related_queries(serpapi.trends_related_queries(keyword, date="today 12-m"))
            except Exception as exc:
                related[keyword] = {"error": str(exc)}
        return {
            "timeseries_scores": extract_timeseries_scores(timeseries),
            "related_queries": related,
            "raw_timeseries": timeseries,
        }
    except Exception as exc:
        return {"error": str(exc)}


def _read_pdf_inputs(pdf_paths: str, max_chars_per_pdf: int = 8000) -> list[dict[str, Any]]:
    items = []
    for raw_path in _split_multiline(pdf_paths):
        path = Path(raw_path).expanduser()
        if not path.exists():
            items.append({"path": raw_path, "error": "file not found"})
            continue
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            text_parts = []
            for page in reader.pages[:20]:
                text = page.extract_text() or ""
                if text.strip():
                    text_parts.append(text.strip())
            text = "\n".join(text_parts)[:max_chars_per_pdf]
            items.append({"path": str(path), "pages": len(reader.pages), "text_excerpt": text})
        except Exception as exc:
            items.append({"path": raw_path, "error": str(exc)})
    return items


def _visibility_metrics(customer_product: str, competitors: str, answers: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(answers)
    customer_mentions = 0
    competitor_counts: dict[str, int] = {}
    for item in answers:
        result = item.get("result") or {}
        if result.get("mentioned_customer"):
            customer_mentions += 1
        for competitor in result.get("mentioned_competitors") or []:
            competitor_counts[str(competitor)] = competitor_counts.get(str(competitor), 0) + 1
    return {
        "total_questions": total,
        "customer_mentions": customer_mentions,
        "customer_mention_rate": round(customer_mentions / total, 4) if total else 0,
        "competitor_counts": competitor_counts,
        "tracked_competitors": _split_multiline(competitors),
    }


def _save_strategy_report(
    storage: Storage,
    report_type: str,
    subject: str,
    city: str,
    industry: str,
    customer_product: str,
    competitors: str,
    report_md: str,
    raw_json: dict[str, Any],
    filename_prefix: str,
) -> dict[str, Any]:
    run_id = f"{utc_now_iso().replace(':', '').replace('-', '').replace('Z', '')}_{uuid.uuid4().hex[:6]}"
    report_dir = STRATEGY_DIR / f"{run_id}_{safe_filename(subject or customer_product, 40)}"
    report_path = report_dir / f"{filename_prefix}.md"
    data_path = report_dir / f"{filename_prefix}_data.json"
    write_text(report_path, report_md)
    write_text(data_path, json.dumps(raw_json, ensure_ascii=False, indent=2))
    report_id = storage.add_strategy_report(
        {
            "report_type": report_type,
            "subject": subject,
            "city": city,
            "industry": industry,
            "customer_product": customer_product,
            "competitors": competitors,
            "report_md": report_md,
            "raw_json": raw_json,
            "file_path": str(report_path),
        }
    )
    return {
        "id": report_id,
        "report_type": report_type,
        "report_path": str(report_path),
        "data_path": str(data_path),
        "report_md": report_md,
        "raw_json": raw_json,
    }


def _base_input(
    city: str,
    industry: str,
    customer_product: str,
    seed_keyword: str,
    competitors: str,
) -> dict[str, Any]:
    return {
        "city": city,
        "industry": industry,
        "customer_product": customer_product,
        "seed_keyword": seed_keyword,
        "competitors": competitors,
    }


def _split_multiline(value: str) -> list[str]:
    return [item.strip() for item in str(value or "").replace("，", "\n").replace(",", "\n").splitlines() if item.strip()]
