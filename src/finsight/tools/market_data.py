from __future__ import annotations

import math
import re
from datetime import UTC, date, datetime
from typing import Any, Literal, Protocol, cast

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests

from finsight.models import (
    CompanyProfile,
    DataSource,
    FinancialStatements,
    PriceHistory,
    PricePoint,
    StatementPeriod,
    StockPrice,
    Ticker,
)
from finsight.tools.cache import TTLCache

YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{ticker}/"


class DataProviderError(RuntimeError):
    def __init__(self, provider: str, ticker: str, detail: str) -> None:
        self.provider = provider
        self.ticker = ticker
        self.detail = detail
        super().__init__(f"{provider} could not retrieve {ticker}: {detail}")


class MarketDataProvider(Protocol):
    name: str

    def get_stock_price(self, ticker: Ticker) -> StockPrice: ...

    def get_price_history(self, ticker: Ticker) -> PriceHistory: ...

    def get_company_info(self, ticker: Ticker) -> CompanyProfile: ...

    def get_financial_statements(self, ticker: Ticker) -> FinancialStatements: ...


class _BoundedSession(curl_requests.Session[Any]):
    """Cap every yfinance HTTP request at the application's configured timeout."""

    def __init__(self, timeout_seconds: float) -> None:
        super().__init__(impersonate="chrome")
        self._timeout_seconds = timeout_seconds

    def request(  # type: ignore[override]
        self,
        method: Literal[
            "GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "TRACE", "PATCH", "QUERY"
        ],
        url: str,
        **kwargs: Any,
    ) -> Any:
        timeout = kwargs.get("timeout")
        if isinstance(timeout, tuple):
            kwargs["timeout"] = tuple(
                self._timeout_seconds if part is None else min(float(part), self._timeout_seconds)
                for part in timeout
            )
        elif timeout is None:
            kwargs["timeout"] = self._timeout_seconds
        else:
            kwargs["timeout"] = min(float(timeout), self._timeout_seconds)
        return super().request(method, url, **kwargs)


