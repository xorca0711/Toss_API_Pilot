import copy
import json
from decimal import Decimal

import httpx
import pytest

from toss_pilot.research.analysis import DEFAULT_ASSUMPTIONS, analyze, drawdown_series, financial_metrics
from toss_pilot.research.cli import main
from toss_pilot.research.demo import populate
from toss_pilot.research.providers import PublicClient, ProviderError, collect_candles, collect_sec, collect_dart, dart_facts, sec_facts
from toss_pilot.research.report import render
from toss_pilot.research.store import Store

AS_OF = "2026-10-11T00:00:00+00:00"


@pytest.fixture
def store(tmp_path):
    with Store(tmp_path / "research.sqlite3") as db:
        yield db


def test_revision_retention_idempotency_and_knowledge_boundary(store):
    identities = populate(store)
    counts = store.status()
    populate(store)
    assert store.status() == counts
    assert store.observations(identities[0], "2026-10-09T23:00:00+00:00") == ([], [])
    before = analyze(store, identities[0], AS_OF)
    old = next(f for f in before["sources"] if f["metric"] == "eps")
    amended = {**old, "value": "5000", "available_at": "2026-10-12T00:00:00+00:00",
               "filing_id": "DEMO-AMENDMENT"}
    store.ingest(identities[0], "synthetic", "revision", {"amendment": True},
                 fetched_at="2026-10-12T00:00:00+00:00", locator="fixture:revision", facts=[amended])
    assert analyze(store, identities[0], AS_OF) == before
    after = analyze(store, identities[0], "2026-10-13T00:00:00+00:00")
    assert after["financials"]["values"]["eps"] == "5000"
    assert store.status()["facts"] == counts["facts"] + 1


def test_invalid_snapshot_rolls_back_without_partial_data(store):
    identity = populate(store)[0]
    count = store.status()["snapshots"]
    for value in ("NaN", "Infinity", 1.2, True):
        fact = {"metric": "eps", "value": value, "period_end": "2025-12-31",
                "available_at": "2026-03-01T00:00:00+00:00", "filing_id": "bad",
                "basis": "annual", "unit": "KRW/shares"}
        with pytest.raises(ValueError):
            store.ingest(identity, "test", "bad", {"v": str(value)}, fetched_at=AS_OF,
                         locator="fixture:invalid", facts=[fact])
    assert store.status()["snapshots"] == count
    with pytest.raises(ValueError, match="credential-free"):
        store.ingest(identity, "test", "bad", {}, fetched_at=AS_OF,
                     locator="https://example.com?crtfc_key=secret")


def test_market_and_financial_hand_calculations(store):
    series, maximum, duration = drawdown_series([100, 80, 90, 110, 55])
    assert series == pytest.approx([0, -.2, -.1, 0, -.5])
    assert maximum == -.5
    assert duration == 2
    report = analyze(store, populate(store)[1], AS_OF)
    f = report["financials"]
    assert f["net_margin"] == .12
    assert f["free_cash_flow_proxy"] == "140000"
    assert f["liabilities_to_equity"] == pytest.approx(2 / 3, abs=.0001)
    assert f["operating_cash_conversion"] == 1.5
    expected = Decimal(8) * Decimal("1.04") ** 2 * 15 / Decimal("1.10") ** 2
    assert report["long_horizon"]["scenarios"]["base"]["present_value_proxy"] == pytest.approx(float(expected), abs=.0001)


def test_reports_reproduce_and_withhold_stale_or_missing_data(store):
    identity = populate(store)[0]
    first = analyze(store, identity, AS_OF)
    assert first == analyze(store, identity, AS_OF)
    stale = analyze(store, identity, "2029-01-01T00:00:00+00:00")
    assert stale["short_horizon"]["status"] == "insufficient_data"
    assert stale["long_horizon"]["scenarios"] == {}
    missing = store.register({"market": "US", "symbol": "EMPTY", "currency": "USD"})
    report = analyze(store, missing, AS_OF)
    assert report["long_horizon"]["status"] == "insufficient_data"
    assert "No eligible annual financial facts" in report["quality"]["financial_issues"]


def test_sector_and_split_checks_withhold_valuation(store):
    populate(store)
    original = store.instrument("US:DEMO")
    # Test exact inputs without silently mutating identity through the public API.
    for modifications in ({"sector": "bank"}, {"per_share_basis_verified": False}):
        body = {**original, **modifications}
        with store.db:
            store.db.execute("UPDATE instruments SET body=? WHERE id=?", (json.dumps(body), "US:DEMO"))
        report = analyze(store, "US:DEMO", AS_OF)
        assert report["long_horizon"]["scenarios"] == {}


def test_annual_financials_never_mix_periods():
    facts = [
        {"metric": "revenue", "value": "100", "period_end": "2025-12-31", "period_start": "2025-01-01"},
        {"metric": "net_income", "value": "5", "period_end": "2024-12-31", "period_start": "2024-01-01"},
    ]
    result, selected, warnings = financial_metrics(facts)
    assert result["net_margin"] is None
    assert "net_income" not in selected


