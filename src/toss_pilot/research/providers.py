"""Official read adapters. Missing/ambiguous financial facts remain unavailable."""
from __future__ import annotations

import time
import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from toss_pilot.market import get_candles
from .store import Store, instant, now, number


class ProviderError(ValueError):
    pass


class PublicClient:
    """No URLs or response text in errors: DART authenticates in query parameters."""
    def __init__(self, *, user_agent: str, transport=None, delay: float = 0.2):
        self.http = httpx.Client(timeout=20, headers={"User-Agent": user_agent}, transport=transport)
        self.delay = delay

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.http.close()

    def get(self, url: str, params: dict | None = None) -> dict:
        for attempt in range(4):
            time.sleep(self.delay)
            response = self.http.get(url, params=params)
            if response.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                try:
                    delay = float(response.headers.get("Retry-After", str(2 ** attempt)))
                except ValueError:
                    delay = 1
                if not 0 <= delay <= 30:
                    raise ProviderError("Provider asks for a long cooldown; retry the job later")
                time.sleep(delay)
                continue
            if response.status_code >= 400:
                raise ProviderError(f"Public data provider returned HTTP {response.status_code}")
            data = json.loads(response.text, parse_float=str)
            if not isinstance(data, dict):
                raise ProviderError("Expected a JSON object from data provider")
            return data
        raise ProviderError("Provider retry budget exhausted")


def collect_candles(store: Store, client: Any, identity: str, *, start: str, end: str,
                    max_pages: int = 100, delay: float = 0.1) -> dict:
    """Daily bars only. Requests stop at start; repeated inclusive boundaries dedupe."""
    start_at, end_at = instant(start), instant(end)
    if start_at > end_at or max_pages < 1:
        raise ValueError("Invalid date window or page budget")
    instrument = store.instrument(identity)
    run = store.start_run("toss-candles", identity, {"start": start_at, "end": end_at})
    cursor, seen_cursors, timestamps, snapshots = end_at, set(), set(), []
    completed = False
    try:
        for page in range(max_pages):
            response = get_candles(client, instrument["symbol"], "1d", count=200,
                                   before=cursor, adjusted=True)
            if not isinstance(response, dict) or not isinstance(response.get("candles"), list):
                raise ProviderError("Malformed candle page")
            raw = response["candles"]
            candles = []
            for row in raw:
                timestamp = instant(row["timestamp"])
                if start_at <= timestamp <= end_at:
                    candles.append({
                        "timestamp": timestamp, "currency": row["currency"], "adjusted": True,
                        **{name: row[wire] for name, wire in (
                            ("open", "openPrice"), ("high", "highPrice"), ("low", "lowPrice"),
                            ("close", "closePrice"), ("volume", "volume"))}})
                    timestamps.add(timestamp)
            snapshots.append(store.ingest(
                identity, "toss", "daily-candles", response, fetched_at=now(),
                locator="https://openapi.tossinvest.com/api/v1/candles", candles=candles))
            next_cursor = response.get("nextBefore")
            if next_cursor is None or (raw and min(instant(x["timestamp"]) for x in raw) <= start_at):
                completed = True
                break
            next_cursor = instant(next_cursor)
            if not raw or next_cursor in seen_cursors or next_cursor >= instant(cursor):
                raise ProviderError("Candle pagination made no progress")
            seen_cursors.add(next_cursor)
            cursor = next_cursor
            time.sleep(delay)
        details = {"run_id": run, "complete": completed, "pages": page + 1,
                   "candles": len(timestamps), "next_before": None if completed else cursor,
                   "snapshot_ids": snapshots, "start": start_at, "end": end_at}
        store.finish_run(run, "succeeded" if completed else "incomplete", details)
        return details
    except Exception as exc:
        store.finish_run(run, "failed", {"error_type": type(exc).__name__, "pages_saved": len(snapshots)})
        raise


# Ordered aliases, but conflicting values are withheld rather than guessed.
SEC_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "Revenue"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "operating_income": ["OperatingIncomeLoss", "ProfitLossFromOperatingActivities"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities", "CashFlowsFromUsedInOperatingActivities"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PurchaseOfPropertyPlantAndEquipment"],
    "assets": ["Assets"], "equity": ["StockholdersEquity", "Equity"],
    "liabilities": ["Liabilities"], "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashAndCashEquivalents"],
    "eps": ["EarningsPerShareDiluted", "DilutedEarningsLossPerShare"],
}
INSTANT_METRICS = {"assets", "equity", "liabilities", "cash"}


