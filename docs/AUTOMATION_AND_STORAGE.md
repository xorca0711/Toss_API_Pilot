# Storage, automation and Notion plan

Decision proposed on 2026-10-11: SQLite is the local authoritative store;
Notion is the personal review surface. Implementation here stops at milestone 3.
No external database, automation schedule or Notion publication has been created.

## Where each kind of information belongs

| Information | Authoritative home | Notion representation |
| --- | --- | --- |
| Price bars and raw API payloads | SQLite initially; Parquet archive later | Latest date, freshness and a compact chart/link |
| Financial facts and restatements | SQLite with filing/snapshot IDs | Selected ratios and source filing links |
| Full JSON/HTML reports | Local report files and report ledger | Short summary and accessible artifact link |
| Runs, retries, hashes and failures | SQLite runs; later orchestration history | Only actionable status or latest successful run |
| Watchlist, thesis notes and personal review | Notion, with explicit sync direction | Editable human fields preserved during publication |
| Credentials and private account details | Local secret/environment storage | Never published |

A daily 20-stock, ten-year OHLCV dataset is about 20 * 252 * 10 = 50,400
observations before revisions. This is an illustrative row count, not a measured
storage estimate. Minute bars, news and model traces grow much faster. Notion
does not need a row for every observation or unchanged daily report.

## Storage alternatives

| Option | Appropriate role | Adoption trigger / tradeoff |
| --- | --- | --- |
| SQLite (implemented) | Local observations, provenance and run ledger | Simple single-machine operation; one writer at a time |
| Notion (planned) | Watchlist, concise reports, decisions and manual notes | Excellent personal interface; publish selected content, not raw time-series storage |
| PostgreSQL, self-hosted or managed | Shared transactional database | Multiple workers/users, remote services, access control and operational requirements |
| DuckDB + Parquet | Historical analytical scans and larger research datasets | Add when measured scan time/volume justifies a separate analytical layer |
| Private object storage | Large report/raw-document archives | Needed for durable remotely accessible report links; decide hosting/privacy first |

SQLite's own guidance distinguishes local application storage from concurrent
client/server workloads: https://www.sqlite.org/whentouse.html
PostgreSQL overview: https://www.postgresql.org/about/
DuckDB Parquet documentation: https://duckdb.org/docs/stable/data/parquet/overview

Do not choose a managed service based on an assumed free allowance. Pricing,
region, backup and private networking should be evaluated when deployment is
actually selected. Notion remains useful even if PostgreSQL is adopted later.

## Workflow mediators

| Mediator | Recommended role | Limit |
| --- | --- | --- |
| Windows Task Scheduler | First local daily runner on the allowlisted machine | Machine must be awake; application must implement job lock/retry/state |
| n8n (self-hosted or hosted) | Visual orchestration and Notion publication, failure routes | Broker reads should remain on the known local worker; do not expose an unauthenticated webhook |
| Prefect | Python-native deployments, run tracking and schedules | More infrastructure; useful when backfills, dependencies and retries become complex |
| GitHub Actions | Offline tests, packaging and public-data checks | Poor default for broker reads tied to an allowlisted IP; do not put broker secrets in pull-request jobs |

Sources:
- Task Scheduler: https://learn.microsoft.com/en-us/windows/win32/taskschd/task-scheduler-start-page
- n8n Notion node: https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.notion/
- Prefect deployments: https://docs.prefect.io/v3/concepts/deployments

Start with Task Scheduler and the CLI. Add n8n when Notion publishing is built.
Do not simultaneously introduce n8n and Prefect unless operational needs justify
both. The connector available in this chat can help set up Notion, but a durable
scheduled worker needs its own authorized integration and destination settings.

## Milestone 6: automation work packages

1. Define a reviewed watchlist/config; validate IDs and the daily market calendar.
2. Add a job runner with one broker-worker lock, explicit timezone (Asia/Seoul),
   a market/session completion check, and bounded retry/backoff.