def sec_payload():
    row = {"start": "2025-01-01", "end": "2025-12-31", "val": 1000,
           "form": "10-K", "filed": "2026-02-01", "accn": "0001-26-001"}
    return {"cik": 1, "facts": {"us-gaap": {"Revenues": {"units": {"USD": [row]}}}}}


def test_sec_alias_conflicts_and_quarters_are_not_guessed():
    payload = sec_payload()
    facts, warnings = sec_facts(payload, "USD")
    assert facts[0]["available_at"] == "2026-02-02T05:00:00+00:00"
    altered = copy.deepcopy(payload["facts"]["us-gaap"]["Revenues"])
    altered["units"]["USD"][0]["val"] = 2000
    payload["facts"]["us-gaap"]["SalesRevenueNet"] = altered
    facts, warnings = sec_facts(payload, "USD")
    assert not facts and warnings
    row = payload["facts"]["us-gaap"]["Revenues"]["units"]["USD"][0]
    row["start"] = "2025-10-01"
    del payload["facts"]["us-gaap"]["SalesRevenueNet"]
    assert sec_facts(payload, "USD") == ([], [])


def test_sec_collection_preserves_identity_and_payloads(store):
    store.register({"market": "US", "symbol": "ONE", "currency": "USD", "cik": "1"})
    def handler(request):
        assert "@" in request.headers["User-Agent"]
        if "/submissions/" in str(request.url):
            return httpx.Response(200, json={"cik": "1", "filings": {"recent": {}}})
        return httpx.Response(200, json=sec_payload())
    with PublicClient(user_agent="Research contact@example.com", transport=httpx.MockTransport(handler), delay=0) as client:
        result = collect_sec(store, client, "US:ONE")
    assert result["facts"] == 1
    assert store.status()["snapshots"] == 2
    assert store.status()["recent_runs"][0]["status"] == "succeeded"


def test_public_http_preserves_decimal_precision_and_hides_key_errors():
    with PublicClient(user_agent="test", delay=0, transport=httpx.MockTransport(
        lambda req: httpx.Response(200, text='{"value":0.1234567890123456789}'))) as client:
        assert client.get("https://example.com")["value"] == "0.1234567890123456789"
    with PublicClient(user_agent="test", delay=0, transport=httpx.MockTransport(
        lambda req: httpx.Response(403, text="SECRET"))) as client:
        with pytest.raises(ProviderError) as error:
            client.get("https://example.com", {"crtfc_key": "SECRET"})
        assert "SECRET" not in str(error.value)


def test_dart_standard_accounts_require_known_publication():
    payload = {"status": "000", "list": [
        {"account_id": "ifrs-full_Revenue", "rcept_no": "123", "thstrm_amount": "1,000",
         "reprt_code": "11011", "fs_div": "CFS", "currency": "KRW"}]}
    facts, warnings = dart_facts(payload, year=2025, period_end="2025-12-31", filing_dates={})
    assert not facts and warnings
    facts, warnings = dart_facts(payload, year=2025, period_end="2025-12-31", filing_dates={"123": "2026-03-02"})
    assert facts[0]["value"] == "1000"
    assert facts[0]["available_at"] == "2026-03-03T00:00:00+00:00"
    payload["list"][0]["currency"] = "USD"
    with pytest.raises(ProviderError):
        dart_facts(payload, year=2025, period_end="2025-12-31", filing_dates={"123": "2026-03-02"})


def candle(day):
    return {"timestamp": f"2026-10-{day:02d}T00:00:00+00:00", "openPrice": "10", "highPrice": "12",
            "lowPrice": "9", "closePrice": "11", "volume": "20", "currency": "USD"}


def test_inclusive_pagination_is_bounded_and_idempotent(store):
    store.register({"market": "US", "symbol": "ONE", "currency": "USD"})
    class Client:
        def request(self, method, path, params):
            assert method == "GET"
            day = int(params["before"][8:10])
            if day == 10:
                return {"candles": [candle(9), candle(8)], "nextBefore": candle(8)["timestamp"]}
            return {"candles": [candle(8), candle(7)], "nextBefore": None}
    args = {"start": "2026-10-07T00:00:00+00:00", "end": "2026-10-10T00:00:00+00:00", "delay": 0}
    result = collect_candles(store, Client(), "US:ONE", **args)
    assert result["complete"] and result["candles"] == 3
    snapshots = store.status()["snapshots"]
    collect_candles(store, Client(), "US:ONE", **args)
    assert store.status()["snapshots"] == snapshots
    assert len(store.observations("US:ONE", "2030-01-01T00:00:00+00:00")[0]) == 3
    result = collect_candles(store, Client(), "US:ONE", **args, max_pages=1)
    assert not result["complete"]
    assert store.status()["recent_runs"][0]["status"] == "incomplete"


def test_stuck_pagination_records_failure(store):
    store.register({"market": "US", "symbol": "ONE", "currency": "USD"})
    class Client:
        def request(self, method, path, params):
            return {"candles": [candle(9)], "nextBefore": params["before"]}
    with pytest.raises(ProviderError, match="no progress"):
        collect_candles(store, Client(), "US:ONE", start="2026-10-01T00:00:00+00:00",
                        end="2026-10-10T00:00:00+00:00", delay=0)
    assert store.status()["recent_runs"][0]["status"] == "failed"


