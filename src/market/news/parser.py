"""Parse RSS XML into NewsArticle. Stdlib only."""

import hashlib
import html
import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

from .models import NewsArticle

log = logging.getLogger(__name__)

TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
SUFFIX_RE = re.compile(r"\s*(Continue reading.*|\[&#8230;\].*|\[…\].*)\s*$", re.IGNORECASE)


def clean_html(raw: str) -> str:
    """Strip tags, unescape entities, collapse whitespace."""
    text = TAG_RE.sub(" ", raw or "")
    text = html.unescape(text)
    text = WS_RE.sub(" ", text).strip()
    text = SUFFIX_RE.sub("", text).strip()
    return text


def parse_date(raw: str) -> datetime | None:
    """Parse RFC2822/ISO dates to aware UTC datetime. None if unparseable."""
    if not raw or not raw.strip():
        return None
    try:
        dt = parsedate_to_datetime(raw.strip())
    except (ValueError, TypeError):
        try:
            dt = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    return (el.text or "").strip() if el is not None and el.text else ""


def parse_feed(source_name: str, raw: bytes) -> list[NewsArticle]:
    """Parse one feed's XML. Skips items without title/link."""
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        log.error("RSS %s XML parse failed: %s", source_name, e)
        return []
    articles: list[NewsArticle] = []
    for item in root.findall(".//item"):
        title = _text(item, "title")
        link = _text(item, "link")
        if not title or not link:
            continue
        summary = clean_html(_text(item, "description"))
        published_at = parse_date(_text(item, "pubDate"))
        if published_at is None:
            continue
        article_id = hashlib.sha1(link.encode()).hexdigest()[:16]
        articles.append(
            NewsArticle(
                id=article_id,
                source_name=source_name,
                title=title,
                summary=summary,
                url=link,
                published_at=published_at,
            )
        )
    return articles


def parse_all(raw_feeds: dict[str, bytes]) -> list[NewsArticle]:
    """Parse every fetched feed, newest first."""
    articles: list[NewsArticle] = []
    for name, raw in raw_feeds.items():
        articles.extend(parse_feed(name, raw))
    articles.sort(key=lambda a: a.published_at, reverse=True)
    return articles
