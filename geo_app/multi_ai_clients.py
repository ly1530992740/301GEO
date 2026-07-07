from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any

import requests

from .config import QwenConfig, load_dotenv_if_available
from .qwen_client import QwenClient
from .utils import extract_json


DEFAULT_DOUBAO_RESPONSES_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
DEFAULT_YUANBAO_RESPONSES_URL = "https://tokenhub.tencentmaas.com/v1/responses"
DEFAULT_DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"


@dataclass
class MultiAIResult:
    provider: str
    ok: bool
    content: str
    parsed: Any = None
    raw: Any = None
    search_results: list[dict[str, Any]] | None = None
    error: str = ""


class BaseAIProvider:
    name = "base"

    def ask_json(self, prompt: str, system: str = "", enable_search: bool = False) -> MultiAIResult:
        raise NotImplementedError


class QwenAIProvider(BaseAIProvider):
    name = "qwen"

    def __init__(self, config: QwenConfig):
        self.client = QwenClient(config)
        self.model = config.search_model
        self.config = config

    def ask_json(self, prompt: str, system: str = "", enable_search: bool = False) -> MultiAIResult:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        try:
            result = self.client._call(
                messages,
                model=self.model,
                enable_search=enable_search,
                search_options={
                    "forced_search": self.config.forced_search,
                    "enable_source": self.config.enable_source,
                    "enable_citation": self.config.enable_citation,
                    "search_strategy": self.config.search_strategy,
                }
                if enable_search
                else None,
            )
            parsed = extract_json(result.content, fallback=None)
            return MultiAIResult(self.name, True, result.content, parsed=parsed, raw=result.raw, search_results=result.search_results or [])
        except Exception as exc:
            return MultiAIResult(self.name, False, "", error=str(exc))


class ResponsesAIProvider(BaseAIProvider):
    def __init__(self, name: str, api_key: str, endpoint: str, model: str, body_style: str, timeout: int = 45):
        self.name = name
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.body_style = body_style
        self.timeout = timeout

    def ask_json(self, prompt: str, system: str = "", enable_search: bool = False) -> MultiAIResult:
        del enable_search
        if not self.api_key:
            return MultiAIResult(self.name, False, "", error="missing api key")
        if self.body_style == "doubao":
            body: dict[str, Any] = {
                "model": self.model,
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": f"{system}\n\n{prompt}".strip()}],
                    }
                ],
            }
        else:
            body = {
                "model": self.model,
                "instructions": system or "You are a helpful assistant.",
                "input": prompt,
                "stream": False,
            }
        return _post_and_parse(self.name, self.endpoint, self.api_key, body, self.timeout, response_style="responses")


class ChatCompletionsAIProvider(BaseAIProvider):
    def __init__(self, name: str, api_key: str, endpoint: str, model: str, timeout: int = 45):
        self.name = name
        self.api_key = api_key
        self.endpoint = endpoint
        self.model = model
        self.timeout = timeout

    def ask_json(self, prompt: str, system: str = "", enable_search: bool = False) -> MultiAIResult:
        del enable_search
        if not self.api_key:
            return MultiAIResult(self.name, False, "", error="missing api key")
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
        }
        return _post_and_parse(self.name, self.endpoint, self.api_key, body, self.timeout, response_style="chat")


def build_default_providers(qwen_config: QwenConfig) -> list[BaseAIProvider]:
    load_dotenv_if_available()
    providers: list[BaseAIProvider] = []
    if qwen_config.api_key:
        providers.append(QwenAIProvider(qwen_config))
    providers.append(
        ResponsesAIProvider(
            "doubao",
            _env_first("DOUBAO_API_KEY", "ARK_API_KEY", "VOLCENGINE_API_KEY"),
            os.getenv("DOUBAO_RESPONSES_API_URL", DEFAULT_DOUBAO_RESPONSES_URL).strip() or DEFAULT_DOUBAO_RESPONSES_URL,
            os.getenv("DOUBAO_MODEL", "doubao-seed-evolving").strip() or "doubao-seed-evolving",
            body_style="doubao",
            timeout=max(_int_env("DOUBAO_TIMEOUT_SECONDS", 90), 90),
        )
    )
    providers.append(
        ResponsesAIProvider(
            "yuanbao",
            _env_first("YUANBAO_API_KEY", "HUNYUAN_API_KEY", "TENCENT_HUNYUAN_API_KEY"),
            os.getenv("YUANBAO_RESPONSES_API_URL", DEFAULT_YUANBAO_RESPONSES_URL).strip() or DEFAULT_YUANBAO_RESPONSES_URL,
            os.getenv("YUANBAO_MODEL", "hy3").strip() or "hy3",
            body_style="yuanbao",
            timeout=_int_env("YUANBAO_TIMEOUT_SECONDS", 45),
        )
    )
    providers.append(
        ChatCompletionsAIProvider(
            "deepseek",
            os.getenv("DEEPSEEK_API_KEY", "").strip(),
            os.getenv("DEEPSEEK_CHAT_API_URL", DEFAULT_DEEPSEEK_CHAT_URL).strip() or DEFAULT_DEEPSEEK_CHAT_URL,
            os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
            timeout=_int_env("DEEPSEEK_TIMEOUT_SECONDS", 45),
        )
    )
    return providers


def deepseek_provider() -> ChatCompletionsAIProvider:
    load_dotenv_if_available()
    return ChatCompletionsAIProvider(
        "deepseek",
        os.getenv("DEEPSEEK_API_KEY", "").strip(),
        os.getenv("DEEPSEEK_CHAT_API_URL", DEFAULT_DEEPSEEK_CHAT_URL).strip() or DEFAULT_DEEPSEEK_CHAT_URL,
        os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat",
        timeout=_int_env("DEEPSEEK_TIMEOUT_SECONDS", 45),
    )


def _post_and_parse(
    provider: str,
    endpoint: str,
    api_key: str,
    body: dict[str, Any],
    timeout: int,
    response_style: str,
) -> MultiAIResult:
    last_error = ""
    for attempt in range(1, 4):
        try:
            response = requests.post(
                endpoint,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=timeout,
            )
            try:
                raw: Any = response.json()
            except ValueError:
                raw = response.text
            if response.status_code >= 400:
                return MultiAIResult(provider, False, "", raw=raw, error=f"HTTP {response.status_code}: {_safe_text(raw, 1000)}")
            content = _responses_text(raw) if response_style == "responses" else _chat_text(raw)
            parsed = extract_json(content, fallback=None)
            return MultiAIResult(provider, True, content, parsed=parsed, raw=raw)
        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(0.6 * attempt)
    return MultiAIResult(provider, False, "", error=last_error)


def _responses_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload or "")
    if payload.get("output_text"):
        return str(payload.get("output_text") or "")
    output = payload.get("output")
    if isinstance(output, list):
        parts = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and (part.get("text") or part.get("output_text")):
                        parts.append(str(part.get("text") or part.get("output_text")))
            elif isinstance(content, str):
                parts.append(content)
        if parts:
            return "\n".join(parts)
    return json.dumps(payload, ensure_ascii=False)


def _chat_text(payload: Any) -> str:
    if not isinstance(payload, dict):
        return str(payload or "")
    choices = payload.get("choices") or []
    if choices:
        message = (choices[0] or {}).get("message") or {}
        if isinstance(message, dict) and message.get("content"):
            return str(message.get("content") or "")
    return json.dumps(payload, ensure_ascii=False)


def _env_first(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\n", " ").replace("\r", " ").strip()
    return text[:limit]
