# Finance Tracker

**Drop a credit card statement in. Find out which card you should have used.**

[Live app](https://web-kw97mkws8-yash-9893s-projects.vercel.app) · No account, no sign-up, nothing uploaded.

---

## Why this exists

I have five credit cards and I use one of them for almost everything.

That is the normal way to hold credit cards, and it is close to the worst way. Every card has categories where it earns well and categories where it earns nothing, and unless you keep the whole matrix in your head at the register, the card you reach for is the card in the front slot — not the card that pays.

The advice available for fixing this is bad. It is blog posts optimizing for affiliate payouts, forum threads that assume you already know what 5/24 means, and comparison sites that rank cards by whoever pays them most. None of it looks at what *you* actually spend. The information needed to decide well — earn rates, issuer application rules, what a point is genuinely worth in each program — exists, but it is scattered, partly folklore, and largely held by people who benefit from you not having it.

Points optimization has quietly become a game with rules, and the people who know the rules do dramatically better than the people who don't. That gap has little to do with income and everything to do with information. This project is an attempt to close it: take the rules, the card data and the application constraints, put them somewhere legible, and point them at your real spending rather than a hypothetical average consumer.

Then say plainly what you're leaving on the table.

## What it does

Drop a statement. Everything below is derived from it — no forms, no questionnaire, no account.

- **Reads the card out of the statement.** Issuer, product, credit limit, balance, last four. If it's printed on the page, it isn't a question worth asking you.
- **Categorizes spending and normalizes merchant names**, so four airline tickets are one airline rather than four ticket numbers.
- **Finds subscriptions by shape** — same payee, steady amount, regular cadence — rather than from a list of known services. Ordering from the same restaurant every Friday is not a subscription, and doesn't get counted as one.
- **Reads income from a bank statement**, projected from its actual pay cycle. Twice-monthly and fortnightly pay differ by two cheques a year and look identical by gap alone; they're told apart by where in the month the money lands.
- **Prices the gap per category** between what you earn now and the best card available, with points converted to what they actually redeem for — 5x in a currency worth half a cent is 2.5%, not 5%.
- **Ranks what to get next** by first-year value net of annual fee, weighted by realistic approval odds including issuer velocity rules like Chase's 5/24.

## Privacy

Statements are parsed **in your browser tab**. The file never leaves your device, nothing is written to a database, and closing the tab erases the session.

One exception, stated plainly: ranking cards needs the public card dataset, so the app sends **aggregates only** — average monthly spend and a category breakdown — to the API. No merchant names, no dates, no amounts, no account numbers, and nothing is stored. Everything else — parsing, spending profile, subscriptions, income, insights — runs with no backend at all, which is why the deployed site works without one.

## Running it

The web app is self-contained. The API is only needed for card ranking.

```bash
cd apps/web
npm install
npm run dev            # http://localhost:3000
```

```bash
cd apps/api
python -m venv .venv && .venv/bin/pip install -e ".[dev]"
cp .env.example .env.local
.venv/bin/uvicorn app.main:app --reload    # http://localhost:8000
```

Point the web app at the API with `NEXT_PUBLIC_API_URL`. Without it, card ranking says so rather than failing silently.

```
apps/
  api/    FastAPI · card dataset, ranking engine, approval odds
  web/    Next.js · statement parsing, spending analysis, UI
```

Tests: `npx vitest run` in `apps/web`, `pytest` in `apps/api`. API docs at `/docs` when it's running.

## Card data

Card details come from [`credit-card-bonuses-api`](https://github.com/yinani24/credit-card-bonuses-api). Corrections belong upstream so everyone benefits — which is rather the point.

## Status

Early and moving. Working today: statement parsing (PDF and CSV), merchant normalization, categorization, subscription detection, income cadence analysis, per-category earn comparison, and card ranking with approval odds.

Not done yet: multi-card portfolio construction that sequences applications around 5/24, real credit score integration (which turns out to be genuinely hard to obtain legitimately — see `docs/prd/credit-score-sourcing.md`), and spending trajectory forecasting.

Contributions welcome, especially statements from issuers the parser hasn't seen. Every parser fix so far came from a real statement breaking it.

## License

MIT — see [LICENSE](LICENSE).
