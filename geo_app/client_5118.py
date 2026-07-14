from __future__ import annotations

from typing import Any
from urllib.parse import unquote

import requests

from .keyword_intelligence import KeywordMetric, KeywordSuggestion, SearchRankItem, normalize_5118_keyword_metric, normalize_5118_rank_item


class Client5118:
    BASE_URL = "https://apis.5118.com"

    def __init__(self, api_key: str = "", base_url: str = BASE_URL, timeout_seconds: int = 30):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()

    def longtail_keywords(
        self,
        keyword: str,
        page_index: int = 1,
        page_size: int = 20,
        api_key: str | None = None,
    ) -> list[KeywordMetric]:
        payload = self.post(
            "/keyword/word/v2",
            {"keyword": keyword, "page_index": page_index, "page_size": page_size},
            api_key=api_key,
        )
        words = ((payload.get("data") or {}).get("word")) or []
        return [normalize_5118_keyword_metric(item) for item in words if isinstance(item, dict)]

    def suggest_words(self, word: str, platform: str = "baidu", api_key: str | None = None) -> list[KeywordSuggestion]:
        payload = self.post("/suggest/list", {"word": word, "platform": platform}, api_key=api_key)
        rows = payload.get("data") or []
        result = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            result.append(
                KeywordSuggestion(
                    keyword=str(item.get("promote_word") or ""),
                    source="5118",
                    platform=str(item.get("platform") or platform),
                    parent_keyword=str(item.get("word") or word),
                    raw=item,
                )
            )
        return result

    def submit_keyword_params(self, keywords: list[str], api_key: str | None = None) -> str:
        payload = self.post("/keywordparam/v2", {"keywords": "|".join(keywords)}, api_key=api_key)
        taskid = ((payload.get("data") or {}).get("taskid")) or ""
        return str(taskid)

    def get_keyword_params(self, taskid: str, api_key: str | None = None) -> list[KeywordMetric]:
        payload = self.post("/keywordparam/v2", {"taskid": taskid}, api_key=api_key)
        rows = ((payload.get("data") or {}).get("keyword_param")) or []
        return [normalize_5118_keyword_metric(item) for item in rows if isinstance(item, dict)]

    def submit_pc_rank_top(self, keywords: list[str], checkrow: int = 50, api_key: str | None = None) -> str:
        payload = self.post(
            "/keywordrank/baidupc",
            {"keywords": "|".join(keywords), "checkrow": checkrow},
            api_key=api_key,
        )
        taskid = ((payload.get("data") or {}).get("taskid")) or ""
        return str(taskid)

    def get_pc_rank_top(self, taskid: str, api_key: str | None = None) -> list[SearchRankItem]:
        payload = self.post("/keywordrank/baidupc", {"taskid": taskid}, api_key=api_key)
        monitors = ((payload.get("data") or {}).get("keyword_monitor")) or []
        return self._normalize_rank_monitors(monitors)

    def submit_realtime_pc_rank(
        self,
        url: str,
        keywords: list[str],
        checkrow: int = 50,
        api_key: str | None = None,
    ) -> str:
        payload = self.post(
            "/morerank/baidupc",
            {"url": url, "keywords": "|".join(keywords), "checkrow": checkrow},
            api_key=api_key,
        )
        taskid = ((payload.get("data") or {}).get("taskid")) or ""
        return str(taskid)

    def get_realtime_pc_rank(self, taskid: str, api_key: str | None = None) -> list[SearchRankItem]:
        payload = self.post("/morerank/baidupc", {"taskid": taskid}, api_key=api_key)
        monitors = ((payload.get("data") or {}).get("keywordmonitor")) or []
        return self._normalize_rank_monitors(monitors)

    def _normalize_rank_monitors(self, monitors: list[Any]) -> list[SearchRankItem]:
        result = []
        for monitor in monitors:
            if not isinstance(monitor, dict):
                continue
            keyword = str(monitor.get("keyword") or "")
            for item in monitor.get("ranks") or []:
                if isinstance(item, dict):
                    result.append(normalize_5118_rank_item(keyword, item))
        return result

    def post(self, endpoint: str, data: dict[str, Any], api_key: str | None = None) -> dict[str, Any]:
        key = (api_key if api_key is not None else self.api_key).strip()
        if not key:
            raise RuntimeError("5118 API key is not configured.")
        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.post(
                url,
                headers={
                    "Authorization": key,
                    "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                },
                data=data,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError(f"5118 request failed: url={url}, reason={exc}") from exc
        try:
            payload = self._decode(response.json())
        except ValueError as exc:
            raise RuntimeError(f"5118 response is not JSON: url={url}, body={response.text[:300]}") from exc
        errcode = str(payload.get("errcode", ""))
        if errcode and errcode != "0":
            raise RuntimeError(f"5118 API error {errcode}: {payload.get('errmsg') or payload}")
        return payload

    def _decode(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._decode(child) for key, child in value.items()}
        if isinstance(value, list):
            return [self._decode(child) for child in value]
        if isinstance(value, str):
            return unquote(value)
        return value