class YFinanceProvider:
    name = "Yahoo Finance via yfinance"

    def __init__(self, timeout_seconds: float = 20) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        self._timeout_seconds = timeout_seconds
        self._session = _BoundedSession(timeout_seconds)
        yf.config.network.retries = 0

    def _client(self, ticker: Ticker) -> yf.Ticker:
        return yf.Ticker(ticker, session=self._session)

    def get_stock_price(self, ticker: Ticker) -> StockPrice:
        try:
            client = self._client(ticker)
            history = client.history(
                period="5d",
                interval="1d",
                auto_adjust=False,
                actions=False,
                timeout=self._timeout_seconds,
                raise_errors=True,
            )
            metadata = client.get_history_metadata() or {}
            if history.empty or "Close" not in history.columns:
                raise DataProviderError(self.name, ticker, "no recent closing price was returned")

            close = _finite_number(history["Close"].iloc[-1])
            if close is None:
                raise DataProviderError(self.name, ticker, "the latest closing price was missing")
            return StockPrice(
                ticker=ticker,
                close=close,
                currency=_optional_text(metadata.get("currency")),
                as_of=_date_from_value(history.index[-1]),
                source=_source(ticker),
            )
        except DataProviderError:
            raise
        except Exception as exc:
            raise DataProviderError(self.name, ticker, _safe_error(exc)) from exc

    def get_price_history(self, ticker: Ticker) -> PriceHistory:
        try:
            client = self._client(ticker)
            history = client.history(
                period="1y",
                interval="1d",
                auto_adjust=True,
                actions=False,
                timeout=self._timeout_seconds,
                raise_errors=True,
            )
            metadata = client.get_history_metadata() or {}
            if history.empty or "Close" not in history.columns:
                raise DataProviderError(
                    self.name, ticker, "no one-year daily price history was returned"
                )
            points = [
                PricePoint(as_of=_date_from_value(timestamp), close=close)
                for timestamp, raw_close in history["Close"].items()
                if (close := _finite_number(raw_close)) is not None and close > 0
            ]
            return PriceHistory(
                ticker=ticker,
                currency=_optional_text(metadata.get("currency")),
                points=points,
                source=_source(ticker),
            )
        except DataProviderError:
            raise
        except Exception as exc:
            raise DataProviderError(self.name, ticker, _safe_error(exc)) from exc

    def get_company_info(self, ticker: Ticker) -> CompanyProfile:
        try:
            info = self._client(ticker).get_info()
            return CompanyProfile(
                ticker=ticker,
                name=_optional_text(info.get("longName") or info.get("shortName")),
                sector=_optional_text(info.get("sector")),
                industry=_optional_text(info.get("industry")),
                exchange=_optional_text(info.get("exchange")),
                country=_optional_text(info.get("country")),
                currency=_optional_text(info.get("currency")),
                website=_optional_text(info.get("website")),
                description=_optional_text(info.get("longBusinessSummary")),
                market_cap=_nonnegative_number(info.get("marketCap")),
                employees=_optional_integer(info.get("fullTimeEmployees")),
                shares_outstanding=_positive_number(info.get("sharesOutstanding")),
                source=_source(ticker),
            )
        except Exception as exc:
            raise DataProviderError(self.name, ticker, _safe_error(exc)) from exc

    def get_financial_statements(self, ticker: Ticker) -> FinancialStatements:
        try:
            client = self._client(ticker)
            income = client.get_income_stmt(freq="yearly")
            balance = client.get_balance_sheet(freq="yearly")
            cash_flow = client.get_cashflow(freq="yearly")
            income_periods = _statement_periods(income)
            balance_periods = _statement_periods(balance)
            cash_flow_periods = _statement_periods(cash_flow)
            warnings: list[str] = []
            if not income_periods:
                warnings.append("The provider returned no annual income statement data.")
            if not balance_periods:
                warnings.append("The provider returned no annual balance sheet data.")
            if not cash_flow_periods:
                warnings.append("The provider returned no annual cash flow data.")
            warnings.append(
                "Statement units and currency are not consistently supplied by the provider; "
                "amounts are preserved as returned."
            )
            return FinancialStatements(
                ticker=ticker,
                income_statement=income_periods,
                balance_sheet=balance_periods,
                cash_flow=cash_flow_periods,
                source=_source(ticker),
                warnings=warnings,
            )
        except Exception as exc:
            raise DataProviderError(self.name, ticker, _safe_error(exc)) from exc


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, ttl_seconds: int = 300) -> None:
        self.provider = provider
        self._cache: TTLCache[tuple[str, str], Any] = TTLCache(ttl_seconds)

    def get_stock_price(self, ticker: str) -> StockPrice:
        normalized = normalize_ticker(ticker)
        return cast(
            StockPrice,
            self._cache.get_or_set(
                ("price", normalized), lambda: self.provider.get_stock_price(normalized)
            ),
        )

    def get_price_history(self, ticker: str) -> PriceHistory:
        normalized = normalize_ticker(ticker)
        return cast(
            PriceHistory,
            self._cache.get_or_set(
                ("price_history", normalized), lambda: self.provider.get_price_history(normalized)
            ),
        )

    def get_company_info(self, ticker: str) -> CompanyProfile:
        normalized = normalize_ticker(ticker)
        return cast(
            CompanyProfile,
            self._cache.get_or_set(
                ("company", normalized), lambda: self.provider.get_company_info(normalized)
            ),
        )

    def get_financial_statements(self, ticker: str) -> FinancialStatements:
        normalized = normalize_ticker(ticker)
        return cast(
            FinancialStatements,
            self._cache.get_or_set(
                ("statements", normalized),
                lambda: self.provider.get_financial_statements(normalized),
            ),
        )


def normalize_ticker(value: str) -> Ticker:
    if not isinstance(value, str):
        raise ValueError("ticker must be a string")
    ticker = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9.-]{0,14}", ticker):
        raise ValueError("ticker must be 1–15 letters, digits, dots, or hyphens")
    return ticker


def _source(ticker: str) -> DataSource:
    return DataSource(
        provider=YFinanceProvider.name,
        url=YAHOO_QUOTE_URL.format(ticker=ticker),
        retrieved_at=datetime.now(UTC),
    )


def _safe_error(exc: Exception) -> str:
    detail = " ".join(str(exc).split())
    if not detail:
        return type(exc).__name__
    return detail[:240]


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_integer(value: Any) -> int | None:
    number = _finite_number(value)
    return int(number) if number is not None and number >= 0 else None


def _nonnegative_number(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and number >= 0 else None


def _positive_number(value: Any) -> float | None:
    number = _finite_number(value)
    return number if number is not None and number > 0 else None


def _finite_number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _date_from_value(value: Any) -> date:
    timestamp = pd.Timestamp(value)
    if pd.isna(timestamp):
        raise ValueError("provider returned an invalid date")
    return date.fromisoformat(str(timestamp.date()))


def _statement_periods(frame: Any) -> list[StatementPeriod]:
    if frame is None or not isinstance(frame, pd.DataFrame) or frame.empty:
        return []

    periods: list[StatementPeriod] = []
    for column in frame.columns:
        values: dict[str, float | None] = {}
        for label, raw_value in frame[column].items():
            values[str(label)] = _finite_number(raw_value)
        periods.append(StatementPeriod(period_end=_date_from_value(column), values=values))
    return sorted(periods, key=lambda item: item.period_end, reverse=True)
