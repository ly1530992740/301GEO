from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT_DIR / "output"
TASKS_DIR = OUTPUT_DIR / "tasks"
DB_PATH = OUTPUT_DIR / "geo_tasks.sqlite3"


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT_DIR / ".env")


@dataclass
class QwenConfig:
    api_key: str = ""
    api_host: str = ""
    search_model: str = "qwen-plus"
    analysis_model: str = "qwen3.7-max"
    writing_model: str = "qwen-plus"
    search_strategy: str = "max"
    analysis_strategy: str = "agent_max"
    forced_search: bool = True
    enable_source: bool = True
    enable_citation: bool = True


@dataclass
class MeijiekuConfig:
    base_url: str = "https://api.meijieku.com"
    mobile: str = ""
    password: str = ""
    token: str = ""
    resource_page_size: int = 100
    resource_max_pages: int = 20
    mock_mode: bool = False


@dataclass
class SerpApiConfig:
    api_key: str = ""
    default_geo: str = "CN"
    default_hl: str = "zh-CN"
    default_gl: str = "cn"
    timeout_seconds: int = 30


@dataclass
class BudgetConfig:
    max_price_per_platform: float = 0.0
    max_total_budget: float = 0.0
    require_fuzzy_confirmation: bool = True


@dataclass
class AppConfig:
    qwen: QwenConfig
    meijieku: MeijiekuConfig
    serpapi: SerpApiConfig
    budget: BudgetConfig


def normalize_meijieku_base_url(value: str) -> str:
    base_url = (value or "https://api.meijieku.com").strip().rstrip("/")
    if base_url.lower().endswith("/api"):
        base_url = base_url[:-4].rstrip("/")
    return base_url or "https://api.meijieku.com"


def _float_env(name: str, default: float = 0.0) -> float:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def load_config() -> AppConfig:
    load_dotenv_if_available()
    return AppConfig(
        qwen=QwenConfig(
            api_key=os.getenv("DASHSCOPE_API_KEY", "").strip(),
            api_host=(
                os.getenv("DASHSCOPE_BASE_HTTP_API_URL", "").strip().rstrip("/")
                or os.getenv("QWEN_API_HOST", "").strip().rstrip("/")
            ),
            search_model=os.getenv("QWEN_SEARCH_MODEL", "qwen-plus").strip(),
            analysis_model=os.getenv("QWEN_ANALYSIS_MODEL", "qwen3.7-max").strip(),
            writing_model=os.getenv("QWEN_WRITING_MODEL", "qwen-plus").strip(),
            search_strategy=os.getenv("QWEN_SEARCH_STRATEGY", "max").strip(),
            analysis_strategy=os.getenv("QWEN_ANALYSIS_STRATEGY", "agent_max").strip(),
        ),
        meijieku=MeijiekuConfig(
            base_url=normalize_meijieku_base_url(os.getenv("MEIJIEKU_BASE_URL", "https://api.meijieku.com")),
            mobile=os.getenv("MEIJIEKU_MOBILE", "").strip(),
            password=os.getenv("MEIJIEKU_PASSWORD", "").strip(),
            token=os.getenv("MEIJIEKU_TOKEN", "").strip(),
            resource_page_size=_int_env("MEIJIEKU_RESOURCE_PAGE_SIZE", 100),
            resource_max_pages=_int_env("MEIJIEKU_RESOURCE_MAX_PAGES", 20),
            mock_mode=os.getenv("MEIJIEKU_MOCK_MODE", "false").lower() in {"1", "true", "yes"},
        ),
        serpapi=SerpApiConfig(
            api_key=os.getenv("SERPAPI_API_KEY", "").strip(),
            default_geo=os.getenv("SERPAPI_DEFAULT_GEO", "CN").strip() or "CN",
            default_hl=os.getenv("SERPAPI_DEFAULT_HL", "zh-CN").strip() or "zh-CN",
            default_gl=os.getenv("SERPAPI_DEFAULT_GL", "cn").strip() or "cn",
            timeout_seconds=_int_env("SERPAPI_TIMEOUT_SECONDS", 30),
        ),
        budget=BudgetConfig(
            max_price_per_platform=_float_env("MAX_PRICE_PER_PLATFORM", 0.0),
            max_total_budget=_float_env("MAX_TOTAL_BUDGET", 0.0),
            require_fuzzy_confirmation=os.getenv("REQUIRE_FUZZY_CONFIRMATION", "true").lower()
            not in {"0", "false", "no"},
        ),
    )


def ensure_dirs() -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
