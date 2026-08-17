"""Base client behavior: envelope unwrapping, error mapping, 429 retry with
Retry-After, one-shot token refresh on 401 expired-token, account header."""

from __future__ import annotations

import httpx
import pytest

from toss_pilot.errors import TossApiError


def test_result_envelope_is_unwrapped(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-token"
        return httpx.Response(200, json={"result": {"value": "42"}})

    with make_client(handler) as client:
        assert client.request("GET", "/api/v1/prices", params={"symbols": "005930"}) == {
            "value": "42"
        }


def test_api_error_envelope_is_mapped(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={
                "error": {
                    "requestId": "01HREQ",
                    "code": "invalid-request",
                    "message": "bad parameter",
                    "data": {"field": "symbols"},
                }
            },
        )

    with make_client(handler) as client:
        with pytest.raises(TossApiError) as excinfo:
            client.request("GET", "/api/v1/prices")
    err = excinfo.value
    assert (err.status_code, err.code, err.request_id) == (400, "invalid-request", "01HREQ")
    assert err.data == {"field": "symbols"}


def test_429_is_retried_honoring_retry_after(make_client):
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "rate-limit-exceeded", "message": ""}},
            )
        return httpx.Response(200, json={"result": []})

    with make_client(handler) as client:
        assert client.request("GET", "/api/v1/trades", params={"symbol": "005930"}) == []
    assert calls["n"] == 2


def test_429_gives_up_after_max_retries(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "0"},
            json={"error": {"code": "rate-limit-exceeded", "message": ""}},
        )

    with make_client(handler) as client:
        with pytest.raises(TossApiError) as excinfo:
            client.request("GET", "/api/v1/trades")
    assert excinfo.value.code == "rate-limit-exceeded"


def test_expired_token_triggers_single_refresh(make_client):
    token_calls = {"n": 0}

    def token_handler(request: httpx.Request) -> httpx.Response:
        token_calls["n"] += 1
        return httpx.Response(
            200,
            json={
                "access_token": f"token-{token_calls['n']}",
                "token_type": "Bearer",
                "expires_in": 3600,
            },
        )

    api_calls = {"n": 0}

    def api_handler(request: httpx.Request) -> httpx.Response:
        api_calls["n"] += 1
        if request.headers["Authorization"] == "Bearer token-1":
            return httpx.Response(401, json={"error": {"code": "expired-token", "message": ""}})
        return httpx.Response(200, json={"result": {"ok": True}})

    with make_client(api_handler, token_handler) as client:
        assert client.request("GET", "/api/v1/accounts") == {"ok": True}
    assert token_calls["n"] == 2
    assert api_calls["n"] == 2


@pytest.mark.parametrize(
    "header, expected",
    [("inf", 1.0), ("nan", 1.0), ("86400", 30.0), ("abc", 1.0), ("-5", 0.0), ("2", 2.0)],
)
def test_retry_after_is_clamped(header, expected):
    from toss_pilot.client import _retry_after_seconds

    response = httpx.Response(429, headers={"Retry-After": header})
    assert _retry_after_seconds(response) == expected


def test_account_header_is_sent(make_client):
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Tossinvest-Account"] == "7"
        return httpx.Response(200, json={"result": {"items": []}})

    with make_client(handler) as client:
        client.request("GET", "/api/v1/holdings", account_seq=7)
