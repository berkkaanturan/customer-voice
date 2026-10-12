"""
Resilient HTTP client shared by HTML-based adapters (Ekşi Sözlük, Şikayetvar).

Features
--------
* Uses ``curl_cffi`` with ``impersonate="chrome"`` when available, so the TLS /
  HTTP2 fingerprint matches a real Chrome browser (Cloudflare bot scoring relies
  heavily on this).  Falls back to ``requests`` + rotating UA headers.
* One persistent session per client → cookies (e.g. Cloudflare ``__cf_bm``)
  are reused across requests.  Optional warm-up request to the home page.
* Random polite delay between requests.
* Retries with exponential back-off on 403 / 429 / 5xx / network errors.
* Optional proxy fallback: if ``proxy_env`` names an env var that is set
  (e.g. ``SIKAYETVAR_PROXY_URL``), the client switches to that proxy after
  repeated 403s and retries.
"""

from __future__ import annotations

import logging
import os
import random
import time
from typing import Any

from config import get_random_headers

logger = logging.getLogger(__name__)

try:  # pragma: no cover - import guard
    from curl_cffi import requests as _creq

    _HAS_CURL_CFFI = True
except Exception:  # pragma: no cover
    _creq = None
    _HAS_CURL_CFFI = False

import requests as _requests

RETRY_STATUSES = {403, 429, 500, 502, 503, 504}


class BlockedError(Exception):
    """Raised when the target keeps answering 403/429 after all retries."""


class HttpStatusError(Exception):
    """Raised for non-retryable HTTP statuses (e.g. 400, 410)."""


class HttpClient:
    def __init__(
        self,
        name: str,
        *,
        min_delay: float = 2.0,
        max_delay: float = 5.0,
        retries: int = 3,
        backoff_base: float = 15.0,
        warmup_url: str | None = None,
        proxy_env: str | None = None,
        timeout: int = 20,
    ) -> None:
        self.name = name
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.retries = retries
        self.backoff_base = backoff_base
        self.warmup_url = warmup_url
        self.timeout = timeout
        self.proxy_url = os.getenv(proxy_env, "").strip() if proxy_env else ""
        self.using_proxy = False
        self.request_count = 0
        self.blocked_count = 0
        self._last_request_at = 0.0
        self._warmed_up = False
        self._session = self._new_session()

    # ── session handling ────────────────────────────────────────────────
    def _new_session(self) -> Any:
        if _HAS_CURL_CFFI:
            session = _creq.Session(impersonate="chrome")
            # Don't override User-Agent: it must match the impersonated TLS fingerprint.
            session.headers.update({"Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"})
        else:
            session = _requests.Session()
            session.headers.update(get_random_headers())
        if self.using_proxy and self.proxy_url:
            session.proxies = {"http": self.proxy_url, "https": self.proxy_url}
        return session

    def _switch_to_proxy(self) -> bool:
        if self.proxy_url and not self.using_proxy:
            logger.warning("[%s] Switching to proxy after repeated blocks.", self.name)
            self.using_proxy = True
            self._session = self._new_session()
            self._warmed_up = False
            return True
        return False

    def _throttle(self) -> None:
        if self._last_request_at:
            wait = random.uniform(self.min_delay, self.max_delay)
            elapsed = time.monotonic() - self._last_request_at
            if elapsed < wait:
                time.sleep(wait - elapsed)

    def _raw_get(self, url: str, referer: str | None) -> Any:
        self._throttle()
        headers = {"Referer": referer} if referer else None
        try:
            return self._session.get(url, headers=headers, timeout=self.timeout, allow_redirects=True)
        finally:
            self._last_request_at = time.monotonic()
            self.request_count += 1

    def _warmup(self) -> None:
        if self._warmed_up or not self.warmup_url:
            return
        self._warmed_up = True
        try:
            resp = self._raw_get(self.warmup_url, None)
            logger.info("[%s] Warm-up %s → %s", self.name, self.warmup_url, resp.status_code)
        except Exception as exc:  # warm-up is best effort
            logger.warning("[%s] Warm-up failed: %s", self.name, exc)

    # ── public API ──────────────────────────────────────────────────────
    def get(self, url: str, *, referer: str | None = None, allow_404: bool = True) -> Any:
        """GET with retries.  Returns the response (status 200, or 404 if allowed).

        Raises:
            BlockedError: still 403/429 after all retries (and proxy fallback).
            Exception:    other persistent failures.
        """
        self._warmup()
        last_error: str = ""
        attempt = 0
        proxy_tried = False

        while attempt <= self.retries:
            try:
                resp = self._raw_get(url, referer)
                status = resp.status_code
                if status == 200 or (status == 404 and allow_404):
                    return resp
                last_error = f"HTTP {status}"
                if status not in RETRY_STATUSES:
                    raise HttpStatusError(f"[{self.name}] {url} → {last_error}")
                if status in (403, 429):
                    self.blocked_count += 1
            except (BlockedError, HttpStatusError):
                raise
            except Exception as exc:
                last_error = f"{type(exc).__name__}: {exc}"

            attempt += 1
            if attempt > self.retries:
                # Last resort: proxy fallback (once)
                if not proxy_tried and last_error in ("HTTP 403", "HTTP 429") and self._switch_to_proxy():
                    proxy_tried = True
                    attempt = 0
                    self._warmup()
                    continue
                break

            wait = self.backoff_base * (2 ** (attempt - 1)) + random.uniform(0, 5)
            logger.warning(
                "[%s] %s failed (%s). Retry %d/%d in %.0fs…",
                self.name, url, last_error, attempt, self.retries, wait,
            )
            time.sleep(wait)
            # Fresh session (new cookies / connection) after a block
            if last_error in ("HTTP 403", "HTTP 429"):
                self._session = self._new_session()
                self._warmed_up = False
                self._warmup()

        if last_error in ("HTTP 403", "HTTP 429"):
            raise BlockedError(f"[{self.name}] {url} → {last_error} after {self.retries} retries")
        raise Exception(f"[{self.name}] {url} → {last_error} after {self.retries} retries")
