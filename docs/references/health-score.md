# Financial Health Score Reference

The health score is a 0–100 composite metric that gives a single-number summary of financial wellness. It is computed by `compute_health_score()` in `dashboard_data.py` and displayed prominently on the Overview tab of the HTML dashboard.

---

## Score Dimensions

The score is the sum of five independent dimension scores. Each dimension has a maximum point value and a specific scoring rule.

### 1. Savings Rate — 30 points

**What it measures:** How much of income is being saved this month.

**Calculation:**

```
savings_rate = saved / income   (0.0 if income == 0)
pts = min(savings_rate / 0.20, 1.0) × 30
```

The scale is linear: 0% savings rate → 0 pts, 20%+ savings rate → 30 pts.

**Passing threshold:** ≥ 25 pts (i.e., savings rate ≥ 16.7%)

| Savings rate | Points |
|-------------|--------|
| 0% | 0 |
| 5% | 7.5 |
| 10% | 15 |
| 15% | 22.5 |
| 20%+ | 30 |

**Passing:** `"Savings rate"` added to `health["passing"]`
**Failing:** `"Savings rate"` added to `health["failing"]`

---

### 2. Spending Trends — 25 points

**What it measures:** Whether spending is growing faster than expected month-over-month.

**Calculation:**

```
offending = [category for category in category_trends if pct_change > 0.20]
pts = max(0.0, 25.0 − len(offending) × 8)
```

Each category whose spending grew more than 20% month-over-month costs 8 points, up to a maximum deduction of 25 points.

| Offending categories | Points |
|---------------------|--------|
| 0 | 25 |
| 1 | 17 |
| 2 | 9 |
| 3+ | 0 (floor) |

**Passing:** `"Spending trends"` added if no offending categories.
**Failing:** Each offending category adds `"<Category> spending"` to `health["failing"]`.

**Example:** If Food & Dining is up 35% and Transport is up 22% this month, the score loses 16 points and the failing list shows `["Food & Dining spending", "Transport spending"]`.

---

### 3. Goal Progress — 25 points

**What it measures:** Whether named savings goals are on track to reach their targets by their deadlines.

**At-risk definition:** A goal is at-risk when:

```
actual_pct < expected_pct

where:
  actual_pct   = current_amount / target_amount
  expected_pct = elapsed_months / total_months
```

`elapsed_months` is measured from the goal's `created` date to today. `total_months` is the total duration from `created` to `deadline`.

**Calculation:**

```
pts = max(0.0, 25.0 − len(at_risk) × 12)
```

| At-risk goals | Points |
|--------------|--------|
| 0 | 25 |
| 1 | 13 |
| 2+ | 0 (floor) |

**Passing:** `"Goal progress"` added if no at-risk goals.
**Failing:** Each at-risk goal adds `"<Goal name> goal"` to `health["failing"]`.

**Edge cases:**
- Goals with missing `created` or `deadline` fields are silently skipped (no impact on score)
- Goals with `target_amount == 0` are treated as 0% complete and will be at-risk after any elapsed time

---

### 4. Subscription Ratio — 10 points

**What it measures:** Whether subscription spending is proportionate to income.

**Calculation:**

```
sub_ratio = subscription_current_amount / income   (0.0 if income == 0)

if sub_ratio < 0.08:   10 pts  → passing
elif sub_ratio ≤ 0.15:  5 pts  → neither passing nor failing
else:                   0 pts  → failing
```

| Subscription % of income | Points |
|-------------------------|--------|
| < 8% | 10 |
| 8%–15% | 5 |
| > 15% | 0 |

**Passing:** `"Subscription ratio"` added to `health["passing"]` if < 8%.
**Failing:** `"Subscriptions"` added to `health["failing"]` if > 15%.

---

### 5. Emergency Fund — 10 points

**What it measures:** Whether an emergency fund goal is at least half-funded.

**Calculation:**

The function searches for a goal whose name contains `"emergency"` (case-insensitive):

```
if emergency fund goal exists:
    if current_amount / target_amount >= 0.50:
        10 pts  → passing
    else:
        0 pts   → failing
else:
    5 pts  (partial credit for no goal configured)
```

| Situation | Points |
|-----------|--------|
| Emergency fund ≥ 50% funded | 10 |
| Emergency fund < 50% funded | 0 |
| No emergency fund goal | 5 (partial credit) |

**Passing:** `"Emergency fund"` added if ≥ 50% funded.
**Failing:** `"Emergency fund"` added if goal exists but < 50% funded.

---

## Grade Thresholds

| Score range | Grade |
|-------------|-------|
| 90–100 | A |
| 80–89 | B+ |
| 75–79 | B |
| 60–74 | C |
| 45–59 | D |
| 0–44 | F |

---

## Return Value

`compute_health_score()` returns:

```python
{
    "score":   int,          # 0–100, sum of all dimension scores rounded
    "grade":   str,          # "A", "B+", "B", "C", "D", or "F"
    "passing": list[str],    # dimension labels where performance is good
    "failing": list[str],    # dimension labels needing improvement
}
```

### Example

```python
{
    "score": 68,
    "grade": "C",
    "passing": ["Savings rate", "Spending trends", "Subscription ratio"],
    "failing": ["Emergency fund", "Vacation Fund goal"],
}
```

---

## Maximum Score Breakdown

| Dimension | Max pts |
|-----------|---------|
| Savings rate | 30 |
| Spending trends | 25 |
| Goal progress | 25 |
| Subscription ratio | 10 |
| Emergency fund | 10 |
| **Total** | **100** |

---

## Interpretation Guide

| Grade | Score | Meaning |
|-------|-------|---------|
| A | 90+ | Excellent — saving aggressively, spending under control, goals on track |
| B+ | 80–89 | Very good — minor issues in one dimension |
| B | 75–79 | Good — solid fundamentals, one notable gap |
| C | 60–74 | Fair — multiple dimensions need attention |
| D | 45–59 | Concerning — significant gaps in savings or spending control |
| F | 0–44 | Critical — overspending, behind on goals, no savings cushion |

---

## Edge Cases

**No transactions:** `kpis["income"] == 0`, `savings_rate == 0.0`. Savings rate dimension scores 0. All other dimensions depend on goals and account data which may still provide points.

**No goals configured:** Goal progress dimension scores 25 (no at-risk goals). Emergency fund dimension scores 5 (partial credit). Maximum achievable score without goals: 90.

**No income but positive savings:** Can occur if income transactions aren't tagged correctly. `savings_rate` will be 0.0 since `income == 0`. Tag income transactions with `finance.py tag <id> --income` to fix.

**New goals (elapsed_months == 0):** `expected_pct == 0` for a brand-new goal. Any progress ≥ 0 satisfies `actual_pct >= expected_pct`, so new goals are never immediately at-risk.

---

## Source

The health score is computed entirely in `dashboard_data.py:compute_health_score()`. It depends only on:

- `kpis` dict from `compute_kpis()`
- `category_trends` list from `compute_category_trends()`
- `goals` dict (the raw goals file data)

No external state or file I/O is required after these inputs are computed.
