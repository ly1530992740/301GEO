from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

import requests
from requests import Response

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from geo_app.baidu_search_client import (  # noqa: E402
    DEFAULT_BAIDU_SEARCH_API_KEY,
    BaiduSearchClient,
    extract_baidu_results,
    extract_baidu_total_count,
)
from geo_app.config import load_config  # noqa: E402
from geo_app.qwen_client import QwenClient  # noqa: E402


DEFAULT_BAIDU_SEARCH_URL = "https://qianfan.baidubce.com/v2/ai_search/web_search"
DEFAULT_DEEPSEEK_CHAT_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_DOUBAO_RESPONSES_URL = "https://ark.cn-beijing.volces.com/api/v3/responses"
DEFAULT_YUANBAO_RESPONSES_URL = "https://tokenhub.tencentmaas.com/v1/responses"


@dataclass
class ConnectivityResult:
    provider: str
    ok: bool
    elapsed_ms: int
    detail: str
    endpoint: str = ""
    model: str = ""
    credential_source: str = ""
    samples: list[dict[str, Any]] = field(default_factory=list)


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(ROOT_DIR / ".env", override=True)


def _env_first(*names: str) -> tuple[str, str]:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    return "", ""


def _int_env(default: int, *names: str) -> int:
    for name in names:
        value = os.getenv(name, "").strip()
        if not value:
            continue
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\r", " ").replace("\n", " ").strip()
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _post_json_with_retries(
    endpoint: str,
    headers: dict[str, str],
    body: dict[str, Any],
    timeout: int,
    attempts: int = 3,
) -> tuple[Response, str]:
    last_error = ""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.post(endpoint, headers=headers, json=body, timeout=timeout)
            return response, "" if attempt == 1 else f" retried={attempt}."
        except requests.RequestException as exc:
            last_error = _safe_text(exc, 1000)
            if attempt >= attempts:
                raise
            time.sleep(0.6 * attempt)
    raise RuntimeError(last_error or "Request failed.")


def _chat_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return _safe_text(payload)

    choices = payload.get("choices") or payload.get("Choices") or []
    if isinstance(choices, list) and choices:
        first = choices[0] or {}
        message = first.get("message") or first.get("Message") or {}
        if isinstance(message, dict):
            content = message.get("content") or message.get("Content")
            if content:
                return _safe_text(content)
        delta = first.get("delta") or first.get("Delta") or {}
        if isinstance(delta, dict):
            content = delta.get("content") or delta.get("Content")
            if content:
                return _safe_text(content)
        text = first.get("text") or first.get("Text")
        if text:
            return _safe_text(text)

    response = payload.get("Response") or payload.get("response")
    if isinstance(response, dict):
        return _chat_content(response)
    return _safe_text(payload)


def _responses_content(payload: Any) -> str:
    if not isinstance(payload, dict):
        return _safe_text(payload)

    direct = payload.get("output_text") or payload.get("text")
    if direct:
        return _safe_text(direct)

    output = payload.get("output")
    if isinstance(output, list):
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    text = part.get("text") or part.get("output_text")
                    if text:
                        parts.append(str(text))
            elif isinstance(content, str):
                parts.append(content)
        if parts:
            return _safe_text("".join(parts))

    return _safe_text(payload)


