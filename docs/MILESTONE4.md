# Milestone 4 delivery and live validation

Delivered locally on 2026-10-11 as version 0.3.0. Trading remains disabled.
The owner authorized read-only live checks and implementation, then clarified
that no separate paid AI API credentials were available. No credit purchase,
paid model call, account read, order request, schedule or Notion write occurred.

## Results

| Area | Observed result | Evidence |
| --- | --- | --- |
| Toss authenticated data path | OAuth connection timed out after 15 seconds; no HTTP response, token or stock data obtained | [Validation record](evidence/live/validation.json) |
| Toss public connectivity | Unauthenticated root check also timed out; this is not evidence that the credential is invalid | Same host independently tested; credentials were never logged |
| SEC | Not run: SEC_USER_AGENT application/contact setting absent; this is not a paid API key | [SEC public API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces) |
| OpenDART | Not run: OPENDART_API_KEY absent; registration is separate from ChatGPT | [OpenDART](https://opendart.fss.or.kr/) |
| Issuer disclosures | Three official Apple/Samsung documents fetched successfully through the new collector; original HTML, hashes and extracted text retained locally | [Collection evidence](evidence/live/disclosures.json), SQLite collection runs |
| AI research | Two Codex-assisted drafts imported, checked and rendered against frozen evidence packets | [Report manifest](evidence/live/research-results.json), [drafts](evidence/live/drafts/) |
| Offline suite | 120 passed, zero failed/errors/skipped | [JUnit evidence](evidence/milestone4-tests.xml) |
| Package | Wheel installed in a fresh environment outside the checkout; broker help, synthetic demo, and M4 abstention/report path passed | [Verification manifest](evidence/milestone4-verification.json) |

The confirmed Toss API address remains `https://openapi.tossinvest.com`.
Current [official docs](https://developers.tossinvest.com/) show v1.2.24 and an IP
allowlist requirement; the repo's v1.2.14 contract remains pinned. A connection
timeout is not an HTTP 403 and does not establish an IP-allowlist diagnosis.
The newer complete REST/AsyncAPI contracts and authenticated behavior remain
unverified; changing credentials or trade permissions would not fix that evidence gap.

## Real-stock reports

- [Apple HTML](examples/live/US-AAPL-deaafb0b42a6.html) / [JSON](examples/live/US-AAPL-deaafb0b42a6.json)
- [Samsung Electronics HTML](examples/live/KR-005930-c31c6dec0f90.html) / [JSON](examples/live/KR-005930-c31c6dec0f90.json)

These are real issuer disclosures, not synthetic prices or a successful broker
smoke. Apple uses its July quarterly release. Samsung uses its July quarterly
release and October preliminary guidance; guidance is identified as an estimate.
Both reports cover thesis, counterarguments and monitoring ideas for the requested
holding periods. Both abstain from a price setup or valuation conclusion because
no adjusted daily series, complete annual financial inputs, or reviewed per-share
basis is available. Entry/exit figures and drawdown measurements are withheld.
The reports cannot yet decide whether either stock is worth investing in.

## What was implemented and fixed

- SQLite schema 2 migrates schema 1 without deleting prior data. It stores dated
  documents, frozen packets and AI drafts alongside the existing run/report ledger.
- Official HTML collection has bounded response size, explicit article boundaries,
  no redirects, a fixed host allowlist and a GET-only transport path. Other source
  text can be explicitly imported as filing, issuer release or news.
- Evidence packets apply both publication and first-retrieval cutoffs. Documents
  older than 180 days are excluded; only the first six 1,400-character chunks per
  document and at most 24 total chunks enter context. Truncation is disclosed.
  This is deterministic bounded selection, not comprehensive news retrieval.
- Draft checks enforce a fixed schema and packet hash, cited evidence membership,
  exact supporting excerpts, source quotation budgets, both horizon gates, and
  known numeric references. Computed numbers are substituted by the report renderer.
  Missing evidence requires abstention; the model can always abstain voluntarily.
- Reports escape model/source text, separate observations from inferences and
  monitoring ideas, link sources and expose human review as pending. Full document
  text stays in the local database/packet, not in published report JSON.
- Prompt/hash/model provenance, draft/report hashes and usage/cost availability
  are recorded. Imported model identity is explicitly unverified. Exact model ID,
  token consumption and monetary allocation of this Codex session are unavailable;
  none is invented.
- Optional OpenAI mode uses the Responses API with a strict JSON schema, bounded
  context/output, no tools, no automatic retry and `store=false`. Refusals, incomplete
  responses and invalid drafts fail closed; observed usage survives failed validation.
  Cost is an estimate only when the caller supplies dated rates. It is never assumed
  to be zero. The live paid API was not called.
- The `.env` allowlist now supports SEC, DART and optional AI settings and quoted
  values/UTF-8 BOM. It still excludes the trading switch. Wheel smoke now selects
  the current version explicitly so an older wheel cannot accidentally pass.

Citation checks prove traceability and exact excerpt membership, **not semantic
entailment**. They cannot detect every misleading paraphrase, unsupported inference,
spelled-out numerical claim, or instruction paraphrase. Human review is required.
The rejection tests evaluate deterministic boundaries, not investment performance
or an empirical hallucination rate for a deployed model.
The earlier automation plan's measurable-research-value acceptance gate remains
open. Implementation delivery does not certify that broader outcome.

## Workflow without separate AI credits

The API platform has separate billing from ChatGPT Pro. The default workflow
uses this Codex conversation for drafting, without extracting or reusing ChatGPT
credentials in a Python API call. [Official billing explanation](https://help.openai.com/en/articles/9039756-managing-billing-settings-on-the-chatgpt-web-and-api-platform)

1. Register identities, collect available market/fundamental data and dated
   documents. For these fixed examples, `scripts/validate_live.py` registers Apple
   and Samsung, and `scripts/collect_research_examples.py` fetches the three releases.
2. Export the stock's packet:

   ```powershell
   uv run toss-research --db data/live.sqlite3 research-packet US:AAPL --output data/apple-packet.json
   ```

3. Ask the current Codex session to read that packet, follow its instructions and
   JSON schema, and save a draft. It must use the exact packet hash, cite evidence
   IDs, keep source quotations short and preserve insufficient-data stances.
   The fixed procedural summary is specified in `research/ai.py`; financial claims
   belong in cited sections. Do not put a new company fact in `missing_information`.
4. Validate and publish local files:

   ```powershell
   uv run toss-research --db data/live.sqlite3 ai-import --file data/apple-draft.json --model "Codex session; exact model ID unavailable" --output reports/live
   ```

5. Review the source-linked draft and missing data. This is a conversation-assisted
   workflow; it is not an unattended model service or scheduled automation.

`document-import --file document.json` requires exactly: `instrument_id`,
`source_url`, `title`, `kind`, `published_at`, `fetched_at`, `text`, `extraction`.
Extraction is `source_text` or `curated_summary`. Use an explicit timezone, and
conservatively use next-day UTC midnight for the date-only issuer releases here.
Publication timestamps are caller-reviewed metadata, not inferred or certified
by the parser. See `collect-document --help` for bounded HTML collection.

## Optional API mode and next work

`ai-openai --packet-hash HASH` is an explicit separately billed path and requires
`OPENAI_API_KEY` and `OPENAI_MODEL`; no default model is silently selected.
It is implemented from the [Responses structured-output documentation](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)
and covered with mock transport tests. It can remain unused indefinitely.

Next, restore Toss connectivity and configure the no-key SEC contact setting / an
OpenDART registration key if wanted. Then validate real candle pagination, financial
taxonomy mappings and corporate-action consistency before enabling valuation outputs.
M5 evaluates strategy and AI utility prospectively; M6 adds scheduled collection
and an outbox; M7 publishes compact summaries to Notion; M8 scales storage only if
needed. The [storage/automation design](AUTOMATION_AND_STORAGE.md) still recommends
SQLite first, Notion for review, Task Scheduler for local jobs and n8n for publishing.
No schedule, external database or Notion integration was activated in this delivery.
