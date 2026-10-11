# Numerical research guide

Milestones 1-3 provide a read-only research CLI and a local SQLite database.
No broker credentials are required for the synthetic demonstration.
Version 0.3.0 adds [milestone 4 evidence packets and AI drafts](MILESTONE4.md).

## Try it yourself

From a clean clone with Python 3.12+ and uv:

~~~powershell
uv sync --locked
uv run toss-research demo --output reports/demo
~~~

Open either generated HTML file in a browser. JSON files contain the full
reproducible report. Both companies and every observation are invented.
The demonstration database is isolated at reports/demo/demo.sqlite3.
The fixed analysis date is 2026-10-11, not the date the command is executed.

~~~powershell
uv run toss-research --db reports/demo/demo.sqlite3 status
~~~

The broker CLI remains available as toss-pilot. The research CLI has no order
commands and uses ResearchClient, which refuses all non-GET application requests.
OAuth token issuance is a separate authentication operation, not an order.

## Register real instruments

Create a private JSON file with market, symbol, currency, name and sector.
US records additionally need a reviewed SEC cik. KR records need an eight-digit
OpenDART corp_code; that is NOT the six-digit exchange symbol.

Example schema (replace every placeholder with reviewed values):

~~~json
{
  "market": "US",
  "symbol": "REPLACE",
  "currency": "USD",
  "name": "Reviewed issuer name",
  "sector": "industrials",
  "cik": "REPLACE_WITH_CIK"
}
~~~

Use market KR, a six-digit symbol, currency KRW, and corp_code instead of cik
for a Korean issuer. Unsupported/specialized sectors should remain unknown
until reviewed. Do not mark a real instrument synthetic.

~~~powershell
uv run toss-research register --file my-stock.json
~~~

Instrument identity is immutable through this command. Registering a different
issuer under an existing identity fails instead of overwriting history.
Ticker reuse and corporate reorganizations need a future dated identity migration.

## Collect official source data

Toss requires credentials in the gitignored .env or process environment and an
allowlisted IP. A token request can invalidate a token in another process;
use one broker worker. This delivery did not issue a token or call a live account.

~~~powershell
uv run toss-research collect-candles US:REPLACE --start 2020-01-01T00:00:00+00:00 --end 2026-10-10T23:59:59+00:00
~~~

The collector requests adjusted daily candles, at most 200 per page under the
vendored contract. It deduplicates inclusive boundaries in the observation view,
keeps raw pages, and fails on a stuck cursor. A page-budget stop is incomplete,
with next_before in the result. Resume the same window with --end set to that
cursor. Re-collecting a window preserves revisions and does not duplicate an
identical source snapshot. Completed pagination does not prove complete exchange
history or absence of missing sessions. Do not include an unfinished session.

SEC_USER_AGENT must contain an application name and your real contact email.
Set it privately in the process environment or ignored .env. SEC reads do not use the Toss key.

~~~powershell
uv run toss-research collect-sec US:REPLACE
~~~

For Korea, set OPENDART_API_KEY privately in the process environment or ignored .env. This key is
never passed on the command line, and request URLs containing the key are not
written to the database or error output.

~~~powershell
uv run toss-research collect-dart KR:000000 --year 2025 --period-end 2025-12-31
~~~

Replace the instrument IDs with those actually registered. The initial DART
adapter supports December-year-end annual consolidated statements only.
It resolves receipt dates from the paginated filing index. Only known taxonomy
IDs are normalized. Missing receipt dates, ambiguous accounts and unavailable
fields remain explicit. It does not guess from account names or mix standalone
and consolidated data.

SEC normalizes annual 10-K/20-F facts and their amendments, including supported
US-GAAP/IFRS aliases. Quarter/YTD data are not converted into annual data.
Custom taxonomy facts may remain unavailable. Financial numbers preserve decimal
precision; aliases with conflicting values are withheld.

Source adapters are tested with mocked official response shapes. Live entitlements,
historical depth, actual issuer taxonomy coverage, and upstream availability are
not validated in this delivery.

## Record a per-share review

Prices and EPS must describe the same stock/share class and split basis.
Until this is checked, reports withhold valuation. Record the evidence and date:

~~~powershell
uv run toss-research review-basis US:REPLACE --sector industrials --verified-through 2026-10-11 --note "Describe the filing and corporate-action records checked"
~~~

This is an explicit human attestation, not an automated split check.
Future dates are refused. Reviews are versioned; a later review does not change
earlier reports. The verification must cover the report's analysis date.
Financials, bank, insurance, REIT, biotech and unknown sectors receive no generic
P/E valuation. Other supported sector classifications use the same transparent
baseline; this is not a comprehensive sector model.

## Generate a report

