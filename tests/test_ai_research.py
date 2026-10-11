import copy
import json
import sqlite3

import httpx
import pytest

from toss_pilot.config import load_env_file
from toss_pilot.research.ai import build_packet, estimate_cost, generate_openai, import_draft, validate_draft
from toss_pilot.research.cli import main
from toss_pilot.research.evidence import collect_document, ingest_document
from toss_pilot.research.store import Store, canonical

AS_OF = "2026-10-11T00:00:00+00:00"
SUMMARY = "Research draft for human review; consult the cited evidence and data gaps."


@pytest.fixture
def research(tmp_path):
    with Store(tmp_path / "research.sqlite3") as store:
        identity = store.register({"market": "US", "symbol": "REAL", "currency": "USD"})
        item = {"instrument_id": identity, "source_url": "https://www.apple.com/research-test/",
                "title": "Issuer release", "kind": "issuer_release", "published_at": "2026-07-31T00:00:00+00:00",
                "fetched_at": "2026-10-10T00:00:00+00:00", "text": "Revenue grew while costs rose. Growth faces execution risks.",
                "extraction": "source_text"}
        ingest_document(store, item)
        yield store, identity, item


def make_draft(packet):
    eid = packet["evidence"][0]["id"] if packet["evidence"] else None
    claim = {"kind": "inference", "text": "Growth deserves monitoring.",
             "citations": [{"evidence_id": eid, "quote": "Revenue grew"}]}
    horizon = {"stance": "insufficient_data", "thesis": [claim], "counterarguments": [copy.deepcopy(claim)], "catalysts": []}
    return {"schema_version": 1, "packet_hash": packet["packet_hash"], "status": "draft", "summary": SUMMARY,
            "short_horizon": copy.deepcopy(horizon), "long_horizon": copy.deepcopy(horizon),
            "missing_information": ["Adjusted price history is missing."]}


def test_documents_preserve_knowledge_boundary_and_revisions(research):
    store, identity, item = research
    first = ingest_document(store, item)
    later = {**item, "fetched_at": AS_OF}
    assert ingest_document(store, later) == first
    before = build_packet(store, identity, "2026-10-09T00:00:00+00:00")
    assert not before["evidence"]
    packet = build_packet(store, identity, AS_OF)
    assert packet == build_packet(store, identity, AS_OF)
    assert packet["evidence"][0]["fetched_at"] == item["fetched_at"]
    revised = {**later, "text": "Corrected disclosure: revenue declined while costs rose."}
    assert ingest_document(store, revised) != first
    assert len(build_packet(store, identity, AS_OF)["evidence"]) == 2
    stale = build_packet(store, identity, "2027-04-01T00:00:00+00:00")
    assert not stale["evidence"] and stale["coverage"]["stale_documents_excluded"] == 2


@pytest.mark.parametrize("change", [
    {"published_at": "2027-01-01T00:00:00Z"}, {"fetched_at": "2030-01-01T00:00:00Z"},
    {"source_url": "https://www.apple.com/?token=secret"}, {"source_url": "javascript:alert(1)"},
    {"source_url": "https://user:password@example.com/"}, {"text": ""}, {"extraction": "verified-by-ai"},
])
def test_document_validation_rejects_unsafe_inputs(research, change):
    store, _, item = research
    with pytest.raises(ValueError):
        ingest_document(store, {**item, **change})
    assert store.status()["documents"] == 1


