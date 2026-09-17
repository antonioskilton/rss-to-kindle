#!/usr/bin/env python3
"""Create an RSS feed containing only Nate Silver posts tagged AI."""

from __future__ import annotations

import html
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests
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


def post_slug(url: str) -> str | None:
    normalized = canonical_post_url(url)
    if not normalized:
        return None
    return urlsplit(normalized).path.removeprefix("/p/")


def is_ai_post(session: requests.Session, url: str) -> tuple[bool, bool]:
    """Return (is_ai, tag_metadata_present) using Substack's public post JSON."""
    slug = post_slug(url)
    if not slug:
        return False, False

    response = session.get(
        f"https://www.natesilver.net/api/v1/posts/{slug}",
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    post = data.get("post", data) if isinstance(data, dict) else {}

    if not isinstance(post, dict):
        return False, False

    present = "postTags" in post or "post_tags" in post
    tags = post.get("postTags") or post.get("post_tags") or []
    for tag in tags:
        if not isinstance(tag, dict):
            continue
        slug_value = str(tag.get("slug", "")).strip().lower()
        name_value = str(tag.get("name", "")).strip().lower()
        if slug_value == "ai" or name_value in {"ai", "ai+"}:
            return True, present
    return False, present


def text(value: object) -> str:
    return "" if value is None else str(value)


def add_text(parent: ET.Element, tag: str, value: object) -> ET.Element:
    child = ET.SubElement(parent, tag)
    child.text = text(value)
    return child


def build_feed() -> int:
    parsed = feedparser.parse(
        SOURCE_FEED,
        request_headers={"User-Agent": USER_AGENT},
    )
    if getattr(parsed, "bozo", False) and not parsed.entries:
        raise RuntimeError(f"Could not parse source feed: {parsed.bozo_exception}")

    session = requests.Session()
    matching = []
    metadata_seen = False

    for entry in parsed.entries:
        normalized = canonical_post_url(entry.get("link", ""))
        if not normalized:
            continue
        try:
            matches_ai, has_metadata = is_ai_post(session, normalized)
        except requests.RequestException as exc:
            raise RuntimeError(f"Could not inspect tags for {normalized}: {exc}") from exc
        metadata_seen = metadata_seen or has_metadata
        if matches_ai:
            matching.append(entry)

    if not metadata_seen:
        raise RuntimeError(
            "Substack post JSON did not expose postTags metadata; refusing to guess."
        )

    if not matching:
        raise RuntimeError(
            "No AI-tagged posts are present in the current source RSS feed. "
            "Existing output was left unchanged."
        )

    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    add_text(channel, "title", "Silver Bulletin — AI+")
    add_text(channel, "link", AI_TAG_PAGE)
    add_text(channel, "description", "Nate Silver posts tagged AI on Silver Bulletin.")
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

    ET.indent(rss, space="  ")
    xml = ET.tostring(rss, encoding="utf-8", xml_declaration=True)
    OUTPUT.write_bytes(xml + b"\n")

    print(f"Wrote {OUTPUT} with {len(matching)} AI-tagged entr{'y' if len(matching) == 1 else 'ies'}.")
    for entry in matching:
        print(f"- {html.unescape(entry.get('title', ''))}")
    return len(matching)


if __name__ == "__main__":
    try:
        build_feed()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
