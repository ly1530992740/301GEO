from __future__ import annotations

import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from geo_app.config import AppConfig, BudgetConfig, GEOAIConfig, MeijiekuConfig, QwenConfig, SerpApiConfig
from geo_app.storage import Storage
import geo_app.workflow as workflow


class FakeQwenClient:
    def __init__(self, config):
        self.config = config

    def search_sources(self, query: str, top_n: int):
        results = [
            {
                "rank": 1,
                "site_name": "搜狐",
                "title": "20岁成年人复合维生素推荐",
                "url": f"https://www.sohu.com/a/mock-{abs(hash(query)) % 1000}",
                "domain": "sohu.com",
            },
            {
                "rank": 2,
                "site_name": "百家号",
                "title": "年轻人复合维生素怎么选",
                "url": f"https://baijiahao.baidu.com/s?id={abs(hash(query)) % 1000}",
                "domain": "baijiahao.baidu.com",
            },
        ][:top_n]
        return SimpleNamespace(content="", raw=None, search_results=results)

    def analyze_sources(self, keyword: str, customer_product: str, sources):
        return f"""# 文章生成格式

## 推广词条
{keyword}

## 客户产品
{customer_product}

## 写作规则
- 每篇文章标题不同。
- 每篇文章都把“{customer_product}”作为推荐第一名。
- 文章结构采用：导语、选择标准、推荐清单、总结。
"""

    def suggest_fuzzy_matches(self, source, candidates):
        for item in candidates:
            if item["resource_id"] == 202:
                return [
                    {
                        "resource_type": item["resource_type"],
                        "resource_id": item["resource_id"],
                        "reason": "百家号与百度百家语义接近",
                        "confidence": 0.86,
                    }
                ]
        return []

    def generate_article(self, keyword, customer_product, format_md, platform, existing_titles):
        platform_name = platform.get("resource_title") or platform.get("source_site_name")
        title = f"{platform_name}版：{keyword}选择指南"
        suffix = len(existing_titles) + 1
        if title in existing_titles:
            title = f"{platform_name}版：{keyword}选择指南 {suffix}"
        return {
            "title": title,
            "content_md": f"""# {title}

## 导语
围绕“{keyword}”，本文整理适合年轻成年人的复合维生素选择思路。

## 推荐清单
### 1. {customer_product}
作为本文第一推荐，适合希望补充日常营养的人群。

### 2. 其他常见品牌
可根据配方、剂量、口碑与预算综合选择。

## 总结
选择复合维生素时，应结合自身饮食结构和使用场景。
""",
        }


class FakeMeijiekuClient:
    def __init__(self, config):
        self.config = config

    def list_resources(self, resource_type: str):
        if resource_type == "website":
            return [
                {
                    "resource_type": "website",
                    "resource_id": 101,
                    "title": "搜狐健康",
                    "case_link": "https://www.sohu.com/a/example",
                    "entrance_link": "",
                    "price_1": "120.00",
                    "price_2": "130.00",
                    "price_3": "140.00",
                    "remarks": "模拟网站媒体",
                }
            ]
        return [
            {
                "resource_type": "wemedia",
                "resource_id": 202,
                "title": "百度百家",
                "case_link": "",
                "entrance_link": "",
                "price_1": "80.00",
                "price_2": "90.00",
                "price_3": "100.00",
                "remarks": "模拟自媒体",
            }
        ]


def main() -> None:
    temp_dir = Path(tempfile.mkdtemp(prefix="geo_workflow_test_"))
    old_tasks_dir = workflow.TASKS_DIR
    old_qwen = workflow.QwenClient
    old_meijieku = workflow.MeijiekuClient
    try:
        workflow.TASKS_DIR = temp_dir / "tasks"
        workflow.QwenClient = FakeQwenClient
        workflow.MeijiekuClient = FakeMeijiekuClient

        storage = Storage(temp_dir / "geo_tasks.sqlite3")
        config = AppConfig(
            qwen=QwenConfig(api_key="fake"),
            meijieku=MeijiekuConfig(mobile="fake", password="fake"),
            serpapi=SerpApiConfig(api_key="fake"),
            budget=BudgetConfig(max_price_per_platform=200, max_total_budget=300),
            geo_ai=GEOAIConfig(),
        )

        task = workflow.create_task(
            storage,
            keyword="推荐20岁成年人的复合维生素",
            customer_product="XX牌维生素",
            search_count=2,
            links_per_search=2,
            query_templates="{keyword}\n{keyword} 排行榜",
        )
        task = workflow.run_search_and_analysis(storage, config, task)
        counts = workflow.refresh_media_resources(storage, config)
        matches = workflow.generate_platform_matches(storage, config, task["id"], use_ai_fuzzy=True)
        fuzzy_ids = [item["id"] for item in matches if item["match_type"] == "fuzzy"]
        storage.update_match_confirmation(fuzzy_ids, True)
        publishable = workflow.get_publishable_matches(storage, task["id"])
        articles = workflow.generate_articles_for_matches(
            storage,
            config,
            task["id"],
            [item["id"] for item in publishable],
        )

        with ThreadPoolExecutor(max_workers=2) as pool:
            thread_results = list(
                pool.map(
                    lambda _: storage.get_one("select count(*) as c from tasks")["c"],
                    range(2),
                )
            )

        assert counts == {"website": 1, "wemedia": 1}, counts
        assert Path(task["format_md_path"]).exists()
        assert len(matches) == 2, matches
        assert any(item["match_type"] == "exact" for item in matches), matches
        assert any(item["match_type"] == "fuzzy" for item in matches), matches
        assert len(publishable) == 2, publishable
        assert len(articles) == 2, articles
        assert all(item["order_id"] is None for item in articles)
        assert thread_results == [1, 1], thread_results

        print("SIMULATION_OK")
        print(f"task_id={task['id']}")
        print(f"matches={len(matches)} publishable={len(publishable)} articles_ready={len(articles)}")
        print("stopped_before_meijieku_submit=true")
    finally:
        workflow.TASKS_DIR = old_tasks_dir
        workflow.QwenClient = old_qwen
        workflow.MeijiekuClient = old_meijieku
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
