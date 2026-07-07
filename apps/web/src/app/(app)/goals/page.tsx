"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getGoals, createGoal } from "@/lib/api";
import { formatCurrency } from "@/lib/format";
import { Plus } from "lucide-react";
import {
  Dialog,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";

export default function GoalsPage() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [goalType, setGoalType] = useState("savings");
  const [target, setTarget] = useState("");
  const [deadline, setDeadline] = useState("");
  const [isMonthly, setIsMonthly] = useState(false);

  const { data: goals = [], isLoading } = useQuery({
    queryKey: ["goals"],
    queryFn: getGoals,
  });

  const mutation = useMutation({
    mutationFn: createGoal,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["goals"] });
      setOpen(false);
      resetForm();
    },
    onError: () => {},
  });

  function resetForm() {
    setName("");
    setGoalType("savings");
    setTarget("");
    setDeadline("");
    setIsMonthly(false);
  }

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-card-foreground">Goals</h1>
          <p className="text-sm text-muted mt-1">
            Track your financial goals
          </p>
        </div>
        <Dialog open={open} onOpenChange={(o) => { setOpen(o); if (!o) resetForm(); }}>
          <DialogTrigger className="flex items-center gap-2 bg-foreground text-background px-4 py-2.5 rounded-lg text-sm font-medium hover:opacity-90 transition-opacity active:translate-y-px">
            <Plus className="w-4 h-4" />
            New Goal
          </DialogTrigger>
          <DialogContent className="sm:max-w-lg">
            <DialogHeader>
              <DialogTitle>New Goal</DialogTitle>
              <DialogDescription>
                Set a financial target to track your progress.
              </DialogDescription>
            </DialogHeader>
            <form
              id="add-goal-form"
              onSubmit={(e) => {
                e.preventDefault();
                mutation.mutate({
                  name,
                  goal_type: goalType,
                  target_amount: parseFloat(target) || 0,
                  current_amount: 0,
                  deadline: deadline || undefined,
                  is_monthly: isMonthly,
                });
              }}
              className="space-y-4"
            >
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Goal Name
                  </label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    required
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                    placeholder="e.g. Emergency Fund"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Type
                  </label>
                  <select
                    value={goalType}
                    onChange={(e) => setGoalType(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                  >
                    <option value="savings">Savings</option>
                    <option value="spending">Spending Limit</option>
                    <option value="debt">Debt Payoff</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Target Amount
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={target}
                    onChange={(e) => setTarget(e.target.value)}
                    required
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                    placeholder="10000"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-card-foreground mb-1.5">
                    Deadline
                  </label>
                  <input
                    type="date"
                    value={deadline}
                    onChange={(e) => setDeadline(e.target.value)}
                    className="w-full border border-input bg-background text-foreground rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-ring transition-colors"
                  />
                </div>
              </div>
              <label className="flex items-center gap-2 text-sm text-card-foreground">
                <input
                  type="checkbox"
                  checked={isMonthly}
                  onChange={(e) => setIsMonthly(e.target.checked)}
                  className="rounded"
                />
                Monthly recurring goal
              </label>
              {mutation.isError && (
                <p className="text-sm text-red-500">
                  Failed to create goal. Please try again.
                </p>
              )}
            </form>
            <DialogFooter>
              <button
                type="submit"
                form="add-goal-form"
                disabled={mutation.isPending}
                className="bg-foreground text-background px-4 py-2 rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity active:translate-y-px"
              >
                {mutation.isPending ? "Creating..." : "Create Goal"}
              </button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>

      {isLoading ? (
        <div className="space-y-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="bg-card rounded-xl border border-border p-6 animate-pulse"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="space-y-2">
                  <div className="h-4 w-36 bg-muted rounded" />
                  <div className="h-3 w-24 bg-muted rounded" />
                </div>
                <div className="text-right space-y-2">
                  <div className="h-4 w-32 bg-muted rounded ml-auto" />
                  <div className="h-3 w-20 bg-muted rounded ml-auto" />
                </div>
              </div>
              <div className="w-full bg-muted rounded-full h-2" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          {goals.map((goal) => {
            const pct =
              goal.target_amount > 0
                ? Math.min(
                    (goal.current_amount / goal.target_amount) * 100,
                    100
                  )
                : 0;
            return (
              <div
                key={goal.id}
                className="bg-card rounded-xl border border-border p-6"
              >
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <div className="text-sm font-medium text-card-foreground">
                      {goal.name}
                    </div>
                    <div className="text-xs text-muted-foreground capitalize">
                      {goal.goal_type}
                      {goal.is_monthly && " \u00B7 Monthly"}
                      {goal.deadline && ` \u00B7 Due ${goal.deadline}`}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-mono font-medium tabular-nums text-card-foreground">
                      {formatCurrency(goal.current_amount)} /{" "}
                      {formatCurrency(goal.target_amount)}
                    </div>
                    <div className="text-xs text-muted-foreground font-mono tabular-nums">
                      {pct.toFixed(0)}% complete
                    </div>
                  </div>
                </div>
                <div className="w-full bg-border rounded-full h-2">
                  <div
                    className={`rounded-full h-2 transition-all ${pct >= 100 ? "bg-emerald-500" : "bg-chart-1"}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
