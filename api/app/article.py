import ipaddress
import re
import socket
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura
from trafilatura.utils import decode_file

from app.config import Settings
from app.models import ExtractedArticle

REDIRECT_CODES = {301, 302, 303, 307, 308}
USER_AGENT = "BetweenTheLines/0.1 (+local research prototype)"
HTML_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
WIRE_EDITOR_NOTE = re.compile(r"^\(ATTN:.*\)$", re.IGNORECASE)
WIRE_END_MARKER = re.compile(r"^\(END\)$", re.IGNORECASE)
EMAIL_LINE = re.compile(r"^\S+@\S+\.\S+$")


class ArticleExtractionError(ValueError):
    pass


def extract_article(raw_url: str, settings: Settings) -> ExtractedArticle:
    url = raw_url
    try:
        with httpx.Client(timeout=10, headers={"User-Agent": USER_AGENT}) as client:
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
                    if "html" not in content_type:
                        raise ArticleExtractionError("That URL does not point to an HTML article.")

                    body = bytearray()
                    for chunk in response.iter_bytes():
                        body.extend(chunk)
                        if len(body) > settings.max_download_bytes:
                            raise ArticleExtractionError(
                                "That page is too large to extract safely."
                            )
                    html = decode_file(bytes(body))
                    break
            else:
                raise ArticleExtractionError("That URL redirected too many times.")
    except httpx.HTTPStatusError as error:
        raise ArticleExtractionError(
            f"That website returned HTTP {error.response.status_code}."
        ) from error
    except httpx.TimeoutException as error:
        raise ArticleExtractionError("That website took too long to respond.") from error
    except httpx.RequestError as error:
        raise ArticleExtractionError("Couldn't download that article.") from error

    extracted = trafilatura.bare_extraction(
        html,
        url=url,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )
    if not extracted or not extracted.text:
        raise ArticleExtractionError("Couldn't find enough article text. Paste the text instead.")
    article_text = _clean_article_text(extracted.text)
    if len(article_text.split()) < 40:
        raise ArticleExtractionError("Couldn't find enough article text. Paste the text instead.")
    replacement_count = article_text.count("\ufffd")
    if replacement_count >= 5 and replacement_count / len(article_text) > 0.005:
        raise ArticleExtractionError(
            "That page's text encoding couldn't be read. Paste the article text instead."
        )

    try:
        metadata = trafilatura.extract_metadata(html, default_url=url)
    except (TypeError, ValueError):
        metadata = None
    title = extracted.title or (metadata.title if metadata else None) or _fallback_title(html)
    return ExtractedArticle(
        url=url,
        title=title,
        published_at=metadata.date if metadata else None,
        text=article_text,
    )


def _clean_article_text(text: str) -> str:
    lines = []
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


def _validate_public_url(raw_url: str) -> None:
    parsed = urlparse(raw_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ArticleExtractionError("Use a public HTTP or HTTPS URL.")
    if parsed.username or parsed.password:
        raise ArticleExtractionError("URLs containing credentials are not allowed.")

    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise ArticleExtractionError("Couldn't resolve that website.") from error

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
