# Toss_API_Pilot

Pilot Python client for the Toss Securities Open API (openapi.tossinvest.com),
built read-first: market data and account reads are the product; order
placement exists only behind an explicit dry-run gate and is never exercised
by automation in this repository.

## Claims

| Claim | Status | Evidence |
| --- | --- | --- |
| Token manager caches and reuses the access token, re-issues on expiry, and maps OAuth error responses | Validated | Offline tests (tests/test_auth.py), 48/48 passing 2026-08-17 |
| Client unwraps the {result} envelope, maps the {error} envelope (requestId, code, data), retries 429 honoring Retry-After with a bounded retry count, and refreshes the token once on 401 expired-token | Validated | tests/test_client.py |
| Market and account calls build spec-exact parameter names and omit unset optionals; account calls carry X-Tossinvest-Account | Validated | tests/test_market.py, tests/test_client.py |
| Order bodies enforce spec v1.2.14 rules (quantity xor orderAmount, LIMIT/MARKET price rules, timeInForce constraints, clientOrderId format, no floats); dry-run returns the payload without network; live sends are refused without TOSS_PILOT_ALLOW_LIVE_ORDERS=yes; the transport itself additionally blocks any ungated non-GET to order endpoints; hostile order ids cannot be interpolated into paths; the live flag is not importable from .env | Validated | tests/test_orders.py, tests/test_config.py |
| Endpoint inventory (36 operations), per-group rate limits, single-active-token rule, IP allowlist, no-sandbox, 100M KRW confirm flag and 3B KRW order cap | Descriptive only | Official OpenAPI spec v1.2.14 vendored at spec/openapi-1.2.14.json; overview at openapi.tossinvest.com/openapi-docs/overview.md |
| Terms: automated trading permitted at own risk; market data personal-use only, redistribution banned; individuals 19+ only; commissions KRX 0.015% / NXT 0.014% / US 0.1% | Descriptive only | corp.tossinvest.com terms and Open API pages (JS-rendered; read via browser rendering, one verification pass could not reproduce; re-check before relying) |
| Any live API behavior (no credentialed call has been made from this repo); quote freshness (real-time vs delayed entitlement); candle history depth; US order funding via auto-FX; client_secret rotation; plain-order session windows; CLOSED order history retention | Not established | No logged artefact; see docs/PROJECT_STATE.md open questions |
| The credential is a Toss Payments key | Retracted-superseded | Initial working assumption, superseded 2026-08-17 after owner confirmation that the credential is a Toss Securities Open API client (see DEVELOPMENT.md) |

## Quickstart

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
.venv\Scripts\python.exe -m pytest -q
```

Live smoke test (user-run, needs credentials and an allowlisted IP):

```
.venv\Scripts\toss-pilot token
.venv\Scripts\toss-pilot price 005930
.venv\Scripts\toss-pilot accounts
```

## Safety model

- There is no sandbox in this API; every order-path call with real
  credentials is a real order on a real account, and no per-order 2FA exists.
- toss_pilot.orders defaults to dry_run=True and returns the would-be request
  instead of sending. A live send requires both dry_run=False in code and the
  environment variable TOSS_PILOT_ALLOW_LIVE_ORDERS=yes, set in the actual
  process environment (the .env loader deliberately refuses to import it).
  A second, independent gate in the transport blocks any non-GET request to
  /api/v1/orders* and /api/v1/conditional-orders* that did not come through
  the gated wrappers.
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
