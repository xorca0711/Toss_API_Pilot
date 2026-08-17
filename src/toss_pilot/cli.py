"""Read-only command-line interface.

Deliberately exposes no order placement, modification, or cancellation:
those live only in toss_pilot.orders behind the dry-run gate. Credentials
come from the environment or a gitignored .env file.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from toss_pilot import account as account_mod
from toss_pilot import market as market_mod
from toss_pilot.client import TossInvestClient
from toss_pilot.errors import CredentialsMissing, TossApiError


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _resolve_account_seq(client: TossInvestClient, explicit: int | None) -> int:
    if explicit is not None:
        return explicit
    accounts = account_mod.get_accounts(client)
    if not accounts:
        raise SystemExit("No BROKERAGE account returned by /api/v1/accounts.")
    return int(accounts[0]["accountSeq"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="toss-pilot",
        description="Read-only pilot CLI for the Toss Securities Open API.",
        epilog=(
            "Order placement is intentionally absent from this CLI; see "
            "toss_pilot.orders (dry-run by default) if you need it in code."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_token = sub.add_parser(
        "token",
        help="Ensure a valid access token exists (cached; re-issue only when needed).",
        description=(
            "Only one token per client is valid at a time; issuing a new one "
            "invalidates the previous. This command reuses the cache when possible."
        ),
    )
    p_token.set_defaults(func=_cmd_token)

    p_price = sub.add_parser("price", help="Current prices for up to 200 symbols.")
    p_price.add_argument("symbols", nargs="+", help="e.g. 005930 000660 AAPL")
    p_price.set_defaults(func=_cmd_price)

    p_candles = sub.add_parser("candles", help="OHLCV candles for one symbol.")
    p_candles.add_argument("symbol")
    p_candles.add_argument("--interval", choices=["1m", "1d"], default="1d")
    p_candles.add_argument("--count", type=int, default=None)
    p_candles.set_defaults(func=_cmd_candles)

    p_cal = sub.add_parser("calendar", help="Market calendar for KR or US.")
    p_cal.add_argument("country", choices=["KR", "US"])
    p_cal.add_argument("--date", default=None, help="YYYY-MM-DD")
    p_cal.set_defaults(func=_cmd_calendar)

    p_fx = sub.add_parser("fx", help="Indicative USD/KRW exchange rate.")
    p_fx.set_defaults(func=_cmd_fx)

    p_accounts = sub.add_parser("accounts", help="List accounts (accountSeq source).")
    p_accounts.set_defaults(func=_cmd_accounts)

    p_holdings = sub.add_parser("holdings", help="Holdings with P/L for one account.")
    p_holdings.add_argument("--account-seq", type=int, default=None)
    p_holdings.add_argument("--symbol", default=None)
    p_holdings.set_defaults(func=_cmd_holdings)

    p_orders = sub.add_parser("orders", help="List orders (read-only).")
    p_orders.add_argument("status", choices=["OPEN", "CLOSED"])
    p_orders.add_argument("--account-seq", type=int, default=None)
    p_orders.add_argument("--symbol", default=None)
    p_orders.set_defaults(func=_cmd_orders)

    args = parser.parse_args(argv)
    try:
        with TossInvestClient() as client:
            args.func(client, args)
    except CredentialsMissing as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except TossApiError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_token(client: TossInvestClient, args: argparse.Namespace) -> None:
    client._tokens.get_token()
    _print({"token": "valid (cached or newly issued)"})


def _cmd_price(client: TossInvestClient, args: argparse.Namespace) -> None:
    _print(market_mod.get_prices(client, args.symbols))


def _cmd_candles(client: TossInvestClient, args: argparse.Namespace) -> None:
    _print(market_mod.get_candles(client, args.symbol, args.interval, count=args.count))


def _cmd_calendar(client: TossInvestClient, args: argparse.Namespace) -> None:
    _print(market_mod.get_market_calendar(client, args.country, date=args.date))


def _cmd_fx(client: TossInvestClient, args: argparse.Namespace) -> None:
    _print(market_mod.get_exchange_rate(client))


def _cmd_accounts(client: TossInvestClient, args: argparse.Namespace) -> None:
    _print(account_mod.get_accounts(client))


def _cmd_holdings(client: TossInvestClient, args: argparse.Namespace) -> None:
    seq = _resolve_account_seq(client, args.account_seq)
    _print(account_mod.get_holdings(client, seq, symbol=args.symbol))


def _cmd_orders(client: TossInvestClient, args: argparse.Namespace) -> None:
    seq = _resolve_account_seq(client, args.account_seq)
    _print(account_mod.list_orders(client, seq, args.status, symbol=args.symbol))


if __name__ == "__main__":
    raise SystemExit(main())
