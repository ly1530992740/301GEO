from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from io import BytesIO
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


@dataclass
class UploadedPdf:
    name: str
    data: bytes


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.text_parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip_depth += 1
            return
        if tag != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self.links.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript", "svg"} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = re.sub(r"\s+", " ", data or "").strip()
        if text:
            self.text_parts.append(text)

    def text(self, max_chars: int = 12000) -> str:
        value = "\n".join(self.text_parts)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value[:max_chars]


def collect_product_sources(
    website_url: str = "",
    uploaded_pdfs: list[UploadedPdf] | None = None,
    max_same_domain_links: int = 5,
) -> dict[str, Any]:
    website_pages = collect_website_pages(website_url, max_same_domain_links) if website_url else []
    pdf_documents = collect_pdf_text(uploaded_pdfs or [])
    return {
        "website_url": website_url,
        "website_pages": website_pages,
        "pdf_documents": pdf_documents,
    }


def collect_website_pages(website_url: str, max_same_domain_links: int = 5) -> list[dict[str, Any]]:
    start_url = _normalize_url(website_url)
    if not start_url:
        return []
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
        }
    )
    first = _fetch_page(session, start_url)
    if first.get("error"):
        return [first]
    base_domain = _domain(start_url)
    links = _same_domain_links(start_url, first.get("links", []), base_domain)[:max_same_domain_links]
    pages = [first]
    seen = {first.get("url")}
    for link in links:
        if link in seen:
            continue
        seen.add(link)
        pages.append(_fetch_page(session, link))
    return pages


def collect_pdf_text(uploaded_pdfs: list[UploadedPdf], max_chars_per_pdf: int = 12000) -> list[dict[str, Any]]:
    if not uploaded_pdfs:
        return []
    try:
        from pypdf import PdfReader
    except Exception as exc:
        return [{"name": item.name, "error": f"pypdf unavailable: {exc}"} for item in uploaded_pdfs]

    items: list[dict[str, Any]] = []
    for item in uploaded_pdfs:
        try:
            reader = PdfReader(BytesIO(item.data))
            text_parts = []
            for page in reader.pages[:25]:
                text = page.extract_text() or ""
                if text.strip():
                    text_parts.append(text.strip())
            items.append(
                {
                    "name": item.name,
                    "pages": len(reader.pages),
                    "text_excerpt": "\n\n".join(text_parts)[:max_chars_per_pdf],
                }
            )
        except Exception as exc:
            items.append({"name": item.name, "error": str(exc)})
    return items


def source_text_for_ai(sources: dict[str, Any], max_chars: int = 36000) -> str:
    chunks: list[str] = []
    for page in sources.get("website_pages") or []:
        if page.get("text"):
            chunks.append(f"## Website: {page.get('url')}\n{page.get('text')}")
        elif page.get("error"):
            chunks.append(f"## Website fetch error: {page.get('url')}\n{page.get('error')}")
    for pdf in sources.get("pdf_documents") or []:
        if pdf.get("text_excerpt"):
            chunks.append(f"## PDF: {pdf.get('name')}\n{pdf.get('text_excerpt')}")
        elif pdf.get("error"):
            chunks.append(f"## PDF error: {pdf.get('name')}\n{pdf.get('error')}")
    return "\n\n".join(chunks)[:max_chars]


def _fetch_page(session: requests.Session, url: str) -> dict[str, Any]:
    errors: list[str] = []
    attempted: list[str] = []
    attempted_keys: set[tuple[str, bool]] = set()
    normalized_url = _normalize_url(url)
    for candidate, verify_tls in _request_candidates(normalized_url):
        key = (candidate, verify_tls)
        if key in attempted_keys:
            continue
        attempted_keys.add(key)
        if candidate not in attempted:
            attempted.append(candidate)
        try:
            response = session.get(candidate, timeout=20, verify=verify_tls, allow_redirects=True)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or response.encoding
            parser = _PageParser()
            parser.feed(response.text or "")
            return {
                "url": response.url or candidate,
                "status_code": response.status_code,
                "text": parser.text(),
                "links": parser.links,
                "attempted_urls": attempted,
            }
        except Exception as exc:
            mode = "verify=true" if verify_tls else "verify=false"
            errors.append(f"{candidate} ({mode}): {exc}")
            continue
    return {
        "url": normalized_url or url,
        "error": " | ".join(errors[:4]) or "fetch failed",
        "attempted_urls": attempted,
    }


def _request_candidates(url: str) -> list[tuple[str, bool]]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return [(url, True)]
    hosts = [parsed.netloc]
    if parsed.netloc.startswith("www."):
        hosts.append(parsed.netloc[4:])
    else:
        hosts.append(f"www.{parsed.netloc}")
    schemes = [parsed.scheme]
    if parsed.scheme == "https":
        schemes.append("http")
    elif parsed.scheme == "http":
        schemes.append("https")
    result: list[tuple[str, bool]] = []
    for scheme in schemes:
        for host in hosts:
            candidate = parsed._replace(scheme=scheme, netloc=host).geturl()
            result.append((candidate, True))
            if scheme == "https":
                result.append((candidate, False))
    return result

def _same_domain_links(start_url: str, links: list[str], base_domain: str) -> list[str]:
    result: list[str] = []
    for href in links:
        absolute = urljoin(start_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if _domain(absolute) != base_domain:
            continue
        if any(parsed.path.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".zip", ".pdf")):
            continue
        clean = parsed._replace(fragment="", query="").geturl().rstrip("/")
        if clean and clean != start_url.rstrip("/") and clean not in result:
            result.append(clean)
    return result


def _normalize_url(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    value = re.sub(r"\s+", "", value)
    if not re.match(r"https?://", value, flags=re.I):
        value = f"https://{value}"
    return value.rstrip("/")


def _domain(value: str) -> str:
    host = urlparse(value).netloc.lower()
    return host[4:] if host.startswith("www.") else host
