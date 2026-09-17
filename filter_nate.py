#!/usr/bin/env python3
"""Create an RSS feed containing only posts from Nate Silver's AI+ tag page."""

from __future__ import annotations

import html
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests
from bs4 import BeautifulSoup
from xml.etree import ElementTree as ET

SOURCE_FEED = "https://www.natesilver.net/feed"
AI_TAG_PAGE = "https://www.natesilver.net/t/ai"
OUTPUT = Path("nate-ai.xml")
USER_AGENT = "rss-to-kindle/1.0 (+https://github.com/antonioskilton/rss-to-kindle)"


def canonical_post_url(url: str) -> str | None:
    """Normalize a natesilver.net /p/ article URL and discard everything else."""
    if not url:
        return None
    parts = urlsplit(url)
    host = parts.netloc.lower().removeprefix("www.")
    if host != "natesilver.net" or not parts.path.startswith("/p/"):
        return None
    path = parts.path.rstrip("/")
    return urlunsplit(("https", "www.natesilver.net", path, "", ""))


def ai_post_urls() -> set[str]:
    response = requests.get(
        AI_TAG_PAGE,
        headers={"User-Agent": USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    urls: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.startswith("/"):
            href = f"https://www.natesilver.net{href}"
        normalized = canonical_post_url(href)
        if normalized:
            urls.add(normalized)

    if not urls:
        raise RuntimeError("No /p/ article links found on the AI+ tag page")
    return urls


def text(value: object) -> str:
    return "" if value is None else str(value)


def add_text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = text(value)
    return child


def build_feed() -> int:
    allowed = ai_post_urls()

    parsed = feedparser.parse(
        SOURCE_FEED,
        request_headers={"User-Agent": USER_AGENT},
    )
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"Could not parse source feed: {parsed.bozo_exception}")

    matching = []
    for entry in parsed.entries:
        normalized = canonical_post_url(entry.get("link", ""))
        if normalized and normalized in allowed:
            matching.append(entry)

    if not matching:
        raise RuntimeError(
            "No current RSS entries matched the AI+ tag page. "
            "The site structure may have changed."
        )

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", "Silver Bulletin — AI+")
    add_text(channel, "link", AI_TAG_PAGE)
    add_text(
        channel,
        "description",
        "Nate Silver posts currently listed on the Silver Bulletin AI+ tag page.",
    )
    add_text(channel, "language", "en")

    for entry in matching:
        item = ET.SubElement(channel, "item")
        add_text(item, "title", entry.get("title", ""))
        add_text(item, "link", canonical_post_url(entry.get("link", "")) or entry.get("link", ""))

        guid_value = entry.get("id") or entry.get("guid") or entry.get("link", "")
        guid = add_text(item, "guid", guid_value)
        guid.set("isPermaLink", "false")

        if entry.get("published"):
            add_text(item, "pubDate", entry.get("published"))
        elif entry.get("updated"):
            add_text(item, "pubDate", entry.get("updated"))

        author = entry.get("author")
        if author:
            add_text(item, "author", author)

        description = entry.get("summary") or entry.get("description")
        if not description and entry.get("content"):
            description = entry.content[0].get("value", "")
        if description:
            add_text(item, "description", description)

        for tag in entry.get("tags", []):
            term = tag.get("term") if isinstance(tag, dict) else None
            if term:
                add_text(item, "category", term)

    ET.indent(rss, space="  ")
    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    OUTPUT.write_bytes(xml + b"\n")

    print(f"Wrote {OUTPUT} with {len(matching)} AI+ entr{'y' if len(matching) == 1 else 'ies'}.")
    for entry in matching:
        print(f"- {html.unescape(entry.get('title', ''))}")
    return len(matching)


if __name__ == "__main__":
    try:
        build_feed()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
