from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from geo_app.config import (
    AppConfig,
    BudgetConfig,
    GEOAIConfig,
    KeywordIntelligenceConfig,
    MeijiekuConfig,
    QwenConfig,
    SerpApiConfig,
)
from geo_app.keyword_intelligence_workflow import build_keyword_prompt_items, build_seed_terms, run_5118_keyword_intelligence


def _app_config(keyword_config: KeywordIntelligenceConfig) -> AppConfig:
    return AppConfig(
        qwen=QwenConfig(api_key="fake"),
        meijieku=MeijiekuConfig(),
        serpapi=SerpApiConfig(),
        budget=BudgetConfig(),
        geo_ai=GEOAIConfig(),
        keyword_intelligence=keyword_config,
    )


def test_build_seed_terms_for_local_medical_beauty() -> None:
    profile = {
        "brand_name": "福州爱美尔医美",
        "category_local": "医疗美容",
        "primary_region": "福州",
        "market_language": "zh",
        "target_market": "domestic",
    }
    seeds = build_seed_terms(profile, max_terms=8)
    assert "福州爱美尔医美" in seeds
    assert "福州医美" in seeds
    assert "福州整形医院" in seeds
    assert "福州双眼皮" in seeds


def test_keyword_prompt_items_filter_brand_terms() -> None:
    profile = {
        "brand_name": "福州爱美尔医美",
        "product_name": "福州爱美尔医美",
        "category_local": "医疗美容",
        "primary_region": "福州",
    }
    keyword_intelligence = {
        "neutral_prompt_candidates": [
            {"keyword": "福州整形医院", "score": 988, "longtail_count": 4723, "bid_company_count": 175, "sem_price": "4.27"},
            {"keyword": "福州双眼皮", "score": 368, "longtail_count": 6440, "bid_company_count": 21, "sem_price": "6.43"},
            {"keyword": "福州爱美尔医美", "score": 1, "longtail_count": 8, "bid_company_count": 0, "sem_price": ""},
        ]
    }
    rows = build_keyword_prompt_items(keyword_intelligence, profile, limit=5)
    questions = [item["question"] for item in rows]
    assert "福州整形医院哪家比较好？" in questions
    assert "福州做双眼皮哪家医院比较推荐？" in questions
    assert all("爱美尔" not in question for question in questions)
    assert rows[0]["keyword_source"] == "5118"


def test_5118_missing_keys_returns_clean_status() -> None:
    profile = {
        "brand_name": "福州爱美尔医美",
        "category_local": "医疗美容",
        "primary_region": "福州",
        "market_language": "zh",
        "target_market": "domestic",
    }
    config = _app_config(KeywordIntelligenceConfig(enable_5118=True))
    result = run_5118_keyword_intelligence(config, profile)
    assert result["status"] == "missing_keys"
    assert result["seed_terms"]


if __name__ == "__main__":
    test_build_seed_terms_for_local_medical_beauty()
    test_keyword_prompt_items_filter_brand_terms()
    test_5118_missing_keys_returns_clean_status()
    print("keyword intelligence workflow tests passed")
