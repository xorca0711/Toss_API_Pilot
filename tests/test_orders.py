"""Order building rules from spec v1.2.14 and the live-order gate.

The dry-run path must never touch the network; these tests pass client=None
to prove it. The live path must refuse without the explicit environment
opt-in even when dry_run=False is passed."""

from __future__ import annotations

import httpx
import pytest

from toss_pilot import orders
from toss_pilot.errors import LiveOrderBlocked


def test_build_limit_order_happy_path():
    body = orders.build_order(
        "005930", "BUY", "LIMIT", quantity="10", price="70000", client_order_id="pilot-1"
    )
    assert body == {
        "symbol": "005930",
        "side": "BUY",
        "orderType": "LIMIT",
        "quantity": "10",
        "price": "70000",
        "clientOrderId": "pilot-1",
    }


@pytest.mark.parametrize(
    "kwargs, match",
    [
        ({"quantity": "10", "order_amount": "100"}, "exactly one"),
        ({}, "exactly one"),
        ({"order_amount": "100"}, "MARKET"),
        ({"quantity": "10"}, "price"),
    ],
)
def test_build_limit_order_rejects_invalid_combinations(kwargs, match):
    with pytest.raises(ValueError, match=match):
        orders.build_order("005930", "BUY", "LIMIT", **kwargs)


def test_market_order_forbids_price():
    with pytest.raises(ValueError, match="must not carry price"):
        orders.build_order("AAPL", "BUY", "MARKET", quantity="1", price="100")


def test_amount_based_order_forbids_time_in_force():
    with pytest.raises(ValueError, match="not defined for amount-based"):
        orders.build_order("AAPL", "BUY", "MARKET", order_amount="100", time_in_force="DAY")


def test_cls_requires_limit():
    with pytest.raises(ValueError, match="CLS"):
        orders.build_order("AAPL", "SELL", "MARKET", quantity="1", time_in_force="CLS")


@pytest.mark.parametrize("bad_id", ["x" * 37, "a.b", "a b", "a:b", ""])
def test_client_order_id_constraints_enforced(bad_id):
    with pytest.raises(ValueError, match="client_order_id"):
        orders.build_order(
            "005930", "BUY", "LIMIT", quantity="1", price="50000", client_order_id=bad_id
        )


@pytest.mark.parametrize("hostile", ["../orders?", "o/1", "o?x=1", "o#f", ".."])
def test_order_id_path_interpolation_is_refused(hostile):
    with pytest.raises(ValueError, match="request path"):
        orders.cancel_order(None, 7, hostile)


def test_floats_are_refused():
    with pytest.raises(TypeError, match="decimal string"):
        orders.build_order("AAPL", "BUY", "MARKET", quantity=1.5)


def test_dry_run_returns_payload_without_network():
    body = orders.build_order("005930", "BUY", "LIMIT", quantity="1", price="50000")
    result = orders.place_order(None, 7, body)  # client unused on dry-run path
    assert result["dry_run"] is True
    assert result["path"] == "/api/v1/orders"
    assert result["body"] == body


def test_live_order_blocked_without_env(monkeypatch):
    monkeypatch.delenv(orders.ENV_ALLOW_LIVE, raising=False)
    body = orders.build_order("005930", "BUY", "LIMIT", quantity="1", price="50000")
    with pytest.raises(LiveOrderBlocked):
        orders.place_order(None, 7, body, dry_run=False)


def test_live_order_sends_when_explicitly_allowed(monkeypatch, make_client):
    monkeypatch.setenv(orders.ENV_ALLOW_LIVE, "yes")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["account"] = request.headers.get("X-Tossinvest-Account")
        return httpx.Response(200, json={"result": {"orderId": "o-1"}})

    body = orders.build_order("005930", "BUY", "LIMIT", quantity="1", price="50000")
    with make_client(handler) as client:
        result = orders.place_order(client, 7, body, dry_run=False)
    assert result == {"orderId": "o-1"}
    assert seen == {"path": "/api/v1/orders", "account": "7"}


def test_cancel_dry_run_names_new_order_id_semantics():
    result = orders.cancel_order(None, 7, "o-1")
    assert result["dry_run"] is True
    assert result["path"] == "/api/v1/orders/o-1/cancel"


def test_conditional_order_dry_run_and_gate(monkeypatch):
    monkeypatch.delenv(orders.ENV_ALLOW_LIVE, raising=False)
    result = orders.place_conditional_order(None, 7, {"symbol": "005930"})
    assert result["dry_run"] is True
    assert result["path"] == "/api/v1/conditional-orders"
    with pytest.raises(LiveOrderBlocked):
        orders.cancel_conditional_order(None, 7, "c-1", dry_run=False)


def test_bare_transport_post_to_orders_is_blocked(monkeypatch, make_client):
    monkeypatch.delenv(orders.ENV_ALLOW_LIVE, raising=False)

    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("transport gate must block before any network call")

    with make_client(handler) as client:
        with pytest.raises(LiveOrderBlocked):
            client.request("POST", "/api/v1/orders", json_body={}, account_seq=7)
        with pytest.raises(LiveOrderBlocked):
            client.request("DELETE", "/api/v1/conditional-orders/c-1", account_seq=7)


def test_transport_requires_flag_even_with_env(monkeypatch, make_client):
    monkeypatch.setenv(orders.ENV_ALLOW_LIVE, "yes")

    def handler(request):  # pragma: no cover - must never be reached
        raise AssertionError("env alone must not open the transport gate")

    with make_client(handler) as client:
        with pytest.raises(LiveOrderBlocked):
            client.request("POST", "/api/v1/orders", json_body={}, account_seq=7)
