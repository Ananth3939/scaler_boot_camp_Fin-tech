from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol

import yfinance as yf

from finsight.models import DataSource, NewsArticle, NewsSearchResult, Ticker
from finsight.tools.cache import TTLCache
from finsight.tools.market_data import (
    YAHOO_QUOTE_URL,
    DataProviderError,
    _BoundedSession,
    _optional_text,
    normalize_ticker,
)


class NewsProvider(Protocol):
    name: str

    def search_recent_news(self, ticker: Ticker, limit: int) -> NewsSearchResult: ...


class YFinanceNewsProvider:
    name = "Yahoo Finance via yfinance"

    def __init__(self, timeout_seconds: float = 20) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._timeout_seconds = timeout_seconds
        self._session = _BoundedSession(timeout_seconds)
        yf.config.network.retries = 0

    def search_recent_news(self, ticker: Ticker, limit: int = 10) -> NewsSearchResult:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        try:
            search = yf.Search(
                ticker,
                news_count=limit,
                include_cb=False,
                include_nav_links=False,
                include_research=False,
                session=self._session,
                timeout=self._timeout_seconds,
                raise_errors=True,
            )
            articles = [article for item in search.news if (article := _parse_article(item))]
            warnings: list[str] = []
            incomplete = sum(
                article.publisher is None or article.published_at is None or article.url is None
                for article in articles
            )
            if incomplete:
                warnings.append(
                    f"{incomplete} article(s) were missing publisher, publication time, "
                    "or URL metadata."
                )
            return NewsSearchResult(
                ticker=ticker,
                articles=articles[:limit],
                source=DataSource(
                    provider=self.name,
                    url=YAHOO_QUOTE_URL.format(ticker=ticker),
                    retrieved_at=datetime.now(UTC),
                ),
                warnings=warnings,
            )
        except Exception as exc:
            if isinstance(exc, DataProviderError):
                raise
            detail = " ".join(str(exc).split()) or type(exc).__name__
            raise DataProviderError(self.name, ticker, detail[:240]) from exc


class NewsService:
    def __init__(self, provider: NewsProvider, ttl_seconds: int = 300) -> None:
        self.provider = provider
        self._cache: TTLCache[tuple[str, str, int], NewsSearchResult] = TTLCache(ttl_seconds)

    def search_recent_news(self, ticker: str, limit: int = 10) -> NewsSearchResult:
        normalized = normalize_ticker(ticker)
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        return self._cache.get_or_set(
            ("news", normalized, limit),
            lambda: self.provider.search_recent_news(normalized, limit),
        )


def _parse_article(item: dict[str, Any]) -> NewsArticle | None:
    content = item.get("content")
    if not isinstance(content, dict):
        content = item

    title = _optional_text(content.get("title"))
    if title is None:
        return None

    provider = content.get("provider")
    publisher = (
        provider.get("displayName")
        if isinstance(provider, dict)
        else provider or content.get("publisher")
    )
    canonical_url = content.get("canonicalUrl")
    url = canonical_url.get("url") if isinstance(canonical_url, dict) else None
    if url is None:
        click_url = content.get("clickThroughUrl")
        url = click_url.get("url") if isinstance(click_url, dict) else item.get("link")

    published_at = _parse_datetime(
        content.get("pubDate") or content.get("displayTime") or item.get("providerPublishTime")
    )
    return NewsArticle(
        title=title,
        publisher=_optional_text(publisher),
        published_at=published_at,
        url=_optional_text(url),
    )


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
