from functools import lru_cache

from finsight.config import Settings, get_settings
from finsight.models import CompanyProfile, FinancialStatements, NewsSearchResult, StockPrice
from finsight.tools.market_data import MarketDataService, YFinanceProvider
from finsight.tools.news import NewsService, YFinanceNewsProvider


def create_market_data_service(settings: Settings | None = None) -> MarketDataService:
    settings = settings or get_settings()
    return MarketDataService(
        provider=YFinanceProvider(timeout_seconds=settings.request_timeout_seconds),
        ttl_seconds=settings.cache_ttl_seconds,
    )


def create_news_service(settings: Settings | None = None) -> NewsService:
    settings = settings or get_settings()
    return NewsService(
        provider=YFinanceNewsProvider(timeout_seconds=settings.request_timeout_seconds),
        ttl_seconds=settings.cache_ttl_seconds,
    )


@lru_cache(maxsize=1)
def _default_market_data_service() -> MarketDataService:
    return create_market_data_service()


@lru_cache(maxsize=1)
def _default_news_service() -> NewsService:
    return create_news_service()


def get_stock_price(ticker: str) -> StockPrice:
    return _default_market_data_service().get_stock_price(ticker)


def get_company_info(ticker: str) -> CompanyProfile:
    return _default_market_data_service().get_company_info(ticker)


def get_financial_statements(ticker: str) -> FinancialStatements:
    return _default_market_data_service().get_financial_statements(ticker)


def search_recent_news(ticker: str, limit: int = 10) -> NewsSearchResult:
    return _default_news_service().search_recent_news(ticker, limit)
