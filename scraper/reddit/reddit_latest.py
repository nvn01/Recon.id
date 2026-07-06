"""
Fetch the latest r/jualbeliindonesia posts for the flair:
WTS: Computers & Peripherals

This is intentionally a starter/proof script:
- no database
- no app integration
- no JSON export
- just fetch, parse, and print the latest posts with body text
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser


SUBREDDIT = "jualbeliindonesia"
FLAIR = "WTS: Computers & Peripherals"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


class HtmlToText(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"br", "p", "div", "li", "tr"}:
            self.parts.append("\n")
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.parts.append(f" {href} ")

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data)

    def text(self) -> str:
        raw = html.unescape("".join(self.parts))
        raw = re.sub(r"\r\n?", "\n", raw)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def fetch_text(url: str, user_agent: str, retries: int, retry_wait: int) -> str:
    headers = {
        "User-Agent": user_agent,
        "Accept": "application/atom+xml,application/xml;q=0.9,*/*;q=0.8",
    }

    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < retries:
                print(f"Reddit returned 429. Waiting {retry_wait}s before retry {attempt + 1}/{retries}...", file=sys.stderr)
                time.sleep(retry_wait)
                continue
            raise

    raise RuntimeError("fetch failed without a specific HTTP error")


def build_rss_url(limit: int) -> str:
    query = urllib.parse.urlencode(
        {
            "q": f'flair:"{FLAIR}"',
            "restrict_sr": "1",
            "sort": "new",
            "limit": str(limit),
        }
    )
    return f"https://www.reddit.com/r/{SUBREDDIT}/search.rss?{query}"


def clean_html(value: str) -> str:
    parser = HtmlToText()
    parser.feed(value or "")
    return parser.text()


def clean_description(value: str, post_url: str) -> str:
    lines = [line.strip() for line in value.splitlines()]
    if lines and post_url and lines[0].rstrip("/") == post_url.rstrip("/"):
        lines = lines[1:]

    cleaned = "\n".join(line for line in lines if line).strip()
    cleaned = re.sub(r"(https?://\S+)\s+\1", r"\1", cleaned)
    cleaned = re.sub(
        r"\s+submitted by\s+https://www\.reddit\.com/user/\S+\s+/u/\S+.*$",
        "",
        cleaned,
        flags=re.S,
    )
    return cleaned.strip()


def parse_feed(xml_text: str, limit: int) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    posts: list[dict[str, str]] = []

    for entry in root.findall("atom:entry", ATOM_NS)[:limit]:
        title = entry.findtext("atom:title", default="", namespaces=ATOM_NS).strip()
        updated = entry.findtext("atom:updated", default="", namespaces=ATOM_NS).strip()
        author = entry.findtext("atom:author/atom:name", default="", namespaces=ATOM_NS).strip()
        content_html = entry.findtext("atom:content", default="", namespaces=ATOM_NS)
        body = clean_html(content_html)

        url = ""
        for link in entry.findall("atom:link", ATOM_NS):
            href = link.attrib.get("href", "")
            rel = link.attrib.get("rel", "")
            if href and (rel == "alternate" or "/comments/" in href):
                url = href
                break
            if href and not url:
                url = href

        if not url:
            match = re.search(r"https://www\.reddit\.com/r/jualbeliindonesia/comments/\S+", body)
            if match:
                url = match.group(0)

        body = clean_description(body, url)

        posts.append(
            {
                "title": title,
                "updated": updated,
                "author": author,
                "url": url,
                "description": body,
            }
        )

    return posts


def print_posts(posts: list[dict[str, str]]) -> None:
    if not posts:
        print("No posts found.")
        return

    for index, post in enumerate(posts, start=1):
        print("=" * 80)
        print(f"{index}. {post['title']}")
        print(f"Author: {post['author']}")
        print(f"Updated: {post['updated']}")
        print(f"URL: {post['url']}")
        print()
        print(post["description"] or "[no description found]")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch latest Reddit WTS computer/peripheral posts.")
    parser.add_argument("--limit", type=int, default=5, help="Number of posts to fetch.")
    parser.add_argument("--retries", type=int, default=3, help="HTTP retry attempts.")
    parser.add_argument("--retry-wait", type=int, default=20, help="Seconds to wait after HTTP 429.")
    parser.add_argument(
        "--user-agent",
        default="ReconDataCollection/0.1 by local developer",
        help="User-Agent header sent to Reddit.",
    )
    args = parser.parse_args()

    url = build_rss_url(args.limit)
    print(f"Fetching: {url}", file=sys.stderr)

    try:
        xml_text = fetch_text(url, args.user_agent, args.retries, args.retry_wait)
        posts = parse_feed(xml_text, args.limit)
    except Exception as exc:
        print(f"Failed to fetch Reddit posts: {exc}", file=sys.stderr)
        return 1

    print_posts(posts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
