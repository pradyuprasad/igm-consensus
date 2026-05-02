from __future__ import annotations

import csv
import hashlib
import html
import io
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse


BASE_URL = "https://kentclarkcenter.org"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(value: str, fallback: str = "item") -> str:
    text = unicodedata.normalize("NFKD", value)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return text or fallback


def stable_id(*parts: str, max_len: int = 96) -> str:
    joined = "__".join(slugify(part, "x") for part in parts if part)
    if len(joined) <= max_len:
        return joined
    digest = hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]
    return f"{joined[: max_len - 12].rstrip('-_')}__{digest}"


def url_slug(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    return path.split("/")[-1] or "surveys"


def absolute_url(url: str) -> str:
    if not url:
        return ""
    if url.startswith("http://") or url.startswith("https://"):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        return BASE_URL + url
    return BASE_URL + "/" + url


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    ensure_dir(path.parent)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv_text(text: str) -> list[dict[str, str]]:
    sample = text.lstrip("\ufeff")
    reader = csv.DictReader(io.StringIO(sample, newline=""))
    return [dict(row) for row in reader]


def decimal(value: float | None, places: int = 6) -> str:
    if value is None:
        return ""
    return f"{value:.{places}f}"
