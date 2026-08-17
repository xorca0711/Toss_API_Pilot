"""Order construction and gated submission.

There is NO sandbox in this API: a successful POST /api/v1/orders is a real
order on a real brokerage account, and no per-order 2FA exists. Two layers
guard the live path: (1) every function here defaults to dry_run=True and a
live send requires the environment variable TOSS_PILOT_ALLOW_LIVE_ORDERS to
be exactly "yes" in the process environment (never importable from .env);
(2) the transport itself (client.request) refuses non-GET calls to order
endpoints unless these wrappers pass allow_live_order=True after their gate.

Spec rules encoded here (v1.2.14): exactly one of quantity/order_amount;
order_amount is US MARKET only and carries no timeInForce; LIMIT requires
price, MARKET forbids it; timeInForce CLS is only valid with LIMIT (US);
clientOrderId is at most 36 chars of [a-zA-Z0-9-_] and acts as a 10-minute
idempotency key; orders of 100,000,000 KRW or more need
confirm_high_value_order=True; orders of 3,000,000,000 KRW or more are
rejected by the server outright (the spec's field description uses the
inclusive 이상; its 422 examples inconsistently say 초과). A successful
modify or cancel returns a NEW orderId and the original becomes REPLACED.
"""

from __future__ import annotations

import os
import re
from typing import Any

from toss_pilot.client import TossInvestClient
from toss_pilot.config import ENV_ALLOW_LIVE
from toss_pilot.errors import LiveOrderBlocked

_SIDES = ("BUY", "SELL")
_ORDER_TYPES = ("LIMIT", "MARKET")
_TIME_IN_FORCE = ("DAY", "CLS")

_CLIENT_ORDER_ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,36}$")
# Conservative ID alphabet; blocks path metacharacters ('..', '/', '?') from
# being interpolated into request paths.
_ORDER_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _check_path_id(name: str, value: str) -> str:
    if not _ORDER_ID_RE.fullmatch(value):
        raise ValueError(
            f"{name} contains characters outside [A-Za-z0-9_-]; refusing to "
            "interpolate it into a request path"
        )
    return value


def build_order(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | None = None,
    order_amount: str | None = None,
    price: str | None = None,
    time_in_force: str | None = None,
    client_order_id: str | None = None,
    confirm_high_value_order: bool | None = None,
) -> dict[str, Any]:
    """Validate and assemble an order request body. Quantities, amounts, and
    prices are decimal STRINGS, exactly as the API defines them; passing float
    is refused to avoid silent precision loss."""
    for name, value in (("quantity", quantity), ("order_amount", order_amount), ("price", price)):
        if isinstance(value, float):
            raise TypeError(f"{name} must be a decimal string, not float")
    if side not in _SIDES:
        raise ValueError(f"side must be one of {_SIDES}")
    if order_type not in _ORDER_TYPES:
        raise ValueError(f"order_type must be one of {_ORDER_TYPES}")
    if time_in_force is not None and time_in_force not in _TIME_IN_FORCE:
        raise ValueError(f"time_in_force must be one of {_TIME_IN_FORCE}")
    if (quantity is None) == (order_amount is None):
        raise ValueError("exactly one of quantity or order_amount is required")
    if order_amount is not None and order_type != "MARKET":
        raise ValueError("order_amount is only valid with order_type='MARKET' (US only)")
    if order_amount is not None and time_in_force is not None:
        raise ValueError(
            "time_in_force is not defined for amount-based orders "
            "(spec OrderCreateAmountBased has no timeInForce field)"
        )
    if time_in_force == "CLS" and order_type != "LIMIT":
        raise ValueError("time_in_force='CLS' is only supported with order_type='LIMIT' (US)")
    if order_type == "LIMIT" and price is None:
        raise ValueError("LIMIT orders require price")
    if order_type == "MARKET" and price is not None:
        raise ValueError("MARKET orders must not carry price")
    if client_order_id is not None and not _CLIENT_ORDER_ID_RE.fullmatch(client_order_id):
        raise ValueError(
            "client_order_id must be 1-36 chars of [a-zA-Z0-9-_] "
            "(spec clientOrderId constraint; it is the idempotency key)"
        )

    body: dict[str, Any] = {"symbol": symbol, "side": side, "orderType": order_type}
    if quantity is not None:
        body["quantity"] = quantity
    if order_amount is not None:
        body["orderAmount"] = order_amount
    if price is not None:
        body["price"] = price
    if time_in_force is not None:
        body["timeInForce"] = time_in_force
    if client_order_id is not None:
        body["clientOrderId"] = client_order_id
    if confirm_high_value_order is not None:
        body["confirmHighValueOrder"] = confirm_high_value_order
    return body


