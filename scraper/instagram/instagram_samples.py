"""
Starter Instagram probe for RECON data collection.

This is intentionally simple:
- no database
- no JSON export
- no browser automation
- no login/session cookies

Instagram currently hides profile timeline data from anonymous static HTML and
often rate-limits the public web_profile_info endpoint. For now, this script
uses one known sale-post sample per seed account and checks whether the post URL
is reachable and whether static HTML exposes a caption.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)

SALE_MARKERS = (
    "harga",
    "price",
    "condition",
    "kondisi",
    "lokasi",
    "garansi",
    "ready",
    "consign price",
    "code item",
    "kelengkapan",
    "rp",
    "idr",
)


@dataclass(frozen=True)
class SamplePost:
    account: str
    url: str
    hint: str


SAMPLE_POSTS: tuple[SamplePost, ...] = (
    SamplePost(
        account="chemicy.consignment",
        url="https://www.instagram.com/p/DZl_Mm4Cdqe/",
        hint="#chemicyready sale-format post with HARGA / LOKASI style caption",
    ),
    SamplePost(
        account="thelazytitip",
        url="https://www.instagram.com/p/DaSiqsnj1Y0/",
        hint="Asus Gaming TUF VG259Q3A, Rp750.000, Serang",
    ),
    SamplePost(
        account="sensegame.id",
        url="https://www.instagram.com/p/DaFOtUctpTk/",
        hint="Nintendo Switch Lite, condition 9/10, Rp2.399.000",
    ),
    SamplePost(
        account="cappee.gaming",
        url="https://www.instagram.com/p/DaKSbHTO-5P/",
        hint="Cappee ready product post with price / condition format",
    ),
    SamplePost(
        account="gamecentral.id",
        url="https://www.instagram.com/p/DZkggnQk6ya/",
        hint="Logitech Webcam C525, price 399.000",
    ),
    SamplePost(
        account="consigngaming",
        url="https://www.instagram.com/p/DaQMaYjmWDC/",
        hint="Ajazz GP100 Galaxy White, condition Good",
    ),
    SamplePost(
        account="ggsconsign",
        url="https://www.instagram.com/p/DaPww81vP4i/",
        hint="ASUS ROG Strix Flare II Animate, Consign Price IDR 2.800.000",
    ),
)


class VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "svg"}:
            self.skip_depth += 1
        if tag in {"br", "p", "div", "li"} and not self.skip_depth:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "svg"} and self.skip_depth:
            self.skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self.skip_depth and data.strip():
            self.parts.append(data)

    def text(self) -> str:
        value = html.unescape(" ".join(self.parts))
        value = re.sub(r"\s+", " ", value)
        return value.strip()


def fetch(url: str, timeout: int) -> tuple[int | None, str]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return exc.code, body
    except urllib.error.URLError as exc:
        return None, str(exc)


def extract_static_caption(html_text: str) -> str:
    meta_match = re.search(
        r'<meta\s+(?:property|name)=["\']og:description["\']\s+content=["\'](.+?)["\']',
        html_text,
        flags=re.I | re.S,
    )
    if meta_match:
        return html.unescape(meta_match.group(1)).strip()

    parser = VisibleTextParser()
    parser.feed(html_text)
    visible = parser.text()

    lower_visible = visible.lower()
    if any(marker in lower_visible for marker in SALE_MARKERS):
        return visible

    return ""


def marker_score(text: str) -> int:
    lower = text.lower()
    return sum(1 for marker in SALE_MARKERS if marker in lower)


def print_sample(sample: SamplePost, status: int | None, caption: str) -> None:
    combined = " ".join(part for part in (caption, sample.hint) if part)
    score = marker_score(combined)

    print("=" * 88)
    print(f"Account: {sample.account}")
    print(f"Post:    {sample.url}")
    print(f"HTTP:    {status if status is not None else 'failed'}")
    print(f"Score:   {score} sale markers")
    print()

    if caption:
        print("Static caption extracted:")
        print(textwrap.shorten(caption, width=900, placeholder=" ..."))
    else:
        print("Static caption extracted: [not exposed by anonymous Instagram HTML]")

    print()
    print("Known sale hint:")
    print(sample.hint)
    print()


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe one Instagram sale-post sample per seed account.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds.")
    parser.add_argument(
        "--account",
        help="Optional account filter, for example: chemicy.consignment",
    )
    args = parser.parse_args()

    samples = SAMPLE_POSTS
    if args.account:
        samples = tuple(sample for sample in samples if sample.account == args.account)
        if not samples:
            print(f"No sample configured for account: {args.account}", file=sys.stderr)
            return 1

    for sample in samples:
        status, html_text = fetch(sample.url, args.timeout)
        caption = extract_static_caption(html_text)
        print_sample(sample, status, caption)

    print("Probe complete.")
    print("Note: profile-to-latest-post discovery still needs a stronger source than anonymous static HTML.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