def publication_day_end(day: str, *, us: bool = False) -> str:
    # SEC filing dates are US dates. Next-day 05:00 UTC covers the complete
    # Eastern day even in standard time, without requiring a tzdata dependency.
    # Next-day UTC midnight is already conservative for a Korean calendar date.
    return (datetime.combine(date.fromisoformat(day), datetime.min.time(), timezone.utc)
            + timedelta(days=1, hours=5 if us else 0)).isoformat(timespec="seconds")


def annual_duration(start: str | None, end: str) -> bool:
    return bool(start and 330 <= (date.fromisoformat(end) - date.fromisoformat(start)).days <= 380)


def sec_facts(payload: dict, currency: str) -> tuple[list[dict], list[str]]:
    groups: dict[tuple, list[dict]] = {}
    warnings = []
    for metric, tags in SEC_TAGS.items():
        expected_unit = currency + "/shares" if metric == "eps" else currency
        for namespace in ("us-gaap", "ifrs-full"):
            namespace_facts = payload.get("facts", {}).get(namespace, {})
            for tag in tags:
                for row in namespace_facts.get(tag, {}).get("units", {}).get(expected_unit, []):
                    if row.get("form") not in ("10-K", "10-K/A", "20-F", "20-F/A"):
                        continue
                    if metric not in INSTANT_METRICS and not annual_duration(row.get("start"), row["end"]):
                        continue
                    if not row.get("filed") or not row.get("accn"):
                        continue
                    # json floats are converted at the HTTP decoding boundary below.
                    fact = {"metric": metric, "period_start": row.get("start"),
                            "period_end": row["end"], "available_at": publication_day_end(row["filed"], us=True),
                            "filing_id": row["accn"], "unit": expected_unit, "value": number(row["val"]),
                            "basis": "annual", "tag": f"{namespace}:{tag}"}
                    groups.setdefault((metric, row["end"], row["accn"]), []).append(fact)
    facts = []
    for key, candidates in groups.items():
        values = {(c["value"], c["period_start"]) for c in candidates}
        if len(values) != 1:
            warnings.append(f"Ambiguous SEC aliases: {key[0]} at {key[1]} ({key[2]})")
        else:
            facts.append(candidates[0])
    return facts, warnings


# Standard IFRS taxonomy IDs only. No fuzzy account-name guesses.
DART_TAGS = {
    "ifrs-full_Revenue": "revenue", "ifrs-full_ProfitLoss": "net_income",
    "dart_OperatingIncomeLoss": "operating_income",
    "ifrs-full_CashFlowsFromUsedInOperatingActivities": "operating_cash_flow",
    "ifrs-full_PurchaseOfPropertyPlantAndEquipment": "capex",
    "ifrs-full_Assets": "assets", "ifrs-full_Equity": "equity",
    "ifrs-full_Liabilities": "liabilities", "ifrs-full_CashAndCashEquivalents": "cash",
    "ifrs-full_DilutedEarningsLossPerShare": "eps",
}


def dart_facts(payload: dict, *, year: int, period_end: str,
               filing_dates: dict[str, str], currency: str = "KRW") -> tuple[list[dict], list[str]]:
    if payload.get("status") == "013":
        return [], ["OpenDART returned no financial data"]
    if payload.get("status") != "000":
        raise ProviderError(f"OpenDART status {payload.get('status', 'missing')}")
    if date.fromisoformat(period_end).year != year:
        raise ValueError("Financial year and period end disagree")
    groups: dict[tuple, list[dict]] = {}
    warnings = []
    for row in payload.get("list", []):
        metric = DART_TAGS.get(row.get("account_id"))
        if not metric:
            continue
        filing = row.get("rcept_no")
        if filing not in filing_dates:
            warnings.append(f"Missing filing publication date for {filing}")
            continue
        if row.get("currency", currency) != currency:
            raise ProviderError("Mixed currency in OpenDART statements")
        if row.get("reprt_code", "11011") != "11011" or row.get("fs_div", "CFS") != "CFS":
            raise ProviderError("Expected annual consolidated statements")
        raw = row.get("thstrm_amount", "")
        if not raw or raw == "-":
            continue
        fact = {"metric": metric, "period_start": None if metric in INSTANT_METRICS else f"{year}-01-01",
                "period_end": period_end, "available_at": publication_day_end(filing_dates[filing]),
                "filing_id": filing, "unit": currency + "/shares" if metric == "eps" else currency,
                "value": number(raw), "basis": "annual", "tag": row["account_id"],
                "source_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={filing}"}
        groups.setdefault((metric, filing), []).append(fact)
    facts = []
    for key, candidates in groups.items():
        if len({x["value"] for x in candidates}) != 1:
            warnings.append(f"Ambiguous DART account: {key[0]} ({key[1]})")
        else:
            facts.append(candidates[0])
    return facts, sorted(set(warnings))


