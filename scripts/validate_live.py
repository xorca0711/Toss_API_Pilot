"""Bounded, serial live reads. Never logs credentials, response errors or accounts."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx

from toss_pilot.client import ResearchClient
from toss_pilot.config import REPO_ROOT, load_config, load_env_file
from toss_pilot.market import get_prices, get_stocks
from toss_pilot.research.providers import PublicClient, collect_candles, collect_dart, collect_sec
from toss_pilot.research.store import Store, now


class ReadTransport(httpx.BaseTransport):
    """Independent allowlist, including only OAuth and public market reads."""
    def __init__(self):
        self.inner = httpx.HTTPTransport(retries=0)
        self.events = []

    def handle_request(self, request):
        host, path, method = request.url.host, request.url.path, request.method
        permitted = host == "openapi.tossinvest.com" and (
            (method == "POST" and path == "/oauth2/token") or
            (method == "GET" and path in {"/api/v1/stocks", "/api/v1/prices", "/api/v1/candles"}))
        if not permitted:
            raise ValueError("Live validation transport rejected request")
        event = {"host": host, "path": path, "method": method}
        self.events.append(event)
        try:
            response = self.inner.handle_request(request)
            event["http_status"] = response.status_code
            return response
        except Exception as exc:
            event["error_type"] = type(exc).__name__
            raise

    def close(self):
        self.inner.close()


def main():
    os.environ.pop("TOSS_PILOT_ALLOW_LIVE_ORDERS", None)
    load_env_file()
    folder = REPO_ROOT / "docs" / "evidence" / "live"
    folder.mkdir(parents=True, exist_ok=True)
    result = {"started_at": now(), "trading_enabled": False, "operations": []}
    transport = ReadTransport()
    with Store(REPO_ROOT / "data" / "live.sqlite3") as store:
        for item in (
            {"market": "US", "symbol": "AAPL", "name": "Apple Inc.", "currency": "USD", "cik": "0000320193"},
            {"market": "KR", "symbol": "005930", "name": "Samsung Electronics", "currency": "KRW", "corp_code": "00126380"},
        ):
            store.register(item)

        def attempt(name, fn):
            started = time.monotonic()
            item = {"operation": name}
            try:
                item.update(status="succeeded", result=fn())
            except Exception as exc:
                item.update(status="failed", error_type=type(exc).__name__)
                if isinstance(getattr(exc, "status_code", None), int):
                    item["http_status"] = exc.status_code
            item["seconds"] = round(time.monotonic() - started, 2)
            result["operations"].append(item)
            (folder / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
            print(json.dumps(item), flush=True)
            return item["status"] == "succeeded"

        config = load_config(REPO_ROOT / "config" / "api.json")
        config["request_timeout_seconds"] = 15
        with ResearchClient(config=config, transport=transport) as client:
            def stocks():
                payload = get_stocks(client, ["005930", "AAPL"])
                # Preserve actual responses locally; output only response shape.
                target = REPO_ROOT / "data" / "live-stocks.json"
                target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                return {"response_type": type(payload).__name__, "local_file": str(target)}
            if attempt("toss-stocks", stocks):
                def prices():
                    payload = get_prices(client, ["005930", "AAPL"])
                    (REPO_ROOT / "data" / "live-prices.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
                    return {"response_type": type(payload).__name__}
                attempt("toss-prices", prices)
                for identity in ("US:AAPL", "KR:005930"):
                    attempt("toss-candles:" + identity, lambda identity=identity: collect_candles(
                        store, client, identity, start="2025-10-01T00:00:00+00:00", end=now(), max_pages=4))
        for name, key, identity in (("sec", "SEC_USER_AGENT", "US:AAPL"), ("dart", "OPENDART_API_KEY", "KR:005930")):
            if not os.environ.get(key):
                result["operations"].append({"operation": name, "status": "not_configured", "missing": key})
                continue
            with PublicClient(user_agent=os.environ.get("SEC_USER_AGENT", "toss-pilot-research/0.2.0")) as public:
                attempt(name, lambda name=name: collect_sec(store, public, identity) if name == "sec" else
                        collect_dart(store, public, identity, api_key=os.environ[key], year=2025, period_end="2025-12-31"))
        result["store"] = store.status()
    result.update(finished_at=now(), transport_events=transport.events,
                  broker_mutations_attempted=0, account_reads_attempted=0)
    (folder / "validation.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
