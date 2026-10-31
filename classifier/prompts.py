"""Builds the prompts sent to the model from the templates in prompts/."""

from __future__ import annotations

import json
import re
from functools import lru_cache

from .taxonomy import PROJECT_ROOT, Taxonomy

PROMPTS_DIR = PROJECT_ROOT / "prompts"

# A message containing "</request>" must not be able to close the data block early.
_CLOSING_TAG = re.compile(r"<\s*/\s*request\s*>", re.IGNORECASE)


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def render_system_prompt(taxonomy: Taxonomy) -> str:
    examples = json.loads(_read("few_shot_examples.json"))
    replacements = {
        "{{DOMAIN}}": taxonomy.domain,
        "{{CATEGORY_DEFINITIONS}}": _render_categories(taxonomy),
        "{{DISAMBIGUATION_RULES}}": "\n".join(
            f"{i}. {rule}" for i, rule in enumerate(taxonomy.disambiguation_rules, 1)
        ),
        "{{PRIORITY_DEFINITIONS}}": "\n".join(
            f"- **{p['level']}** (respond within {p['response_target']}): {p['description']}"
            for p in taxonomy.priorities
        ),
        "{{FEW_SHOT_EXAMPLES}}": "\n\n".join(_render_example(e) for e in examples),
    }
    prompt = _read("system_prompt.md")
    for placeholder, value in replacements.items():
        prompt = prompt.replace(placeholder, value)
    return prompt.strip()


def build_user_message(text: str) -> str:
    return _read("user_message.md").replace("{{TEXT}}", _CLOSING_TAG.sub("[/request]", text)).strip()


def _render_categories(taxonomy: Taxonomy) -> str:
    blocks = []
    for c in taxonomy.categories:
        lines = [f"### {c['name']}", f"Routes to {c['routes_to']}. {c['description']}"]
        lines += [f"- **{s['name']}**: {s['description']}" for s in c["subcategories"]]
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def _render_example(example: dict) -> str:
    secondary = ", ".join(example["secondary_categories"]) or "none"
    lines = [
        f"Message: \"{example['text']}\"",
        f"Result: {example['category']} / {example['subcategory']}, priority {example['priority']}, "
        f"secondary: {secondary}",
    ]
    if example.get("clarifying_question"):
        lines.append(f"Clarifying question: \"{example['clarifying_question']}\"")
    lines.append(f"Why: {example['why']}")
    return "\n".join(lines)
