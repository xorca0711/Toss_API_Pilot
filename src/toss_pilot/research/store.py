"""SQLite research ledger. Raw payloads and observation revisions are retained."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def instant(value: str) -> str:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Timestamp requires an explicit timezone")
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def number(value: Any) -> str:
    if isinstance(value, (float, bool)) or value is None:
        raise ValueError("Numeric observations must be decimal strings or integers")
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal observation") from exc
    if not parsed.is_finite():
        raise ValueError("Numeric observations must be finite")
    return format(parsed, "f")


SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments(
 id TEXT PRIMARY KEY, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS instrument_reviews(
 id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL REFERENCES instruments(id),
 reviewed_at TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots(
 id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL REFERENCES instruments(id),
 source TEXT NOT NULL, kind TEXT NOT NULL, locator TEXT NOT NULL,
 first_seen TEXT NOT NULL, last_seen TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS candles(
 snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 instrument_id TEXT NOT NULL REFERENCES instruments(id), timestamp TEXT NOT NULL,
 adjusted INTEGER NOT NULL, body TEXT NOT NULL,
 PRIMARY KEY(snapshot_id,timestamp,adjusted));
CREATE INDEX IF NOT EXISTS candle_lookup ON candles(instrument_id,timestamp);
CREATE TABLE IF NOT EXISTS facts(
 snapshot_id TEXT NOT NULL REFERENCES snapshots(id),
 instrument_id TEXT NOT NULL REFERENCES instruments(id), metric TEXT NOT NULL,
 period_end TEXT NOT NULL, available_at TEXT NOT NULL, filing_id TEXT NOT NULL,
 body TEXT NOT NULL, PRIMARY KEY(snapshot_id,metric,period_end,filing_id));
CREATE INDEX IF NOT EXISTS fact_lookup ON facts(instrument_id,period_end,available_at);
CREATE TABLE IF NOT EXISTS runs(
 id TEXT PRIMARY KEY, kind TEXT NOT NULL, instrument_id TEXT,
 started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
 details TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS reports(
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
 instrument_id TEXT NOT NULL, as_of TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL REFERENCES instruments(id),
 published_at TEXT NOT NULL, first_seen TEXT NOT NULL, body TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS document_lookup ON documents(instrument_id,published_at,first_seen);
CREATE TABLE IF NOT EXISTS research_packets(
 id TEXT PRIMARY KEY, instrument_id TEXT NOT NULL REFERENCES instruments(id),
 as_of TEXT NOT NULL, body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_drafts(
 id TEXT PRIMARY KEY, packet_id TEXT NOT NULL REFERENCES research_packets(id),
 run_id TEXT NOT NULL REFERENCES runs(id), body TEXT NOT NULL);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        version = self.db.execute("PRAGMA user_version").fetchone()[0]
        if version not in (0, 1, 2):
            self.db.close()
            raise ValueError(f"Unsupported database schema {version}")
        self.db.executescript(SCHEMA)
        self.db.execute("PRAGMA user_version=2")
        self.db.commit()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def register(self, instrument: dict) -> str:
        item = dict(instrument)
        market, symbol = item["market"], item["symbol"]
        if market not in ("KR", "US") or not re.fullmatch(r"[A-Z0-9.-]{1,20}", symbol):
            raise ValueError("Expected KR/US and an explicit supported exchange symbol")
        if market == "KR" and not re.fullmatch(r"\d{6}", symbol):
            raise ValueError("KR symbols require six digits")
        if item["currency"] != {"KR": "KRW", "US": "USD"}[market]:
            raise ValueError("Instrument currency does not match the supported market")
        identity = f"{market}:{symbol}"
        item["id"] = identity
        item.setdefault("sector", "unknown")
        item.setdefault("name", symbol)
        existing = self.db.execute("SELECT body FROM instruments WHERE id=?", (identity,)).fetchone()
        if existing and json.loads(existing[0]) != item:
            raise ValueError("Instrument already registered differently; identity changes need review")
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO instruments VALUES(?,?)", (identity, canonical(item)))
        return identity

    def instrument(self, identity: str, as_of: str | None = None) -> dict:
        row = self.db.execute("SELECT body FROM instruments WHERE id=?", (identity,)).fetchone()
        if row is None:
            raise ValueError(f"Unknown instrument {identity}; register explicit provider IDs first")
        item = json.loads(row[0])
        review = self.db.execute(
            "SELECT body FROM instrument_reviews WHERE instrument_id=? AND reviewed_at<=? "
            "ORDER BY reviewed_at DESC,rowid DESC LIMIT 1", (identity, instant(as_of) if as_of else now())
        ).fetchone()
        if review:
            item.update(json.loads(review[0]))
        return item

    def review(self, identity: str, *, sector: str, verified_through: str, note: str,
               reviewed_at: str | None = None) -> str:
        self.instrument(identity)
        reviewed = instant(reviewed_at) if reviewed_at else now()
        date.fromisoformat(verified_through)
        if verified_through > reviewed[:10]:
            raise ValueError("Cannot attest to future corporate actions")
        if not sector.strip() or not note.strip():
            raise ValueError("Sector and a review-evidence note are required")
        body = {"sector": sector.lower(), "per_share_basis_verified": True,
                "per_share_basis_verified_through": verified_through,
                "review_note": note, "reviewed_at": reviewed}
        rid = digest({"instrument": identity, **body})
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO instrument_reviews VALUES(?,?,?,?)",
                            (rid, identity, reviewed, canonical(body)))
        return rid

    def ingest(self, identity: str, source: str, kind: str, payload: dict, *,
               fetched_at: str, locator: str, candles: list[dict] | None = None,
               facts: list[dict] | None = None) -> str:
        instrument = self.instrument(identity)
        fetched_at = instant(fetched_at)
        # Locators are provenance, not request URLs containing credentials.
        if "?" in locator or "@" in locator or not locator.startswith(("https://", "fixture:")):
            raise ValueError("Use a credential-free provenance locator without a query string")
        normalized_candles, normalized_facts = [], []
        candle_keys, fact_keys = {}, {}
        for original in candles or []:
            c = dict(original)
            c["timestamp"] = instant(c["timestamp"])
            if c["currency"] != instrument["currency"] or type(c["adjusted"]) is not bool:
                raise ValueError("Candle currency or adjustment basis mismatch")
            for key in ("open", "high", "low", "close", "volume"):
                c[key] = number(c[key])
            o, h, lo, close, volume = [Decimal(c[k]) for k in ("open", "high", "low", "close", "volume")]
            if min(o, h, lo, close) <= 0 or volume < 0 or not lo <= min(o, close) <= max(o, close) <= h:
                raise ValueError("Invalid OHLCV bounds")
            if c["timestamp"] > fetched_at:
                raise ValueError("Candle timestamp is after retrieval")
            key = (c["timestamp"], c["adjusted"])
            if key in candle_keys and candle_keys[key] != c:
                raise ValueError("Conflicting candles in one snapshot")
            candle_keys[key] = c
            normalized_candles.append(c)
        for original in facts or []:
            f = dict(original)
            f["value"] = number(f["value"])
            f["available_at"] = instant(f["available_at"])
            date.fromisoformat(f["period_end"])
            if f.get("period_start"):
                date.fromisoformat(f["period_start"])
                if f["period_start"] > f["period_end"]:
                    raise ValueError("Invalid financial period")
            if f["period_end"] > f["available_at"][:10]:
                raise ValueError("Financial period ends after publication")
            if f["available_at"] > fetched_at:
                raise ValueError("Filing is not yet public at retrieval")
            if f["unit"] not in (instrument["currency"], "shares", instrument["currency"] + "/shares"):
                raise ValueError("Financial fact currency mismatch")
            if f.get("basis") != "annual":
                raise ValueError("Milestone 3 normalizes annual facts only")
            expected_unit = instrument["currency"] + "/shares" if f["metric"] == "eps" else instrument["currency"]
            if f["unit"] != expected_unit:
                raise ValueError("Financial metric unit mismatch")
            key = (f["metric"], f["period_end"], f["filing_id"])
            if key in fact_keys and fact_keys[key] != f:
                raise ValueError("Conflicting facts in one snapshot")
            fact_keys[key] = f
            normalized_facts.append(f)
        sid = digest({"instrument": identity, "source": source, "kind": kind,
                      "locator": locator, "payload": payload})
        with self.db:
            self.db.execute(
                "INSERT INTO snapshots VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) "
                "DO UPDATE SET last_seen=MAX(last_seen,excluded.last_seen)",
                (sid, identity, source, kind, locator, fetched_at, fetched_at, canonical(payload)))
            for c in normalized_candles:
                self.db.execute("INSERT OR IGNORE INTO candles VALUES(?,?,?,?,?)",
                                (sid, identity, c["timestamp"], int(c["adjusted"]), canonical(c)))
            for f in normalized_facts:
                self.db.execute("INSERT OR IGNORE INTO facts VALUES(?,?,?,?,?,?,?)",
                                (sid, identity, f["metric"], f["period_end"], f["available_at"],
                                 f["filing_id"], canonical(f)))
        return sid

    def observations(self, identity: str, as_of: str) -> tuple[list[dict], list[dict]]:
        as_of = instant(as_of)
        # Conservative knowledge boundary: data first collected today cannot be
        # passed off as an archived point-in-time dataset for an earlier run.
        candles = self.db.execute(
            "SELECT c.body,c.snapshot_id,s.locator,s.first_seen FROM candles c JOIN snapshots s "
            "ON s.id=c.snapshot_id WHERE c.instrument_id=? AND c.timestamp<=? AND s.first_seen<=? "
            "AND c.adjusted=1 ORDER BY c.timestamp,s.first_seen,s.id", (identity, as_of, as_of)).fetchall()
        latest = {}
        for row in candles:
            body = json.loads(row["body"])
            body.update(snapshot_id=row["snapshot_id"], source_url=row["locator"])
            latest[body["timestamp"]] = body
        facts = self.db.execute(
            "SELECT f.body,f.snapshot_id,s.locator,s.first_seen FROM facts f JOIN snapshots s "
            "ON s.id=f.snapshot_id WHERE f.instrument_id=? AND f.available_at<=? AND s.first_seen<=? "
            "ORDER BY f.period_end,f.available_at,s.first_seen,s.id", (identity, as_of, as_of)).fetchall()
        selected = {}
        for row in facts:
            body = json.loads(row["body"])
            body.update(snapshot_id=row["snapshot_id"], source_url=body.get("source_url") or row["locator"])
            selected[(body["metric"], body["period_end"])] = body
        return list(latest.values()), list(selected.values())

    def start_run(self, kind: str, identity: str | None, details: dict) -> str:
        import uuid
        rid = uuid.uuid4().hex
        with self.db:
            self.db.execute("INSERT INTO runs VALUES(?,?,?,?,?,?,?)",
                            (rid, kind, identity, now(), None, "running", canonical(details)))
        return rid

    def finish_run(self, rid: str, status: str, details: dict) -> None:
        if status not in ("succeeded", "failed", "incomplete"):
            raise ValueError("Invalid final run status")
        with self.db:
            self.db.execute("UPDATE runs SET finished_at=?,status=?,details=? WHERE id=?",
                            (now(), status, canonical(details), rid))

    def save_report(self, rid: str, report: dict) -> str:
        report_id = digest(report)
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO reports VALUES(?,?,?,?,?)",
                            (report_id, rid, report["instrument"]["id"], report["as_of"], canonical(report)))
        return report_id

    def status(self) -> dict:
        counts = {name: self.db.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
                  for name in ("instruments", "instrument_reviews", "snapshots", "candles", "facts", "runs", "reports",
                               "documents", "research_packets", "ai_drafts")}
        counts["recent_runs"] = [dict(row) for row in self.db.execute(
            "SELECT id,kind,instrument_id,status FROM runs ORDER BY started_at DESC,rowid DESC LIMIT 10")]
        return counts
