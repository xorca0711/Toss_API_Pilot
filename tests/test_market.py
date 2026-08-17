"""Request construction for market endpoints: exact parameter names, symbol
joining, and omission of unset optionals."""

from __future__ import annotations

import httpx

from toss_pilot import market


def capture(seen: dict):
    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = request.url
        return httpx.Response(200, json={"result": []})

    return handler


def test_prices_joins_symbol_list(make_client):
    seen: dict = {}
    with make_client(capture(seen)) as client:
        market.get_prices(client, ["005930", "000660", "AAPL"])
    assert seen["url"].params["symbols"] == "005930,000660,AAPL"


def test_candles_omits_unset_optionals(make_client):
    seen: dict = {}
    with make_client(capture(seen)) as client:
        market.get_candles(client, "005930", "1d")
    params = seen["url"].params
    assert params["symbol"] == "005930"
    assert params["interval"] == "1d"
    for absent in ("count", "before", "adjusted"):
        assert absent not in params


def test_rankings_uses_spec_parameter_names(make_client):
    seen: dict = {}
    with make_client(capture(seen)) as client:
        market.get_rankings(client, "TOP_GAINERS", "KR", "1d", count=50)
    params = seen["url"].params
    assert params["type"] == "TOP_GAINERS"
    assert params["marketCountry"] == "KR"
    assert params["duration"] == "1d"
    assert params["count"] == "50"


def test_calendar_rejects_unknown_country(make_client):
    with make_client(capture({})) as client:
        try:
            market.get_market_calendar(client, "JP")
        except ValueError as exc:
            assert "KR" in str(exc)
        else:
            raise AssertionError("expected ValueError for unsupported country")
