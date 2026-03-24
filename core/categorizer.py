"""Assigns spending categories to transactions using keyword-based matching."""

import re
import json


def normalize_merchant(name: str) -> str:
    """Normalise a merchant name for consistent keyword matching.

    Converts the name to lowercase, strips branch numbers (e.g. ``#42``),
    replaces asterisks with spaces, and collapses repeated whitespace.

    Args:
        name: Raw merchant name as it appears in a transaction.

    Returns:
        Cleaned, lowercase merchant string.
    """
    name = name.lower()
    name = re.sub(r'#\d+', '', name)      # strip branch numbers
    name = re.sub(r'\*', ' ', name)        # replace * with space
    name = re.sub(r'\s+', ' ', name)       # collapse whitespace
    return name.strip()


class Categorizer:
    """Categorises merchants by matching normalised names against configured keywords."""

    def __init__(self, config_path: str = "config.json") -> None:
        """Load category keywords from the configuration file.

        Args:
            config_path: Path to the JSON configuration file containing a
                ``categories`` key mapping category names to lists of keywords.
        """
        with open(config_path) as f:
            config = json.load(f)
        self.categories: dict[str, list[str]] = config["categories"]

    def categorize(self, merchant: str) -> str:
        """Return the best-matching category for the given merchant name.

        Normalises the merchant name and finds the category whose keyword
        produces the longest match within the normalised string. The ``Other``
        category is used as a fallback when no keyword matches.

        Args:
            merchant: Raw merchant name to categorise.

        Returns:
            Category name string; ``"Other"`` when no keyword matches.
        """
        normalized = normalize_merchant(merchant)
        best_match = None
        best_len = 0
        for category, keywords in self.categories.items():
            if category == "Other":
                continue
            for keyword in keywords:
                if keyword in normalized and len(keyword) > best_len:
                    best_match = category
                    best_len = len(keyword)
        return best_match if best_match else "Other"
