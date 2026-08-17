# AI handoff

Machine-oriented context for future agent sessions. Human narrative lives in
README.md and docs/PROJECT_STATE.md.

## Invariants (do not violate)

- Never execute a live order. Two independent gates: orders.py wrappers
  (dry_run defaults True; live needs dry_run=False AND process-env
  TOSS_PILOT_ALLOW_LIVE_ORDERS=yes, which the .env loader refuses to import)
  and the transport (client.request raises LiveOrderBlocked on any non-GET
  to /api/v1/orders* or /api/v1/conditional-orders* without
  allow_live_order=True). Both are user-only decisions. No sandbox upstream.
- Never request, print, or log TOSSINVEST_CLIENT_SECRET. Credentials enter
  only via environment or gitignored .env.
- Do not issue tokens casually: one valid token per client; re-issue kills
  the previous token. Always go through toss_pilot.auth.TokenManager, which
  caches in .token_cache.json.
- All monetary/quantity API values are decimal strings; never convert to
  float in code paths that resend them.

## Facts (verified against spec v1.2.14, vendored at spec/openapi-1.2.14.json)

- Base https://openapi.tossinvest.com; POST /oauth2/token (form-encoded
  client_credentials); Bearer auth; account/asset/order endpoints also need
  X-Tossinvest-Account: {accountSeq} from GET /api/v1/accounts.
- Envelopes: success {result: ...}; business errors {error: {requestId,
  code, message, data}}; OAuth errors {error, error_description}.
- 429 carries Retry-After and X-RateLimit-*; headers are authoritative over
  the config table. Per-group TPS in config/api.json.
- Order rules: quantity xor orderAmount; orderAmount is US MARKET only;
  LIMIT needs price, MARKET forbids it; confirmHighValueOrder for >= 100M
  KRW; > 3B KRW rejected (max-order-amount-exceeded); modify/cancel return a
  NEW orderId; opposite-direction pending order on the same symbol is 422.
- IP allowlist enforced at the edge (403 on unlisted IPs, token endpoint
  included). KR orders may 422 prerequisite-required or
  investor-exchange-not-integrated until in-app settings are completed.

## Repo mechanics

- Windows 11 ARM64, no C compiler; uv-managed .venv (CPython 3.12.10
  arm64); pure-Python deps only (httpx, pytest). uv sync then
  .venv\Scripts\python.exe -m pytest -q (25 tests, offline).
- Branch model: Claude/<topic> plus PR to main; tracked tree stays clean.
- Config: config/api.json; TOSS_PILOT_CONFIG env var overrides its path.
- Session artefacts: research journal at
  C:\Users\dream\.claude\projects\X--GitHub-Toss-API-Pilot\
  2c707fc8-41f4-4560-a0da-9bb397973fb2\subagents\workflows\wf_8ed24b57-57e\
  journal.jsonl (5 research slices + fact-check + critic).
- Capability-map artifact (owner-facing report):
  https://claude.ai/code/artifact/db5d3b21-02e1-4e00-abeb-7cc43e714089
- One-time scheduled task toss-pilot-continue (06:00 KST 2026-08-17) exists
  as a token-runout safety net; it self-disables after firing and stops
  early if the PR is already open. Disable it if work completes first.