def test_demo_cli_and_escaped_html(tmp_path, store, capsys):
    output = tmp_path / "demo"
    assert main(["demo", "--output", str(output)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert len(result["reports"]) == 2
    assert len(list(output.glob("*.html"))) == 2
    report = analyze(store, populate(store)[0], AS_OF)
    report["instrument"]["name"] = "<script>alert(1)</script>"
    page = render(report)
    assert "<script>" not in page
    assert "&lt;script&gt;" in page
    assert "SYNTHETIC DEMONSTRATION" in page
    assert page.count("<svg") == 2


def test_dart_collection_reads_filing_pages_and_never_persists_key(store):
    store.register({"market": "KR", "symbol": "000001", "currency": "KRW", "corp_code": "00000001"})
    def handler(request):
        assert request.url.params["crtfc_key"] == "SECRET"
        if request.url.path.endswith("fnlttSinglAcntAll.json"):
            return httpx.Response(200, json={"status": "000", "list": [{
                "account_id": "ifrs-full_Revenue", "rcept_no": "20260302000001",
                "corp_code": "00000001", "bsns_year": "2025",
                "reprt_code": "11011", "fs_div": "CFS", "thstrm_amount": "2000", "currency": "KRW"}]})
        if request.url.params["page_no"] == "1":
            return httpx.Response(200, json={"status": "000", "total_page": 2, "list": []})
        return httpx.Response(200, json={"status": "000", "total_page": 2, "list": [
            {"rcept_no": "20260302000001", "rcept_dt": "20260302"}]})
    with PublicClient(user_agent="test", delay=0, transport=httpx.MockTransport(handler)) as client:
        result = collect_dart(store, client, "KR:000001", api_key="SECRET", year=2025, period_end="2025-12-31")
    assert result["facts"] == 1
    assert store.status()["snapshots"] == 3
    assert "SECRET" not in "\n".join(store.db.iterdump())


def test_public_retry_honors_header_and_long_cooldown_fails(monkeypatch):
    waits = []
    monkeypatch.setattr("toss_pilot.research.providers.time.sleep", waits.append)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(429, headers={"Retry-After": "2"}) if len(calls) == 1 else httpx.Response(200, json={"ok": True})
    with PublicClient(user_agent="test", delay=0, transport=httpx.MockTransport(handler)) as client:
        assert client.get("https://example.com")["ok"]
    assert 2 in waits and len(calls) == 2
    with PublicClient(user_agent="test", delay=0, transport=httpx.MockTransport(
        lambda req: httpx.Response(429, headers={"Retry-After": "600"}))) as client:
        with pytest.raises(ProviderError, match="cooldown"):
            client.get("https://example.com")


def test_conflicting_daily_rows_and_mixed_currency_fail_atomically(store):
    identity = populate(store)[1]
    candles, _ = store.observations(identity, AS_OF)
    c = {k:v for k,v in candles[0].items() if k not in {"snapshot_id", "source_url"}}
    count = store.status()["snapshots"]
    with pytest.raises(ValueError, match="Conflicting"):
        store.ingest(identity, "test", "conflict", {}, fetched_at=AS_OF, locator="fixture:conflict",
                     candles=[c, {**c, "volume": "200000"}])
    with pytest.raises(ValueError, match="currency"):
        store.ingest(identity, "test", "mixed", {}, fetched_at=AS_OF, locator="fixture:mixed",
                     candles=[{**c, "currency": "KRW"}])
    assert store.status()["snapshots"] == count


@pytest.mark.parametrize("change", [
    {"minimum_bars": 20}, {"entry_margin": "NaN"}, {"valuation_years": 0},
    {"atr_invalidation_multiple": "Infinity"},
])
def test_invalid_assumptions_fail_before_computation(store, change):
    identity = populate(store)[1]
    assumptions = {**DEFAULT_ASSUMPTIONS, **change}
    with pytest.raises(ValueError):
        analyze(store, identity, AS_OF, assumptions)


def test_report_failure_is_logged_without_partial_report(tmp_path, store):
    from toss_pilot.research.cli import generate
    identity = populate(store)[1]
    with pytest.raises(ValueError):
        generate(store, identity, "2026-10-11", None, tmp_path / "reports")
    assert store.status()["recent_runs"][0]["status"] == "failed"
    assert store.status()["reports"] == 0


def test_basis_review_is_dated_and_does_not_rewrite_history(store):
    identity = populate(store)[1]
    before = analyze(store, identity, AS_OF)
    store.review(identity, sector="bank", verified_through="2026-10-12",
                 note="Test review", reviewed_at="2026-10-12T00:00:00+00:00")
    assert analyze(store, identity, AS_OF) == before
    assert analyze(store, identity, "2026-10-12T01:00:00+00:00")["long_horizon"]["scenarios"] == {}
    with pytest.raises(ValueError, match="future"):
        store.review(identity, sector="industrials", verified_through="2099-01-01", note="Invalid future attestation")