~~~powershell
uv run toss-research report US:REPLACE --output reports
uv run toss-research report KR:000000 --assumptions config/research.json --output reports
~~~

The default cutoff is now in UTC; --as-of accepts an explicit timezone-aware ISO
timestamp. Both filing availability and first collection time must precede it.
Date-only SEC publication becomes available at 05:00 UTC the next day, covering
the complete Eastern calendar day even in winter. DART dates become available
at the next UTC midnight. These are conservative approximations, not exact
release timestamps.
Downloading today's Company Facts cannot retroactively create an archived
point-in-time dataset.

Report filenames include a content hash. Identical inputs, cutoff, instrument
review and assumptions reproduce the same JSON content ID. SQLite stores reports
and input/config hashes; separate runs record operational success/failure.
A successful report may deliberately say insufficient_data.

## Calculations and interpretation

- Net margin = annual net income / annual revenue.
- Operating margin = annual operating income / annual revenue.
- Liabilities/equity uses total liabilities, not interest-bearing debt.
- Cash conversion = operating cash flow / positive net income.
- Free-cash-flow proxy = operating cash flow minus nonnegative reported PP&E
  capex. Acquisitions, intangibles and net borrowing are not reconstructed.
- Trailing P/E = last adjusted price / positive diluted annual EPS, after the
  dated per-share review.
- Valuation proxy = EPS * (1 + assumed EPS growth)^years * assumed terminal P/E /
  (1 + assumed discount rate)^years. It excludes dividends and is not a DCF,
  consensus target or intrinsic-value estimate.
- Entry-review threshold = base proxy * (1 - configured margin). Scenarios
  are assumptions, not calibrated probabilities.
- Price setup: observe a pullback within one ATR of SMA20 while price and SMA20
  exceed SMA60. Invalidation reference = SMA20 minus configured ATR multiple.
  This is an unvalidated rule illustration. No fills or orders are simulated.
- ATR14 is the simple mean of the last 14 true ranges, not Wilder smoothing.
- Volatility is sample standard deviation of up to 63 daily simple returns,
  annualized by sqrt(252), with at least 20 returns.
- Drawdown = close / running peak - 1. Maximum is the worst observed value.
  Longest underwater observations includes any still-unrecovered episode; it
  is not a guaranteed recovery time or an exchange-day calendar calculation.
- Returns and SMAs refer to observation counts. Splits, dividends, index/sector
  comparisons and currency risk need richer validated data in later milestones.

Default checks require 63 bars, price age <=7 calendar days, annual period age
<=550 days, positive compatible EPS and required quality facts. Gaps over 10
calendar days and multiple UTC-day bars flag the series for review. A market
calendar, benchmark-relative strength, full debt schedules, peer multiples,
portfolio stress and analyst-estimate integrations remain later work.

## Local database

Default: data/research.sqlite3 in an editable checkout. An installed wheel uses
the per-user toss-pilot state directory (LOCALAPPDATA on Windows, otherwise
XDG_STATE_HOME or ~/.local/state). Override with --db before the subcommand.

Tables: instruments, instrument_reviews, snapshots, candles, facts, runs, reports.
The schema version is stored in PRAGMA user_version. WAL and foreign keys are
enabled. Keep the database on a local disk, not a shared/cloud-synced live file.
Backups should use SQLite's backup API; automated backup/restore tests are M6.

Raw source payloads use canonical JSON; decimal tokens are preserved as strings.
Snapshots are content-addressed. first_seen never moves; last_seen can advance
when identical data are retrieved. Observation revisions reference source IDs.
The current view selects the latest eligible revision. Cross-provider adjustment
basis reconciliation is not automatic; do not mix price vendors in one
instrument's daily series without review.

## Import schema

The import command accepts a local JSON object with instrument_id, source, kind,
payload, fetched_at, locator, and optional normalized candles/facts lists.
The instrument must already be registered. See demo.py and test_research.py for
complete normalized examples. This is a trusted local import interface; it
does not independently verify an external file's claimed provenance.

## Verification

~~~powershell
uv run pytest -q --basetemp .pytest_cache/local-check --junitxml=docs/evidence/offline-tests.xml
uv build --wheel
uv run python scripts/wheel_smoke.py
~~~

The wheel smoke uses a fresh isolated environment, installs runtime dependencies
exported from the lock and the wheel itself, checks packaged config from another
directory, and runs both help and the synthetic demo. CI additionally resolves
the pinned dependency lock on Linux and Windows. CI is configured, not yet
observed running remotely.

Run scripts/audit_contract.py to retry public REST/AsyncAPI downloads.
It retains fetched contracts by hash and records failure without replacing the
vendored spec. The current audit could not fetch either public contract.
