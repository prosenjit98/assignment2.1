"""Category and priority definitions.

data/categories.json is the single source of truth: it is rendered into the system
prompt, turned into the JSON-schema enums the model must answer with, used to
validate the model's answer, and rendered into docs/CATEGORIES.md.
"""

from __future__ import annotations

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY_PATH = PROJECT_ROOT / "data" / "categories.json"

UNCLASSIFIED = "Unclassified"
NEEDS_CLARIFICATION = "Needs Clarification"


class Taxonomy:
    def __init__(self, data: dict):
        self.data = data
        self.domain: str = data["domain"]
        self.description: str = data["description"]
        self.categories: list[dict] = data["categories"]
        self.priorities: list[dict] = data["priorities"]
        self.disambiguation_rules: list[str] = data["disambiguation_rules"]

        # Subcategory names are unique across categories, so a subcategory alone
        # identifies its parent. That keeps the output schema flat.
        self._parent: dict[str, str] = {}
        for category in self.categories:
            for sub in category["subcategories"]:
                if sub["name"] in self._parent:
                    raise ValueError(f"Subcategory {sub['name']!r} is defined more than once")
                self._parent[sub["name"]] = category["name"]

        if UNCLASSIFIED not in self.category_names:
            raise ValueError(f"The taxonomy must define an {UNCLASSIFIED!r} category")
        if NEEDS_CLARIFICATION not in self.subcategories_of(UNCLASSIFIED):
            raise ValueError(f"{UNCLASSIFIED!r} must have a {NEEDS_CLARIFICATION!r} subcategory")

    @classmethod
    def load(cls, path: Path = DEFAULT_TAXONOMY_PATH) -> Taxonomy:
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @property
    def category_names(self) -> list[str]:
        return [c["name"] for c in self.categories]

    @property
    def subcategory_names(self) -> list[str]:
        return list(self._parent)

    @property
    def priority_levels(self) -> list[str]:
        """Most to least urgent."""
        return [p["level"] for p in self.priorities]

    def parent_of(self, subcategory: str) -> str | None:
        return self._parent.get(subcategory)

    def subcategories_of(self, category: str) -> list[str]:
        for c in self.categories:
            if c["name"] == category:
                return [s["name"] for s in c["subcategories"]]
        return []

    def routes_to(self, category: str) -> str | None:
        for c in self.categories:
            if c["name"] == category:
                return c["routes_to"]
        return None

    def to_markdown(self) -> str:
        """Human-readable category definitions (written to docs/CATEGORIES.md)."""
        lines = [
            "# Category Definitions",
            "",
            "<!-- Generated from data/categories.json by `python scripts/build_category_docs.py`. Do not edit by hand. -->",
            "",
            f"**Domain:** {self.domain}. {self.description}",
            "",
            "## Summary",
            "",
            "| Category | Routes to | Subcategories |",
            "|---|---|---|",
        ]
        for c in self.categories:
            subs = ", ".join(s["name"] for s in c["subcategories"])
            lines.append(f"| {c['name']} | {c['routes_to']} | {subs} |")

        for c in self.categories:
            lines += ["", f"## {c['name']}", "", f"*Routes to: {c['routes_to']}.* {c['description']}", ""]
            lines += ["| Subcategory | Covers |", "|---|---|"]
            lines += [f"| {s['name']} | {s['description']} |" for s in c["subcategories"]]

        lines += ["", "## Priority levels", "", "| Priority | Response target | When to use |", "|---|---|---|"]
        lines += [f"| {p['level']} | {p['response_target']} | {p['description']} |" for p in self.priorities]
        lines += [
            "",
            "Priority is judged by described impact and urgency, never by tone: \"URGENT!!!\" on a minor issue stays Low,",
            "and a serious risk described casually still gets the priority its impact deserves.",
            "",
            "## Overlap rules",
            "",
            "When a message could belong to more than one category:",
            "",
        ]
        lines += [f"{i}. {rule}" for i, rule in enumerate(self.disambiguation_rules, 1)]
        lines.append("")
        return "\n".join(lines)
