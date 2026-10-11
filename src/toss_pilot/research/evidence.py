"""Dated documentary evidence, separate from normalized annual financial facts."""
from __future__ import annotations

import re
import hashlib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .store import Store, canonical, digest, instant, now

# Fetching credentials, local services, arbitrary redirects or user-selected
# hosts is intentionally outside this collector. Other sources can be imported.
OFFICIAL_HOSTS = {"www.apple.com", "www.samsung.com", "news.samsung.com",
                  "www.sec.gov", "data.sec.gov", "dart.fss.or.kr"}
KINDS = {"filing", "issuer_release", "news"}


def source_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.fragment or parsed.port not in (None, 443)
            or re.search(r"(?i)(key|token|secret|password|auth)=", parsed.query)):
        raise ValueError("Evidence needs a credential-free HTTPS source URL")
    return value


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def ingest_document(store: Store, item: dict) -> str:
    required = {"instrument_id", "source_url", "title", "kind", "published_at", "fetched_at", "text", "extraction"}
    if set(item) != required:
        raise ValueError("Document keys must match the documented schema")
    store.instrument(item["instrument_id"])
    source_url(item["source_url"])
    if item["kind"] not in KINDS or item["extraction"] not in {"source_text", "curated_summary"}:
        raise ValueError("Unsupported document kind or extraction")
    if not isinstance(item["text"], str) or not 20 <= len(item["text"]) <= 80000:
        raise ValueError("Document text must be 20-80000 characters")
    if not isinstance(item["title"], str) or not 1 <= len(item["title"]) <= 250:
        raise ValueError("Invalid document title")
    body = dict(item)
    body["published_at"], body["fetched_at"] = instant(item["published_at"]), instant(item["fetched_at"])
    if body["published_at"] > body["fetched_at"] or body["fetched_at"] > now():
        raise ValueError("Document publication/retrieval cannot be in the future")
    # Same source text keeps its original knowledge boundary on repeated imports.
    identity = digest({k: v for k, v in body.items() if k != "fetched_at"})
    with store.db:
        store.db.execute("INSERT OR IGNORE INTO documents VALUES(?,?,?,?,?)",
                         (identity, item["instrument_id"], body["published_at"], body["fetched_at"], canonical(body)))
    return identity


def collect_document(store: Store, *, identity: str, url: str, title: str,
                     published_at: str, kind: str = "issuer_release", start_text: str,
                     end_text: str, user_agent: str = "toss-pilot-research/0.3.0", transport=None) -> str:
    source_url(url)
    if urlsplit(url).hostname not in OFFICIAL_HOSTS:
        raise ValueError("Collector accepts only documented official hosts; use document-import for others")
    if urlsplit(url).hostname in {"www.sec.gov", "data.sec.gov"} and "@" not in user_agent:
        raise ValueError("SEC requires a configured contact User-Agent")
    if not start_text or not end_text:
        raise ValueError("Explicit article boundaries are required")
    run = store.start_run("document-collection", identity, {"source_url": url})
    try:
        with httpx.Client(timeout=20, transport=transport, follow_redirects=False) as client:
            with client.stream("GET", url, headers={"User-Agent": user_agent}) as response:
                if response.status_code != 200:
                    raise ValueError(f"Document provider HTTP {response.status_code}")
                if "text/html" not in response.headers.get("content-type", ""):
                    raise ValueError("Collector supports HTML only; import extracted PDF text separately")
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise ValueError("Document exceeds collection limit")
        parser = ArticleText()
        parser.feed(raw.decode("utf-8"))
        text = " ".join(parser.parts)
        start = text.find(start_text)
        end = text.find(end_text, start + len(start_text)) if start >= 0 else -1
        if start < 0 or end < 0:
            raise ValueError("Article boundaries were not found; no guessed extraction")
        identifier = ingest_document(store, {
            "instrument_id": identity, "source_url": url, "title": title, "kind": kind,
            "published_at": published_at, "fetched_at": now(), "text": text[start:end].strip(),
            "extraction": "source_text"})
        raw_hash = hashlib.sha256(raw).hexdigest()
        raw_path = store.path.parent / "raw-documents" / (raw_hash + ".html")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        if not raw_path.exists():
            raw_path.write_bytes(raw)
        store.finish_run(run, "succeeded", {"document_id": identifier, "raw_content_hash": raw_hash,
                                             "raw_file": str(raw_path.resolve()), "http_status": 200, "bytes": len(raw)})
        return identifier
    except Exception as exc:
        store.finish_run(run, "failed", {"error_type": type(exc).__name__})
        raise
