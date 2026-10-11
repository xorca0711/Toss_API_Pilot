"""Read-only collection, local storage and reproducible numerical reports."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import httpx

from toss_pilot.client import ResearchClient
from toss_pilot.config import STATE_ROOT, load_env_file
from toss_pilot.errors import CredentialsMissing, TossApiError
from .analysis import analyze
from .demo import populate
from .providers import PublicClient, collect_candles, collect_dart, collect_sec
from .report import write_report
from .store import Store, now
from .ai import build_packet, generate_openai, import_draft
from .evidence import collect_document, ingest_document


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"), parse_float=str)


def generate(store, identity, as_of, assumptions, output):
    run = store.start_run("report", identity, {"as_of": as_of})
    try:
        result = analyze(store, identity, as_of, assumptions)
        report_id = store.save_report(run, result)
        files = write_report(result, output)
        store.finish_run(run, "succeeded", {"report_id": report_id, "files": files})
        return {"run_id": run, "report_id": report_id, "files": files,
                "short_status": result["short_horizon"]["status"],
                "long_status": result["long_horizon"]["status"]}
    except Exception as exc:
        store.finish_run(run, "failed", {"error_type": type(exc).__name__})
        raise


def main(argv=None):
    load_env_file()
    parser = argparse.ArgumentParser(description="Stock research and local data ledger. No trading commands.")
    parser.add_argument("--db", default=str(STATE_ROOT / "data" / "research.sqlite3"))
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register", help="Register reviewed instrument identity from JSON")
    register.add_argument("--file", required=True)
    review = commands.add_parser("review-basis", help="Record a dated human review of sector and per-share consistency")
    review.add_argument("instrument")
    review.add_argument("--sector", required=True)
    review.add_argument("--verified-through", required=True)
    review.add_argument("--note", required=True, help="Evidence checked; do not include secrets")
    imp = commands.add_parser("import", help="Import a normalized, source-attributed snapshot")
    imp.add_argument("--file", required=True)
    commands.add_parser("status", help="Show row counts and recent run statuses")
    candles = commands.add_parser("collect-candles", help="Collect Toss adjusted daily candles")
    candles.add_argument("instrument")
    candles.add_argument("--start", required=True, help="ISO timestamp including timezone")
    candles.add_argument("--end", required=True, help="ISO timestamp including timezone")
    candles.add_argument("--max-pages", type=int, default=100)
    sec = commands.add_parser("collect-sec", help="Collect official SEC annual facts and submissions")
    sec.add_argument("instrument")
    sec.add_argument("--user-agent", default=os.environ.get("SEC_USER_AGENT"))
    dart = commands.add_parser("collect-dart", help="Collect annual consolidated OpenDART facts")
    dart.add_argument("instrument")
    dart.add_argument("--year", required=True, type=int)
    dart.add_argument("--period-end", required=True)
    report = commands.add_parser("report", help="Create JSON/HTML from eligible local observations")
    report.add_argument("instrument")
    report.add_argument("--as-of", default=None, help="ISO timestamp including timezone; defaults to now")
    report.add_argument("--assumptions", default=None)
    report.add_argument("--output", default=str(STATE_ROOT / "reports"))
    demo = commands.add_parser("demo", help="Generate two explicitly synthetic reports without network")
    demo.add_argument("--output", default=str(STATE_ROOT / "reports" / "demo"))
    doc = commands.add_parser("document-import", help="Import dated source text or an explicitly labeled curated summary")
    doc.add_argument("--file", required=True)
    fetch = commands.add_parser("collect-document", help="Fetch a bounded official HTML article; no API key required")
    fetch.add_argument("instrument")
    fetch.add_argument("--url", required=True)
    fetch.add_argument("--title", required=True)
    fetch.add_argument("--published-at", required=True, help="Reviewed publication timestamp; date-only sources use next UTC midnight")
    fetch.add_argument("--kind", default="issuer_release", choices=["issuer_release", "filing", "news"])
    fetch.add_argument("--start-text", required=True)
    fetch.add_argument("--end-text", required=True)
    packet = commands.add_parser("research-packet", help="Export evidence, computed metrics and AI schema; no paid model call")
    packet.add_argument("instrument")
    packet.add_argument("--as-of", default=None)
    packet.add_argument("--output", required=True, help="Packet JSON file")
    imp_ai = commands.add_parser("ai-import", help="Validate and render a Codex-assisted draft against a stored packet")
    imp_ai.add_argument("--file", required=True)
    imp_ai.add_argument("--model", required=True, help="Actual model ID, or explicitly say unavailable")
    imp_ai.add_argument("--output", default=str(STATE_ROOT / "reports"))
    ai = commands.add_parser("ai-openai", help="OPTIONAL separately billed Responses API request; never used implicitly")
    ai.add_argument("--packet-hash", required=True)
    ai.add_argument("--model", default=os.environ.get("OPENAI_MODEL"))
    ai.add_argument("--pricing", help="Optional dated rates JSON; otherwise cost remains unavailable")
    ai.add_argument("--output", default=str(STATE_ROOT / "reports"))
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            # Synthetic records never enter the default real-data database.
            db = Path(args.output) / "demo.sqlite3"
        else:
            db = args.db
        with Store(db) as store:
            if args.command == "register":
                result = {"instrument": store.register(read_json(args.file))}
            elif args.command == "review-basis":
                result = {"review_id": store.review(args.instrument, sector=args.sector,
                    verified_through=args.verified_through, note=args.note)}
            elif args.command == "import":
                item = read_json(args.file)
                result = {"snapshot_id": store.ingest(
                    item["instrument_id"], item["source"], item["kind"], item["payload"],
                    fetched_at=item["fetched_at"], locator=item["locator"],
                    candles=item.get("candles"), facts=item.get("facts"))}
            elif args.command == "status":
                result = store.status()
            elif args.command == "document-import":
                result = {"document_id": ingest_document(store, read_json(args.file))}
            elif args.command == "collect-document":
                result = {"document_id": collect_document(store, identity=args.instrument, url=args.url,
                    title=args.title, published_at=args.published_at, kind=args.kind,
                    start_text=args.start_text, end_text=args.end_text,
                    user_agent=os.environ.get("SEC_USER_AGENT") or "toss-pilot-research/0.3.0")}
            elif args.command == "research-packet":
                value = build_packet(store, args.instrument, args.as_of or now())
                path = Path(args.output)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
                result = {"packet_hash": value["packet_hash"], "file": str(path.resolve()), "coverage": value["coverage"]}
            elif args.command == "ai-import":
                result = import_draft(store, read_json(args.file), model=args.model, output=args.output)
            elif args.command == "ai-openai":
                result = generate_openai(store, args.packet_hash, api_key=os.environ.get("OPENAI_API_KEY", ""),
                    model=args.model, output=args.output, pricing=read_json(args.pricing) if args.pricing else None)
            elif args.command == "collect-candles":
                with ResearchClient() as client:
                    result = collect_candles(store, client, args.instrument, start=args.start,
                                             end=args.end, max_pages=args.max_pages)
            elif args.command == "collect-sec":
                if not args.user_agent or "@" not in args.user_agent:
                    raise ValueError("Set SEC_USER_AGENT to an application name and contact email")
                with PublicClient(user_agent=args.user_agent) as client:
                    result = collect_sec(store, client, args.instrument)
            elif args.command == "collect-dart":
                key = os.environ.get("OPENDART_API_KEY", "")
                if not key:
                    raise ValueError("Set OPENDART_API_KEY in the process environment")
                with PublicClient(user_agent="toss-pilot-research/0.2.0") as client:
                    result = collect_dart(store, client, args.instrument, api_key=key,
                                          year=args.year, period_end=args.period_end)
            elif args.command == "report":
                result = generate(store, args.instrument, args.as_of or now(),
                                  read_json(args.assumptions) if args.assumptions else None, args.output)
            else:
                result = {"synthetic": True, "reports": [
                    generate(store, identity, "2026-10-11T00:00:00+00:00", None, args.output)
                    for identity in populate(store)]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, sqlite3.Error, CredentialsMissing, TossApiError) as exc:
        # Avoid provider messages/URLs that might include a query-string API key.
        print(f"Research operation failed ({type(exc).__name__}). "
              "Check inputs, credentials, provider availability and database run status.", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"Network operation failed ({type(exc).__name__}); no response details logged.", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
