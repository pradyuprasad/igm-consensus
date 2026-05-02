from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .http_client import HttpClient
from .util import clean_text


SURVEY_SITEMAPS = [
    "https://kentclarkcenter.org/survey-sitemap.xml",
    "https://kentclarkcenter.org/survey-special-sitemap.xml",
]


def discover_poll_urls(client: HttpClient) -> list[str]:
    client.fetch_text("https://kentclarkcenter.org/robots.txt", "robots", "robots.txt")
    urls: list[str] = []
    for sitemap_url in SURVEY_SITEMAPS:
        text = client.fetch_text(sitemap_url, "sitemap", sitemap_url.rsplit("/", 1)[-1])
        urls.extend(_parse_sitemap_urls(text))
    poll_urls: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url.rstrip("/") == "https://kentclarkcenter.org/surveys":
            continue
        if "/surveys/" not in url and "/surveys-special/" not in url:
            continue
        normalized = url.rstrip("/") + "/"
        if normalized not in seen:
            seen.add(normalized)
            poll_urls.append(normalized)
    return poll_urls


def _parse_sitemap_urls(text: str) -> list[str]:
    try:
        root = ET.fromstring(text.encode("utf-8"))
        namespace = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        return [clean_text(node.text) for node in root.findall(".//sm:loc", namespace) if node.text]
    except ET.ParseError:
        return re.findall(r"<loc>(.*?)</loc>", text)

