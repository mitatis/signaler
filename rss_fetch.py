#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import feedparser
from datetime import datetime as dt
from datetime import timezone as tz
from dateutil import parser as date_parser

from newspaper import Article
import urllib
import ssl
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from markdownify import markdownify as md

FEEDS  = [
    "https://export.arxiv.org/rss/cs.AI",  # arXiv – 最新AI论文
    "https://techcrunch.com/tag/artificial-intelligence/feed/",  # TechCrunch AI – AI初创和趋势报道
]

OUTPUT_DIR = "_" + dt.now().strftime("%Y-%m-%d")

timestamp_file = "last_fetched.json"

# 加载上次时间记录
if os.path.exists(timestamp_file):
    with open(timestamp_file, "r") as f:
        last_times = json.load(f)
else:
    last_times = {}
# 当前抓取后的最新时间记录
new_last_times = {}

def sanitize_filename(name: str) -> str:
    """Turn a string into a safe filename (alphanumeric, spaces, dots and underscores)."""
    return "".join(c for c in name if c.isalnum() or c in (" ", ".", "_")).rstrip()

def fetch_full_text(url: str) -> str:
    """
    Fetch the full article text with graceful fallbacks:
    1. Try `requests` with retry logic (handles most modern TLS configs).
    2. If that fails, fall back to `urllib` with a relaxed SSL context.
    """
    headers = {"User-Agent": "Mozilla/5.0"}

    # First attempt: `requests` with automatic retries
    try:
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
        )
        session.mount("https://", HTTPAdapter(max_retries=retries))

        resp = session.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        html = resp.text

        article = Article(url)
        article.set_html(html)
        article.parse()
        article_html = getattr(article, "article_html", None) or html
        body_md = md(article_html, strip=["img"]).strip()
        return body_md or "[Empty article body]"
    except Exception as e:
        print(f"[fetch_full_text] `requests` failed for {url} → {e}")

    # Fallback: urllib with relaxed SSL checks (last resort)
    try:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(url, headers=headers)
        html = urllib.request.urlopen(req, context=ctx, timeout=10).read()

        article = Article(url)
        article.set_html(html)
        article.parse()
        article_html = getattr(article, "article_html", None) or html
        body_md = md(article_html, strip=["img"]).strip()
        return body_md or "[Empty article body]"
    except Exception as e:
        print(f"[fetch_full_text] urllib fallback failed for {url} → {e}")
        return "[Content unavailable due to access restrictions]"

def save_feed_as_md(feed_url: str):
    feed = feedparser.parse(feed_url)
    feed_title = feed.feed.get("title", feed_url.split("//")[-1].split("/")[0])
    # create a subfolder per feed
    feed_dir = os.path.join(OUTPUT_DIR, "_" + sanitize_filename(feed_title))
    os.makedirs(feed_dir, exist_ok=True)

    last_time_str = last_times.get(feed_url)
    last_time = date_parser.parse(last_time_str) if last_time_str else dt(2000, 1, 1, tzinfo=tz.utc)

    latest_seen = last_time

    for entry in feed.entries:
        # grab fields (fallbacks if missing)
        title     = entry.get("title", "no-title").strip()
        published = entry.get("published", entry.get("updated", ""))
        if not published:
            continue
        published_time = date_parser.parse(published)
        if published_time <= last_time:
            continue
        if published_time > latest_seen:
            latest_seen = published_time

        link = entry.get("link", "")

        body = fetch_full_text(link) # 按 RSS 提供的链接获取正文内容
                # 可选优先将 RSS 内容作为正文
        # if hasattr(entry, "content") and entry.content:
        #     body = entry.content[0].value.strip()
        # elif hasattr(entry, "summary") and entry.summary:
        #     body = entry.summary.strip()
        # else:
        #     body = fetch_full_text(link)

        # Skip saving if the article body is empty or only placeholder text
        if not body or body.strip() in ("[Empty article body]", "[Content unavailable due to access restrictions]"):
            print(f"[{dt.now().strftime('%Y-%m-%d %H:%M:%S')}] Skipped → {title} (no content)")
            continue

        # build a safe filename, e.g. "2025-06-11_my-post-title.md"
        date_prefix = ""
        if published:
            try:
                published_dt = dt(*entry.published_parsed[:6])
                date_prefix = published_dt.strftime("%Y-%m-%d") + "_"
            except Exception:
                pass

        fname = f"{date_prefix}{sanitize_filename(title)}.md"
        path  = os.path.join(feed_dir, fname)

        escaped_title = title.replace('"', '\\"')

        # compose Markdown with YAML front matter
        md = (
            f"---\n"
            f"title: \"{escaped_title}\"\n"
            f"date: \"{published_time.isoformat()}\"\n"
            f"link: \"{link}\"\n"
            f"---\n\n"
            f"{body}\n"
        )

        with open(path, "w", encoding="utf-8") as f:
            f.write(md)

        print(f"[{dt.now().strftime('%Y-%m-%d %H:%M:%S')}] Saved → {path}")
    new_last_times[feed_url] = latest_seen.isoformat()

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    for url in FEEDS:
        save_feed_as_md(url)
        
    # Save the latest timestamps
    with open(timestamp_file, "w") as f:
        json.dump(new_last_times, f, indent=4)

if __name__ == "__main__":
    main()