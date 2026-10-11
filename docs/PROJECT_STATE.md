# Project state

Update this before stopping work, every session.

Updated: 2026-10-11. Branch: codex/research-milestones-1-3.

Publication update: the owner explicitly authorized committing, pushing this
branch and opening a GitHub PR for milestones 1-4. The branch was fast-forwarded
to origin/main's existing merge commit; its file tree was unchanged. The
implementation matched the recorded 120-test and wheel evidence before final
terminal-blank-line cleanup. That cleanup preserves every Python AST; see
docs/evidence/publication-verification.json for before/after hashes.
Publication authorization does not imply merge approval or validation of live
broker behavior. GitHub carries the current PR/check status.

## Current delivery

Milestones 1-4 are implemented. Numerical/provider foundations are verified offline;
M4 also has real issuer-disclosure collection and two Codex-assisted reports.
See [MILESTONE4](MILESTONE4.md) for the latest delivery and [ROADMAP](ROADMAP.md)
for task IDs, [RESEARCH_GUIDE](RESEARCH_GUIDE.md) for commands and formulas,
and [AUTOMATION_AND_STORAGE](AUTOMATION_AND_STORAGE.md) for the later workflow.

- 0.3.0 adds dated evidence, frozen research packets, checked AI drafts and an optional paid API adapter to toss-research.
- The raw-path order-guard bypass found in this chat is fixed by accepting only
  canonical application paths before auth and gating every non-GET mutation.
- ResearchClient refuses mutations regardless of live opt-ins.
- SQLite preserves source snapshots, daily candle revisions, annual financial
  facts, dated human basis reviews, runs and report content. Schema 2 also retains
  documents, packets and AI drafts, with a tested migration from schema 1.
- Official-source adapters: Toss daily pagination, SEC Company Facts/submissions,
  OpenDART annual consolidated statements plus filing-date index.
- Deterministic JSON/HTML reports cover two horizons, basic annual financial
  ratios, explicit P/E scenarios, trend/ATR/volatility, price drawdown and
  underwater duration. Synthetic KR/US artifacts are in docs/examples.
- Current offline pytest results: 120 passed in docs/evidence/milestone4-tests.xml.
  A fresh-environment wheel smoke passes outside the checkout; exact final
  verification is recorded in docs/evidence/milestone4-verification.json.
  docs/evidence/verification.json retains the earlier M1-3 baseline.
- Local browser inspection confirms readable reports, visible synthetic labels,
  separate horizon panels, charts, scenarios and source tables.
- CI is configured for Linux and Windows, but no hosted run has been observed.
- Authorized Toss authentication was attempted but the connection timed out
  before a response. No token, account data, candle data or order resulted.
  Three official Apple/Samsung disclosures were fetched successfully, retained
  locally and used in two real-stock AI reports in docs/examples/live.
  No Notion publishing or schedule creation was performed. The original local-only
  delivery is now followed by the separately authorized GitHub publication above.

## Explicit validation boundaries

- Public REST and AsyncAPI downloads failed with connection timeout/error,
  including an unsandboxed attempt. docs/evidence/contracts/audit.json records
  the result. Vendored v1.2.14 remains the offline contract; freshness is not claimed.
- Current official documentation describes WebSockets. The old "no push API"
  statement is superseded; a streaming client is not implemented.
- Broker/SEC/DART adapters passed mocked response tests, not a successful credentialed live smoke.
  Quote delay, candle depth and real-world financial taxonomy coverage are unknown.
- Annual financials only. The initial DART path is December year-end CFS only.
- Generic valuation is withheld for unsupported sectors and unverified per-share
  basis. Scenarios are assumed earnings multiples, not a full cash-flow DCF.
- M4 drafts were authored in this Codex session, then imported and validated.
  No separately billed model API call occurred. Model ID/usage/cost are explicitly
  unavailable for imported drafts. The optional API adapter is mock-tested only.
- Citation/excerpt/schema checks do not prove semantic entailment. Human review
  remains pending; both real-stock reports withhold price and valuation conclusions.
- The original measurable-research-value acceptance gate remains open; current
  evidence establishes implementation and traceability, not that broader outcome.
- SEC contact User-Agent and OpenDART key remain unconfigured. The owner reported
  not having separate AI credits; keep the Codex-assisted path as the default.
- No comprehensive news feed, peer/consensus dataset, benchmark-relative strength,
  backtest, portfolio-risk engine or validated investment edge exists.
- Source snapshots collected today cannot establish a historical knowledge state.
- Broker token cache remains single-worker; do not run concurrent issuers.

## Next work

1. Restore Toss connectivity, then rerun scripts/validate_live.py. Check local
   network and WTS IP settings, but do not call a timeout an observed IP rejection.
   Configure SEC contact User-Agent/OpenDART registration separately if wanted.
2. Retry the public contract audit and review any drift before changing the spec.
3. Broaden tested issuer/sector coverage and implement exchange calendars and
   corporate-action reconciliation.
4. M5 strategy evaluation, M6 automation/backups/outbox, M7 Notion
   summaries and review workflow. Keep raw time-series data in the database.
5. Choose a Notion destination and report hosting approach before publishing.
   A local HTML path will not work as a remote Notion artifact URL.

## Historical context

The August 17 pilot comprised 48 offline tests and had no logged live validation.
Its pre-commit independent correctness review was incomplete. This delivery
adds deterministic regression and numerical tests but is not an independent
external financial audit. The old one-time August continuation reminder is
historical; its current scheduler state has not been inspected or changed.
