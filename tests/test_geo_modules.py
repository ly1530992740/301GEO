from __future__ import annotations

import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geo_app.action_planner import build_action_plan
from geo_app.content_monitoring import build_content_monitoring
from geo_app.geo_metrics import build_standard_geo_metrics
from geo_app.owned_asset_audit import audit_owned_assets
from geo_app.integrated_report_renderer import render_integrated_outputs
from geo_app.source_intelligence import build_source_intelligence, classify_domain


def sample_profile() -> dict:
    return {
        "product_name": "测试医美",
        "brand_name": "美贝尔",
        "brand_aliases": ["MeiBeiEr"],
        "category_local": "福州医美",
    }


def test_standard_geo_metrics() -> None:
    metrics = build_standard_geo_metrics(
        {
            "neutral_visibility_summary": {
                "visibility_score": 25,
                "visibility_level": "low",
                "brand_mentioned_responses": 1,
                "total_ai_responses": 4,
                "mention_count": 1,
                "avg_position": 7,
                "sentiment_score": 58,
                "prompt_success_rate": 0.25,
                "provider_coverage_count": 1,
                "provider_total_count": 4,
            },
            "brand_visibility_metrics": [
                {"brand_name": "美贝尔", "is_user_brand": True, "mention_count": 1, "share_of_voice": 0.1},
                {"brand_name": "竞品A", "mention_count": 5},
                {"brand_name": "竞品B", "mention_count": 4},
            ],
            "prompt_runs": [{"prompt": "推荐一下福州医美"}],
        }
    )
    assert metrics["visibility"]["score"] == 25
    assert metrics["sov"]["value_label"] == "10.0%"
    assert metrics["position"]["value_label"] == "#7"


def test_source_intelligence() -> None:
    source_links = [
        {"url": "https://www.zhihu.com/question/1", "domain": "www.zhihu.com", "engine": "qwen", "label": "竞品A 福州医美"},
        {"url": "https://news.sohu.com/a", "domain": "news.sohu.com", "engine": "deepseek", "label": "美贝尔 资质"},
        {"url": "https://news.sohu.com/a", "domain": "news.sohu.com", "engine": "doubao", "label": "美贝尔 案例"},
    ]
    source_articles = [
        {"url": "https://www.zhihu.com/question/1", "text_excerpt": "竞品A 医美 推荐"},
        {"url": "https://news.sohu.com/a", "text_excerpt": "美贝尔 医美 资质 案例"},
    ]
    result = build_source_intelligence(source_links, source_articles, [], [{"brand_name": "竞品A"}], sample_profile())
    assert classify_domain("www.zhihu.com") == "UGC"
    assert result["domain_summary"][0]["citation_count"] >= 1
    assert any(item["domain_type"] == "UGC" for item in result["domain_summary"])
    assert result["source_opportunities"]


def test_owned_asset_audit() -> None:
    audit = audit_owned_assets(
        {
            "website_url": "https://example.com",
            "website_pages": [
                {"url": "https://example.com/about", "text": "品牌 简介 专业 服务 联系 电话 Organization schema.org"},
                {"url": "https://example.com/faq", "text": "FAQ 常见问题 价格 资质 案例"},
            ],
        },
        sample_profile(),
    )
    assert audit["ai_readability_score"] > 50
    assert audit["crawl_success_count"] == 2
    assert any(item["asset_key"] == "faq" and item["present"] for item in audit["asset_checks"])