def _extract_generic_samples(payload: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            title = value.get("title") or value.get("name")
            url = value.get("url") or value.get("link")
            snippet = value.get("summary") or value.get("snippet") or value.get("content")
            if title or url:
                found.append(
                    {
                        "title": _safe_text(title, 120),
                        "url": _safe_text(url, 240),
                        "snippet": _safe_text(snippet, 180),
                    }
                )
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(payload)
    dedup: dict[str, dict[str, Any]] = {}
    for item in found:
        key = item.get("url") or item.get("title")
        if key and key not in dedup:
            dedup[key] = item
    return list(dedup.values())[:5]


def test_openai_compatible_chat(
    provider: str,
    query: str,
    api_key_names: tuple[str, ...],
    url_env: str,
    default_url: str,
    model_env: str,
    default_model: str,
    timeout_env: str,
    extra_body: dict[str, Any] | None = None,
) -> ConnectivityResult:
    _load_dotenv()
    api_key, key_name = _env_first(*api_key_names)
    endpoint, endpoint_source = _env_first(url_env)
    endpoint = endpoint or default_url
    model, model_source = _env_first(model_env)
    model = model or default_model
    timeout = _int_env(30, timeout_env, "AI_TIMEOUT_SECONDS")
    started = time.perf_counter()

    if not api_key:
        return ConnectivityResult(
            provider=provider,
            ok=False,
            elapsed_ms=0,
            detail=f"Missing one of: {', '.join(api_key_names)}.",
            endpoint=endpoint,
            model=model,
        )

    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a connectivity test assistant. Reply briefly."},
            {"role": "user", "content": f"请只回复 OK，并补一句中文说明。测试问题：{query}"},
        ],
        "stream": False,
    }
    if extra_body:
        body.update(extra_body)

    try:
        response, retry_note = _post_json_with_retries(
            endpoint,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body,
            timeout,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            return ConnectivityResult(
                provider=provider,
                ok=False,
                elapsed_ms=elapsed_ms,
                detail=f"HTTP {response.status_code}: {_safe_text(payload, 1000)}",
                endpoint=endpoint,
                model=model,
                credential_source=key_name,
            )

        content = _chat_content(payload)
        detail = content or "Empty response."
        detail += retry_note
        if not model_source:
            detail += f" Default model used: {default_model}."
        if not endpoint_source:
            detail += " Default endpoint used."
        return ConnectivityResult(
            provider=provider,
            ok=bool(content),
            elapsed_ms=elapsed_ms,
            detail=detail,
            endpoint=endpoint,
            model=model,
            credential_source=key_name,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConnectivityResult(provider, False, elapsed_ms, _safe_text(exc, 1000), endpoint, model, key_name)


def test_responses_api(
    provider: str,
    query: str,
    api_key_names: tuple[str, ...],
    url_env: str,
    default_url: str,
    model_env: str,
    default_model: str,
    timeout_env: str,
    body_style: str,
) -> ConnectivityResult:
    _load_dotenv()
    api_key, key_name = _env_first(*api_key_names)
    endpoint, endpoint_source = _env_first(url_env)
    endpoint = endpoint or default_url
    model, model_source = _env_first(model_env)
    model = model or default_model
    timeout = _int_env(30, timeout_env, "AI_TIMEOUT_SECONDS")
    started = time.perf_counter()

    if not api_key:
        return ConnectivityResult(
            provider=provider,
            ok=False,
            elapsed_ms=0,
            detail=f"Missing one of: {', '.join(api_key_names)}.",
            endpoint=endpoint,
            model=model,
        )

    if body_style == "doubao":
        body: dict[str, Any] = {
            "model": model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"请只回复 OK，并补一句中文说明。测试问题：{query}",
                        }
                    ],
                }
            ],
        }
    else:
        body = {
            "model": model,
            "instructions": "You are a helpful connectivity test assistant. Reply briefly.",
            "input": f"请只回复 OK，并补一句中文说明。测试问题：{query}",
            "stream": False,
        }

    try:
        response, retry_note = _post_json_with_retries(
            endpoint,
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            body,
            timeout,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        try:
            payload: Any = response.json()
        except ValueError:
            payload = response.text

        if response.status_code >= 400:
            return ConnectivityResult(
                provider=provider,
                ok=False,
                elapsed_ms=elapsed_ms,
                detail=f"HTTP {response.status_code}: {_safe_text(payload, 1000)}",
                endpoint=endpoint,
                model=model,
                credential_source=key_name,
            )

        content = _responses_content(payload)
        detail = content or "Empty response."
        detail += retry_note
        if not model_source:
            detail += f" Default model used: {default_model}."
        if not endpoint_source:
            detail += " Default endpoint used."
        return ConnectivityResult(
            provider=provider,
            ok=bool(content),
            elapsed_ms=elapsed_ms,
            detail=detail,
            endpoint=endpoint,
            model=model,
            credential_source=key_name,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConnectivityResult(provider, False, elapsed_ms, _safe_text(exc, 1000), endpoint, model, key_name)


def test_qwen(query: str) -> ConnectivityResult:
    _load_dotenv()
    config = load_config()
    started = time.perf_counter()
    model = config.qwen.search_model
    if not config.qwen.api_key:
        return ConnectivityResult("qwen", False, 0, "Missing DASHSCOPE_API_KEY.", model=model)

    client = QwenClient(config.qwen)
    last_error = ""
    for attempt in range(1, 4):
        try:
            result = client._call(
                [{"role": "user", "content": f"连通性测试：请用一句中文回答这个问题：{query}"}],
                model=model,
                enable_search=False,
            )
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            content = _safe_text(result.content)
            detail = content or "Empty response."
            if attempt > 1:
                detail += f" retried={attempt}."
            return ConnectivityResult("qwen", bool(content), elapsed_ms, detail, model=model, credential_source="DASHSCOPE_API_KEY")
        except Exception as exc:
            last_error = _safe_text(exc, 1000)
            if attempt < 3:
                time.sleep(0.6 * attempt)
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return ConnectivityResult("qwen", False, elapsed_ms, last_error, model=model, credential_source="DASHSCOPE_API_KEY")


def test_baidu(query: str) -> ConnectivityResult:
    _load_dotenv()
    api_key, key_name = _env_first("BAIDU_API_KEY", "BAIDU_QIANFAN_API_KEY", "BAIDU_SEARCH_API_KEY")
    credential_source = key_name
    if not api_key and DEFAULT_BAIDU_SEARCH_API_KEY:
        api_key = DEFAULT_BAIDU_SEARCH_API_KEY
        credential_source = "geo_app.baidu_search_client.DEFAULT_BAIDU_SEARCH_API_KEY"

    endpoint, endpoint_source = _env_first("BAIDU_SEARCH_API_URL")
    endpoint = endpoint or DEFAULT_BAIDU_SEARCH_URL
    top_k = _int_env(5, "BAIDU_SEARCH_TOP_K")
    timeout = _int_env(30, "BAIDU_TIMEOUT_SECONDS")
    started = time.perf_counter()

    if not api_key:
        return ConnectivityResult(
            provider="baidu",
            ok=False,
            elapsed_ms=0,
            detail="Missing BAIDU_API_KEY, BAIDU_QIANFAN_API_KEY, or BAIDU_SEARCH_API_KEY.",
            endpoint=endpoint,
        )

    try:
        client = BaiduSearchClient(api_key=api_key, timeout_seconds=timeout)
        client.endpoint = endpoint
        retry_note = ""
        for attempt in range(1, 4):
            try:
                raw = client.web_search(query[:80], top_k=top_k)
                if attempt > 1:
                    retry_note = f" retried={attempt}."
                break
            except Exception:
                if attempt >= 3:
                    raise
                time.sleep(0.6 * attempt)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        results = extract_baidu_results(raw)
        samples = [
            {
                "title": _safe_text(item.get("title"), 120),
                "url": _safe_text(item.get("url"), 240),
                "snippet": _safe_text(item.get("snippet"), 180),
            }
            for item in results[:5]
        ]
        if not samples:
            samples = _extract_generic_samples(raw)
        total_count = extract_baidu_total_count(raw)
        total_part = f" total_count={total_count}." if total_count is not None else " total_count not found."
        endpoint_part = " Default endpoint used." if not endpoint_source else ""
        return ConnectivityResult(
            provider="baidu",
            ok=True,
            elapsed_ms=elapsed_ms,
            detail=f"Baidu search API returned JSON with {len(samples)} sample result(s).{total_part}{endpoint_part}{retry_note}",
            endpoint=endpoint,
            credential_source=credential_source,
            samples=samples,
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return ConnectivityResult("baidu", False, elapsed_ms, _safe_text(exc, 1000), endpoint=endpoint, credential_source=credential_source)


def test_doubao(query: str) -> ConnectivityResult:
    return test_responses_api(
        provider="doubao",
        query=query,
        api_key_names=("DOUBAO_API_KEY", "ARK_API_KEY", "VOLCENGINE_API_KEY"),
        url_env="DOUBAO_RESPONSES_API_URL",
        default_url=DEFAULT_DOUBAO_RESPONSES_URL,
        model_env="DOUBAO_MODEL",
        default_model="doubao-seed-evolving",
        timeout_env="DOUBAO_TIMEOUT_SECONDS",
        body_style="doubao",
    )


def test_yuanbao(query: str) -> ConnectivityResult:
    return test_responses_api(
        provider="yuanbao",
        query=query,
        api_key_names=("YUANBAO_API_KEY", "HUNYUAN_API_KEY", "TENCENT_HUNYUAN_API_KEY"),
        url_env="YUANBAO_RESPONSES_API_URL",
        default_url=DEFAULT_YUANBAO_RESPONSES_URL,
        model_env="YUANBAO_MODEL",
        default_model="hy3",
        timeout_env="YUANBAO_TIMEOUT_SECONDS",
        body_style="yuanbao",
    )


def test_deepseek(query: str) -> ConnectivityResult:
    return test_openai_compatible_chat(
        provider="deepseek",
        query=query,
        api_key_names=("DEEPSEEK_API_KEY",),
        url_env="DEEPSEEK_CHAT_API_URL",
        default_url=DEFAULT_DEEPSEEK_CHAT_URL,
        model_env="DEEPSEEK_MODEL",
        default_model="deepseek-chat",
        timeout_env="DEEPSEEK_TIMEOUT_SECONDS",
    )


PROVIDER_TESTS: dict[str, Callable[[str], ConnectivityResult]] = {
    "qwen": test_qwen,
    "baidu": test_baidu,
    "doubao": test_doubao,
    "yuanbao": test_yuanbao,
    "deepseek": test_deepseek,
}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Test connectivity for AI model/search providers.")
    parser.add_argument(
        "--provider",
        choices=["all", *PROVIDER_TESTS.keys()],
        default="all",
        help="Provider to test. Use all to test every configured provider.",
    )
    parser.add_argument("--query", default="GEO 内容营销是什么？")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON only.")
    args = parser.parse_args()

    _load_dotenv()
    names = list(PROVIDER_TESTS) if args.provider == "all" else [args.provider]
    results = [PROVIDER_TESTS[name](args.query) for name in names]

    if args.json:
        print(json.dumps([asdict(item) for item in results], ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = "OK" if item.ok else "FAIL"
            target = item.model or item.endpoint
            credential = f" credential={item.credential_source}" if item.credential_source else ""
            print(f"[{status}] {item.provider} ({item.elapsed_ms} ms) {target}{credential}")
            print(f"  {item.detail}")
            for idx, sample in enumerate(item.samples, start=1):
                title = sample.get("title", "")
                url = sample.get("url", "")
                print(f"  sample {idx}: {title} {url}".rstrip())

    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
