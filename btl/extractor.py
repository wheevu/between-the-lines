"""SSRF-guarded public HTML extraction and bounded batch page retrieval."""

from __future__ import annotations

import ipaddress
import re
import socket
from collections.abc import Callable, Sequence
from html import unescape
from urllib.parse import urljoin, urlparse, urlsplit

import httpx
import trafilatura
from trafilatura.utils import decode_file

from btl.language import resolve_language
from btl.provenance import canonicalize_url, text_hash
from btl.types import ExtractedDocument, RetrievalFailure

REDIRECT_CODES = {301, 302, 303, 307, 308}
USER_AGENT = "BetweenTheLines/0.2 (+local research tool)"
HTML_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
WIRE_EDITOR_NOTE = re.compile(r"^\(ATTN:.*\)$", re.IGNORECASE)
WIRE_END_MARKER = re.compile(r"^\(END\)$", re.IGNORECASE)
EMAIL_LINE = re.compile(r"^\S+@\S+\.\S+$")
WHITESPACE = re.compile(r"\s+")
DEFAULT_MAX_DOWNLOAD_BYTES = 2 * 1024 * 1024


class ArticleExtractionError(ValueError):
    """Raised when a URL cannot be safely downloaded or extracted as readable text."""


def extract_url(
    raw_url: str,
    *,
    max_download_bytes: int = DEFAULT_MAX_DOWNLOAD_BYTES,
    timeout: float = 10.0,
) -> ExtractedDocument:
    """Download a public HTML page safely and extract cleaned article prose."""
    url, html = _download_html(
        raw_url,
        max_download_bytes=max_download_bytes,
        timeout=timeout,
    )
    extracted = trafilatura.bare_extraction(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not extracted or not extracted.text:
        raise ArticleExtractionError("Could not find enough readable article text.")
    article_text = _clean_article_text(extracted.text)
    if len(article_text.split()) < 40 and len(article_text) < 120:
        raise ArticleExtractionError("Could not find enough readable article text.")
    replacement_count = article_text.count("\ufffd")
    if replacement_count >= 5 and replacement_count / max(1, len(article_text)) > 0.005:
        raise ArticleExtractionError("Page text encoding could not be decoded cleanly.")

    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
    except (TypeError, ValueError):
        metadata = None

    title = extracted.title or (metadata.title if metadata else None) or _fallback_title(html)
    canonical = canonicalize_url(url, strict=True) or url
    return ExtractedDocument(
        url=url,
        canonical_url=canonical,
        title=title,
        published_at_unverified=metadata.date if metadata else None,
        publisher=_publisher_host(canonical),
        text=article_text,
    )


def fetch_batch(
    urls: Sequence[str],
    *,
    input_url: str | None = None,
    limit: int = 12,
    max_per_publisher: int = 3,
    extractor: Callable[[str], ExtractedDocument] = extract_url,
) -> tuple[list[ExtractedDocument], list[RetrievalFailure]]:
    """Fetch up to `limit` unique public pages with self-cite and publisher-cap guards."""
    docs: list[ExtractedDocument] = []
    failures: list[RetrievalFailure] = []
    seen_urls: set[str] = set()
    seen_content: set[str] = set()
    publisher_counts: dict[str, int] = {}
    canonical_input = canonicalize_url(input_url) if input_url else None

    for raw_url in urls:
        if len(docs) >= limit:
            break
        try:
            canonical = canonicalize_url(raw_url, strict=True)
        except ValueError as error:
            failures.append(RetrievalFailure(url=None, reason=str(error)))
            continue
        if canonical is None:
            continue
        if canonical_input and canonical == canonical_input:
            failures.append(
                RetrievalFailure(url=canonical, reason="Input article cannot cite itself.")
            )
            continue
        if _is_obviously_private_host(canonical):
            failures.append(
                RetrievalFailure(
                    url=canonical,
                    reason="Local and private-network URLs are not allowed.",
                )
            )
            continue
        if canonical in seen_urls:
            continue
        seen_urls.add(canonical)
        initial_publisher = _publisher_host(canonical)
        if publisher_counts.get(initial_publisher, 0) >= max_per_publisher:
            continue

        try:
            doc = extractor(canonical)
            final_url = canonicalize_url(doc.url, strict=True) or canonical
        except ArticleExtractionError as error:
            failures.append(RetrievalFailure(url=canonical, reason=str(error)))
            continue
        except Exception:
            failures.append(RetrievalFailure(url=canonical, reason="The page could not be read."))
            continue

        if canonical_input and final_url == canonical_input:
            failures.append(
                RetrievalFailure(url=final_url, reason="Input article cannot cite itself.")
            )
            continue
        if final_url in {existing.canonical_url for existing in docs}:
            continue
        final_publisher = _publisher_host(final_url)
        if publisher_counts.get(final_publisher, 0) >= max_per_publisher:
            continue

        digest = text_hash(WHITESPACE.sub(" ", doc.text).strip().lower())
        if digest in seen_content:
            continue
        seen_content.add(digest)
        publisher_counts[final_publisher] = publisher_counts.get(final_publisher, 0) + 1
        # Trigger language sanity once so downstream callers rely on clean text.
        resolve_language(doc.text, "auto")
        docs.append(doc)

    return docs, failures


def _download_html(
    raw_url: str,
    *,
    max_download_bytes: int,
    timeout: float,
) -> tuple[str, str]:
    url = raw_url
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            for _ in range(4):
                _validate_public_url(url)
                with client.stream("GET", url, follow_redirects=False) as response:
                    if response.status_code in REDIRECT_CODES:
                        location = response.headers.get("location")
                        if not location:
                            raise ArticleExtractionError(
                                "The article redirected without a destination."
                            )
                        url = urljoin(url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "").lower()
                    if "html" not in content_type and "text/plain" not in content_type:
                        raise ArticleExtractionError(
                            "That URL does not point to an HTML or text article."
                        )

                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > max_download_bytes:
                            raise ArticleExtractionError(
                                "That page is too large to extract safely."
                            )
                    html = decode_file(bytes(body))
                    break
            else:
                raise ArticleExtractionError("That URL redirected too many times.")
    except httpx.HTTPStatusError as error:
        raise ArticleExtractionError(
            f"Website returned HTTP {error.response.status_code}."
        ) from error
    except httpx.TimeoutException as error:
        raise ArticleExtractionError("Website timed out before responding.") from error
    except httpx.RequestError as error:
        raise ArticleExtractionError("Could not download that URL.") from error
    return url, html


def _clean_article_text(text: str) -> str:
    lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if WIRE_END_MARKER.match(line):
            break
        if not lines and WIRE_EDITOR_NOTE.match(line):
            continue
        if EMAIL_LINE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _fallback_title(html: str) -> str | None:
    match = HTML_TITLE.search(html)
    if not match:
        return None
    title = unescape(re.sub(r"<[^>]+>", "", match.group(1))).strip()
    return title or None


def _publisher_host(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.hostname:
        raise ValueError("URL has no publisher host.")
    return parsed.hostname.lower().removeprefix("www.")


def _is_obviously_private_host(raw_url: str) -> bool:
    host = (urlsplit(raw_url).hostname or "").lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return any(
        (
            ip.is_private,
            ip.is_loopback,
            ip.is_link_local,
            ip.is_multicast,
            ip.is_reserved,
            ip.is_unspecified,
        )
    )


def _validate_public_url(raw_url: str) -> None:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ArticleExtractionError("Use a public HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise ArticleExtractionError("URLs containing credentials are not allowed.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ArticleExtractionError("Could not resolve that hostname.") from error

    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if any(
            (
                ip.is_private,
                ip.is_loopback,
                ip.is_link_local,
                ip.is_multicast,
                ip.is_reserved,
                ip.is_unspecified,
            )
        ):
            raise ArticleExtractionError("Local and private-network URLs are not allowed.")
