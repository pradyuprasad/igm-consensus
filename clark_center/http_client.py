from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .models import SourceLogEntry
from .util import ensure_dir, slugify


class HttpClient:
    def __init__(self, raw_dir: Path, delay_seconds: float = 0.18, use_cache: bool = True) -> None:
        self.raw_dir = raw_dir
        self.delay_seconds = delay_seconds
        self.use_cache = use_cache
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "ClarkCenterDatasetBuilder/0.1 "
                    "(research data extraction; contact via site terms)"
                )
            }
        )
        self.source_log: list[SourceLogEntry] = []
        self._last_request_at = 0.0

    def fetch_text(
        self,
        url: str,
        resource_type: str,
        cache_name: str | None = None,
        timeout: int = 45,
    ) -> str:
        content = self.fetch_bytes(url, resource_type, cache_name, timeout)
        return content.decode("utf-8-sig", errors="replace")

    def fetch_bytes(
        self,
        url: str,
        resource_type: str,
        cache_name: str | None = None,
        timeout: int = 45,
    ) -> bytes:
        local_path = self._cache_path(resource_type, cache_name or slugify(url) + ".dat")
        ensure_dir(local_path.parent)
        if self.use_cache and local_path.exists() and local_path.stat().st_size > 0:
            content = local_path.read_bytes()
            self.source_log.append(
                SourceLogEntry(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    resource_type=resource_type,
                    url=url,
                    status_code="cache",
                    bytes_downloaded=len(content),
                    local_path=str(local_path),
                    notes="reused cached raw response",
                )
            )
            return content
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.delay_seconds:
            time.sleep(self.delay_seconds - elapsed)
        status: int | str = ""
        notes = ""
        content = b""
        try:
            last_error: Exception | None = None
            for attempt in range(1, 4):
                try:
                    response = self.session.get(url, timeout=timeout)
                    self._last_request_at = time.monotonic()
                    status = response.status_code
                    if status in {403, 429, 500, 502, 503, 504} and attempt < 3:
                        time.sleep(1.5 * attempt)
                        continue
                    response.raise_for_status()
                    content = response.content
                    local_path.write_bytes(content)
                    last_error = None
                    break
                except Exception as exc:  # noqa: BLE001 - retry before logging.
                    last_error = exc
                    if attempt < 3:
                        time.sleep(1.5 * attempt)
                        continue
                    raise
            if last_error is not None:
                raise last_error
        except Exception as exc:  # noqa: BLE001 - logged and re-raised with URL context.
            notes = repr(exc)
            self._last_request_at = time.monotonic()
            raise RuntimeError(f"Failed to fetch {url}: {exc}") from exc
        finally:
            self.source_log.append(
                SourceLogEntry(
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    resource_type=resource_type,
                    url=url,
                    status_code=status,
                    bytes_downloaded=len(content),
                    local_path=str(local_path),
                    notes=notes,
                )
            )
        return content

    def _cache_path(self, resource_type: str, cache_name: str) -> Path:
        safe_name = slugify(cache_name.rsplit(".", 1)[0])
        suffix = "." + cache_name.rsplit(".", 1)[-1] if "." in cache_name else ".dat"
        return self.raw_dir / resource_type / f"{safe_name}{suffix}"
