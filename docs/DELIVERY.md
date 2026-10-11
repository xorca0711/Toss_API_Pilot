# Milestones 1-3 delivery

Historical milestone 1-3 baseline. The subsequent authorized live checks and
milestone 4 implementation are recorded in [MILESTONE4.md](MILESTONE4.md).
Its current results supersede the earlier "no live calls/no AI" boundaries below.

Date: 2026-10-11. Local branch: codex/research-milestones-1-3.
Implementation is complete for the bounded offline scope below. Live data
validation and an upstream contract refresh remain explicitly open.

## Delivered work and evidence

| Milestone | Deliverables | Verification / boundary |
| --- | --- | --- |
| 1: foundation | Canonical path validation before auth; every mutation gated; GET-only research client; wheel-bundled configs; atomic token-cache replacement; offline CI and public-contract audit script | Guard regressions and isolated wheel smoke pass. Public REST/AsyncAPI downloads failed; latest upstream contract not verified. |
| 2: data | Versioned SQLite schema; reviewed instrument IDs; content-addressed snapshots; candle and filing revisions; run ledger; dated per-share reviews; Toss pagination; SEC and OpenDART annual financial adapters | Mocked-response and synthetic ingestion tests pass. No live Toss or OpenDART request was made. |
| 3: numerical reports | Annual financial ratios; explicit earnings-multiple scenarios; daily trend, ATR, volatility, entry/invalidation references; historical drawdown/underwater duration; reproducible HTML and JSON | Hand-calculated and failure-case tests pass. Synthetic KR/US reports inspected in the browser. No strategy profitability or live investment suitability established. |

Final offline result: **85 tests passed**.
Evidence: [pytest XML](evidence/offline-tests.xml), [wheel smoke log](evidence/wheel-smoke.txt),
[verification manifest](evidence/verification.json), [contract audit](evidence/contracts/audit.json).

The wheel was built and installed with locked runtime dependencies into a fresh
isolated environment; configuration, CLI help and an offline demo ran from
outside the checkout. CI was configured but not run on GitHub during this task.

## Review the concrete outputs

- [Detailed task plan and acceptance criteria](ROADMAP.md)
- [Commands, data contracts, formulas and limitations](RESEARCH_GUIDE.md)
- [Synthetic Korean-stock report](examples/KR-000001-82410e0de978.html)
- [Synthetic US-stock report](examples/US-DEMO-a24aed1a5709.html)
- [Korean example JSON](examples/KR-000001-82410e0de978.json)
- [US example JSON](examples/US-DEMO-a24aed1a5709.json)
- [Storage, automation and Notion plan](AUTOMATION_AND_STORAGE.md)

~~~powershell
uv sync --locked
uv run toss-research demo --output reports/demo
~~~

No credentials are needed for this command. Both examples contain invented data.

## Deliberate scope decisions

- Uses only the existing httpx dependency plus Python's standard library.
  SQLite and report generation do not introduce compiled analytics dependencies.
- Valuation is an explicit discounted earnings-multiple proxy, not a DCF.
  A defensible equity-cash-flow model needs more information than the initial
  annual cash-flow fields provide.
- Bank/insurance/REIT/biotech/unknown sectors are withheld from generic valuation.
  A dated per-share review is required; there is no automatic split reconciliation.
- Initial DART support is annual consolidated statements for December-year-end
  issuers. Missing/custom/ambiguous taxonomy facts are not guessed.
- Historical eligibility includes first collection time. Present-day downloads
  cannot masquerade as an archived point-in-time dataset.
- Timing rules are descriptive hypotheses. They have no measured strategy edge,
  transaction-cost model or paper-trading results yet.
- Source coverage does not include peers, consensus estimates, exchange-calendar
  completeness, portfolio risk/FX or AI research. Those remain later milestones.

## What needs live verification

1. Public REST and streaming contract retrieval/drift review.
2. User-authorized read-only Toss smoke with allowlisted IP and verified symbols.
3. SEC/DART issuer mapping and taxonomy coverage on representative real issuers.
4. Candle adjustment semantics, retention depth and quote delay.
5. Windows and Linux hosted CI results after a future push.

## Further milestones

M4: source-grounded AI research, counterarguments and evidence validation.
M5: walk-forward comparisons and prospective paper decisions.
M6: unattended collection/reporting, singleton worker, retries, backup/restore,
run health and publication outbox.
M7: Notion watchlist/review pages, compact summaries and idempotent publishing.
M8: scale storage and intraday support when measured requirements justify it.

**Recommended storage/automation:** SQLite now; Task Scheduler for the first
local runner; optional n8n for Notion publication. Keep raw facts and candles
local. Use Notion for review notes, meaningful report changes and concise
summaries. PostgreSQL and DuckDB/Parquet are later alternatives, not required
installations for the current personal workflow.

No external pages, recurring schedules, broker orders, commits, pushes or PRs
were created. Changes remain local for review.
