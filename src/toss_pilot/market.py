"""Market data, stock info, and market info endpoints (Bearer token only).

Parameter names mirror the OpenAPI spec v1.2.14 exactly. Symbols are KR
six-digit codes (005930) or US tickers (AAPL); batch endpoints take up to
200 comma-separated symbols. Candle intervals are only "1m" and "1d".
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from toss_pilot.client import TossInvestClient


def _join_symbols(symbols: str | Iterable[str]) -> str:
    if isinstance(symbols, str):
        return symbols
    return ",".join(symbols)


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def get_prices(client: TossInvestClient, symbols: str | Iterable[str]) -> Any:
    return client.request("GET", "/api/v1/prices", params={"symbols": _join_symbols(symbols)})


def get_orderbook(client: TossInvestClient, symbol: str) -> Any:
    return client.request("GET", "/api/v1/orderbook", params={"symbol": symbol})


def get_trades(client: TossInvestClient, symbol: str, count: int | None = None) -> Any:
    return client.request(
        "GET", "/api/v1/trades", params=_clean({"symbol": symbol, "count": count})
    )


def get_price_limits(client: TossInvestClient, symbol: str) -> Any:
    return client.request("GET", "/api/v1/price-limits", params={"symbol": symbol})


def get_candles(
    client: TossInvestClient,
    symbol: str,
    interval: str,
    count: int | None = None,
    before: str | None = None,
    adjusted: bool | None = None,
) -> Any:
    return client.request(
        "GET",
        "/api/v1/candles",
        params=_clean(
            {
                "symbol": symbol,
                "interval": interval,
                "count": count,
                "before": before,
                "adjusted": adjusted,
            }
        ),
    )


def get_stocks(client: TossInvestClient, symbols: str | Iterable[str]) -> Any:
    return client.request("GET", "/api/v1/stocks", params={"symbols": _join_symbols(symbols)})


def get_all_stocks(
    client: TossInvestClient,
    market: str,
    status: str | None = None,
    security_type: str | None = None,
    common_share: bool | None = None,
) -> Any:
    return client.request(
        "GET",
        "/api/v1/stocks/all",
        params=_clean(
            {
                "market": market,
                "status": status,
                "securityType": security_type,
                "commonShare": common_share,
            }
        ),
    )


def get_exchange_rate(
    client: TossInvestClient,
    base_currency: str = "USD",
    quote_currency: str = "KRW",
    date_time: str | None = None,
) -> Any:
    return client.request(
        "GET",
        "/api/v1/exchange-rate",
        params=_clean(
            {
                "baseCurrency": base_currency,
                "quoteCurrency": quote_currency,
                "dateTime": date_time,
            }
        ),
    )


def get_market_calendar(client: TossInvestClient, country: str, date: str | None = None) -> Any:
    if country not in ("KR", "US"):
        raise ValueError("country must be 'KR' or 'US'")
    return client.request(
        "GET", f"/api/v1/market-calendar/{country}", params=_clean({"date": date})
    )


def get_rankings(
    client: TossInvestClient,
    ranking_type: str,
    market_country: str,
    duration: str,
    exclude_investment_caution: bool | None = None,
    count: int | None = None,
) -> Any:
    return client.request(
        "GET",
        "/api/v1/rankings",
        params=_clean(
            {
                "type": ranking_type,
                "marketCountry": market_country,
                "duration": duration,
                "excludeInvestmentCaution": exclude_investment_caution,
                "count": count,
            }
        ),
    )


def get_market_indicator_prices(client: TossInvestClient, symbols: str | Iterable[str]) -> Any:
    return client.request(
        "GET", "/api/v1/market-indicators/prices", params={"symbols": _join_symbols(symbols)}
    )
