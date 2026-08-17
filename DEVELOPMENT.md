# Development notes

## AI disclosure

This repository was researched and written by Claude (Fable 5) in Claude Code
sessions on 2026-08-17, directed by Junil Byeon. Research ran as a 7-agent
workflow (5 research slices, 1 adversarial fact-checker, 1 completeness
critic) over the official docs (developers.tossinvest.com llms.txt,
openapi.tossinvest.com spec v1.2.14, overview.md) plus community sources; the
fact-checker verified 14 load-bearing claims against official sources only.
An earlier session produced a Toss Payments capability map before the
credential was identified; it is superseded (see below).

## Who decided what

| Decision | Who |
| --- | --- |
| Target is the Toss Securities Open API (credential is client_id/client_secret) | Junil (confirmed 2026-08-17) |
| Build the pilot in Python | Junil |
| Read-first scope; CLI has no order commands; dry-run default plus env gate for live orders; Claude never executes trades | Claude proposed, standing safety rule |
| Plain httpx REST client, no codegen, no community SDK dependency | Claude (community SDKs stale/incomplete; spec vendored instead) |
| Token file-cache with single-token semantics | Claude (forced by documented one-token-per-client rule) |
| 06:00 KST scheduled continuation task as token-runout safety net | Junil |

## Pre-commit adversarial review

Before the first commit, a 12-agent review workflow (correctness, spec
conformance, safety reviewers; every finding adversarially verified) examined
the package and confirmed 9 findings, all fixed and regression-tested in the
same change: 1 critical (the transport could reach live order endpoints
without any gate; a deny-by-default gate now lives in client.request), 1
major (the token cache path was CWD-relative and could drop a live bearer
token outside the repo; now anchored to the repo root), and 7 minor
(unbounded Retry-After trust, .env able to arm the live-order flag,
unvalidated order_id path interpolation, missing timeInForce/clientOrderId
spec validations, rate-limit provenance, an inclusive-threshold docstring
error). The correctness reviewer died on an API stream error and was re-run
separately; its outcome is recorded in docs/PROJECT_STATE.md.

## Rejected or corrected AI output

- The account-trading research agent's summary stated a "30B KRW" hard order
  cap. The adversarial fact-checker refuted it against the spec: the cap is
  3,000,000,000 KRW (30억), a 10x unit error of 억. Corrected before anything
  landed. The agent's own detail section had the correct figure.
- Terms-page claims (eligibility 19+, redistribution ban, commission rates)
  could not be re-verified by the fact-checker because corp.tossinvest.com is
  JS-rendered; they are carried as Descriptive only with that caveat in the
  README claims table rather than being silently promoted to fact.
- Initial working assumption that "a Toss API key" meant Toss Payments was
  superseded on owner confirmation; the full Toss Payments capability map
  produced under that assumption is retained in the artifact version history,
  not deleted.

## Conventions

Cross-project conventions from the owner's global CLAUDE.md apply: English
repo content, no emoji, no em-dashes, config as reviewable JSON, uv-managed
native ARM64 venv, pure-Python dependencies only (no C compiler on this
machine), full-sentence commit messages with Co-Authored-By trailer, work
lands via Claude/<topic> branches and PRs.
