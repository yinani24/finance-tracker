# PRD — Credit-Score Sourcing and a Locally-Derived Band Proxy

- **Status:** RESEARCH (agent-authored, 2026-08-02). Investigates whether the credit-score band
  that drives approval-odds ranking can be obtained programmatically instead of being typed in by
  the user. **No code changes.** Ends with `## QUESTIONS FOR HUMAN`.
- **Scope trigger:** #226 shipped `credit_profile` → approval-odds ranking end to end
  (`apps/api/app/services/approval_odds.py`). Ranking is now
  *expected value = first-year value × approval odds*, and the odds term is keyed off a
  hand-entered band. That input is the weakest link in the ranking.
- **Depends on / constrains:** `docs/prd/recommendation-engine.md` (the value half of the
  product), `docs/prd/plaid-integration.md` (where the proxy's inputs would come from).

---

## Problem

`approval_odds.py` maps a coarse band (`poor` / `fair` / `good` / `excellent`) onto a tier × band
odds matrix. The band comes from one `<select>` in
`apps/web/src/app/(app)/settings/page.tsx:212`, persisted as
`UserPreferences.credit_score_band` (`apps/api/app/models/user.py:33`).

Three problems with that:

1. **Most users don't know their band**, and the ones who do often quote a VantageScore from a
   free app while issuers underwrite on FICO — different models, different numbers.
2. **It's optional, so it's usually empty.** With no band, `estimate_approval_odds` returns `1.0`
   for every card and the whole expected-value ranking silently degrades back to raw first-year
   value — the exact failure mode #226 existed to fix.
3. **Self-reported bands are optimistic.** Nothing validates the input.

So: can we source the score (or a defensible proxy) programmatically?

---

## Constraints this must satisfy

These are non-negotiable and they eliminate most of the option space before cost is even
considered.

| # | Constraint | Consequence |
|---|---|---|
| C1 | **Nothing is persisted.** Moving to a client-side-only session model; financial data lives in browser memory and dies on tab close. | Any credit lookup is a **server-side pass-through only** — no DB write, no cache, no queue. A score fetched at 10:00 is gone at 10:01. |
| C2 | **No PII in logs.** | Rules out request/response logging on any credit call, and rules out most off-the-shelf APM auto-instrumentation on that route. |
| C3 | **FCRA compliance.** US consumer credit data is FCRA-regulated. | See "FCRA analysis" below — this is the binding constraint, not cost. |
| C4 | **Free / self-serve / no contract.** | Anything requiring a signed agreement, FCRA permissible-purpose certification, or enterprise onboarding is *effectively unavailable* and is marked ❌ below regardless of technical fit. |

A subtlety worth stating plainly: **C1 and C3 pull in opposite directions.** FCRA compliance
generally requires you to *retain* records — of the consumer's authorization, of the permissible
purpose certified, and of what was disclosed — precisely so disputes can be adjudicated later. A
system architected to persist nothing is architecturally hostile to being an FCRA-regulated data
user. That tension is itself an argument for never touching bureau data at all.

---

## Option comparison

Verdict key: ❌ unavailable to a solo dev · ⚠️ possible but heavy · ✅ viable now

| Option | What it returns | Who can actually sign up | Cost | Compliance burden | Verdict |
|---|---|---|---|---|---|
| **Equifax Consumer Engagement Suite** | **VantageScore** (not FICO), current + historical, 1- or 3-bureau; credit reports w/ utilization + avg account age attributes | Sandbox: anyone. **Production: credentialing docs + separately executed written agreement + member number** | Sandbox free & unmetered; production unpublished | Full end-user credentialing; on-site inspection | ❌ (sandbox ✅ for dev) |
| **Experian Developer Portal** | Mostly business-info/identity APIs self-serve; **consumer credit products sit behind "Request Access"** | Sandbox self-serve "in minutes"; UAT/prod need subscription + manual verification | Unpublished | Vetting happens off-portal | ❌ for consumer credit |
| **Experian Connect** | Consumer-permissioned report + **VantageScore 4.0**; soft pull | **Lead form only.** No self-serve, no public sandbox | Unpublished | Recipient accepts FCRA "Notice to Users" obligations | ❌ |
| **Experian Partner Solutions** | Best data on this list — **both FICO and VantageScore**, score tracker + simulator, white-label | Sales only ("business inquiries only") | Unpublished | Enterprise | ❌ |
| **TransUnion (US direct)** | — | **No public US developer portal.** TruVision is sales-led. (The CIBIL API Marketplace is India-only.) | — | Contract-first | ❌ |
| **Bloom Credit** | Tri-bureau reports + **FICO 10 or VantageScore 4**, monitoring webhooks, Metro 2 furnishment | **Not self-serve** — even sandbox needs issued credentials via onboarding | Tiered, unpublished; per-inquiry / per-enrolled-user | SOC 2 II, PCI DSS; Bloom holds bureau credentialing for you | ❌ (best fit *if* incorporated) |
| **Array** | Embeddable score widgets, My Credit Manager; tri-bureau, FICO via 2025 partnership | Marketing page claims "test with no signup" — **contradicted: `docs.array.com` is now password-walled** | Unpublished | Enterprise; flows down | ❌ (stale marketing) |
| **MeasureOne** | **No credit scores at all** — insurance/education/employment/income/tax verification only | 14-day free trial, genuinely open | ~$49/mo Basic, $250/mo Plus *(third-party listing, unverified)* | SOC 2; FCRA status not addressed | ❌ wrong data domain |
| **CRS Credit API / StitchCredit** | Broadest menu: tri-bureau soft+hard, **FICO, VantageScore & others**, JSON/XML/PDF | Sales-gated, but most small-customer-friendly posture; **public sandbox host + public B2C docs** | Unpublished. Comparable reseller publishes **from $100/mo + paid up-front site inspection** | "One contract, one vetting process" | ⚠️ most plausible paid route |
| **Method Financial** | Liabilities (balances, **credit limits**, APRs, due dates, payoff quotes) via soft pull, **plus tri-bureau VantageScore 3.0/4.0** + threshold subscriptions. No FICO | Requires **full entity verification** (phone + identity/KBA) before scores unlock; dashboard sandbox self-serve status unverified | Unpublished | Method is the credentialed party | ⚠️ best DX; worth a spike |
| **Plaid Liabilities** | **No score** — but APRs, balances, minimum payment, next due date, `is_overdue`, loan terms | **Anyone** — Sandbox, no extra permissions | Subscription fee per Item; per-unit rates unpublished. Free Sandbox + 200 live calls | None beyond existing Plaid terms | ✅ **the useful one** |
| **Plaid Check — LendScore** | **Proprietary 1–99 default-risk score, lender-facing**, with adverse-action reason codes. Not FICO, not VantageScore | ❌ **Sandbox not granted by default**; sales required, Beta needs per-module enablement | Unpublished | Plaid Check is a **registered CRA**; permissible-purpose certification | ❌ |
| **MX** | **No credit product exists at all** | Enterprise sales | Unpublished | — | ❌ |
| **Finicity / Mastercard Open Banking** | **Proprietary two-digit Payment Risk Score** (missed payment in 1–180 days) + 24-mo cash-flow attributes. Not a bureau score | Free dev account + **self-serve "Test Drive" sandbox**; production needs Mastercard contract | Unpublished | Finicity is a **registered CRA** | ⚠️ sandbox only |
| **Credit Karma / Chase Credit Journey / Amex MyCredit Guide / Discover Scorecard / CreditWise** | Real consumer scores (VantageScore 3.0 or **FICO 8**) — but **no public API exists for any of them** | N/A | Free to consumer | Scraping/credential-sharing = ToS breach + security disaster | ❌ never |
| **Locally-derived band proxy** | A coarse band + confidence, computed in-browser from data we already hold | **Us. Today.** | $0 | **Zero** — no PII leaves the device, no CRA, no FCRA user status | ✅ **recommended** |

---

## FCRA analysis

**The gate is not cost — it is [15 U.S.C. §1681b](https://www.ftc.gov/system/files/documents/statutes/fair-credit-reporting-act/545a_fair-credit-reporting-act-0918.pdf) (FCRA §604).**

- **§604(a)(2)** lets a CRA furnish a report *"in accordance with the written instructions of the
  consumer to whom it relates."* This is the consumer-permissioned pathway, and it is a genuine,
  bona fide permissible purpose. It is what every vendor in the table above runs on.
- **§604(f)** is the part that stops us: no person may *obtain* a consumer report unless they have
  **certified to the CRA** the permissible purpose and that the report will not be used for any
  other purpose. **There is no self-serve certification.** It requires a legal entity and a
  contract.
- **§607(a)** obliges the CRA to maintain reasonable procedures to verify the identity and intended
  use of prospective users. This is the statutory root of the vetting and on-site inspection
  regime — the bureaus are discharging their own legal duty when they inspect you.
- **§607(e)** requires resellers to disclose the end user's identity and each permissible purpose.

**Conclusion on §604(a)(2): legally yes, operationally no.** The consumer's consent removes the
*legal* barrier; it does nothing about the *commercial* one. §604(a)(2) describes what the CRA may
do — it creates no obligation for any CRA to contract with us, and §§604(f)/607(a) affirmatively
require them to vet and contract with us first. Every provider researched treats consumer consent
as necessary but not sufficient.

**Two further risks that argue for staying out entirely:**

1. **We could become a CRA ourselves.** By aggregating and re-communicating consumer credit
   information, an app can meet the definition of a consumer reporting agency, inheriting §§607/609/611
   duties — disclosure, dispute resolution, reasonable accuracy procedures. The CFPB's
   [FCRA examination procedures](https://files.consumerfinance.gov/f/documents/102012_cfpb_fair-credit-reporting-act-fcra_procedures.pdf)
   note that holding consumer information *"could constitute a consumer report and cause the
   institution to become a consumer reporting agency."* Displaying a score only back to the
   consumer who generated it is probably on the safe side of that line — **probably is not a
   standard to build on without counsel.**
2. **Identity matching is itself regulated.** The CFPB's 2022 advisory opinions
   ([87 FR 41042](https://www.federalregister.gov/documents/2022/07/12/2022-14823/fair-credit-reporting-permissible-purposes-for-furnishing-using-and-obtaining-consumer-reports))
   hold that permissible purpose is **consumer-specific**, and that **name-only matching can itself
   violate §604** — disclaimers do not cure it. Any real integration would therefore have to collect
   SSN-last-4 + DOB + address and run KBA. **That is strictly more PII than we hold today**, which
   is the opposite of the product's privacy direction.

### The on-site inspection

Worth calling out because it is the concrete thing that ends this for a solo developer. Bureaus
have required a **third-party physical on-site inspection since 2003**. The inspector verifies the
business physically exists at the stated address, checks permissible use, and photographs visible
physical security — shredders, lockable files, password-protected machines. It happens wherever
consumer reports are received, managed and stored, and it is **billed to you up front**. A
residential address is the most common rejection point, and the photograph requirement makes it
non-fakeable.

*(E&O insurance is widely repeated in practitioner discussion as a requirement. It could not be
confirmed in any primary bureau or regulatory source — the FCRA does not impose it. Treat it as a
contract-specific term, not a legal mandate.)*

### Section 1033 / open banking — do not plan around it

- Final rule issued Oct 2024; **never took effect.**
- July 2025: CFPB told the court it considers its own rule **unlawful and that it should be
  vacated**; court stayed it.
- Aug 2025: CFPB published an ANPRM reopening the rulemaking, including whether banks may **charge**
  for data access.
- The April 1, 2026 first compliance date passed with the rule still enjoined and under
  reconsideration; the rewrite is still pending as of mid-2026.

**Even fully in force, 1033 covers deposit/transaction/card data held by financial institutions — it
has never covered credit bureau files.** It would not have produced a score. Irrelevant to this
problem.

---

## PII and privacy analysis

**GLBA is the sleeper issue.** The FTC is the primary GLBA regulator for non-bank financial
institutions, and the definition reaches fintech and SaaS firms handling consumer financial data.
Under the amended **Safeguards Rule** (in force since June 2023, breach-notification provisions
fully enforced from **13 May 2024**), a covered institution must maintain a written information
security program with a designated qualified individual, risk assessments, and administrative /
technical / physical safeguards — and must **report security events affecting 500+ consumers to the
FTC within 30 days**.

Pulling bureau data would make that framework unambiguously ours to own, with a solo developer as
the "qualified individual." Declining to pull it keeps the question far simpler.

**Against constraint C1/C2, if a pass-through were ever built, the non-negotiables would be:**

- Score is fetched, mapped to a band, and returned in the same request. **Never written to
  Postgres, Redis, or any queue.** The `credit_score_band` column would need to *stay* the only
  credit artifact, and even it moves to session memory under the client-side-only model.
- **Route-level logging suppression** — no request/response bodies, no structured-log fields
  carrying SSN4/DOB/score. Default APM auto-instrumentation must be disabled on that path
  specifically; this is easy to get wrong and impossible to detect after the fact.
- The raw score never reaches the browser as a number if a band is sufficient — **return the band,
  not the score.** Minimising what crosses the wire is the cheapest control available.
- No third-party frontend scripts on any page that renders credit data.

**The proxy approach sidesteps every one of these**, because the computation happens on data the
user has already given us for other reasons, and the derived band never leaves the device.

---

## Aggregators — what they actually sell

**None of Plaid, MX, or Finicity will give a consumer their FICO or VantageScore.** Every "score"
they sell is a **proprietary, lender-facing risk score**, not a bureau score. This is the single
most commonly mistaken point in this space, so being precise matters:

- **Plaid Check is a registered CRA** — a separate legal entity from Plaid Inc., specifically so
  FCRA-regulated products live apart from the plumbing. **LendScore** is a **1–99 default-risk
  score** with adverse-action reason codes, built from cash-flow and Plaid-network behaviour. It is
  Beta, and **Sandbox access is not granted by default** — the docs say to contact sales. A solo dev
  cannot even sandbox it. Confirming the point from the other direction: Plaid's own consumer
  disclosure says the Plaid Check file *"does not impact your traditional credit score. Instead, our
  report works alongside it."* If a consumer score existed, it would be in the consumer's own file.
  It isn't.
- **Plaid Liabilities is self-serve, Sandbox-testable, and needs no extra permissions** — and is the
  genuinely useful product here (see the proxy spec).
- **Plaid Income is explicitly non-CRA** (*"Income is a product of Plaid Inc., which is not a
  consumer reporting agency"*). Operational trap: it **cannot share a Link flow with Plaid CRA
  products**.
- The June 2025 **Plaid–Experian partnership** flows Plaid cash-flow data **into** Experian's
  Cashflow Score. Data goes in, bureau scores do not come out. It is not a FICO pipe.
- **MX has no credit-score product whatsoever** — the entire published API surface is aggregation,
  enrichment, consent, and reporting. Dead end; don't spend time here.
- **Finicity is also a registered CRA.** Mastercard's Credit Risk Scoring returns a **two-digit
  Payment Risk Score** (likelihood of a missed payment within 1–180 days). Mastercard is the most
  permissive of the three for exploration — a free developer account gets a self-serve **Test Drive**
  sandbox with a public OpenAPI spec — but production requires a Mastercard commercial contract.

**The pattern is structural, not a rate limit to route around.** These are lender-side underwriting
inputs, priced and contracted as such, because furnishing a consumer report obliges the recipient to
certify a permissible purpose under §1681b. Sales gating *is* how Plaid Check and Finicity discharge
that duty.

---

## Free consumer sources — and why we will not touch them

Confirmed: **no official public API or developer program exists for any of them.**

| Service | Score shown | Bureau | Public API? |
|---|---|---|---|
| Credit Karma (Intuit) | VantageScore 3.0 | TransUnion + Equifax | ❌ none |
| Chase Credit Journey | VantageScore 3.0 | Experian | ❌ none |
| Amex MyCredit Guide | **FICO Score 8** | Experian | ❌ none |
| Discover Credit Scorecard | **FICO Score 8** | TransUnion | ❌ none |
| Capital One CreditWise | **FICO Score 8** (moved off VantageScore in 2025) | TransUnion | ❌ none |

**This is contractual prohibition upstream, not neglect.** These are bureau-licensed score displays.
The licences permit display *to the consumer, in that issuer's own channel*. Redistributing the
score through an API to a third party would breach the licence. There is no business path to an
official API here, so none will appear.

### Do not scrape, and do not ask for credentials

**The unofficial tooling is dead.** The only two credit-score scrapers findable on GitHub —
`ziplokk1/credit-karma-scraper` (14★) and `natecj/creditkarma-php` (3★) — were last pushed in
**2017** and **2013** respectively. The only *actively maintained* Credit Karma projects export
**transactions, not scores**, and all converged on **browser extensions running in the user's own
authenticated session** rather than headless scripted logins. For Chase, Amex, Discover and Capital
One, essentially nothing exists — bank-grade auth with device fingerprinting and mandatory MFA makes
it unsustainable.

**Terms of Service — two clauses are individually dispositive:**

- **Credit Karma:** *"You must keep your password confidential, **you must not share it and you may
  not allow anyone else to log into our Services as you**."* That kills any credential-storage
  architecture outright, before any other analysis. Their terms also bar reverse engineering, which
  reaches their internal GraphQL endpoints.
- **Chase:** the Digital Services Agreement expressly addresses third-party aggregators and agents,
  **explicitly including AI agents**, and prohibits them from using Chase platforms to access
  credentials or the Services once logged in. Chase enforces this — it has cut off fintechs using
  stored passwords.
- **Amex** bars any "robot", "spider", or automatic device — *"or any manual process"* — to monitor,
  scrape, or copy pages. That last phrase forecloses the "but a human clicked it" defence.

**The CFAA case law does not help us.** *Van Buren* (2021) narrowed "exceeds authorized access" to a
gates-up-or-down test, and *hiQ v. LinkedIn* protected scraping of **pages "that do not require the
creation of an account for access."** Credit scores are never on a public page — all five targets
require authentication, and under *Van Buren* a login wall is the paradigm case of a gate. **hiQ
falls on the wrong side of its own holding for this use case.**

And the usual citation of *hiQ* omits how it ended: in December 2022 hiQ accepted a **$500,000
consent judgment** covering breach of contract, **a CFAA violation "based on hiQ's direct access to
password-protected pages,"** trespass to chattels, and spoliation — plus a permanent injunction to
cease scraping and **destroy all derived code and data**. hiQ ceased operations. **Winning the CFAA
argument is not winning**; the courts were explicit that the CFAA analysis says nothing about
contract, trespass, misappropriation, or privacy claims.

**Regulatory direction:** CFPB Director Chopra: *"Screen scraping is risky, since it can involve
unencrypted credential sharing and massive overcollection of data."* The 1033 final rule prohibited
authorized third parties from using consumer-interface credentials at all. That rule is currently
**enjoined** (E.D. Ky.) and under CFPB reconsideration — but **do not misread the injunction as a
green light.** It restrains the CFPB from enforcing against *banks*; it grants us nothing. The
private-ordering pressure is unaffected and runs the other way.

**The security case ends it independently of law.** There is no read-only "score" scope: Credit
Karma credentials are Intuit SSO (reaching TurboTax and full tax history), and issuer credentials
are **money-movement credentials**. Automating past MFA means persisting session or device-trust
tokens, turning the service into a standing MFA bypass. Every bank agreement disclaims
responsibility once a customer shares credentials, so if we are the leak vector the fraud loss lands
on our user. **This is categorically off the table.**

---

## Spec — locally-derived credit-band proxy (recommended)

### What we actually have today (verified against the codebase, not assumed)

| Model | Fields |
|---|---|
| `Transaction` | `occurred_on`, `posted_at`, `amount`, `merchant`, `normalized_merchant`, `category`, `is_income`, `is_savings`, `account_id`, `source` |
| `Account` | `name`, `type`, `institution_name`, `balance`, `currency`, `last_synced_at`, `created_at` |
| `Card` | `name`, `network`, `issuer`, `annual_fee`, `rewards_config_json` |

### What we are missing — and this is the headline finding

**The proxy is not currently computable.** Four of the five FICO factors need inputs we do not
store. Verified by grep, not inferred:

1. **No credit limit exists anywhere in the schema.** `grep -rn "credit_limit\|creditLimit"` over
   `apps/` returns **zero hits**. `Account` has `balance` only. **Utilization — 30% of FICO, and
   by far our strongest available signal — cannot be computed today.**
2. **No account open date.** `Account.created_at` is the row-insert timestamp, not the tradeline
   open date. Length of credit history (15%) is unavailable.
3. **No statement due date, minimum payment, or overdue flag.** Worse, this is discarded
   deliberately: the extraction prompt at `apps/api/app/services/statement_pdf.py:54` instructs the
   model to ignore *"payment-due/minimum lines."*
4. **No inquiry or new-account data.** `recent_applications` on `ApprovalProfile` is user-entered.

**The unlock is small and cheap.** `apps/api/app/services/plaid_service.py:61` requests
`products=[Products("transactions")]` only. Per
[Plaid's liabilities docs](https://plaid.com/docs/api/products/liabilities/):

- **`accounts[].balances.limit` carries the credit limit for credit-type accounts** — it is **not**
  part of the liabilities product. We are very likely **already receiving it and throwing it
  away.** Persisting (or, under the session model, holding in memory) that one field makes
  utilization computable with no new Plaid product, no new scope, and no new consent.
- Adding the **`liabilities`** product then yields `last_payment_amount`, `last_payment_date`,
  `last_statement_balance`, `last_statement_issue_date`, `minimum_payment_amount`,
  `next_payment_due_date`, **`is_overdue`**, and `aprs[]` — turning payment history from "weakly
  inferred from `AUTOMATIC PAYMENT` text matching" into **directly observed**.

That single change moves us from *one* weakly-derivable factor to roughly **70% of the FICO weight
observed directly**.

### Factor coverage after the unlock

| Factor | FICO | VS 4.0 | Computable? |
|---|---|---|---|
| Payment history | 35% | 41% | **Partial** — card payments observable; blind to non-card tradelines, collections, public records |
| Utilization / amounts owed | 30% | 28% | **Fully** — per-card and aggregate, and *trended* |
| Length of credit history | 15% | 20% (with mix) | **Partial** — bounded by data window; systematically under-estimates |
| New credit | 10% | 11% | **Weak** — new accounts visible, hard inquiries invisible |
| Credit mix | 10% | (in Age/Mix) | **Partial** — depends on Plaid coverage |

Blended weighting, defensible across both models: **payment ~38%, utilization+balances ~29%,
age+mix ~22%, new credit ~11%.**

### Banding rules

Bands use **FICO's canonical cutoffs** (not VantageScore's — issuers publish approval criteria
against FICO, and users have seen these elsewhere): Exceptional 800+, Very Good 740–799,
Good 670–739, Fair 580–669, Poor <580.

**Step 1 — utilization base band.** Calibrated directly against Experian's Q3 2024 average
utilization by band, which is steeply monotonic and is the best single-variable classifier
available:

| Aggregate utilization | Base band | (Experian observed avg for that band) |
|---|---|---|
| ≤ 10% | Exceptional | 6–7.7% |
| ≤ 20% | Very Good | 15.2% |
| ≤ 45% | Good | 38.6% |
| ≤ 70% | Fair | 61.4% |
| > 70% | Poor | 80.7% |

> **Read this table in the right direction.** It reports *the average utilization of people at
> score X*, not *the score you get at utilization X*. It is correlational and partly
> reverse-causal. Hence steps 2–3.

**Step 2 — payment history as a hard ceiling, never a subtraction.** FICO's own simulations show
the penalty for a late payment is *asymmetric and starting-score-dependent* — a 30-day late costs a
793 file 63–83 points but a 607 file only 17–37. No additive model captures that; a ceiling does,
and it is far easier to explain to a user:

- any 30-day-late signal in the last 12 months → **cap at Good**
- any 90+-day late, or `is_overdue` true → **cap at Fair**
- ≥ 2 late signals in 12 months → **cap at Fair**

Late signals: `liabilities.is_overdue`; a `next_payment_due_date` passing with no payment
transaction; or a late-fee line in transactions. Text-matching `AUTOMATIC PAYMENT` is a *positive*
signal only — its absence proves nothing (users pay by other means), so it must never push a band
down.

**Step 3 — thin-file gate.** Prevents a 3-month-old file at 5% utilization from reading as
Exceptional. FICO 800+ holders carry a **median average open account age of ~10.7 years**:

- average account age < 2 years, or fewer than 2 revolving accounts → **cap at Good**
- < 5 years → **cap at Very Good**

**Step 4 — velocity.** ≥ 3 accounts opened in 24 months → drop one band. (This overlaps the
existing Chase 5/24 rule in `approval_odds.py`, which already handles issuer-specific velocity —
keep them separate; 5/24 is an *issuer* rule, this is a *score* effect.)

**Step 5 — trended overlay (the genuine edge).** VantageScore 4.0 is the first generic model built
on trended data, and FICO 10T followed. We can compute the same attributes — 24-month utilization
slope, average and peak monthly utilization, payment as a % of balance. Most valuably, a
**revolver vs. transactor flag**: does the user pay the statement balance in full each cycle?
The bureaus had actual bankcard payment amounts for only **56% of loans** as of 2016. **We observe
them directly for every connected card.** A consistent transactor at moderate utilization should
be nudged up one band; a revolver on a rising balance slope nudged down.

**Step 6 — confidence, always.** Emit `high` / `medium` / `low` alongside the band, degrading
explicitly for: no limit data, < 6 months of history, only one card connected, no liabilities
product. **The UI must name which inputs are missing**, not just show a hedge.

### Calibration

Fit offline, ship static. `optbinning` (Apache 2.0) or `scorecardpy` (MIT) give monotonic binning
with WoE and a scorecard class. Neither runs in a browser — so fit **once**, offline, and ship the
resulting **bin edges and point allocations as a static JSON table** in the JS bundle. Explainable,
monotonic, zero runtime dependency.

Use **Lending Club** as the calibration set: it is the one accessible dataset carrying an actual
FICO value (`fico_range_low` / `fico_range_high`) *as a feature*, alongside `revol_util`,
`revol_bal`, `open_acc`, `total_acc`, `earliest_cr_line`, `delinq_2yrs`, `inq_last_6mths`. Regress
FICO as the **label** onto the rest.

> **The distinction that matters:** UCI "Default of Credit Card Clients", Give Me Some Credit, and
> Home Credit all target **default**, not FICO. A PD model is not a score estimator. Use those only
> to sanity-check risk *ordering* — never to derive band cutoffs.

Two biases to correct for: Lending Club is a self-selected personal-loan applicant pool, and the
accepted-loans file is post-approval-filtered, so low bands are under-represented. **Reweight
against the national distribution** before trusting cutoffs, then sanity-check that our output
distribution roughly matches it: 23.0% Exceptional, 27.5% Very Good, 20.4% Good, 14.9% Fair,
14.2% Poor, mean ≈ 713.

### Integration

The seam already exists and is clean. `ApprovalProfile` (`approval_odds.py`) takes `score_band` and
`recent_applications`; `card_recommendation.py:302` accepts it as an optional argument and
`:435` applies it. The proxy simply becomes a **second source** for that struct. Suggested
precedence: **user-entered band wins** (they may know their real FICO) → proxy fills the gap →
neither, and behaviour is unchanged at odds `1.0`. Recommend adding a `source` field
(`"user"` / `"proxy"`) so the UI can attribute the estimate honestly.

### Honest limitations

This must not be oversold, in the doc or the UI.

- **It is not a credit score, and it is not from a bureau.** Output a **band**, never a three-digit
  number — users anchor hard on numbers, and any number we produce would be wrong.
- **Structurally blind to:** hard inquiries (~10–11% of both models), collections, public records
  and bankruptcies, non-card tradelines not in Plaid (student loans, mortgage, auto), closed-account
  history, and true file age.
- **Weakest exactly where a user is most likely to have a surprise.** A clean-looking card profile
  masking a charged-off student loan will read far too high. Derogatories are invisible to us and
  are the single biggest driver of low scores.
- **Better for thin files than thick ones.** FinRegLab's work is the relevant literature, and its
  honest reading is that cash-flow data is *complementary* to bureau data — at least as predictive
  when no score exists, and additive on top of one. **No published study reconstructs a FICO score
  from cash-flow data alone.** Our proxy will be meaningfully weaker than a real score for a
  thick-file user.
- **Only sees connected accounts.** A user with five cards who connects one gets a proxy computed on
  20% of their revolving credit — and aggregate utilization will be wrong, not merely incomplete.
- **The utilization table is correlational**, as flagged above.
- **Statement-timing skew:** issuers report the statement balance, so a user who pays in full after
  the statement cuts still shows high reported utilization. Prefer `last_statement_balance` over
  live `balance` when available.

Given all of the above, the proxy should be positioned as *"based on the accounts you've connected,
your profile looks like the **Good** range"* with an obvious correction affordance — never as a
score, and never with false precision.

---

## Recommendation

**Build the local proxy. Do not integrate any credit-score API.**

1. **No self-serve path to real scores exists for a solo developer.** Every route ends at FCRA
   §604(f) certification, an executed contract, and a photographed on-site inspection. This is a
   legal-structural wall, not a pricing problem, and it will not yield to effort.
2. **Bureau data is actively hostile to this product's architecture.** It would require *more* PII
   (SSN4 + DOB + KBA) to satisfy the CFPB's name-only-matching guidance, likely pull us into GLBA
   Safeguards Rule scope, and raise a real question about becoming a CRA — all while the product is
   moving toward persisting nothing.
3. **The proxy needs no third party and no new consent.** It runs on data the user already gave us
   for other reasons, and the derived band never leaves the device.

**Sequenced plan:**

- **Step 0 (do this first, it is nearly free).** Capture `accounts[].balances.limit`, which we are
  probably already receiving. This alone makes utilization — the strongest signal — computable, and
  a **utilization-only proxy already beats an empty `<select>`**, which is the real status quo.
- **Step 1.** Add the Plaid `liabilities` product for `is_overdue`, statement balances and payment
  dates → payment-history ceiling becomes observable rather than guessed.
- **Step 2.** Calibrate offline against Lending Club, ship static bin edges.
- **Step 3.** Add the trended/transactor overlay.
- **Not now:** revisit a paid API only if the product ever incorporates, gets a commercial address,
  and has a reason to need real scores. **CRS/StitchCredit** and **Method Financial** are the two
  worth a call at that point — Method especially, since its liabilities data is useful to this
  product independent of scores.

**Is the proxy good enough?** For its actual purpose — ranking cards by expected value — **yes.**
The odds matrix in `approval_odds.py` is already coarse (four bands, three tiers), so the proxy
only has to land in the right bucket, not predict a number. It will be right most of the time for
users who connect most of their cards, and it degrades honestly via the confidence signal. It is
**not** good enough to tell a user what their credit score is, and the product must never imply
that it does.

---

## Open-source libraries and datasets

**Libraries** — none run in a browser, so the pattern is *fit offline, ship a static JSON bin table*:

| Library | Licence | Notes |
|---|---|---|
| [optbinning](https://github.com/guillermo-navas-palencia/optbinning) | Apache 2.0 | Best maintained. Optimal/monotonic binning with constraints, WoE, full `Scorecard` class, counterfactual explanations |
| [scorecardpy](https://github.com/ShichenXie/scorecardpy) | MIT | Python port of R `scorecard`. WoE binning, IV, PSI |
| [skorecard](https://pypi.org/project/skorecard) | OSS | sklearn-compatible API built on optbinning |

**Datasets** — the critical distinction is that **almost all of these target default, not FICO**:

| Dataset | Carries a real FICO value? | Access |
|---|---|---|
| [Lending Club](https://www.kaggle.com/datasets/wordsforthewise/lending-club) | **Yes** — `fico_range_low`/`high` as a *feature* | Public (Kaggle mirror) |
| [Fannie Mae SF Loan Performance](https://capitalmarkets.fanniemae.com/credit-risk-transfer/single-family-credit-risk-transfer/fannie-mae-single-family-loan-performance-data) | **Yes** — score at acquisition | Free, registration required |
| [Freddie Mac SF Loan-Level](https://freddiemac.com/research/datasets/sf-loanlevel-dataset) | **Yes** — score at origination | Free, registration; **licence needed for commercial redistribution** |
| [UCI Default of Credit Card Clients](https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients) | No | CC BY 4.0 |
| [Give Me Some Credit](https://www.kaggle.com/c/give-me-some-credit) | No | Kaggle comp rules |
| [Home Credit Default Risk](https://www.kaggle.com/c/home-credit-default-risk) | No (normalised `EXT_SOURCE_*` only) | Kaggle comp rules |

Only the FICO-bearing three can be used *backwards* — FICO as the label — to build a genuine
score-approximation model rather than a PD model wearing a FICO costume. **Lending Club is the best
fit** for a card-focused proxy (it carries `revol_util`, `open_acc`, `earliest_cr_line`,
`delinq_2yrs`, `inq_last_6mths`); Fannie/Freddie are cleaner and far larger but mortgage-skewed with
fewer revolving attributes.

---

## Key sources

**FCRA / regulatory:** [15 U.S.C. §1681b (FCRA §604)](https://www.ftc.gov/system/files/documents/statutes/fair-credit-reporting-act/545a_fair-credit-reporting-act-0918.pdf) ·
[CFPB permissible-purpose advisory opinion, 87 FR 41042](https://www.federalregister.gov/documents/2022/07/12/2022-14823/fair-credit-reporting-permissible-purposes-for-furnishing-using-and-obtaining-consumer-reports) ·
[CFPB FCRA examination procedures](https://files.consumerfinance.gov/f/documents/102012_cfpb_fair-credit-reporting-act-fcra_procedures.pdf) ·
[Section 1033 enjoined and under reconsideration (Cozen, 2026)](https://www.cozen.com/news-resources/publications/2026/section-1033-compliance-date-open-banking-rule-enjoined-and-under-reconsideration) ·
[hiQ v. LinkedIn, 9th Cir. 2022](https://cdn.ca9.uscourts.gov/datastore/opinions/2022/04/18/17-16783.pdf) ·
[hiQ consent judgment analysis (Morgan Lewis)](https://www.morganlewis.com/blogs/sourcingatmorganlewis/2022/12/linkedin-v-hiq-landmark-data-scraping-suit-provides-guidance-to-data-scrapers-and-web-operators)

**Scoring models:** [myFICO — What's in your credit score](https://www.myfico.com/credit-education/whats-in-your-credit-score) ·
[myFICO — how credit actions impact scores](https://www.myfico.com/credit-education/faq/affects-of-credit-actions) ·
[VantageScore 4.0 User Guide (PDF)](https://cdn.vantagescore.com/uploads/2022/09/VantageScore-4.0-UserGuide_abr_Sep22.pdf) — Figure 13 carries the contribution percentages, which are **not** published on any VantageScore web page ·
[FICO High Achievers](https://www.fico.com/blogs/fico-score-high-achievers-age-only-factor)

**Empirical anchors:** [Experian — credit utilization by band](https://www.experian.com/blogs/ask-experian/credit-education/score-basics/credit-utilization-rate/) ·
[Experian 2025 Consumer Credit Review](https://www.experian.com/blogs/ask-experian/consumer-credit-review/) ·
[Experian — score range distribution](https://www.experian.com/blogs/ask-experian/infographic-what-are-the-different-scoring-ranges/)

**Cash-flow underwriting:** [FinRegLab 2019 — empirical research findings](https://finreglab.org/research/the-use-of-cash-flow-data-in-underwriting-credit-empirical-research-findings/) ·
[FinRegLab 2025 — ML & cash-flow data](https://finreglab.org/research/advancing-the-credit-ecosystem-machine-learning-cash-flow-data-in-consumer-underwriting/)

**Vendors:** [Plaid Liabilities](https://plaid.com/docs/api/products/liabilities/) ·
[Consumer Report by Plaid Check](https://plaid.com/docs/check/) ·
[Equifax developer portal](https://developer.equifax.com/) ·
[Experian developer portal](https://developer.experian.com/) ·
[Method Financial credit scores](https://docs.methodfi.com/guides/additional-products/credit-scores) ·
[Bloom Credit](https://bloomcredit.io/) ·
[CRS Credit API](https://crscreditapi.com/)

---

## QUESTIONS FOR HUMAN

1. **Is Step 0 approved?** Capturing `accounts[].balances.limit` — a field we are very likely already
   receiving from Plaid and discarding — is the difference between "utilization is uncomputable" and
   "we have the strongest single signal." Under the session-only model it would be held in memory,
   not persisted. **This is the one change that unblocks everything else, and it is nearly free.**
   Should it be filed as an issue now, independently of the rest?

2. **Do we add the Plaid `liabilities` product?** It converts payment history from guesswork to
   observation (`is_overdue`, statement balances, payment dates). Cost: a new billed subscription
   per Item, and users must re-authenticate through Link to grant the new scope. Is that re-consent
   friction acceptable, and is the recurring cost acceptable for a personal project?

3. **How should the proxy and the user's own input interact?** Proposed: user-entered band wins,
   proxy fills the gap. Alternative: show the proxy and ask the user to confirm or correct it — more
   accurate over time, but it puts a possibly-wrong estimate in front of the user unprompted. Which
   do you want?

4. **How visible should the proxy be?** Options: (a) fully internal, silently improving ranking;
   (b) shown as "based on your connected accounts, your profile looks like *Good*" with a correction
   affordance; (c) a full credit-health surface with factor breakdown. (c) is the most product, and
   the most risk of being read as a real score. **Recommend (b).**

5. **Is offline calibration against Lending Club worth the effort now**, or do we ship the
   hand-tuned rules in this doc first and calibrate only if they prove wrong? The heuristic bands
   here are defensible from published data on their own; calibration is a meaningful chunk of work
   for an uncertain accuracy gain at this coarseness.

6. **Do you want the statement PDF parser changed?** It currently discards payment-due and minimum
   lines by design (`statement_pdf.py:54`). Those lines are exactly the payment-history signal we
   lack for cards *not* connected via Plaid. Changing it widens coverage but adds parsing surface.

7. **Confirm the FCRA read is directionally right before any future API work.** This doc concludes
   we should never pull bureau data, so the question is moot today — but if that ever changes,
   whether the app becomes a CRA is a **question for counsel, not for an agent.** Flagging it so it
   is not treated as settled.

8. **Should `credit_score_band` be removed from the database now?** Under the client-side-only
   session model it should live in session memory, not `user_preferences`. This doc's
   recommendation makes that column's future ambiguous — is its removal in scope for the
   session-model migration, or tracked separately?
