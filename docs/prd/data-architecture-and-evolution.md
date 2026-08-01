# Data Architecture & Product-Evolution Plan

- **Status:** DRAFT for owner review. Research + planning only — no app code/logic changed.
- **North-star:** [`docs/prd/PRODUCT.md`](./PRODUCT.md) — the credit-card usage optimizer.
- **Author:** architecture agent. **Date:** 2026-08-01.
- **Scope:** answers the owner's two framing questions — *is the current data-fetching
  approach right?* and *are MCP-based tools a better way to integrate with financial data?* —
  and lays out a phased, backend→frontend evolution toward the product goal.

> Read this top-to-bottom. §1–2 establish where we are, §3–4 answer the data-integration
> question with evidence, §5 is the concrete build plan. Owner decisions are collected in
> [`## QUESTIONS FOR HUMAN`](#questions-for-human).

---

## 1. Product goal — restated crisply

`finance-tracker` is **a credit-card-usage / spending optimizer**, not a general budgeting or
net-worth app (budgeting, forecasting-for-its-own-sake, bill pay, and investment tracking are
explicitly out of scope — [`PRODUCT.md`](./PRODUCT.md) §"Explicitly OUT of scope"). Everything
serves one loop: *pull the user's real spending → understand it → tell them which card to use
(and which to get) to extract the most value.*

Sharpened into the three capabilities the owner named:

1. **Classification accuracy** — every ingested transaction must be correctly identified:
   the right **merchant** (`SQ *`, `TST*`, `SP ` prefixes stripped) and the right **category**
   in our fixed 10-way taxonomy (`dining, groceries, travel, transport, shopping, bills,
   entertainment, health, income, other` — `enrichment/taxonomy.py`). Category quality is the
   *upstream dependency of the entire product*: the spending profile groups by `category`, and
   the recommender ranks cards by category spend. Garbage-in here poisons the recommendation.

2. **Financial-trajectory analysis** — understand *where the user is heading*: category-spend
   trends over time, recurring-commitment detection, and forward cash-flow projection. Note this
   is a **deliberate expansion** of today's scope: `PRODUCT.md` lists "forecasting" as out of
   scope for the MVP. It is in scope *only* insofar as it sharpens the card recommendation
   (e.g. "your dining spend is trending up 15%/quarter, so the dining multiplier matters more
   than the flat card") — see [`## QUESTIONS FOR HUMAN`](#questions-for-human) Q1.

3. **Improving financial flow** — the recommendation surface: which card to use per category,
   which new card to apply for, and (Phase-5) the optimal *portfolio* of cards, each with a
   dollar-denominated, data-backed rationale ("you'd earn ~$X more/year").

The optimization objective is **owner-decided: total first-year value** (ongoing rewards +
sign-up bonuses), across **both held and new cards** (`PRODUCT.md` "Decisions", 2026-07-07).

---

## 2. Current architecture — how data flows TODAY

Traced from the real code, not the docs. Two ingest paths converge on one shared enrichment +
dedup seam, then feed the spending profile and the recommendation engine.

```
 INGESTION                          NORMALIZE / DEDUP / ENRICH            ANALYZE                RECOMMEND
 ─────────                          ─────────────────────────            ───────                ─────────

 (A) Plaid transactions/sync        ┌──────────────────────────┐
   plaid_service.sync_transactions  │ dedupe.generate_dedupe_  │
   - cursor loop add/modify/remove  │   hash(date,amount,       │       spending_profile.py       card_recommendation.py
   - amount sign flipped (Plaid     │   merchant, account_id)   │       compute_profile():        - recommend_next_card()
     positive=outflow → stored neg) │   → collapses CSV twin of │       - lookback N months        - analyze_portfolio()
   - reads personal_finance_        │     a Plaid txn           │       - avg_monthly_spend        - optimize wallet (per-cat)
     category.primary/.detailed     └────────────┬─────────────┘       - category_breakdown{}     scored on FIRST-YEAR VALUE
   - source="plaid"                              │                     - category_counts{}         = ongoing earn + sign-up
        │                                        ▼                     - top_merchants[]             bonus + credits - fee
        │                          ┌──────────────────────────┐            │                            │
 (B) Statement import              │ enrichment/apply.py       │            │                     card data sources:
   statement_import.run_import     │   apply_enrichment()      │            ▼                     - card_bonuses.py → sibling
   - CSV: parse_csv (header alias,  │   fail-open, in place     │       SpendingProfile (DB)         credit-card-bonuses-api
     debit/credit or signed col)    │                          │       served to web UI            (flat universalCashback%)
   - PDF: statement_pdf.parse_pdf   │ get_provider():           │                                  - card_category_rates.json
     · heuristic regex (free) first │   FT_ENRICHMENT_PROVIDER  │                                    (curated per-cat rates,
     · else LLM (Anthropic) extract │   default = "noop"        │                                     ~in-repo bridge)
   - source="import"                │   "rules" = keyword rules │
        │                           │ taxonomy.map_to_internal()│
        └──────────────────────────►│   vendor label → 10-way   │
                                    └──────────────────────────┘
```

### Path A — Plaid (`plaid_service.py`, `api/plaid.py`)
- `create_link_token` / `exchange_public_token` / cursor-based `sync_transactions`
  (add/modify/remove, dedup by `dedupe_hash`). Errors are mapped to HTTP codes
  (`plaid_errors.py`), and a webhook path exists (`plaid_webhook.py`) for event-driven sync.
- Category signal is Plaid's `personal_finance_category`: `.primary` normally, but
  `.detailed` when primary is `FOOD_AND_DRINK` (to split groceries from restaurants — the
  dining-first recommender depends on it; `plaid_service.py` L180–199, issue #52).
- Sign convention: Plaid positive = outflow, stored negative = spend.

### Path B — Statement import (`statement_import.py`, `statement_pdf.py`)
- **CSV**: header-alias matching (`date`/`description`/`amount`, or a `debit`/`credit` pair),
  currency/parentheses parsing, per-row error collection. Plaid-free ingest (issue #22/#149).
- **PDF**: extract text with `pdfplumber`, try a **free regex heuristic** on date-led lines
  first, fall back to an **Anthropic LLM** extraction (`_MODEL = pdf_import_model or
  "claude-sonnet-5"`) with a sign-convention system prompt. `is_credit` flips signs.
- Imported rows carry **no category** (`category=None`) → they rely entirely on enrichment.

### Dedup (`dedupe.py`)
- `generate_dedupe_hash(date, amount, merchant, account_id)` — fed the *Plaid outflow-positive*
  amount on both paths so a CSV row and its Plaid twin for the same purchase collapse to one.

### Enrichment / categorization (`enrichment/`)
- Provider-swappable behind a `Protocol` (`base.py`), selected by `FT_ENRICHMENT_PROVIDER`
  (`__init__.py`). Applied in place, **fail-open**, on both ingest paths (`apply.py`).
- **Default provider is `noop`** — it echoes the raw Plaid category unchanged.
- **`rules` provider** (`rules.py`): ordered **merchant-keyword substring rules** → category.
  If a Plaid category is present it is trusted (confidence 0.6); otherwise keyword match
  (0.9); otherwise **`"other"` (0.3)**. This is the only categorizer for statement-import data.
- `taxonomy.map_to_internal()` maps any vendor/Plaid label into the fixed 10-way set;
  unknown → `other`.

### Spending profile (`spending_profile.py`)
- Aggregates non-income txns over a lookback window into `avg_monthly_spend`,
  `category_breakdown` (monthly avg per category), `category_counts` (frequency — "how many
  times did I dine out"), and `top_merchants`. Cached with a freshness + window-slide check.

### Recommendation engine (`card_recommendation.py`, `data/card_category_rates.json`)
- Pure-function, DB-free. `recommend_next_card` (apply-for-new) and `analyze_portfolio`
  (optimize held wallet) both score on **total first-year value** = ongoing earn + best
  achievable sign-up bonus + credits − first-year fee.
- Card metadata comes from the sibling **`credit-card-bonuses-api`** via `card_bonuses.py`,
  which exposes **only a flat `universalCashbackPercent`** — no per-category earn. The gap is
  bridged by the **curated, in-repo `card_category_rates.json`** (issue #38, path A), because
  that upstream repo is a read-only mirror that won't accept PRs.

### Honest list of current limitations

| # | Limitation | Where | Impact on the goal |
|---|---|---|---|
| L1 | **Plaid production is blocked** — live link needs the owner's real keys + a manual OAuth handshake (Chase/OAuth banks need `redirect_uri` registered). Everything to date is sandbox/mocked. | `plaid_service.py`, `plaid-integration.md` | No real spending data flows yet → the whole loop is unproven on real data. |
| L2 | **Categorization is keyword-rule / passthrough.** Default provider is `noop`; even `rules` is brittle substrings and dumps unmatched, category-less statement rows into **`other`**. | `enrichment/rules.py`, `__init__.py` | Directly caps classification accuracy — the product's #1 dependency. A big "other" bucket makes category-aware recommendations weak. |
| L3 | **No merchant normalization.** `normalized_merchant` is just `lower().strip()`; `SQ *`, `TST*`, `SP `, `PAYPAL *`, city/store-number noise survive. | both ingest paths | Same merchant appears as many; keyword rules miss; `top_merchants` fragments. |
| L4 | **No trajectory/forecasting at all.** The profile is a single-window snapshot — no trend, no month-over-month, no projection, no recurring-commitment detection. | `spending_profile.py` | Can't answer "where am I heading" or weight recommendations by *trending* spend. |
| L5 | **Card earn data is coarse.** Upstream is flat-cashback only; per-category rates are a small hand-curated in-repo file (`_meta.provenance`: "pending owner verification"). Rotating 5% categories, portal rates, and spend caps are unmodeled. | `card_bonuses.py`, `card_category_rates.json` | Recommendation precision is bounded by card-data fidelity, not just spend data. |
| L6 | **No existing-card (liabilities) awareness from a connection.** `Card` is manually entered; nothing pulls held cards / APR / limit from Plaid. | `models/card.py`, research #12 | "Optimize the cards you already hold" relies on manual entry today. |
| L7 | **PDF LLM path has known correctness bugs** (spend↔income sign inversion — open issue #203) and the free heuristic can misread descriptions-with-digits. | `statement_pdf.py`, #203 | Silent data corruption → wrong categories/spend → wrong recommendations. |
| L8 | **Enrichment is synchronous + in-request, no backfill.** A network provider would run inline in the sync path; there's no `enrich_existing` job for historical rows. | `apply.py`, `base.py` | Blocks adopting a real ML/LLM enrichment provider at scale. |

---

## 3. Competitor / prior-art scan

Sourced from a web survey (Aug 2026). Inline citations throughout.

### 3a. The two products the owner named

- **"error.finance / Eradout / Arrowout"** — **no product exists with any of those literal
  names** (`error.finance` doesn't resolve; "Arrowout" is a puzzle game; "Air Out" is a venting
  app). Mis-hearing. The two plausible real targets, given it was paired with Range:
  - **Arta Finance** (most likely) — an **AI-powered "private bank"** for high earners.
    Its **Arta AI** (2025) runs conversational *Investment Planner* + *Research Analyst* agents
    built on **function-calling, RAG, agentic systems, and classic ML**. Wealth-management
    focus, not card optimization. ([artafinance.com/ai-for-wealth](https://artafinance.com/global/ai-for-wealth),
    [Meet Arta AI](https://artafinance.com/global/insights/meet-arta-ai-private-wealth-guided-by-ai-agents))
  - **Arro** (secondary, if the *card* angle was meant) — a credit-*builder* Mastercard with
    income-based underwriting and gamified literacy; 1% cash back. Not spend-optimization.
    ([Nav review](https://www.nav.com/business-credit-card/arro-mastercard/))
  - → **Owner: which did you mean?** (Q5.)

- **"range.com / Range"** — **confirmed: Range Finance**, a flat-fee ($0 AUM) SEC-registered
  RIA / all-in-one wealth manager for high-income households. **Ingests via Plaid, MX, and
  Yodlee.** Its AI advisor **"Rai"** does genuine **year-by-year cash-flow projection** and
  thousands of scenario models (validated by human advisors). No public MCP surface.
  ([range.com](https://www.range.com/), [Why Rai](https://www.range.com/blog/the-ai-built-for-financial-advice),
  [NerdWallet](https://www.nerdwallet.com/financial-advisors/reviews/range))
  **Takeaway:** Range is the reference for the *trajectory* capability (L4) — real forward
  projection, not just trend charts.

### 3b. Established consumer PFM & business-finance products

| Product | Ingest | Classification | Trajectory / forecast | MCP? |
|---|---|---|---|---|
| **Monarch Money** | Plaid + MX + Mastercard Data Connect (Finicity); per-institution best-connection fallback | Auto-categorize + **user rules engine** + **ML corrections** that learn from edits | Cash-flow tracking, recurring/forecast views (planning, not deep prediction) | No official; **community `monarch-money-mcp`** exposes ~17 read-first tools |
| **Copilot Money** | Plaid primary + MX/Mastercard/Akoya | **"Copilot Intelligence" — per-user ML model** (merchant, amount, day, card); learns per correction. Strongest categorization moat. | Trends, recurring, budget rollovers; light forecast | No |
| **Origin** | Plaid + MX + Finicity (13k+ institutions) | Auto-categorize + AI insights | AI planning insights, goal projection; broad | No |
| **Cleo** | Plaid (read-only) | ML auto-categorization | Lightweight pattern forecast; chatbot UX | No (is an LLM chat product, but no exposed server) |
| **Ramp** | **First-party card issuer** (owns the ledger) | **Production ML + GenAI**, auto-codes ~**90%** of txns with **rationale + confidence scores**; flags duplicate subscriptions | Spend analytics, anomaly/duplicate detection, accruals | **YES — official `ramp-mcp`** (ETL → in-memory SQLite for LLM querying; OAuth-scoped) ([docs.ramp.com/…/mcp](https://docs.ramp.com/developer-api/v1/mcp)) |
| **Mercury** | First-party business banking | Not a headline feature | Treasury/cash management | **YES — official Mercury MCP**, per-user OAuth, read-only ([docs.mercury.com/…/what-is-mercury-mcp](https://docs.mercury.com/docs/what-is-mercury-mcp)) |

Sources: [Monarch data providers](https://help.monarch.com/hc/en-us/articles/33707613533972-Understanding-Data-Providers-and-Connections),
[Copilot Intelligence](https://help.copilot.money/en/articles/8182433-copilot-intelligence-for-spending),
[Plaid × Copilot](https://plaid.com/customer-stories/copilot/),
[Origin FAQ](https://useorigin.com/resources/blog/your-most-asked-questions-about-origin-answered),
[Ramp AI accounting](https://ramp.com/accounting-automation-software).

**Patterns worth stealing:**
1. **Multi-aggregator fallback (Plaid + MX + Finicity/Yodlee) is table stakes** for consumer PFM.
2. **Classification has bifurcated** into (a) rules + classic ML (Monarch), (b) **per-user
   personalized ML** (Copilot — best consumer categorizer), and (c) **GenAI with
   confidence + rationale** (Ramp — best *explainability*). Our keyword rules (L2) are a
   generation behind all three.
3. **Trajectory is where wealth players (Range, Arta) differentiate** — true projection, not
   trend lines.
4. **MCP is live but B2B-led:** the only two products shipping real MCP servers are Ramp and
   Mercury, both first-party ledger owners. **No consumer PFM exposes MCP yet — a genuine gap.**

### 3c. The MCP financial-data landscape

*Question: is there a Plaid MCP server / a credible MCP pattern for financial data?*

- **Plaid ships official MCP servers — but NOT for consumer transaction data.** A **Dashboard
  MCP** (usage/analytics/debug) and an **AI Coding Toolkit** (docs, sandbox tokens, mock data)
  exist; Plaid explicitly states **"Claude does not have access to consumer financial data"**
  via these. ([plaid.com/docs/resources/mcp](https://plaid.com/docs/resources/mcp/),
  [plaid.com/blog/plaid-mcp-ai-assistant-claude](https://plaid.com/blog/plaid-mcp-ai-assistant-claude/))
  → To let an agent read a user's Plaid transactions you'd **build your own MCP wrapper** over
  Plaid's normal API (community ones exist: [`mcp-server-plaid`](https://pypi.org/project/mcp-server-plaid/),
  low maturity, you hold the credentials).
- **First-party bank MCP servers are early** — 8 institutions per
  [Open Banking Tracker](https://www.openbankingtracker.com/banks-with-mcp-servers)
  (Mercury, Coinbase, Griffin, Grasshopper via Narmi, Qonto, Slash…), mostly beta, launched in
  the last ~12 months, mostly read-only.
- **Vendor MCP servers that DO exist and are relevant:** Stripe (official, `mcp.stripe.com`),
  QuickBooks (official Intuit), PayPal (official), **Ntropy** transaction-enrichment MCP
  ([github.com/ntropy-network/ntropy-mcp](https://github.com/ntropy-network/ntropy-mcp)),
  **BankSync** (aggregated bank-feed MCP, ~36 tools, [banksync.io/product/mcp](https://banksync.io/product/mcp)).
- **No MCP for Teller / MX / Finicity / SimpleFIN / Method Financial** — real gap.
- **Prior art for "a PFM app exposing ITS OWN data as MCP" is established and proven:**
  **Monarch Money MCP** ([github.com/felixgalindo/monarch-money-mcp](https://github.com/felixgalindo/monarch-money-mcp))
  exposes accounts/transactions/budgets/cashflow as ~17 read-first tools so Claude can analyze
  spending; **Actual Budget MCP** does similarly. Both are community-built, single-maintainer.
- **Spec basics** ([modelcontextprotocol.io](https://modelcontextprotocol.io/), current rev
  2025-11-25): servers advertise **tools** (name + JSON-Schema `inputSchema`) via `tools/list`,
  invoked with `tools/call` over JSON-RPC; **stdio** transport for local/single-user,
  **Streamable HTTP + OAuth** for remote/multi-user. Security convention: **read-only by
  default, writes behind explicit opt-in; the server holds the credentials, the model never
  does; treat the server as an OAuth 2.1 resource server with per-user scoped tokens.**

---

## 4. Data-integration options — evaluation & recommendation

Three axes matter for the goal: **correctness** (classification), **coverage** (all accounts),
and **cost/effort**.

### (a) Current: Plaid + statement import — *keep as the ingestion substrate*
- **Correctness:** Plaid's `personal_finance_category` is a **weak** classifier (owner's own
  feedback, issue #11); statement rows arrive category-less. Ingestion mechanics are sound.
- **Coverage:** Plaid's FI network + a manual CSV/PDF fallback for anything unlinkable.
- **Cost/effort:** already built. **Blocked only on the owner's production keys + OAuth
  handshake (L1).** This is a config/ops step, not an engineering one.
- **Verdict:** **the data *transport* is fine — the problem the owner senses is not "wrong
  aggregator," it's the weak *classification layer on top* (L2/L3) and missing trajectory
  (L4).** Swapping aggregators does **not** fix categorization (issue #11's core insight).

### (b) Alternative aggregators — *don't switch; keep as documented fallbacks*
Cross-referenced with prior repo research (`research/11.md`, `research/12.md`, BACKLOG):
- **Enrichment vendors (Ntropy / Spade)** — the *real* fix for classification. Ntropy has a
  **2,000-txn free tier**, batch API over our stored txns, confidence scores + custom
  categories; Spade is card-auth-grade but sales-led/no free tier (`research/11.md`
  recommends **Ntropy first**, behind our existing provider interface). Both are hosted (raw
  merchant strings leave our infra — a privacy call, Q3).
- **Teller / MX / Finicity / SimpleFIN** — alternative *connection* layers. No advantage for
  *our* problem (classification), add a second onboarding, and none is needed while Plaid works.
  Keep as documented fallbacks per BACKLOG "Plaid alternatives" item.
- **Method Financial** — for **existing-card/liability** awareness (L6). `research/12.md`
  recommends **Plaid Liabilities for the MVP** (zero marginal integration — reuse the item) and
  Method as a Phase-3+ upgrade (soft-pull auto-discovery + paydown). Still stands.

### (c) MCP-based approach — *adopt as an analysis/consumption layer, not as the ingestion substrate*
Two distinct directions — evaluate separately:

1. **finance-tracker EXPOSES its own data/tools as an MCP server** (read-first: `list_accounts`,
   `query_transactions`, `get_spending_profile`, `recommend_card`, `project_cashflow`).
   - **Value:** lets the owner (and any MCP client — Claude Desktop/Code) do open-ended
     spending analysis over their real data, and turns the recommendation engine into an
     agent-callable tool. Directly serves "analyze all transactions." **Proven pattern**
     (Monarch/Actual MCP). **Highest strategic upside, lowest risk** — it's additive, read-only,
     reuses existing services, and needs no new vendor.
   - **Effort:** moderate — wrap existing repository/service functions as MCP tools
     (Python MCP SDK), OAuth-scope per user, host over Streamable HTTP.
2. **finance-tracker CONSUMES financial MCP tools for ingestion** (e.g. a Plaid-wrapping MCP,
   BankSync, Ntropy MCP).
   - **Value:** low for *ingestion* right now. Plaid's official MCP **doesn't expose consumer
     data**; a community Plaid MCP is just a thinner wrapper over the Plaid API we already call
     directly — **adds a dependency and a moving target without new capability.** For
     *enrichment*, the Ntropy MCP is interesting but the plain Ntropy batch API fits our
     existing synchronous provider interface better.
   - **Verdict:** **not now** for ingestion. Revisit if a first-party aggregator MCP matures.

### Recommendation

> **Keep Plaid + statement import as the ingestion substrate** (it's the right transport; just
> unblock production — L1). **Fix the actual problem the owner senses by upgrading the layers
> ON TOP of ingestion**, in this order of leverage:
> 1. **Classification** — merchant normalization + a real enrichment provider (Ntropy behind
>    the existing interface, or an LLM provider), replacing keyword rules (L2/L3). *Highest ROI.*
> 2. **Trajectory** — add trend + cash-flow projection over the profile (L4).
> 3. **MCP — build finance-tracker's OWN read-first MCP server** exposing transactions,
>    profile, and recommendations, so the app's data/tools are agent-analyzable. This is the
>    part of the MCP question that pays off. **Do NOT replace Plaid ingestion with an MCP
>    consumer** — that's effort without capability today.
> 4. **Existing-card awareness** via Plaid Liabilities (defer Method).

MCP is **complementary, not a replacement**: it's the *analysis/interface* upgrade, while Plaid
remains the *data-acquisition* layer.

---

## 5. Product evolution — phased plan (backend → frontend)

Each phase is independently shippable and ordered by leverage toward the goal. Phase 0 unblocks
data; 1–2 fix classification (the #1 dependency); 3 adds trajectory; 4 is the MCP surface; 5
deepens card data & recommendations. Existing open issues are referenced where they belong.

### Phase 0 — Unblock real data (ops, not code)
- **Backend:** owner provisions production Plaid keys; register `redirect_uri` for OAuth banks
  (Chase/BofA/CapOne — issue #18 already handled the code path); run the live link→exchange→sync
  loop once (owner-local step, `research/5.md` harness).
- **Frontend:** ensure the Plaid Link flow surfaces `ITEM_LOGIN_REQUIRED` re-link.
- **Fix known corruption first:** close **#203** (PDF LLM sign inversion) so imported data is trustworthy.
- **Acceptance:** real `Account` + `Transaction` rows from a live bank; a PDF credit-card
  statement imports with correct signs.

### Phase 1 — Merchant normalization (backend)
- **Change:** a `normalize_merchant()` step before enrichment that strips processor prefixes
  (`SQ *`, `TST*`, `SP `, `PAYPAL *`, `POS `), trailing store numbers/cities, and casing —
  producing a stable `normalized_merchant`. Shared by both ingest paths (like `apply_enrichment`).
- **Why first:** every downstream signal (keyword rules, enrichment vendors, `top_merchants`,
  dedup quality) improves for free once merchants collapse correctly (L3).
- **Acceptance:** `SQ *COFFEE #123 SF` and `TST* Coffee Bar` normalize to a single stable
  merchant; `top_merchants` stops fragmenting; unit tests over a prefix corpus.

### Phase 2 — Classification beyond keyword rules (backend) — *highest ROI*
- **Change:** implement a real `EnrichmentProvider` behind the existing interface (no caller
  changes — `apply.py` already swaps by `FT_ENRICHMENT_PROVIDER`). Two candidate providers:
  - **`NtropyProvider`** — batch API over stored txns; map its taxonomy via
    `map_to_internal`; persist `category_confidence` + `enriched_at` (nullable migration per
    `research/11.md` slice 2). Free 2,000-txn tier to validate dining accuracy.
  - **`LLMProvider`** — Anthropic classification with a few-shot prompt over the 10-way
    taxonomy + confidence, batched; reuses the `anthropic` client already used for PDF import.
- **Backfill:** a one-shot `enrich_existing` job for `enriched_at IS NULL` rows (fixes L8).
- **Frontend:** the recategorize UI already exists (#109); surface `category_confidence` and let
  low-confidence rows be corrected — those corrections become training/rule signal (Copilot's moat).
- **Acceptance:** the `other` bucket shrinks materially on real data; category assignments carry
  a confidence; a measured dining-precision lift vs the keyword baseline on a labeled sample.

### Phase 3 — Financial-trajectory analysis (backend → frontend)
- **Backend:** extend spending intelligence beyond the single-window snapshot:
  - **Category trend series** — monthly `category_breakdown` history (month-over-month deltas).
  - **Recurring-commitment detection** — cadence detection over `normalized_merchant`
    (subscriptions, rent) → feeds both "flow improvement" and duplicate-subscription flags (à la Ramp).
  - **Cash-flow projection** — a simple, explainable forward projection (income cadence −
    recurring − category run-rates) → "projected discretionary next month." Keep it
    recommendation-serving, not a general forecaster (Range is the north-star for depth; scope
    per Q1).
- **Frontend:** trend charts per category, a projection tile, a "trending up/down" badge that
  the recommender cites ("dining is trending +15%/qtr → dining multiplier matters more").
- **Acceptance:** given ≥3 months of data, the app shows per-category trend + a next-month
  projection, and a recommendation rationale references a trend.

### Phase 4 — finance-tracker MCP server (backend → frontend/clients) — *the MCP bet*
- **Backend:** a **read-first MCP server** (Python MCP SDK) exposing existing services as tools:
  `list_accounts`, `query_transactions(filters)`, `get_spending_profile`,
  `get_category_trends`, `recommend_next_card`, `analyze_portfolio`, `project_cashflow`.
  - **Security:** per-user OAuth-scoped access; the server holds DB/vendor credentials, the
    model never does; **read-only** (no write tools in v1) — matching the Ramp/Mercury/Monarch
    convention and the MCP spec's resource-server guidance.
  - **Transport:** Streamable HTTP (multi-user) with the option of stdio for the owner's local
    Claude Desktop/Code.
  - **Spike first** (small, time-boxed) to prove one tool (`get_spending_profile`) end-to-end
    against Claude before building the full surface.
- **Frontend/clients:** documented connection for Claude Desktop/Code; optionally the app's own
  chat (`api/chat.py`) consumes the same tools internally so in-app Q&A and external agents
  share one tool contract.
- **Acceptance:** from Claude, the owner can ask "how much did I spend on dining last quarter and
  which card should I have used" and get a correct, tool-backed answer over their real data.

### Phase 5 — Deeper card data & recommendation/flow surface (backend → frontend)
- **Backend:**
  - **Existing-card awareness** — Plaid Liabilities behind a `LiabilitiesProvider` +
    `held_card` model + product-matcher against `credit-card-bonuses-api` with manual-confirm
    fallback (`research/12.md` plan; defer Method). Feeds the held-vs-new comparison.
  - **Richer card earn** — extend `card_category_rates.json` coverage; model rotating 5%
    categories, portal rates, and spend caps (the README's named follow-ups); owner-verify the
    curated rates (`_meta.provenance`). Continue sourcing base metadata from the open-source
    **`credit-card-bonuses-api`**.
  - Close standing rec-engine value bugs (#201, #202, #196) so dollar rationales are correct.
- **Frontend:** per-category "use THIS card" assignments (#177/#183), multi-card portfolio
  (#185), and a flow-improvement view that combines trajectory (Phase 3) with card assignment
  ("you're leaving ~$X/yr on dining; use card Y and consider applying for Z").
- **Acceptance:** the app recommends a per-category card set with correct first-year-value
  dollars, aware of the user's held cards, and ties the advice to their spending trajectory.

### Where new APIs / tools / MCP servers map (backend → frontend)

| Layer | New/changed thing | Serves |
|---|---|---|
| Ingestion | Plaid production unblock (P0); Plaid Liabilities provider (P5) | real data; held-card awareness |
| Normalize | `normalize_merchant()` step (P1) | classification, dedup, merchants |
| Classify | `NtropyProvider`/`LLMProvider` + backfill + confidence (P2) | classification accuracy (goal #1) |
| Analyze | trend series + recurring detection + cash-flow projection (P3) | trajectory (goal #2) |
| Interface | **finance-tracker MCP server** (P4) | agent-analyzable data/tools (owner's MCP question) |
| Recommend | held-card model + richer card rates + value-bug fixes (P5) | flow improvement (goal #3) |

---

## QUESTIONS FOR HUMAN

1. **Trajectory scope (Q1, blocks P3).** `PRODUCT.md` lists forecasting as *out of scope*. This
   plan re-introduces **recommendation-serving** trajectory (category trends + a light cash-flow
   projection) — *not* a general Range-style planner. Confirm this bounded scope, or hold P3.
2. **Classification provider (blocks P2).** Preferred fix for categorization: (a) **Ntropy**
   (2,000-txn free tier, hosted — merchant strings + amounts leave our infra), (b) an
   **Anthropic LLM provider** (reuses the key we already use for PDF import; also hosted), or
   (c) stay rules-only for now? `research/11.md` recommended Ntropy-first.
3. **Data-privacy posture (blocks P2 for any hosted provider).** Both Ntropy and an LLM provider
   send raw merchant strings + amounts off-infra. Acceptable for this personal app, or must
   enrichment stay on-device/in-repo (which rules out both and keeps us on keyword rules)?
4. **MCP investment (blocks P4).** Approve building finance-tracker's **own read-first MCP
   server** (recommended) as the MCP answer — vs. the (not-recommended) path of consuming a
   Plaid-wrapping MCP for ingestion? A small time-boxed **spike** (one tool → Claude) is the
   proposed first step.
5. **The named competitor (informational).** Did "error.finance / Arrowout" mean **Arta Finance**
   (AI wealth mgmt — most likely) or **Arro** (credit-builder card)? No product exists with that
   literal name; confirming sharpens the competitive framing.
6. **Existing-card source (blocks P5 held-card work).** Confirm **Plaid Liabilities for MVP**
   (reuse the existing item) and defer **Method Financial** to a later phase, per `research/12.md`?
7. **Card-rate ground truth (P5).** `card_category_rates.json` is agent-curated and
   "pending owner verification." OK to keep using it as-is meanwhile, and would you verify the
   curated rates before we treat them as ground truth?

---

_Research + planning only; no application code or logic changed. Sources cited inline. Prior
repo research cross-referenced: `docs/agent/research/{11,12,5,8,38}.md`, `docs/prd/*.md`, and
open issues (#11, #12, #18, #22, #38, #52, #109, #177, #183, #185, #196, #201, #202, #203)._
