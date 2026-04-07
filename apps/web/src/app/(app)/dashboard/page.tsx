"use client";

import { useQuery } from "@tanstack/react-query";
import { getAccounts, getTransactions, getGoals } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  ArrowUpRight,
  ArrowDownRight,
} from "lucide-react";
import { Chat } from "@/components/chat";

function StatCard({
  label,
  value,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  icon: React.ElementType;
  trend?: "up" | "down" | "neutral";
}) {
  return (
    <div className="bg-card rounded-xl border border-border p-6">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-muted">{label}</span>
        <Icon className="w-5 h-5 text-muted-foreground" />
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-semibold tracking-tight text-card-foreground font-mono">
          {value}
        </span>
        {trend === "up" && (
          <ArrowUpRight className="w-4 h-4 text-emerald-500 mb-1" />
        )}
        {trend === "down" && (
          <ArrowDownRight className="w-4 h-4 text-red-500 mb-1" />
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const { data: accounts = [] } = useQuery({
    queryKey: ["accounts"],
    queryFn: getAccounts,
  });
  const { data: transactions = [] } = useQuery({
    queryKey: ["transactions"],
    queryFn: () => getTransactions(),
  });
  const { data: goals = [] } = useQuery({
    queryKey: ["goals"],
    queryFn: getGoals,
  });

  const netWorth = accounts.reduce((sum, a) => sum + a.balance, 0);
  const totalIncome = transactions
    .filter((t) => t.is_income)
    .reduce((sum, t) => sum + t.amount, 0);
  const totalExpenses = transactions
    .filter((t) => !t.is_income)
    .reduce((sum, t) => sum + Math.abs(t.amount), 0);

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-card-foreground">
          Dashboard
        </h1>
        <p className="text-sm text-muted mt-1">Your financial overview</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard
          label="Net Worth"
          value={formatCurrency(netWorth)}
          icon={Wallet}
          trend="up"
        />
        <StatCard
          label="Income"
          value={formatCurrency(totalIncome)}
          icon={TrendingUp}
          trend="up"
        />
        <StatCard
          label="Expenses"
          value={formatCurrency(totalExpenses)}
          icon={TrendingDown}
          trend="down"
        />
        <StatCard
          label="Active Goals"
          value={String(goals.length)}
          icon={Target}
        />
      </div>

      <Chat />
    </div>
  );
}
