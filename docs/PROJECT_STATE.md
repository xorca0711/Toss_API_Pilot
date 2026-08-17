# Project state

Updated: 2026-08-17 (session 2c707fc8, Python pilot build)

## Where things stand

- Research: complete and adversarially verified (7-agent workflow; 12/14
  claims CONFIRMED against official sources, 1 corrected, 1 unreproducible
  terms-page item carried with caveat). Raw results live in the session
  workflow journal; the distilled facts are in README, AI_HANDOFF, and code
  comments.
- Code: toss-pilot 0.1.0 package built and passing 48/48 offline tests
  (pytest, httpx.MockTransport, no network). CLI installed as toss-pilot.
- Pre-commit review: 12-agent adversarial workflow confirmed 9 findings
  (1 critical transport-gate bypass, 1 major CWD-relative token cache, 7
  minor); all fixed and regression-tested before the first commit. Caveat,
  recorded per the fail-visible convention: the correctness dimension was
  never independently reviewed. Its reviewer crashed twice on infrastructure
  stalls, and the pass was done by the authoring session instead (retry-loop
  termination, token expiry arithmetic, httpx parameter serialization, gate
  test loudness); treat independent correctness review as still open.
- Not yet done: any live call against openapi.tossinvest.com. Zero
  credentialed requests have been made from this repo. Live behavior is
  Not established until the owner runs the smoke test.

## Next steps (owner)

1. Register this machine's public IP in WTS Settings > Open API > Allowed IP
   management, put credentials in .env (never in chat), then run:
   toss-pilot token; toss-pilot price 005930; toss-pilot accounts.
2. Decide the pilot's direction: (a) market-data collection (candles/quotes
   snapshots, possibly on a schedule), (b) portfolio monitoring (holdings,
   buying power), or (c) strategy prototyping with dry-run orders only.
3. If (a): a recurring scheduled task can call the CLI; note ACCOUNT group is
   1 req/s and MARKET_DATA 15 req/s.

## Open questions (from the completeness critic; all Not established)

- Real-time vs delayed quote entitlement, especially US; test empirically by
  comparing API lastPrice against the app during market hours.
- US order funding: whether API orders can draw KRW via auto-FX or need
  manual conversion in the app first (API has no FX execution).
- Plain-order session windows (NXT pre/after-market, US overnight session).
- Candle history depth; CLOSED order-history retention.
- client_secret rotation/revocation procedure; whether multiple client_ids
  per user are possible (would relax the single-token constraint).
- Whether the Toss app shows push notifications for API-placed orders.

## Safety notes carried forward

- No sandbox; no per-order 2FA. Key + allowlisted IP = trading power. The
  dry-run gate and the TOSS_PILOT_ALLOW_LIVE_ORDERS env guard are the rails.
- One access token per client; .token_cache.json is the shared cache. The
  06:00 KST one-time continuation task (toss-pilot-continue) fires today; it
  self-checks and stops if the PR already exists.