def test_content_monitoring_and_action_plan() -> None:
    source_intelligence = {
        "domain_summary": [
            {
                "domain": "www.zhihu.com",
                "mentioned_user_brand": False,
                "brands_appear": ["竞品A"],
                "action": "补充问答内容",
            }
        ],
        "source_opportunities": [
            {"priority": "高", "domain": "www.zhihu.com", "domain_type": "UGC", "reason": "竞品出现但客户未出现"}
        ],
    }
    monitoring = build_content_monitoring(
        {
            "prompt_runs": [
                {
                    "provider": "qwen",
                    "prompt": "推荐一下福州医美",
                    "sentiment_score": 35,
                    "risk_terms": ["投诉"],
                    "answer_excerpt": "美贝尔存在投诉，需谨慎。",
                }
            ],
            "brand_visibility_metrics": [
                {"brand_name": "美贝尔", "is_user_brand": True, "mention_count": 1, "avg_position": 8, "sentiment_score": 35},
                {"brand_name": "竞品A", "mention_count": 5, "avg_position": 1, "sentiment_score": 76},
            ],
            "recommendation_items": [{"brand_name": "竞品A", "reason": "口碑和资质更突出"}],
            "source_intelligence": source_intelligence,
        }
    )
    metrics = build_standard_geo_metrics(
        {
            "neutral_visibility_summary": {
                "visibility_score": 25,
                "brand_mentioned_responses": 1,
                "total_ai_responses": 4,
                "mention_count": 1,
                "avg_position": 8,
                "sentiment_score": 35,
                "prompt_success_rate": 0.25,
                "provider_coverage_count": 1,
                "provider_total_count": 4,
            },
            "brand_visibility_metrics": [{"brand_name": "美贝尔", "is_user_brand": True, "mention_count": 1, "share_of_voice": 0.1}],
        }
    )
    audit = audit_owned_assets({"website_pages": [{"url": "https://example.com", "text": "品牌 服务"}]}, sample_profile())
    plan = build_action_plan(
        {
            "standard_geo_metrics": metrics,
            "source_intelligence": source_intelligence,
            "owned_asset_audit": audit,
            "content_monitoring": monitoring,
            "media_cost_analysis": {"target_articles": 3, "estimated_total_cost": 900},
        }
    )
    assert monitoring["opinion_monitoring"]["negative_mentions"]
    assert plan["summary"]["total_count"] > 0
    assert any(item["module"] == "Sources" for item in plan["actions"])


def test_report_renderer_backfills_new_modules() -> None:
    data = {
        "workflow_version": "test",
        "product_profile": sample_profile(),
        "sources": {
            "website_url": "https://example.com",
            "website_pages": [{"url": "https://example.com", "text": "品牌 服务 FAQ 价格 资质 schema.org Organization"}],
        },
        "recommendation_items": [
            {
                "engine": "qwen",
                "question": "推荐一下福州医美",
                "brand_name": "竞品A",
                "rank": 1,
                "reason": "专业 口碑",
                "citation_urls": ["https://www.zhihu.com/question/1"],
            },
            {
                "engine": "qwen",
                "question": "推荐一下福州医美",
                "brand_name": "美贝尔",
                "rank": 8,
                "reason": "存在投诉 风险",
                "citation_urls": ["https://news.sohu.com/a"],
            },
        ],
        "source_links": [
            {"url": "https://www.zhihu.com/question/1", "domain": "www.zhihu.com", "engine": "qwen", "label": "竞品A 医美"},
            {"url": "https://news.sohu.com/a", "domain": "news.sohu.com", "engine": "qwen", "label": "美贝尔 资质"},
        ],
        "source_articles": [
            {"url": "https://www.zhihu.com/question/1", "domain": "www.zhihu.com", "text_excerpt": "竞品A 口碑 医美"},
            {"url": "https://news.sohu.com/a", "domain": "news.sohu.com", "text_excerpt": "美贝尔 投诉 风险"},
        ],
    }
    with TemporaryDirectory() as temp_dir:
        outputs = render_integrated_outputs(Path(temp_dir), data, "zh")
        markdown = Path(outputs["report_md_path"]).read_text(encoding="utf-8")
        dashboard = Path(outputs["dashboard_html_path"]).read_text(encoding="utf-8")
        assert "GEO 指标定义" in markdown
        assert "Sources AI 信源分析" in markdown
        assert "官网结构化信源审计" in markdown
        assert "Actions 优化待办清单" in markdown
        assert "GEO 指标定义" in dashboard
        assert "AI 推荐引用信源" in dashboard
        assert "官网结构化信源审计" in dashboard
        assert "内容监控与舆情监控" in dashboard
        assert "Actions 优化待办清单" in dashboard


if __name__ == "__main__":
    test_standard_geo_metrics()
    test_source_intelligence()
    test_owned_asset_audit()
    test_content_monitoring_and_action_plan()
    test_report_renderer_backfills_new_modules()
    print("geo module tests passed")
