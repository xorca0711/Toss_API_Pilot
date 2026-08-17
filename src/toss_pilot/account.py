"""Account and asset endpoints (Bearer token + X-Tossinvest-Account header).

The accountSeq passed as account_seq comes from get_accounts(); currently only
BROKERAGE accounts are returned. All values are decimal strings.
"""

from __future__ import annotations

from typing import Any

from toss_pilot.client import TossInvestClient


def _clean(params: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in params.items() if v is not None}


def get_accounts(client: TossInvestClient) -> Any:
    """The entry point: no account header needed. Rate group ACCOUNT is
    1 request/second, the tightest limit in the API; cache the result."""
    return client.request("GET", "/api/v1/accounts")


def get_holdings(client: TossInvestClient, account_seq: int, symbol: str | None = None) -> Any:
    return client.request(
        "GET",
        "/api/v1/holdings",
        params=_clean({"symbol": symbol}),
        account_seq=account_seq,
    )


def get_buying_power(client: TossInvestClient, account_seq: int, currency: str) -> Any:
    if currency not in ("KRW", "USD"):
        raise ValueError("currency must be 'KRW' or 'USD'")
    return client.request(
        "GET",
        "/api/v1/buying-power",
        params={"currency": currency},
        account_seq=account_seq,
    )


def get_sellable_quantity(client: TossInvestClient, account_seq: int, symbol: str) -> Any:
    return client.request(
        "GET",
        "/api/v1/sellable-quantity",
        params={"symbol": symbol},
        account_seq=account_seq,
    )


def get_commissions(client: TossInvestClient, account_seq: int) -> Any:
    return client.request("GET", "/api/v1/commissions", account_seq=account_seq)


def list_orders(
    client: TossInvestClient,
    account_seq: int,
    status: str,
    symbol: str | None = None,
    from_: str | None = None,
    to: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> Any:
    """status is required: OPEN returns every pending order (cursor/limit
    ignored by the server); CLOSED is cursor-paginated."""
    if status not in ("OPEN", "CLOSED"):
        raise ValueError("status must be 'OPEN' or 'CLOSED'")
    return client.request(
        "GET",
        "/api/v1/orders",
        params=_clean(
            {
                "status": status,
                "symbol": symbol,
                "from": from_,
                "to": to,
                "cursor": cursor,
                "limit": limit,
            }
        ),
        account_seq=account_seq,
    )


def get_order(client: TossInvestClient, account_seq: int, order_id: str) -> Any:
    """Order detail, including the execution block. Polling this (rate group
    ORDER_HISTORY, 5/s) is the only way to observe fills; the API has no push."""
    from toss_pilot.orders import _check_path_id

    path = f"/api/v1/orders/{_check_path_id('order_id', order_id)}"
    return client.request("GET", path, account_seq=account_seq)
