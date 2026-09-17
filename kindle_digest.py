#!/usr/bin/env python3
"""Build one Kindle-friendly EPUB per configured RSS section."""

from __future__ import annotations

import argparse
import calendar
import hashlib
import html
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import feedparser
import requests
import trafilatura
import yaml
from bs4 import BeautifulSoup
from ebooklib import epub

USER_AGENT = "rss-to-kindle/1.0 (+https://github.com/antonioskilton/rss-to-kindle)"
REQUEST_TIMEOUT = 25

ALLOWED_TAGS = {
    "p", "br", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "blockquote", "pre", "code",
    "em", "strong", "b", "i", "a", "hr", "sup", "sub"
}
DROP_TAGS = {"script", "style", "iframe", "form", "button", "nav", "aside", "footer"}

CSS = """
body { font-family: serif; line-height: 1.48; margin: 5%; }
h1 { font-size: 1.7em; margin: 0.25em 0 0.2em; }
h2 { font-size: 1.35em; margin-top: 1.6em; }
h3 { font-size: 1.1em; margin-top: 1.4em; }
.kicker { font-family: sans-serif; font-size: 0.82em; letter-spacing: 0.06em; text-transform: uppercase; }
.meta { font-family: sans-serif; font-size: 0.82em; margin: 0.3em 0 1.4em; }
.deck { font-style: italic; margin: 0.8em 0 1.5em; }
.toc ul { list-style: none; padding-left: 0; }
.toc li { margin: 0.55em 0; }
.publication { margin-top: 1.7em; }
.source, .back { font-family: sans-serif; font-size: 0.82em; margin-top: 2em; }
pre, code { font-family: monospace; }
pre { white-space: pre-wrap; }
hr { border: 0; border-top: 1px solid #999; margin: 2em 0; }
"""

@dataclass
class Article:
    section: str
    publication: str
    title: str
    url: str
    published: datetime
    body_html: str
    article_id: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="feeds.yaml")
    parser.add_argument("--output-dir", default="dist")
    parser.add_argument("--lookback-hours", type=int, default=48)
    parser.add_argument("--state", default="state/kindle.json")
    parser.add_argument(
        "--mark-sent",
        action="store_true",
        help="After successful build, record included article IDs in the state file.",
    )
    return parser.parse_args()


def canonicalize_url(url: str) -> str:
    if not url:
        return ""
    parts = urlsplit(url.strip())
    query = parts.query
    if query:
        kept = []
        for pair in query.split("&"):
            key = pair.split("=", 1)[0].lower()
            if not (key.startswith("utm_") or key in {"ref", "source", "mc_cid", "mc_eid"}):
                kept.append(pair)
        query = "&".join(kept)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, query, ""))


def article_id(entry: Any, url: str) -> str:
    stable = canonicalize_url(url) or str(entry.get("id") or entry.get("guid") or entry.get("title") or "")
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:24]


def parse_entry_date(entry: Any) -> datetime | None:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if value:
            return datetime.fromtimestamp(calendar.timegm(value), tz=timezone.utc)
    return None


def clean_html(raw_html: str) -> str:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    for tag in soup.find_all(DROP_TAGS):
        tag.decompose()

    for tag in list(soup.find_all(True)):
        if tag.name not in ALLOWED_TAGS:
            tag.unwrap()
            continue
        attrs = {}
        if tag.name == "a":
            href = tag.get("href")
            if href:
                attrs["href"] = href
        tag.attrs = attrs

    for p in soup.find_all("p"):
        if not p.get_text(" ", strip=True) and not p.find("br"):
            p.decompose()
    return str(soup)


def extract_feed_body(entry: Any) -> str:
    candidates = []
    for item in entry.get("content", []) or []:
        value = item.get("value")
        if value:
            candidates.append(value)
    summary = entry.get("summary") or entry.get("description")
    if summary:
        candidates.append(summary)
    if not candidates:
        return ""
    return max(candidates, key=lambda text: len(BeautifulSoup(text, "html.parser").get_text(" ", strip=True)))


def fetch_article_body(session: requests.Session, url: str) -> str:
    if not url:
        return ""
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        print(f"  page fetch failed: {url} ({exc})")
        return ""

    extracted = trafilatura.extract(
        response.text,
        url=response.url,
        output_format="html",
        include_links=True,
        include_formatting=True,
        include_comments=False,
        favor_precision=True,
    )
    return extracted or ""


def best_body(session: requests.Session, entry: Any, url: str) -> str:
    feed_html = extract_feed_body(entry)
    feed_text_len = len(BeautifulSoup(feed_html, "html.parser").get_text(" ", strip=True))
    if feed_text_len >= 1200:
        return clean_html(feed_html)

    page_html = fetch_article_body(session, url)
    page_text_len = len(BeautifulSoup(page_html, "html.parser").get_text(" ", strip=True))
    if page_text_len > feed_text_len:
        return clean_html(page_html)
    return clean_html(feed_html)