def test_collector_boundaries_redirects_and_host_allowlist(research):
    store, identity, _ = research
    kwargs = dict(identity=identity, url="https://www.apple.com/release/", title="Release",
                  published_at="2026-07-31T00:00:00Z", start_text="BEGIN", end_text="END")
    def handler(request):
        assert request.method == "GET" and "authorization" not in request.headers
        return httpx.Response(200, text="<script>do not collect this</script><p>BEGIN Revenue rose and costs grew. END</p>",
                              headers={"content-type": "text/html"})
    identifier = collect_document(store, **kwargs, transport=httpx.MockTransport(handler))
    body = store.db.execute("SELECT body FROM documents WHERE id=?", (identifier,)).fetchone()[0]
    assert "Revenue rose" in body and "do not collect" not in body
    for url in ("https://localhost/release", "http://www.apple.com/release", "https://www.apple.com.evil.test/"):
        with pytest.raises(ValueError):
            collect_document(store, **{**kwargs, "url": url})
    with pytest.raises(ValueError, match="HTTP 302"):
        collect_document(store, **kwargs, transport=httpx.MockTransport(lambda r: httpx.Response(302, headers={"location":"https://localhost/"})))
    with pytest.raises(ValueError, match="boundaries"):
        collect_document(store, **{**kwargs, "start_text": "NOT THERE"}, transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("case", ["number", "unicode_number", "missing_metric", "bad_cite", "bad_quote", "override_gate", "packet", "extra", "buy", "uncited", "uncited_summary", "no_counter", "long_quote"])
def test_adversarial_drafts_are_rejected(research, case):
    store, identity, _ = research
    packet = build_packet(store, identity, AS_OF)
    draft = make_draft(packet)
    claim = draft["short_horizon"]["thesis"][0]
    if case == "number": claim["text"] = "The target is $999."
    if case == "unicode_number": claim["text"] = "The target is ９９９."
    if case == "missing_metric": claim["text"] = "Value {{metric:market.imaginary}}."
    if case == "bad_cite": claim["citations"][0]["evidence_id"] = "invented"
    if case == "bad_quote": claim["citations"][0]["quote"] = "Earnings doubled"
    if case == "override_gate": draft["short_horizon"]["stance"] = "watch"
    if case == "packet": draft["packet_hash"] = "other-packet"
    if case == "extra": draft["confidence"] = .99
    if case == "buy": claim["text"] = "Buy immediately."
    if case == "uncited": claim["citations"] = []
    if case == "uncited_summary": draft["summary"] = "This company will outperform."
    if case == "no_counter": draft["long_horizon"]["counterarguments"] = []
    if case == "long_quote":
        for h in ("short_horizon", "long_horizon"):
            for s in ("thesis", "counterarguments"):
                draft[h][s][0]["citations"][0]["quote"] = packet["evidence"][0]["text"]
    with pytest.raises(ValueError):
        validate_draft(packet, draft)


def test_missing_evidence_abstains_without_paid_call(tmp_path):
    with Store(tmp_path / "empty.sqlite3") as store:
        identity = store.register({"market": "KR", "symbol": "005930", "currency": "KRW"})
        packet = build_packet(store, identity, AS_OF)
        draft = make_draft(packet)
        draft["status"] = "abstain"
        for h in ("short_horizon", "long_horizon"):
            for s in ("thesis", "counterarguments", "catalysts"):
                draft[h][s] = []
        result = import_draft(store, draft, model="unavailable", output=tmp_path / "reports")
        assert result["draft_status"] == "abstain"
        assert store.status()["recent_runs"][0]["status"] == "incomplete"


def test_model_can_abstain_even_with_sufficient_numerical_data(research):
    store, identity, _ = research
    packet = build_packet(store, identity, AS_OF)
    packet["required_stances"] = {h: "watch" for h in ("short_horizon", "long_horizon")}
    draft = make_draft(packet)
    draft["status"] = "abstain"
    for h in ("short_horizon", "long_horizon"):
        for s in ("thesis", "counterarguments", "catalysts"):
            draft[h][s] = []
    validate_draft(packet, draft)


def test_ai_report_preserves_numbers_and_escapes_text(research, tmp_path):
    store, identity, _ = research
    packet = build_packet(store, identity, AS_OF)
    draft = make_draft(packet)
    draft["short_horizon"]["thesis"][0]["text"] = '<script>alert("x")</script> Bars: {{metric:market.bars}}.'
    result = import_draft(store, draft, model="Codex session; ID unavailable", output=tmp_path)
    report = json.loads(__import__("pathlib").Path(result["files"]["json"]).read_text(encoding="utf-8"))
    assert report["market"] == packet["report"]["market"]
    assert report["ai_research"]["usage"] is None
    assert report["ai_research"]["estimated_cost_usd"] is None
    assert "text" not in report["ai_research"]["evidence"][0]
    html = __import__("pathlib").Path(result["files"]["html"]).read_text(encoding="utf-8")
    assert '<script>' not in html and '&lt;script&gt;' in html and 'Bars: 0' in html
    assert "Semantic entailment is not automatically verified" in html
    assert "human review pending" in html
    assert "available from 2026-07-31" in html


def test_failed_ai_import_records_failure_without_report(research, tmp_path):
    store, identity, _ = research
    draft = make_draft(build_packet(store, identity, AS_OF))
    draft["long_horizon"]["stance"] = "watch"
    with pytest.raises(ValueError):
        import_draft(store, draft, model="test", output=tmp_path)
    assert store.status()["reports"] == 0
    assert store.status()["recent_runs"][0]["status"] == "failed"


@pytest.mark.parametrize("mode", ["success", "incomplete", "refusal", "hallucination", "http_error", "missing_model"])
def test_responses_api_transport_and_failure_usage(research, tmp_path, mode):
    store, identity, _ = research
    packet = build_packet(store, identity, AS_OF)
    draft = make_draft(packet)
    usage = {"input_tokens": 1000, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 200}}
    calls = []
    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert body["store"] is False and "tools" not in body and body["max_output_tokens"] == 4000
        assert body["text"]["format"]["strict"] is True
        if mode == "http_error": return httpx.Response(429, text="secret error data")
        if mode == "hallucination": draft["short_horizon"]["thesis"][0]["text"] = "Returns will be 99 percent."
        block = {"type": "refusal", "refusal": "No"} if mode == "refusal" else {"type": "output_text", "text": json.dumps(draft)}
        return httpx.Response(200, json={"id":"response-test", "model": None if mode == "missing_model" else "provider-model-id",
              "status": "incomplete" if mode == "incomplete" else "completed", "usage": usage,
              "output": [{"type": "message", "content": [block]}]})
    kwargs = dict(api_key="test-secret", model="requested-model", output=tmp_path,
                  transport=httpx.MockTransport(handler))
    if mode == "success":
        result = generate_openai(store, packet["packet_hash"], **kwargs)
        assert result["model"] == "provider-model-id" and result["usage"] == usage
    else:
        with pytest.raises(ValueError): generate_openai(store, packet["packet_hash"], **kwargs)
        assert store.status()["reports"] == 0
        row = store.db.execute("SELECT details,status FROM runs WHERE kind='openai-request'").fetchone()
        assert row["status"] == "failed" and "test-secret" not in row["details"]
        if mode != "http_error": assert json.loads(row["details"])["usage"] == usage
    assert len(calls) == 1


