# AI handoff

Human state: docs/PROJECT_STATE.md. Plan: docs/ROADMAP.md.
Follow current session instructions; do not assume another application's global
instructions are loaded.

## Invariants

- Never execute a live order. ResearchClient is GET-only. The broker client
  rejects noncanonical paths before auth and requires both explicit flag and
  process-env opt-in for all non-GET application calls.
- Never print keys/tokens or store query-string credentials in provenance.
  The .env allowlist accepts Toss credentials, SEC_USER_AGENT, OPENDART_API_KEY,
  OPENAI_API_KEY and OPENAI_MODEL; live-order opt-in remains process-only.
- Use one broker worker: token issuance can invalidate another process's token.
- API monetary/quantity values remain decimal strings. Risk calculations may
  use floats internally; they are never resent as order values.
- Synthetic fixtures/reports are explicitly labeled and isolated from real data.
- No score or scenario is a validated investment recommendation.
- Preserve raw snapshots and amendment history. Missing values are not zeros.
- Do not publish account details or raw research data to Notion implicitly.
- Default to packet export and Codex-assisted draft import. The owner has no
  separate AI API credentials/credits; never silently activate paid API calls.
- Claims need sources and both-horizon gates. Validation does not prove semantic
  entailment; human review remains pending. Never fabricate model usage or costs.

## Code map

- src/toss_pilot: original auth/client/market/account/order/CLI.
- research/store.py: SQLite schema version 2; additive migration from version 1.
- research/providers.py: official-source adapters and conservative normalization.
- research/analysis.py: annual ratios, daily technicals, P/E scenarios, quality gates.
- research/report.py: escaped, self-contained HTML and JSON.
- research/evidence.py: bounded official HTML collection, dated source imports,
  retained original HTML/hash, explicit publication metadata.
- research/ai.py: frozen packets, strict draft checks, optional Responses transport,
  usage/cost provenance and safe report assembly. No tools or trading exposed.
- research/demo.py: invented data; fixed 2026-10-11 report cutoff.
- research/cli.py: register, review-basis, import, status, collect-candles,
  collect-sec, collect-dart, report, demo, collect-document, document-import,
  research-packet, ai-import and explicit optional ai-openai.
- config/research.json: reviewable assumptions, bundled in the wheel.
- scripts/audit_contract.py: public contract fetch/hash/drift evidence.
- scripts/wheel_smoke.py: wheel installation and demo from another directory.
- scripts/validate_live.py: serial broker/public API validation with a second
  request allowlist; scripts/collect_research_examples.py: three fixed disclosures.

## Data and time

Default editable state is the repository root; wheels use a per-user application
directory. --db overrides the SQLite path. data/, reports/, token cache and all
SQLite files are ignored. docs/examples holds synthetic reports;
docs/examples/live holds real-source reports that explicitly withhold price/valuation outputs.

Timestamps normalize to UTC. Date-only filing availability is the following
05:00 UTC for SEC or UTC midnight for DART. Eligibility also requires first_seen <= as_of.
Daily candle gaps use a calendar-day heuristic, not an exchange calendar.
Per-share verification is a dated human review; no automatic split engine exists.
Initial DART normalization: annual consolidated December-year-end only.

## Verification

uv sync --locked
uv run pytest -q --basetemp .pytest_cache/unique-check --junitxml=docs/evidence/milestone4-tests.xml
uv build --wheel
uv run python scripts/wheel_smoke.py

Use a fresh pytest basetemp name in this Windows sandbox. Tests prohibit real
httpx HTTPTransport access. Public network fetches can fail in this environment.
Windows CLI launcher installation required unsandboxed execution in this session.
Use a writable UV_CACHE_DIR for local builds when sandbox caches fail.

Read docs/evidence/milestone4-verification.json and docs/MILESTONE4.md for final
results. Toss timed out at OAuth connection; SEC/DART settings were absent.
Official Apple/Samsung HTML collection succeeded. Do not claim hosted CI ran,
the full upstream contract is current, or authenticated broker reads succeeded.
The old no-push-API assertion is superseded by current official WebSocket docs.

## Remaining work

See M5-M8 in ROADMAP and AUTOMATION_AND_STORAGE. Notion is a planned compact
review/publishing surface, SQLite the current authoritative store. No schedule
or external publishing integration exists yet. Multi-agent debate, ML frameworks
and trading automation are not part of this delivery.
