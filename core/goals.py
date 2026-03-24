"""Manages savings goals persisted as JSON in a configurable data directory."""

import json
import os
from datetime import date

DEFAULT_GOALS = {
    "monthly_target": 0.0,
    "goals": [],
    "monthly_streak": {"current": 0, "best": 0, "history": {}}
}


def load_goals(data_dir: str = "data") -> dict:
    """Load goals from the goals.json file in the given data directory.

    Args:
        data_dir: Path to the directory containing goals.json.

    Returns:
        Dictionary of goal data, or a copy of ``DEFAULT_GOALS`` if the file
        does not exist.
    """
    path = f"{data_dir}/goals.json"
    if not os.path.exists(path):
        return DEFAULT_GOALS.copy()
    with open(path) as f:
        return json.load(f)


def save_goals(goals: dict, data_dir: str = "data") -> None:
    """Persist goals to goals.json in the given data directory.

    Creates the directory if it does not already exist.

    Args:
        goals: Dictionary of goal data to serialise.
        data_dir: Path to the directory where goals.json will be written.
    """
    path = f"{data_dir}/goals.json"
    os.makedirs(data_dir, exist_ok=True)
    with open(path, "w") as f:
        json.dump(goals, f, indent=2)


def set_monthly_target(amount: float, data_dir: str = "data") -> None:
    """Set the monthly savings target and persist it.

    Args:
        amount: Target savings amount for the month.
        data_dir: Path to the data directory containing goals.json.
    """
    goals = load_goals(data_dir)
    goals["monthly_target"] = amount
    save_goals(goals, data_dir)


def add_named_goal(name: str, target: float, deadline: str, data_dir: str = "data") -> None:
    """Add a named savings goal and persist it.

    Args:
        name: Human-readable name for the goal.
        target: Target amount to save.
        deadline: ISO-format date string by which the goal should be reached.
        data_dir: Path to the data directory containing goals.json.
    """
    goals = load_goals(data_dir)
    goals["goals"].append({
        "name": name,
        "target_amount": target,
        "current_amount": 0.0,
        "deadline": deadline,
        "created": date.today().isoformat()
    })
    save_goals(goals, data_dir)


def get_goal_progress(data_dir: str = "data") -> dict:
    """Return the current goals dictionary, including progress for all goals.

    Args:
        data_dir: Path to the data directory containing goals.json.

    Returns:
        Dictionary of goal data as stored in goals.json.
    """
    return load_goals(data_dir)
