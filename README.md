# Toss_API_Pilot

Pilot Python client for the Toss Securities Open API (openapi.tossinvest.com),
built read-first: market data and account reads are the product; order
placement exists only behind an explicit dry-run gate and is never exercised
by automation in this repository.

## Claims

| Claim | Status | Evidence |
| --- | --- | --- |
| Token manager caches and reuses the access token, re-issues on expiry, and maps OAuth error responses | Validated | docs/evidence/offline-tests.xml; tests/test_auth.py |
| Client unwraps the {result} envelope, maps the {error} envelope (requestId, code, data), retries 429 honoring Retry-After with a bounded retry count, and refreshes the token once on 401 expired-token | Validated | docs/evidence/offline-tests.xml; tests/test_client.py |
| Market and account calls build spec-exact parameter names and omit unset optionals; account calls carry X-Tossinvest-Account | Validated | docs/evidence/offline-tests.xml; tests/test_market.py; tests/test_client.py |
| Order bodies enforce spec v1.2.14 rules (quantity xor orderAmount, LIMIT/MARKET price rules, timeInForce constraints, clientOrderId format, no floats); dry-run returns the payload without network; live sends are refused without TOSS_PILOT_ALLOW_LIVE_ORDERS=yes; the transport itself additionally blocks any ungated non-GET to order endpoints; hostile order ids cannot be interpolated into paths; the live flag is not importable from .env | Retracted-superseded | docs/DELIVERY.md; the original raw-path transport-gate claim was false for alternate URL forms |
| Canonical paths are validated before auth; all non-GET application calls require both opt-ins; ResearchClient permits GET only | Validated | docs/evidence/offline-tests.xml; tests/test_guard_regression.py |
| Local SQLite snapshots, revisions, dated reviews and numerical KR/US reports work with synthetic/mocked data | Validated | docs/evidence/offline-tests.xml; docs/examples/ |
| Installed-wheel configuration, offline demo and M4 abstention work outside the checkout | Validated | docs/evidence/milestone4-wheel-smoke.txt; docs/evidence/milestone4-verification.json |
| Current upstream REST/AsyncAPI spec freshness | Not established | docs/evidence/contracts/audit.json |
| Dated evidence packets, checked AI draft imports and source-linked reports within the documented validation scope | Validated | docs/evidence/milestone4-tests.xml; docs/MILESTONE4.md; docs/examples/live/ |
| Official Apple/Samsung disclosure collection and real-source Codex-assisted reports | Validated | docs/evidence/live/disclosures.json; docs/evidence/live/research-results.json |
| Optional paid Responses API integration passes mock-transport checks; live behavior remains unverified | Validated | docs/evidence/milestone4-tests.xml; tests/test_ai_research.py |
| Investment performance, semantic correctness of every AI claim, unattended automation and Notion publishing | Not established | docs/PROJECT_STATE.md |
| Endpoint inventory (36 operations), per-group rate limits, single-active-token rule, IP allowlist, no-sandbox, 100M KRW confirm flag and 3B KRW order cap | Descriptive only | Official OpenAPI spec v1.2.14 vendored at spec/openapi-1.2.14.json; overview at openapi.tossinvest.com/openapi-docs/overview.md |
| Terms: automated trading permitted at own risk; market data personal-use only, redistribution banned; individuals 19+ only; commissions KRX 0.015% / NXT 0.014% / US 0.1% | Not established | DEVELOPMENT.md (historical terms research could not be reproduced; re-check current terms before relying) |
| Authenticated Toss API behavior, quote freshness, candle depth and account/order semantics | Not established | docs/evidence/live/validation.json: authorized connection attempt timed out before authentication completed; no account/order request attempted |
| The credential is a Toss Payments key | Retracted-superseded | Initial working assumption, superseded 2026-08-17 after owner confirmation that the credential is a Toss Securities Open API client (see DEVELOPMENT.md) |

## If you want... -> Read

| If you want... | Read |
| --- | --- |
| Run numerical reports and understand the formulas | [Research guide](docs/RESEARCH_GUIDE.md) |
| See tasks and milestone acceptance criteria | [Roadmap](docs/ROADMAP.md) |
| Review what was delivered and verified | [Delivery report](docs/DELIVERY.md) |
| Use grounded AI without separate API credits; see real-stock examples | [Milestone 4 guide and results](docs/MILESTONE4.md) |
| Plan Notion, database choices and automation | [Storage and automation](docs/AUTOMATION_AND_STORAGE.md) |
| Continue implementation | [Project state](docs/PROJECT_STATE.md), [Agent handoff](docs/AI_HANDOFF.md) |

## Try it yourself

No credentials or market data required:

~~~powershell
uv sync --locked
uv run toss-research demo --output reports/demo
~~~

Open the generated HTML files. Both examples contain invented data and explicit
synthetic labels. Version 0.2.0 added annual financial ratios, assumed valuation
ranges, daily technicals and drawdown charts; it does not establish a strategy's
profitability. JSON, SQLite run history and content hashes support reproduction.

Version 0.3.0 adds dated documentary evidence and AI drafts. The default workflow
exports a packet for this Codex session and imports the resulting checked draft;
it requires no separate AI API key. Actual Apple/Samsung reports are linked in
[the milestone 4 report](docs/MILESTONE4.md). Their price/valuation conclusions
are withheld because the live broker connection and annual inputs are unverified.

## Broker quickstart

```
uv sync
copy .env.example .env   # fill in TOSSINVEST_CLIENT_ID / TOSSINVEST_CLIENT_SECRET
.venv\Scripts\toss-pilot price 005930 AAPL
```

Requirements: Python 3.12+, uv, and your public IP registered in Toss
Securities WTS under Settings > Open API > Allowed IP management (calls from
unregistered IPs fail with 403, including token issuance).

Read-only CLI commands: `token`, `price`, `candles`, `calendar`, `fx`,
`accounts`, `holdings`, `orders OPEN|CLOSED`. The CLI deliberately has no
order-placement command.

Offline verification (no credentials needed):

```
.venv\Scripts\python.exe -m pytest -q --basetemp=.pytest_cache/local-tests
```

Bounded live validation (needs credentials and an allowlisted IP; no accounts or orders):

```
.venv\Scripts\python.exe scripts/validate_live.py
```

## Safety model

- There is no sandbox in this API; every order-path call with real
  credentials is a real order on a real account, and no per-order 2FA exists.
- toss_pilot.orders defaults to dry_run=True and returns the would-be request
  instead of sending. A live send requires both dry_run=False in code and the
  environment variable TOSS_PILOT_ALLOW_LIVE_ORDERS=yes, set in the actual
  process environment (the .env loader deliberately refuses to import it).
  A second, independent gate in the transport blocks any non-GET request to any application endpoint without both opt-ins. Noncanonical paths are
  rejected before authentication. ResearchClient additionally refuses every mutation.
- Exactly one access token is valid per client; issuing a new one invalidates
  the previous. The token is cached in .token_cache.json (gitignored) and
  reused. Do not run multiple processes that each issue their own token.
- Credentials live only in environment variables or a gitignored .env.

## Layout

- src/toss_pilot: auth, client, market, account, orders, cli
- config/api.json: reviewable API contract (base URL, rate limits, retries)
- spec/openapi-1.2.14.json: vendored official OpenAPI spec (source of truth)
- tests: offline unit tests (httpx.MockTransport, no network)
- docs/PROJECT_STATE.md: living handoff; docs/AI_HANDOFF.md: machine context
