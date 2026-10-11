# Research system delivery plan

Updated: 2026-10-11. Scope authorized: implement milestones 1-4, attempt read-only live validation, and plan the later stages.
Markets: KR and US. Horizons: 2-12 weeks and 6-24 months. Analysis, not automated trading.

## Milestone 1: dependable client and reproducible verification

- M1.1 Reject ambiguous/noncanonical URLs before authentication; gate every mutation; add a read-only research client. Regress the observed bypasses.
- M1.2 Make installed-wheel configuration work outside the checkout. Keep credential/token files outside tracked artifacts.
- M1.3 Check public upstream REST/streaming contracts and record retrieval/hash evidence without silently replacing the vendored contract.
- M1.4 Add offline CI, wheel smoke verification, and a machine-readable test artifact. Refresh stale handoffs.
- Acceptance: offline tests pass; malformed paths cannot reach the transport; research rejects mutations even with opt-ins; wheel CLI works from another directory.

## Milestone 2: timestamped data and run tracking

- M2.1 Create a versioned SQLite store for explicit instrument identities, immutable source snapshots, observation revisions, and run/report history.
- M2.2 Collect daily Toss candles with inclusive-cursor deduplication, bounded pagination, validation, and resumable date windows.
- M2.3 Add SEC Company Facts/submissions and OpenDART annual consolidated-statement adapters. Preserve raw responses and source identifiers; normalize only supported unambiguous facts.
- M2.4 Separate financial period, publication/availability date, and retrieval time. Exclude future filings and revisions from historical views. Keep missing data explicit.
- M2.5 Add instrument registration, collection, import, and store-inspection CLI commands plus deterministic offline KR/US fixtures.
- Acceptance: duplicate imports do not multiply observations; amended filings survive; incomplete collections are marked; malformed/mixed-currency data fail; offline end-to-end fixtures cover both markets.

## Milestone 3: numerical stock reports

- M3.1 Compute documented profitability, cash-flow, leverage, and valuation ratios from compatible annual facts. Specialized financial sectors receive explicit unsupported valuation status.
- M3.2 Compute daily trend, volatility, ATR, historical drawdown and recovery, with minimum-history/freshness checks.
- M3.3 Generate transparent bear/base/bull earnings-multiple scenarios and conditional entry/invalidation reference levels. Assumptions are configuration, not predictions. Full equity-cash-flow DCF is deferred because annual CFO/PP&E capex alone does not establish cash available to equity holders.
- M3.4 Produce reproducible JSON and escaped self-contained HTML with source references, data-quality findings, both horizons, a price chart, and a drawdown chart.
- M3.5 Record input/config hashes and run status in SQLite. Demonstrate synthetic KR/US examples, visibly labeled as non-investment data.
- Acceptance: hand-calculated numerical tests pass; unavailable/ambiguous inputs cannot become confident recommendations; repeated identical snapshots reproduce results; outputs render correctly.

## Milestone 4: grounded AI research

- M4.1 Add immutable dated documents, retained original HTML and SHA-256, bounded official-source collection, and explicit imports for other filings/news. Migrate existing SQLite records without loss.
- M4.2 Export a frozen evidence packet with publication/retrieval cutoffs, stale-source exclusion, context limits, computed metrics, quality gates, prompt/schema versions, and content hash.
- M4.3 Support Codex-assisted packet-to-draft import without a separately billed model API. Add an explicit optional Responses API command; never call it implicitly.
- M4.4 Require source-linked thesis/counterarguments for both horizons; allow monitoring hypotheses. Reject unknown citations, nonmatching excerpts, literal numeric claims, invented metric references, and overridden abstention gates. Keep calculations in the numerical engine.
- M4.5 Persist drafts and generation metadata, model identity availability, token usage/cost availability, errors and report IDs. Render human-review status and source links in JSON/HTML.
- M4.6 Evaluate rejection/abstention with offline cases; run real Apple/Samsung issuer disclosures through collection, packet export, Codex-assisted drafting, validation, and reporting.
- Acceptance: provenance/structure/number checks pass; lack of evidence cannot produce an actionable stance; real-source examples remain explicit about missing market/fundamental inputs. Citation membership and matching excerpts do **not** establish semantic entailment; human review remains pending. Model quality/return prediction evaluation belongs to M5.

## Later milestones

5. Strategy evaluation: walk-forward rules, point-in-time universes, corporate actions, costs/slippage/FX, benchmark comparison, and prospective paper decisions. Evaluate numerical-only versus AI-assisted results. Short pilots cannot validate 6-24 month returns.
6. Automation and operations: exchange-aware collection schedules, singleton broker worker, retries, idempotent jobs, backups/restores, health alerts, and report publication outbox. No live trading. Gate: duplicate triggers and restarts do not duplicate outputs; outages are visible.
7. Notion publishing and dashboard: publish compact per-stock/per-run summaries, evidence links, review notes, and watchlist changes. SQLite remains authoritative for raw facts/candles/run history. Gate: idempotent page upserts, retry/rate-limit handling, explicit destination and credential configuration.
8. Scale only on evidence: PostgreSQL for concurrent writers/remote services; Parquet/DuckDB for large analytical scans. Reassess streaming and intraday analysis after the daily workflow is reliable.

## Delivery status

| Tasks | Status and evidence |
| --- | --- |
| M1.1-M1.2 | Implemented; offline guard tests and installed-wheel smoke |
| M1.3 | Audit implemented and attempted; upstream REST/AsyncAPI download unavailable, so spec freshness remains unverified |
| M1.4 | Offline CI configured; local test evidence recorded; hosted CI has not run |
| M2.1-M2.5 | Implemented and verified with synthetic/mocked data; Toss live smoke timed out before authentication completed; SEC/DART settings missing |
| M3.1-M3.5 | Implemented; numerical, abstention and reproducibility tests; browser-checked synthetic reports |
| M4.1-M4.6 | Implemented; 120 offline tests, installed-wheel smoke and real issuer-disclosure reports. Codex-assisted drafts validated; paid API transport only mocked; semantic/human review pending |
| M5-M8 | Planned, not implemented or scheduled |

- [Commands, formulas and exact limits](RESEARCH_GUIDE.md)
- [Storage alternatives, automation mediators and Notion design](AUTOMATION_AND_STORAGE.md)
- [Delivery report](DELIVERY.md)
- [Milestone 4 delivery and live results](MILESTONE4.md)
- [Machine-readable verification](evidence/verification.json)