def test_cost_estimate_and_env_file_are_explicit(tmp_path, monkeypatch):
    rates = {"input_per_million": "2", "cached_input_per_million": "1", "output_per_million": "4",
             "as_of": AS_OF, "source_url": "https://developers.openai.com/api/docs/pricing"}
    cost = estimate_cost({"input_tokens": 1000, "output_tokens": 100, "input_tokens_details": {"cached_tokens": 200}}, rates)
    assert cost["estimated_cost_usd"] == "0.0022"
    for key in ("OPENAI_API_KEY", "SEC_USER_AGENT", "TOSS_PILOT_ALLOW_LIVE_ORDERS"):
        monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text('\ufeffOPENAI_API_KEY="test-value"\nSEC_USER_AGENT=app contact@example.com\nTOSS_PILOT_ALLOW_LIVE_ORDERS=yes', encoding="utf-8")
    load_env_file(path)
    import os
    assert os.environ["OPENAI_API_KEY"] == "test-value"
    assert "TOSS_PILOT_ALLOW_LIVE_ORDERS" not in os.environ
    monkeypatch.delenv("OPENAI_API_KEY")
    monkeypatch.delenv("SEC_USER_AGENT")


def test_v1_migration_preserves_existing_data(tmp_path):
    path = tmp_path / "v1.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE instruments(id TEXT PRIMARY KEY,body TEXT NOT NULL)")
        db.execute("INSERT INTO instruments VALUES(?,?)", ("US:AAPL", canonical({"id":"US:AAPL"})))
        db.execute("PRAGMA user_version=1")
    with Store(path) as store:
        assert store.instrument("US:AAPL")["id"] == "US:AAPL"
        assert store.db.execute("PRAGMA user_version").fetchone()[0] == 2
        assert store.status()["documents"] == 0


def test_cli_packet_and_import_round_trip(research, tmp_path, capsys):
    store, identity, _ = research
    packetfile, draftfile = tmp_path / "packet.json", tmp_path / "draft.json"
    base = ["--db", str(store.path)]
    assert main(base + ["research-packet", identity, "--as-of", AS_OF, "--output", str(packetfile)]) == 0
    draftfile.write_text(json.dumps(make_draft(json.loads(packetfile.read_text(encoding="utf-8")))), encoding="utf-8")
    assert main(base + ["ai-import", "--file", str(draftfile), "--model", "test", "--output", str(tmp_path / "output")]) == 0
