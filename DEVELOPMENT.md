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

## 2026-10-11 development session

Codex implemented milestones 1-3 in the local branch
codex/research-milestones-1-3 after the owner requested structured tasks and
implementation through the numerical-report milestone. No subagents were used.
No human acceptance of the delivered code, commit, push or PR is recorded.

| Date | Item | Proposed by | Decided by | Decision | Reason |
| --- | --- | --- | --- | --- | --- |
| 2026-10-11 | Implement milestones 1-3; plan automation and Notion | Codex plan | Owner, explicit chat instruction | Authorized implementation scope; delivery acceptance pending | KR/US stock research over two horizons |
| 2026-10-11 | SQLite authoritative store; Notion summaries later | Codex | Pending owner review | Implemented local SQLite within authorized milestone 2; external publishing remains a proposal | Preserve raw data and revisions without overloading personal pages |

## Corrections and rejected proposals from this session

| Date | Proposal or prior claim | Correction / reason | By |
| --- | --- | --- | --- |
| 2026-10-11 | Raw-prefix transport check blocked every order route | Retracted after offline reproduction of relative/absolute/dot-segment bypasses; canonical-path rejection and all-mutation gate added | Codex scan and regression tests |
| 2026-10-11 | API has no push events | Superseded by current official WebSocket documentation; streaming implementation remains later work | Codex source research |
| 2026-10-11 | Generic equity-cash-flow DCF in the first numerical report | Replaced with explicit earnings-multiple scenarios; CFO minus PP&E capex does not establish distributable equity cash flow | Codex implementation decision |
| 2026-10-11 | All 48 original tests alone demonstrate client safety | Expanded bypass, ingestion, chronology, numerical and packaging verification; passing old tests did not cover the discovered defect | Codex verification |

## 2026-10-11 milestone 4 and authorized live validation

The owner authorized read-only live validation, issue fixes and milestone 4,
with trading disabled. Subsequent clarification established that separate paid
AI credentials were not available. Codex implemented a packet/draft-import path,
used this conversation to author two real-disclosure drafts, and left the optional
Responses API integration unused outside mocks. No acceptance, commit, push or PR
is implied by this delivery.

| Date | Item | Proposed by | Decided by | Decision | Reason |
| --- | --- | --- | --- | --- | --- |
| 2026-10-11 | Read-only live validation and M4 implementation | Owner | Owner, explicit chat instruction | Implemented; live constraints documented | Requested next milestone using real stock data |
| 2026-10-11 | Codex-assisted draft import as the default AI workflow | Codex | Codex within owner scope and credit constraint | Implemented without a separate paid call | ChatGPT plan does not supply a Python API key |

Validation: 120 offline tests; clean installed-wheel smoke, including M4 abstention.
Three official HTML disclosures fetched and stored; two real-stock reports have
source-linked claims and pending human review. Toss connection timed out before
auth completed; SEC contact and OpenDART key absent. These are logged limitations,
not successful provider validation. Citation checks do not prove semantic entailment.
See docs/MILESTONE4.md and docs/evidence/milestone4-verification.json.

## 2026-10-11 GitHub publication

The owner explicitly requested a commit, push and PR for the completed local
work. Publication is authorized; human code acceptance and merging remain
separate. Codex reused the matching implementation-hash/test evidence, checked
the publishable file set for configured credential values, and fast-forwarded
the branch to the remote's existing merge commit with an identical file tree.

| Date | Item | Proposed by | Decided by | Decision | Reason |
| --- | --- | --- | --- | --- | --- |
| 2026-10-11 | Commit, push and open a PR for milestones 1-4 | Owner | Owner, explicit chat instruction | Authorized publication for review; merge approval not recorded | Update the remote GitHub repository with the delivered work |