3. Assign job keys by instrument, data window, provider and configuration hash.
   Repeated triggers resume unfinished work and do not repeat successful writes.
4. Refresh candles after completed KR and US sessions; update fundamentals when
   new filings are detected; regenerate changed reports only.
5. Implement a transactional publication outbox: pending, sending, confirmed,
   retryable_failure and permanent_failure. Database commit precedes publishing.
6. Add SQLite backup through its backup API; test restoring to a separate file
   and comparing report hashes. Define archive retention and disk-space alerts.
7. Notify only for missing/stale data, failed runs, changed thesis/setup, or needed
   human review. Keep routine unchanged runs quiet.
8. Run restart, duplicate-trigger, rate-limit, disk-full and provider-outage drills.
   Record outcomes before enabling unattended daily operation.

Schedules depend on the market calendar and US daylight-saving changes, not a
fixed assumption that the same Korea time always follows the US close.
No schedule has been installed by this task.

## Milestone 7: Notion integration work packages

1. Select the user's destination page/data source and establish least-needed
   integration access. Do not guess a destination or reuse broker credentials.
2. Create a Stocks data source with Symbol, Market, Currency, Sector, Latest
   Analysis, Data Quality, Short-Horizon Status, Long-Horizon Status and Report
   Link. Preserve user-owned Notes, Thesis and Review Status fields.
3. Create a linked Research Reviews data source for material changes, with
   instrument ID, as-of time, report hash, source references and human decision.
   Avoid appending unchanged daily copies.
4. Generate a compact publication payload from the report JSON: key figures,
   valuation assumptions, timing conditions, risk, missing evidence and links.
   Use the existing report hash for local idempotency and save the Notion page ID.
5. Publish through a queue. Before retrying an uncertain create/write, reconcile
   the saved page ID/hash to avoid duplicates. Handle remote edits and partial
   writes without overwriting human notes.
6. Upload/host full artifacts only in an explicitly chosen accessible location.
   A local X:/... path is not a usable remote Notion report link. A compact report
   can alternatively be embedded directly in the Notion page.
7. Test partial outage recovery, duplicate delivery, revoked permissions,
   oversized payloads and preservation of manual fields.

Notion's current docs describe plan-dependent request limits, shared workspace
limits, 429/529 retry handling, and payload limits of 1,000 block elements and
500 KB. They also note that a write returning 503 may already have committed.
These are practical reasons for summaries, batching and reconciliation:
https://developers.notion.com/reference/request-limits

The intended flow:

~~~mermaid
flowchart LR
    S[Task Scheduler or Prefect] --> W[Local read-only worker]
    W --> D[SQLite source and run ledger]
    D --> R[Numerical report and AI draft]
    R --> O[Publication outbox]
    O --> N[n8n or direct Notion adapter]
    N --> P[Notion watchlist and review pages]
    N --> E[Delivery confirmation or retry state]
    E --> D
~~~

## Later acceptance gates

M4 implementation and deterministic provenance/abstention checks are delivered in
[MILESTONE4.md](MILESTONE4.md). The original measurable-research-value gate below
remains open: source traceability is established, semantic correctness and added
investment research value are not. The pipeline diagram remains a proposed
automation architecture; no schedule or publisher has been installed.

- M4: evidence-grounded AI adds measurable research value; unsupported claims
  and numbers are rejected; token/cost logs support budgeting.
- M5: numerical-only and AI-assisted variants are compared with appropriate
  benchmarks, transaction costs, market regimes and forward paper observations.
  No conclusion about long-horizon profitability from a short trial.
- M6: unattended operation survives interruptions and restores from backup.
- M7: human notes survive sync, duplicated jobs do not duplicate pages, failures
  are visible, and only approved information leaves the local system.
- M8: migrate to PostgreSQL or add Parquet/DuckDB only after measuring a real
  constraint; retain source IDs and report hashes across the migration.