def load_state(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    return set(data.get("sent_article_ids", []))


def save_state(path: Path, sent: set[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "sent_article_ids": sorted(sent),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def collect_articles(config: dict[str, Any], lookback_hours: int, sent: set[str]) -> dict[str, list[Article]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    result: dict[str, list[Article]] = {}
    global_seen_urls: set[str] = set()

    for section_name, feeds in config["sections"].items():
        section_articles: list[Article] = []
        print(f"\n[{section_name}]")
        for feed in feeds:
            publication = feed["name"]
            feed_url = feed["url"]
            print(f"- {publication}")
            parsed = feedparser.parse(feed_url, agent=USER_AGENT)

            if getattr(parsed, "bozo", False):
                print(f"  feed warning: {getattr(parsed, 'bozo_exception', 'unknown parse issue')}")

            feed_articles: list[Article] = []
            for entry in parsed.entries:
                published = parse_entry_date(entry)
                if published is None or published < cutoff:
                    continue

                url = canonicalize_url(str(entry.get("link") or ""))
                if not url:
                    continue

                if feed.get("kind") == "hn-target" and "news.ycombinator.com/item" in url:
                    continue

                if url in global_seen_urls:
                    continue
                aid = article_id(entry, url)
                if aid in sent:
                    continue

                body = best_body(session, entry, url)
                body_text = BeautifulSoup(body, "html.parser").get_text(" ", strip=True)
                if len(body_text) < 120:
                    print(f"  skipping thin content: {entry.get('title', '(untitled)')}")
                    continue

                title = str(entry.get("title") or "Untitled").strip()
                feed_articles.append(
                    Article(
                        section=section_name,
                        publication=publication,
                        title=title,
                        url=url,
                        published=published,
                        body_html=body,
                        article_id=aid,
                    )
                )
                global_seen_urls.add(url)

            feed_articles.sort(key=lambda article: article.published, reverse=True)
            section_articles.extend(feed_articles)

        result[section_name] = section_articles

    return result


def chapter_filename(article: Article, index: int) -> str:
    return f"article-{index:03d}-{article.article_id}.xhtml"


def build_epub(section: str, articles: list[Article], output_dir: Path, tz: ZoneInfo) -> Path | None:
    if not articles:
        print(f"No new articles for {section}; no EPUB created.")
        return None

    local_now = datetime.now(tz)
    display_date = local_now.strftime("%B %-d, %Y")
    iso_date = local_now.strftime("%Y-%m-%d")
    title = f"{section} — {display_date}"

    book = epub.EpubBook()
    book.set_identifier(f"rss-to-kindle:{section}:{iso_date}")
    book.set_title(title)
    book.set_language("en")
    book.add_author("rss-to-kindle")

    css = epub.EpubItem(
        uid="style",
        file_name="style.css",
        media_type="text/css",
        content=CSS.encode("utf-8"),
    )
    book.add_item(css)

    cover = epub.EpubHtml(title=title, file_name="cover.xhtml", lang="en")
    cover.content = f"""
    <div class="kicker">Personal Daily Reader</div>
    <h1>{html.escape(section)}</h1>
    <p class="deck">{html.escape(display_date)}</p>
    <hr/>
    <p><strong>{len(articles)} article{"s" if len(articles) != 1 else ""}</strong></p>
    <p>New writing from sources you chose. No ranking. No filler.</p>
    """
    cover.add_item(css)
    book.add_item(cover)

    grouped: dict[str, list[tuple[Article, epub.EpubHtml]]] = {}
    chapters: list[epub.EpubHtml] = []

    for idx, article in enumerate(articles, start=1):
        chapter = epub.EpubHtml(
            title=article.title,
            file_name=chapter_filename(article, idx),
            lang="en",
        )
        date_text = article.published.astimezone(tz).strftime("%B %-d, %Y")
        chapter.content = f"""
        <div class="kicker">{html.escape(article.publication)}</div>
        <h1>{html.escape(article.title)}</h1>
        <div class="meta">{html.escape(article.publication)} · {html.escape(date_text)}</div>
        {article.body_html}
        <p class="source"><a href="{html.escape(article.url, quote=True)}">Open original article →</a></p>
        <p class="back"><a href="contents.xhtml">← Back to contents</a></p>
        """
        chapter.add_item(css)
        book.add_item(chapter)
        chapters.append(chapter)
        grouped.setdefault(article.publication, []).append((article, chapter))

    toc_rows = []
    for publication, items in grouped.items():
        links = "".join(
            f'<li><a href="{ch.file_name}">{html.escape(a.title)}</a></li>'
            for a, ch in items
        )
        toc_rows.append(
            f'<div class="publication"><h2>{html.escape(publication)}</h2><ul>{links}</ul></div>'
        )

    contents = epub.EpubHtml(title="Contents", file_name="contents.xhtml", lang="en")
    contents.content = f"""
    <div class="kicker">Contents</div>
    <h1>{html.escape(section)}</h1>
    <div class="toc">{''.join(toc_rows)}</div>
    """
    contents.add_item(css)
    book.add_item(contents)

    book.toc = tuple(
        (epub.Section(publication), tuple(ch for _, ch in items))
        for publication, items in grouped.items()
    )

    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [cover, contents, *chapters, "nav"]

    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{section}-{iso_date}.epub"
    epub.write_epub(str(path), book, {})
    print(f"Created {path} ({len(articles)} articles)")
    return path


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    state_path = Path(args.state)
    output_dir = Path(args.output_dir)

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    sent = load_state(state_path)
    by_section = collect_articles(config, args.lookback_hours, sent)
    tz = ZoneInfo(config.get("timezone", "America/Los_Angeles"))

    included_ids: set[str] = set()
    created = []
    for section, articles in by_section.items():
        built = build_epub(section, articles, output_dir, tz)
        if built:
            created.append(built)
            included_ids.update(a.article_id for a in articles)

    if args.mark_sent and created:
        sent.update(included_ids)
        save_state(state_path, sent)
        print(f"Recorded {len(included_ids)} article IDs in {state_path}")

    if not created:
        print("No EPUBs created.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
