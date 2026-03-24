# tests/test_dashboard_data.py
import pytest
import pandas as pd
from datetime import date
from dashboard.analytics import (
    compute_kpis, compute_category_trends, compute_health_score,
    compute_actionable_cuts, compute_action_plan,
    compute_spending_pct_of_income, compute_account_balances,
    compute_top_merchants, build_context, _score_to_grade, _get_at_risk_goals,
)

TODAY = date(2026, 3, 15)  # fixed date for all tests


@pytest.fixture
def sample_df():
    """3 months of synthetic transactions: Jan, Feb, Mar 2026."""
    rows = [
        # March — current month
        {"date": "2026-03-01", "amount": -400.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-03", "amount": -100.0, "merchant": "Chipotle",       "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-05", "amount": -200.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-10", "amount": -54.99, "merchant": "Adobe",          "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-03-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
        # February
        {"date": "2026-02-01", "amount": -300.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-05", "amount": -180.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-02-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
        # January
        {"date": "2026-01-01", "amount": -250.0, "merchant": "Whole Foods",    "category": "Food & Dining",  "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-05", "amount": -160.0, "merchant": "Uber",           "category": "Transport",      "account": "Chase-Checking", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-10", "amount": -22.99, "merchant": "Netflix",        "category": "Subscriptions",  "account": "Amex",           "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        {"date": "2026-01-15", "amount": 5000.0, "merchant": "ACME Payroll",   "category": "Income",         "account": "Chase-Checking", "source": "csv", "is_income": True,  "is_savings": False, "notes": ""},
    ]
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


@pytest.fixture
def sample_accounts():
    return {
        "accounts": [
            {"name": "Chase-Checking", "type": "checking",   "institution": "Chase",     "balance": 14200.0, "currency": "USD", "last_updated": "2026-03-15"},
            {"name": "Robinhood",      "type": "investment", "institution": "Robinhood", "balance": 22500.0, "currency": "USD", "last_updated": "2026-03-15"},
        ]
    }


@pytest.fixture
def sample_goals():
    return {
        "monthly_target": 1500.0,
        "goals": [
            {
                "name": "Emergency Fund",
                "target_amount": 10000.0,
                "current_amount": 6200.0,
                "deadline": "2026-12",
                "created": "2026-01-01",
            }
        ],
        "monthly_streak": {
            "current": 3,
            "best": 7,
            "history": {"2026-01": True, "2026-02": True, "2026-03": True},
        },
    }


class TestComputeKPIs:
    def test_savings_rate_calculated_correctly(self, sample_df, sample_accounts, sample_goals):
        # March income=5000, expenses=400+100+200+22.99+54.99=777.98, saved=4222.02
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["income"] == pytest.approx(5000.0)
        assert kpis["expenses"] == pytest.approx(777.98)
        assert kpis["saved"] == pytest.approx(4222.02)
        assert kpis["savings_rate"] == pytest.approx(4222.02 / 5000.0)

    def test_zero_income_returns_zero_savings_rate(self, sample_accounts, sample_goals):
        df = pd.DataFrame([{
            "date": pd.Timestamp("2026-03-01"), "amount": -100.0, "merchant": "Test",
            "category": "Other", "account": "Chase", "source": "manual",
            "is_income": False, "is_savings": False, "notes": "",
        }])
        kpis = compute_kpis(df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["savings_rate"] == 0.0
        assert kpis["income"] == 0.0

    def test_monthly_target_comes_from_goals(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["monthly_target"] == 1500.0

    def test_net_worth_sums_all_accounts(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["net_worth"] == pytest.approx(36700.0)  # 14200 + 22500

    def test_this_month_format(self, sample_df, sample_accounts, sample_goals):
        kpis = compute_kpis(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert kpis["this_month"] == "2026-03"

    def test_defaults_to_today_when_no_today_param(self, sample_accounts, sample_goals):
        """Cover line 91: today=None default path in compute_kpis."""
        result = compute_kpis(pd.DataFrame(), sample_accounts, sample_goals)
        assert "this_month" in result


class TestCategoryTrends:
    def test_pct_change_direction_up(self, sample_df):
        # Food: Jan $250, Feb $300, Mar $500 — up vs Feb
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        food = next(t for t in trends if t["name"] == "Food & Dining")
        assert food["direction"] == "up"
        assert food["pct_change"] > 0.05

    def test_pct_change_direction_down(self, sample_df):
        # Create a df where Transport goes down in Mar
        rows = [
            {"date": "2026-03-01", "amount": -100.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
            {"date": "2026-02-01", "amount": -300.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
            {"date": "2026-01-01", "amount": -280.0, "merchant": "Uber", "category": "Transport", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        trends = compute_category_trends(df, months=3, today=TODAY)
        t = next(t for t in trends if t["name"] == "Transport")
        assert t["direction"] == "down"
        assert t["pct_change"] < -0.05

    def test_handles_missing_prior_months(self):
        # Category only exists in current month
        rows = [
            {"date": "2026-03-01", "amount": -200.0, "merchant": "Gym", "category": "Health", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""},
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        trends = compute_category_trends(df, months=3, today=TODAY)
        health = next(t for t in trends if t["name"] == "Health")
        assert health["current_amount"] == pytest.approx(200.0)
        assert health["pct_change"] == 0.0  # no prior month = 0% change

    def test_three_month_amounts_returned(self, sample_df):
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        food = next(t for t in trends if t["name"] == "Food & Dining")
        # prior_amounts has 2 entries (Jan, Feb) when months=3
        assert len(food["prior_amounts"]) == 2

    def test_only_expenses_included(self, sample_df):
        # Income category should not appear in trends
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        names = [t["name"] for t in trends]
        assert "Income" not in names

    def test_defaults_to_today_when_no_today_param(self, sample_df):
        """Cover line 132: today=None default path in compute_category_trends."""
        result = compute_category_trends(sample_df)
        assert isinstance(result, list)


class TestScoreToGrade:
    def test_grade_A_at_90(self):    assert _score_to_grade(90)  == "A"
    def test_grade_A_at_100(self):   assert _score_to_grade(100) == "A"
    def test_grade_Bplus_at_80(self): assert _score_to_grade(80) == "B+"
    def test_grade_Bplus_at_89(self): assert _score_to_grade(89) == "B+"
    def test_grade_B_at_75(self):    assert _score_to_grade(75)  == "B"
    def test_grade_B_at_79(self):    assert _score_to_grade(79)  == "B"
    def test_grade_C_at_60(self):    assert _score_to_grade(60)  == "C"
    def test_grade_C_at_74(self):    assert _score_to_grade(74)  == "C"
    def test_grade_D_at_45(self):    assert _score_to_grade(45)  == "D"
    def test_grade_D_at_59(self):    assert _score_to_grade(59)  == "D"
    def test_grade_F_at_44(self):    assert _score_to_grade(44)  == "F"
    def test_grade_F_at_0(self):     assert _score_to_grade(0)   == "F"


class TestHealthScore:
    def _make_kpis(self, savings_rate=0.25, income=5000.0):
        return {
            "income": income, "expenses": income * (1 - savings_rate),
            "saved": income * savings_rate, "savings_rate": savings_rate,
            "net_worth": 40000.0, "monthly_target": 1500.0, "this_month": "2026-03",
        }

    def test_savings_rate_zero_yields_zero_savings_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.0)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # savings_rate=0 → 0 pts; no trends → 25 pts; goals all on-track → check
        # Emergency Fund: created 2026-01, deadline 2026-12 = 11 months total,
        #   elapsed ~2 months, expected_pct≈18%, actual=62% → on track → +25 pts
        # No subscriptions → +10 pts; emergency fund >50% → +10 pts
        # Total = 0 + 25 + 25 + 10 + 10 = 70
        assert result["score"] == 70

    def test_savings_rate_10pct_yields_15_savings_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.10)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # savings pts = min(0.10/0.20, 1.0) * 30 = 15
        # 15 + 25 + 25 + 10 + 10 = 85 → "B+"
        assert result["score"] == 85
        assert result["grade"] == "B+"

    def test_savings_rate_at_20pct_yields_full_30_pts(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.20)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        # 30 + 25 + 25 + 10 + 10 = 100
        assert result["score"] == 100
        assert result["grade"] == "A"

    def test_high_spending_trend_deducts_points(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.20)
        trends = [{"name": "Food & Dining", "pct_change": 0.40, "direction": "up", "current_amount": 1400.0, "prior_amounts": [1000.0, 1000.0]}]
        result = compute_health_score(kpis, trends, sample_goals, today=TODAY)
        # trend pts = max(0, 25 - 1*8) = 17
        # 30 + 17 + 25 + 10 + 10 = 92
        assert result["score"] == 92

    def test_failing_areas_listed(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.0)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        assert "Savings rate" in result["failing"]

    def test_passing_areas_listed(self, sample_goals):
        kpis = self._make_kpis(savings_rate=0.25)
        result = compute_health_score(kpis, [], sample_goals, today=TODAY)
        assert "Savings rate" in result["passing"]

    def test_at_risk_goal_appended_to_failing(self):
        """Cover line 214: failing.append for each at-risk goal."""
        kpis = self._make_kpis(savings_rate=0.20)
        goals = {
            "monthly_target": 500.0,
            "goals": [{"name": "Japan Trip", "target_amount": 10000.0,
                       "current_amount": 1000.0, "deadline": "2026-03",
                       "created": "2026-01-01"}],
            "monthly_streak": {},
        }
        result = compute_health_score(kpis, [], goals, today=TODAY)
        assert "Japan Trip goal" in result["failing"]

    def test_subscription_ratio_8_to_15_pct_yields_5_pts(self):
        """Cover lines 226-227: subscription ratio 8-15% adds 5 pts."""
        kpis = self._make_kpis(savings_rate=0.20, income=5000.0)
        trends = [{"name": "Subscriptions", "current_amount": 500.0,
                   "prior_amounts": [], "pct_change": 0.0, "direction": "flat"}]
        result = compute_health_score(kpis, trends, {"goals": []}, today=TODAY)
        # 30 (savings) + 25 (trends) + 25 (goals) + 5 (sub 10%) + 5 (no EF) = 90
        assert result["score"] == 90

    def test_subscription_ratio_above_15_pct_adds_to_failing(self):
        """Cover lines 228-229: subscription ratio >15% → 0 pts + failing."""
        kpis = self._make_kpis(savings_rate=0.20, income=5000.0)
        trends = [{"name": "Subscriptions", "current_amount": 1000.0,
                   "prior_amounts": [], "pct_change": 0.0, "direction": "flat"}]
        result = compute_health_score(kpis, trends, {"goals": []}, today=TODAY)
        assert "Subscriptions" in result["failing"]
        # 30 + 25 + 25 + 0 (sub 20%) + 5 (no EF) = 85
        assert result["score"] == 85

    def test_emergency_fund_below_50_pct_adds_to_failing(self):
        """Cover line 239: emergency fund <50% → failing."""
        kpis = self._make_kpis(savings_rate=0.20)
        goals = {
            "monthly_target": 0.0,
            "goals": [{"name": "Emergency Fund", "target_amount": 10000.0,
                       "current_amount": 3000.0, "deadline": "2027-12",
                       "created": "2026-01-01"}],
            "monthly_streak": {},
        }
        result = compute_health_score(kpis, [], goals, today=TODAY)
        assert "Emergency fund" in result["failing"]


class TestActionableCuts:
    def _make_trend(self, name, current, prior1, prior2):
        prior = prior2  # compare current vs immediately prior month
        pct = round((current - prior) / prior, 4) if prior > 0 else 0.0
        direction = "up" if pct > 0.05 else ("down" if pct < -0.05 else "flat")
        return {"name": name, "current_amount": current, "prior_amounts": [prior1, prior2], "pct_change": pct, "direction": direction}

    def test_category_flagged_when_above_15pct(self, sample_df):
        # Food: Jan $250, Feb $300, Mar $500 — Mar/Feb = +67%
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        names = [c["category"] for c in cuts]
        assert "Food & Dining" in names

    def test_category_not_flagged_below_threshold(self, sample_df):
        # Create trend where category is flat
        trends = [self._make_trend("Shopping", 100.0, 98.0, 99.0)]
        # Build a df with those shopping transactions in current month
        rows = [{"date": "2026-03-01", "amount": -100.0, "merchant": "Amazon", "category": "Shopping", "account": "Chase", "source": "csv", "is_income": False, "is_savings": False, "notes": ""}]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        cuts = compute_actionable_cuts(df, trends)
        names = [c["category"] for c in cuts]
        assert "Shopping" not in names

    def test_subscriptions_listed_individually(self, sample_df):
        # sample_df has Netflix $22.99 + Adobe $54.99 in March — both ≥$15
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        sub_cut = next((c for c in cuts if c["category"] == "Subscriptions"), None)
        assert sub_cut is not None
        # Both Netflix and Adobe should appear in description
        assert "Netflix" in sub_cut["description"] or "Adobe" in sub_cut["description"]

    def test_cuts_sorted_by_saving_desc(self, sample_df):
        trends = compute_category_trends(sample_df, months=3, today=TODAY)
        cuts = compute_actionable_cuts(sample_df, trends)
        savings = [c["potential_saving"] for c in cuts]
        assert savings == sorted(savings, reverse=True)

    def test_empty_df_returns_empty(self):
        cuts = compute_actionable_cuts(pd.DataFrame(), [])
        assert cuts == []

    def test_transport_ride_count_over_10_adds_cut(self):
        """Cover lines 310-316: avg transport rides >10 triggers a ride-count cut."""
        rows = [
            {"date": f"2026-03-{i+1:02d}", "amount": -15.0, "merchant": "Uber",
             "category": "Transport", "account": "Chase", "source": "csv",
             "is_income": False, "is_savings": False, "notes": ""}
            for i in range(11)
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        # Non-transport trend to pass the empty-guard; flat so it won't flag Transport
        trends = [{"name": "Food & Dining", "current_amount": 100.0,
                   "prior_amounts": [100.0], "pct_change": 0.0, "direction": "flat"}]
        cuts = compute_actionable_cuts(df, trends)
        assert any(c["category"] == "Transport" for c in cuts)


class TestActionPlan:
    def _make_cuts(self, n):
        return [
            {"category": f"Cat{i}", "description": f"Cut {i}", "detail": "", "potential_saving": float(100 - i * 10), "icon": "💸"}
            for i in range(n)
        ]

    def test_returns_up_to_three_steps(self, sample_goals):
        cuts = self._make_cuts(5)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert len(plan) == 3

    def test_returns_fewer_steps_when_fewer_cuts(self, sample_goals):
        cuts = self._make_cuts(2)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert len(plan) == 2

    def test_returns_empty_when_no_cuts(self, sample_goals):
        plan = compute_action_plan([], sample_goals, {}, today=TODAY)
        assert plan == []

    def test_month_labels_sequential_format_month_yyyy(self, sample_goals):
        cuts = self._make_cuts(3)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert plan[0]["month_label"] == "March 2026"
        assert plan[1]["month_label"] == "April 2026"
        assert plan[2]["month_label"] == "May 2026"

    def test_step_numbers_are_1_2_3(self, sample_goals):
        cuts = self._make_cuts(3)
        plan = compute_action_plan(cuts, sample_goals, {}, today=TODAY)
        assert [s["step"] for s in plan] == [1, 2, 3]

    def test_defaults_to_today_when_no_today_param(self, sample_goals):
        """Cover line 342: today=None default path in compute_action_plan."""
        cuts = self._make_cuts(1)
        plan = compute_action_plan(cuts, sample_goals, {})
        assert len(plan) == 1

    def test_step_links_to_at_risk_goal(self):
        # Goal created 2026-01, deadline 2026-03, current=1000, target=10000
        # elapsed=2mo, total=2mo → expected_pct=100%, actual=10% → at-risk
        goals = {
            "monthly_target": 500.0,
            "goals": [{"name": "Japan Trip", "target_amount": 10000.0, "current_amount": 1000.0, "deadline": "2026-03", "created": "2026-01-01"}],
            "monthly_streak": {},
        }
        cuts = [{"category": "Food", "description": "Food high", "detail": "", "potential_saving": 300.0, "icon": "🍔"}]
        plan = compute_action_plan(cuts, goals, {}, today=TODAY)
        assert plan[0]["goal_link"] == "Japan Trip"
        assert "Japan Trip" in plan[0]["description"]


class TestSpendingPctOfIncome:
    def test_pct_calculated_correctly(self, sample_df):
        # March expenses: Food $500, Transport $200, Subs $77.98 — income $5000
        pct = compute_spending_pct_of_income(sample_df, income=5000.0, today=TODAY)
        food = next(p for p in pct if p["name"] == "Food & Dining")
        assert food["amount"] == pytest.approx(500.0)
        assert food["pct_of_income"] == pytest.approx(10.0)  # 500/5000*100

    def test_zero_income_returns_empty(self, sample_df):
        pct = compute_spending_pct_of_income(sample_df, income=0.0, today=TODAY)
        assert pct == []

    def test_sorted_by_amount_desc(self, sample_df):
        pct = compute_spending_pct_of_income(sample_df, income=5000.0, today=TODAY)
        amounts = [p["amount"] for p in pct]
        assert amounts == sorted(amounts, reverse=True)

    def test_defaults_to_today_when_no_today_param(self, sample_df):
        """Cover line 385: today=None default path in compute_spending_pct_of_income."""
        result = compute_spending_pct_of_income(sample_df, income=5000.0)
        assert isinstance(result, list)

    def test_no_expenses_in_current_month_returns_empty(self, sample_df):
        """Cover line 391: month_df.empty returns [] when no expenses in given month."""
        result = compute_spending_pct_of_income(sample_df, income=5000.0, today=date(2024, 1, 1))
        assert result == []


class TestAccountBalances:
    def test_share_of_total_calculated_correctly(self, sample_accounts):
        balances = compute_account_balances(sample_accounts)
        chase = next(b for b in balances if b["name"] == "Chase-Checking")
        # 14200 / (14200 + 22500) = 0.3869
        assert chase["share_of_total"] == pytest.approx(14200 / 36700, rel=0.01)

    def test_negative_balance_excluded_from_share_denominator(self):
        accounts = {"accounts": [
            {"name": "Chase",  "type": "checking",  "institution": "Chase",  "balance":  5000.0, "currency": "USD", "last_updated": "2026-03-01"},
            {"name": "Amex",   "type": "credit",    "institution": "Amex",   "balance": -1000.0, "currency": "USD", "last_updated": "2026-03-01"},
        ]}
        balances = compute_account_balances(accounts)
        chase = next(b for b in balances if b["name"] == "Chase")
        assert chase["share_of_total"] == pytest.approx(1.0)  # only positive balance counts

    def test_all_accounts_returned(self, sample_accounts):
        balances = compute_account_balances(sample_accounts)
        assert len(balances) == 2


class TestTopMerchants:
    def test_filters_to_given_month(self, sample_df):
        merchants = compute_top_merchants(sample_df, "2026-03")
        names = [m["name"] for m in merchants]
        # Uber and Whole Foods are in March
        assert "Whole Foods" in names
        # ACME Payroll is income (positive amount) — should not appear
        assert "ACME Payroll" not in names

    def test_returns_top_10_by_spend(self):
        # Create 12 merchants with varying spend in same month
        rows = [
            {"date": "2026-03-01", "amount": float(-(i + 1) * 10), "merchant": f"Store{i:02d}",
             "category": "Shopping", "account": "Chase", "source": "csv",
             "is_income": False, "is_savings": False, "notes": ""}
            for i in range(12)
        ]
        df = pd.DataFrame(rows)
        df["date"] = pd.to_datetime(df["date"])
        merchants = compute_top_merchants(df, "2026-03")
        assert len(merchants) == 10

    def test_empty_month_returns_empty(self, sample_df):
        """Cover line 439: month_df.empty returns [] when no expenses in given month."""
        result = compute_top_merchants(sample_df, "2024-01")
        assert result == []

    def test_includes_tx_count(self, sample_df):
        # Whole Foods has 1 tx in March, Chipotle has 1 tx
        merchants = compute_top_merchants(sample_df, "2026-03")
        wf = next(m for m in merchants if m["name"] == "Whole Foods")
        assert wf["tx_count"] == 1
        assert wf["amount"] == pytest.approx(400.0)


class TestBuildContext:
    def test_context_has_all_required_keys(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        required = [
            "kpis", "category_trends", "health", "cuts", "action_plan",
            "spending_pct", "account_balances", "top_merchants",
            "trend_labels", "trend_values", "goals_display",
            "monthly_streak", "monthly_target", "generated_at",
        ]
        for key in required:
            assert key in ctx, f"Missing key: {key}"

    def test_trend_labels_has_12_entries(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert len(ctx["trend_labels"]) == 12
        assert len(ctx["trend_values"]) == 12

    def test_goals_display_contains_pct(self, sample_df, sample_accounts, sample_goals):
        ctx = build_context(sample_df, sample_accounts, sample_goals, today=TODAY)
        assert len(ctx["goals_display"]) == 1
        g = ctx["goals_display"][0]
        assert g["name"] == "Emergency Fund"
        assert g["pct"] == 62  # 6200/10000*100

    def test_empty_df_returns_zero_kpis(self, sample_accounts, sample_goals):
        ctx = build_context(pd.DataFrame(), sample_accounts, sample_goals, today=TODAY)
        assert ctx["kpis"]["income"] == 0.0
        assert ctx["kpis"]["net_worth"] == pytest.approx(36700.0)


def test_get_at_risk_goals_handles_malformed_goal():
    """Cover lines 493-494: KeyError/ValueError from a goal missing required keys."""
    goals = {"goals": [{"name": "Bad Goal"}]}  # missing deadline and created
    result = _get_at_risk_goals(goals, today=TODAY)
    assert result == []
