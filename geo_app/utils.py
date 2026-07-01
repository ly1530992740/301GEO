from __future__ import annotations

import html
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def safe_filename(value: str, max_length: int = 90) -> str:
    value = re.sub(r'[\\/:*?"<>|\r\n\t]+', "_", value).strip(" ._")
    value = re.sub(r"\s+", "_", value)
    return (value or "untitled")[:max_length]


def domain_from_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def normalize_text(value: str) -> str:
    value = (value or "").lower().strip()
    value = re.sub(r"[\s\-_·•|｜（）()【】\[\]{}<>《》:：,，.。/\\]+", "", value)
    return value


def extract_json(text: str, fallback: Any = None) -> Any:
    if not text:
        return fallback
    candidates = []
    fenced = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    candidates.extend(fenced)
    candidates.append(text)
    for candidate in candidates:
        candidate = candidate.strip()
        try:
            return json.loads(candidate)
        except Exception:
            pass
        match = re.search(r"(\{.*\}|\[.*\])", candidate, flags=re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except Exception:
                pass
    return fallback


def parse_price(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(",", "").strip() or "0")
    except ValueError:
        return 0.0


def markdown_to_html(markdown_text: str) -> str:
    try:
        import markdown

        return markdown.markdown(markdown_text, extensions=["extra", "sane_lists"])
    except Exception:
        lines = []
        for raw_line in markdown_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("### "):
                lines.append(f"<h3>{html.escape(line[4:])}</h3>")
            elif line.startswith("## "):
                lines.append(f"<h2>{html.escape(line[3:])}</h2>")
            elif line.startswith("# "):
                lines.append(f"<h1>{html.escape(line[2:])}</h1>")
            elif line.startswith("- "):
                lines.append(f"<p>• {html.escape(line[2:])}</p>")
            else:
                lines.append(f"<p>{html.escape(line)}</p>")
        return "\n".join(lines)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