def _gate(dry_run: bool, action: str, method: str, path: str, body: dict | None, account_seq: int) -> dict | None:
    if dry_run:
        return {
            "dry_run": True,
            "action": action,
            "method": method,
            "path": path,
            "account_seq": account_seq,
            "body": body,
        }
    if os.environ.get(ENV_ALLOW_LIVE) != "yes":
        raise LiveOrderBlocked(
            f"Refusing live {action}: set {ENV_ALLOW_LIVE}=yes in the process "
            "environment and pass dry_run=False deliberately. There is no "
            "sandbox; this would be a real order."
        )
    return None


def place_order(
    client: TossInvestClient,
    account_seq: int,
    order: dict[str, Any],
    dry_run: bool = True,
) -> Any:
    blocked = _gate(dry_run, "place_order", "POST", "/api/v1/orders", order, account_seq)
    if blocked is not None:
        return blocked
    return client.request(
        "POST",
        "/api/v1/orders",
        json_body=order,
        account_seq=account_seq,
        allow_live_order=True,
    )


def modify_order(
    client: TossInvestClient,
    account_seq: int,
    order_id: str,
    changes: dict[str, Any],
    dry_run: bool = True,
) -> Any:
    """KR modifies require quantity (integer string); US modifies are
    price-only. The response carries a NEW orderId; track it."""
    path = f"/api/v1/orders/{_check_path_id('order_id', order_id)}/modify"
    blocked = _gate(dry_run, "modify_order", "POST", path, changes, account_seq)
    if blocked is not None:
        return blocked
    return client.request(
        "POST", path, json_body=changes, account_seq=account_seq, allow_live_order=True
    )


def cancel_order(
    client: TossInvestClient,
    account_seq: int,
    order_id: str,
    dry_run: bool = True,
) -> Any:
    path = f"/api/v1/orders/{_check_path_id('order_id', order_id)}/cancel"
    blocked = _gate(dry_run, "cancel_order", "POST", path, None, account_seq)
    if blocked is not None:
        return blocked
    return client.request(
        "POST", path, json_body={}, account_seq=account_seq, allow_live_order=True
    )


def place_conditional_order(
    client: TossInvestClient,
    account_seq: int,
    body: dict[str, Any],
    dry_run: bool = True,
) -> Any:
    """Conditional orders (SINGLE/OCO/OTO) auto-fire real orders server-side
    when trigger prices are touched. Body shape follows the spec's
    ConditionalOrderCreateRequest; this wrapper gates but does not deep-validate
    it. One OCO/OTO per symbol; expireDate is required."""
    blocked = _gate(
        dry_run, "place_conditional_order", "POST", "/api/v1/conditional-orders", body, account_seq
    )
    if blocked is not None:
        return blocked
    return client.request(
        "POST",
        "/api/v1/conditional-orders",
        json_body=body,
        account_seq=account_seq,
        allow_live_order=True,
    )


def modify_conditional_order(
    client: TossInvestClient,
    account_seq: int,
    conditional_order_id: str,
    body: dict[str, Any],
    dry_run: bool = True,
) -> Any:
    """Modify is cancel-and-recreate upstream: the full body is required and a
    NEW conditionalOrderId is issued; the old one is invalidated."""
    path = (
        "/api/v1/conditional-orders/"
        f"{_check_path_id('conditional_order_id', conditional_order_id)}/modify"
    )
    blocked = _gate(dry_run, "modify_conditional_order", "POST", path, body, account_seq)
    if blocked is not None:
        return blocked
    return client.request(
        "POST", path, json_body=body, account_seq=account_seq, allow_live_order=True
    )


def cancel_conditional_order(
    client: TossInvestClient,
    account_seq: int,
    conditional_order_id: str,
    dry_run: bool = True,
) -> Any:
    path = (
        "/api/v1/conditional-orders/"
        f"{_check_path_id('conditional_order_id', conditional_order_id)}"
    )
    blocked = _gate(dry_run, "cancel_conditional_order", "DELETE", path, None, account_seq)
    if blocked is not None:
        return blocked
    return client.request("DELETE", path, account_seq=account_seq, allow_live_order=True)