def collect_sec(store: Store, client: PublicClient, identity: str) -> dict:
    instrument = store.instrument(identity)
    cik = str(instrument.get("cik", "")).zfill(10)
    if instrument["market"] != "US" or not cik.isdigit() or int(cik) == 0:
        raise ValueError("Register a verified US CIK first")
    run = store.start_run("sec-financials", identity, {"cik": cik})
    try:
        facts_url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        submissions = client.get(submissions_url)
        payload = client.get(facts_url)
        if int(payload.get("cik", -1)) != int(cik) or int(submissions.get("cik", -1)) != int(cik):
            raise ProviderError("SEC issuer identity mismatch")
        facts, warnings = sec_facts(payload, instrument["currency"])
        fetched = now()
        facts = [f for f in facts if f["available_at"] <= fetched]
        ids = [store.ingest(identity, "sec", "submissions", submissions,
                            fetched_at=fetched, locator=submissions_url)]
        ids.append(store.ingest(identity, "sec", "companyfacts", payload,
                                fetched_at=fetched, locator=facts_url, facts=facts))
        result = {"run_id": run, "facts": len(facts), "warnings": warnings, "snapshot_ids": ids}
        store.finish_run(run, "succeeded" if facts and not warnings else "incomplete", result)
        return result
    except Exception as exc:
        store.finish_run(run, "failed", {"error_type": type(exc).__name__})
        raise


def collect_dart(store: Store, client: PublicClient, identity: str, *, api_key: str,
                 year: int, period_end: str) -> dict:
    instrument = store.instrument(identity)
    corp = str(instrument.get("corp_code", ""))
    if instrument["market"] != "KR" or len(corp) != 8 or not corp.isdigit() or not api_key:
        raise ValueError("Register a verified DART corp_code and set OPENDART_API_KEY")
    if period_end != f"{year}-12-31":
        raise ValueError("Initial DART adapter supports December year-end issuers only")
    run = store.start_run("dart-financials", identity, {"year": year, "corp_code": corp})
    try:
        base = "https://opendart.fss.or.kr/api/"
        payload = client.get(base + "fnlttSinglAcntAll.json", {
            "crtfc_key": api_key, "corp_code": corp, "bsns_year": str(year),
            "reprt_code": "11011", "fs_div": "CFS"})
        if payload.get("status") not in ("000", "013"):
            raise ProviderError(f"OpenDART status {payload.get('status')}")
        if any(r.get("corp_code", corp) != corp for r in payload.get("list", [])):
            raise ProviderError("DART issuer identity mismatch")
        dates, filing_snapshots = {}, []
        for page in range(1, 101):
            listings = client.get(base + "list.json", {
                "crtfc_key": api_key, "corp_code": corp, "bgn_de": f"{year}0101",
                "end_de": date.today().strftime("%Y%m%d"), "page_no": page,
                "page_count": 100, "last_reprt_at": "N"})
            if listings.get("status") not in ("000", "013"):
                raise ProviderError("DART filing index failed")
            filing_snapshots.append(store.ingest(identity, "dart", "filings", listings,
                fetched_at=now(), locator=base + "list.json"))
            for row in listings.get("list", []):
                day = row["rcept_dt"]
                dates[row["rcept_no"]] = f"{day[:4]}-{day[4:6]}-{day[6:8]}"
            if page >= int(listings.get("total_page", 0)):
                break
        else:
            raise ProviderError("DART filing pagination budget exhausted")
        facts, warnings = dart_facts(payload, year=year, period_end=period_end, filing_dates=dates)
        fetched = now()
        facts = [f for f in facts if f["available_at"] <= fetched]
        sid = store.ingest(identity, "dart", "annual-CFS", payload, fetched_at=fetched,
                           locator=base + "fnlttSinglAcntAll.json", facts=facts)
        result = {"run_id": run, "facts": len(facts), "warnings": warnings,
                  "snapshot_ids": filing_snapshots + [sid]}
        store.finish_run(run, "succeeded" if facts and not warnings else "incomplete", result)
        return result
    except Exception as exc:
        store.finish_run(run, "failed", {"error_type": type(exc).__name__})
        raise
