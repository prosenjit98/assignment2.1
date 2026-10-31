"""LLM-powered text classifier: one chat-completion call per message, structured JSON out.

Works with any OpenAI-compatible endpoint: OpenRouter by default, or a local server
(Ollama, vLLM, LM Studio) by pointing LLM_BASE_URL at it.
"""

from __future__ import annotations

import json
import os
import re
import time
from urllib.parse import urlparse

import openai

from .prompts import build_user_message, render_system_prompt
from .taxonomy import NEEDS_CLARIFICATION, UNCLASSIFIED, Taxonomy

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
MAX_INPUT_CHARS = 5000
# Reasoning tokens count toward max_tokens on most servers, so leave room beyond the ~200-token JSON.
MAX_OUTPUT_TOKENS = 4096
REVIEW_CONFIDENCE_THRESHOLD = 0.6

# json_schema: the server enforces the schema (OpenAI, Ollama, vLLM, and OpenRouter models
# that support structured outputs). json_object: valid JSON only, for servers without schema
# support. none: rely on the prompt alone. Set with CLASSIFIER_RESPONSE_FORMAT.
RESPONSE_FORMATS = ("json_schema", "json_object", "none")

# Local servers usually ignore the API key, but the SDK requires one.
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
LOCAL_PLACEHOLDER_KEY = "not-needed"

# Without schema enforcement, models may wrap the JSON in ``` fences or add a sentence around it,
# and some reasoning models put their thinking in <think> tags before the answer.
_THINK_BLOCK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)

DEFAULT_CLARIFYING_QUESTION = (
    "Could you tell us a bit more: what isn't working or what do you need, "
    "and how is it affecting your work?"
)


class ClassificationError(RuntimeError):
    """The model call failed or returned something unusable."""


class ConfigurationError(ClassificationError):
    """No usable endpoint, model or credentials."""


class InputValidationError(ValueError):
    """The input can't be classified as given."""


def build_output_schema(taxonomy: Taxonomy) -> dict:
    """JSON schema enforced through structured outputs, so every response parses
    and every label comes from the taxonomy."""
    categories = {"type": "string", "enum": taxonomy.category_names}
    properties = {
        "summary": {"type": "string"},
        "category": categories,
        "subcategory": {"type": "string", "enum": taxonomy.subcategory_names},
        "priority": {"type": "string", "enum": taxonomy.priority_levels},
        "confidence": {"type": "number"},
        "needs_clarification": {"type": "boolean"},
        "clarifying_question": {"type": "string"},
        "secondary_categories": {"type": "array", "items": categories},
        "rationale": {"type": "string"},
    }
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


def _short(message: str, limit: int = 300) -> str:
    # Proxies and some servers answer errors with a whole HTML page.
    message = " ".join(str(message).split())
    return message if len(message) <= limit else message[: limit - 1] + "…"


class TextClassifier:
    def __init__(
        self,
        client: openai.OpenAI | None = None,
        *,
        model: str | None = None,
        base_url: str | None = None,
        effort: str | None = None,
        response_format: str | None = None,
        taxonomy: Taxonomy | None = None,
    ):
        self.taxonomy = taxonomy or Taxonomy.load()
        self.base_url = base_url or os.getenv("LLM_BASE_URL") or DEFAULT_BASE_URL
        self.model = model or os.getenv("CLASSIFIER_MODEL") or ""
        # Only sent when set: many models don't accept a reasoning effort.
        self.effort = effort or os.getenv("CLASSIFIER_EFFORT") or None
        self.response_format = response_format or os.getenv("CLASSIFIER_RESPONSE_FORMAT") or "json_schema"
        if self.response_format not in RESPONSE_FORMATS:
            raise ValueError(
                f"CLASSIFIER_RESPONSE_FORMAT must be one of {', '.join(RESPONSE_FORMATS)}; got {self.response_format!r}"
            )
        self.system_prompt = render_system_prompt(self.taxonomy)
        self.output_schema = build_output_schema(self.taxonomy)
        self._client = client

    @property
    def client(self) -> openai.OpenAI:
        if self._client is None:
            api_key = os.getenv("LLM_API_KEY")
            if not api_key:
                if urlparse(self.base_url).hostname not in LOCAL_HOSTS:
                    raise ConfigurationError(
                        f"No API key for {self.base_url}. Set LLM_API_KEY in your environment or .env file."
                    )
                api_key = LOCAL_PLACEHOLDER_KEY
            self._client = openai.OpenAI(base_url=self.base_url, api_key=api_key)
        return self._client

    def classify(self, text: str) -> dict:
        started = time.perf_counter()
        text = (text or "").strip()

        if not text:
            result = self._result(
                category=UNCLASSIFIED,
                subcategory=NEEDS_CLARIFICATION,
                priority="Low",
                confidence=1.0,
                needs_clarification=True,
                clarifying_question="Your message was empty. What do you need help with?",
                secondary_categories=[],
                summary="Empty message.",
                rationale="No text was provided, so the request cannot be routed.",
                warnings=[],
            )
            meta = {"source": "guardrail"}
        else:
            if len(text) > MAX_INPUT_CHARS:
                raise InputValidationError(
                    f"Message is {len(text)} characters long; the limit is {MAX_INPUT_CHARS}."
                )
            response = self._call_model(text)
            result, meta = self._parse_response(response)

        meta["latency_ms"] = round((time.perf_counter() - started) * 1000)
        result["meta"] = meta
        return result

    def _call_model(self, text: str):
        if not self.model:
            raise ConfigurationError("No model configured. Set CLASSIFIER_MODEL in your environment or .env file.")

        request = {
            "model": self.model,
            "max_tokens": MAX_OUTPUT_TOKENS,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": build_user_message(text)},
            ],
        }
        if self.response_format == "json_schema":
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "classification", "strict": True, "schema": self.output_schema},
            }
        elif self.response_format == "json_object":
            request["response_format"] = {"type": "json_object"}
        if self.effort:
            request["reasoning_effort"] = self.effort

        try:
            return self.client.chat.completions.create(**request)
        except openai.AuthenticationError as exc:
            raise ConfigurationError(f"{self.base_url} rejected the API key: {_short(exc.message)}") from exc
        except openai.PermissionDeniedError as exc:
            raise ConfigurationError(
                f"Access to {self.base_url} was denied (HTTP 403). Check the API key, or whether a "
                f"network proxy blocks this endpoint: {_short(exc.message)}"
            ) from exc
        except openai.NotFoundError as exc:
            raise ConfigurationError(
                f"Model {self.model!r} or the endpoint was not found at {self.base_url}: {_short(exc.message)}"
            ) from exc
        except openai.BadRequestError as exc:
            hint = (
                " If the model doesn't support JSON schemas, set CLASSIFIER_RESPONSE_FORMAT=json_object."
                if self.response_format == "json_schema"
                else ""
            )
            raise ClassificationError(f"The server rejected the request: {_short(exc.message)}.{hint}") from exc
        except openai.RateLimitError as exc:
            raise ClassificationError("Rate limited by the server; try again shortly.") from exc
        except openai.APIStatusError as exc:
            raise ClassificationError(f"Server error {exc.status_code}: {_short(exc.message)}") from exc
        except openai.APIConnectionError as exc:
            raise ClassificationError(f"Could not reach {self.base_url} (network error or timeout).") from exc

    def _parse_response(self, response) -> tuple[dict, dict]:
        if not response.choices:
            raise ClassificationError("The server returned no answer.")
        choice = response.choices[0]
        usage = response.usage
        meta = {
            "source": "llm",
            "model": response.model or self.model,
            "effort": self.effort,
            "finish_reason": choice.finish_reason,
            "usage": {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "cached_input_tokens": getattr(getattr(usage, "prompt_tokens_details", None), "cached_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
            },
        }

        if getattr(choice.message, "refusal", None) or choice.finish_reason == "content_filter":
            # The model or a provider filter declined. Don't guess; hand it to a person.
            return self._result(
                category=UNCLASSIFIED,
                subcategory=NEEDS_CLARIFICATION,
                priority="Medium",
                confidence=0.0,
                needs_clarification=True,
                clarifying_question=DEFAULT_CLARIFYING_QUESTION,
                secondary_categories=[],
                summary="The model declined to classify this message.",
                rationale="Automatic classification was declined, so the message needs manual triage.",
                warnings=["Model declined to classify this message; route it to a human."],
            ), meta
        if choice.finish_reason == "length":
            raise ClassificationError("The model ran out of output tokens before completing its answer.")

        raw = choice.message.content or ""
        try:
            data = json.loads(self._extract_json(raw))
        except json.JSONDecodeError as exc:
            raise ClassificationError(f"Model returned invalid JSON: {raw[:200]!r}") from exc
        if not isinstance(data, dict):
            raise ClassificationError(f"Model returned JSON that is not an object: {raw[:200]!r}")
        return self._normalize(data), meta

    @staticmethod
    def _extract_json(raw: str) -> str:
        raw = _THINK_BLOCK.sub("", raw)
        match = _JSON_OBJECT.search(raw)
        return match.group(0) if match else raw

    def _normalize(self, data: dict) -> dict:
        """Validate the model's answer against the taxonomy. Problems are reported
        in `warnings` (which also flags the result for human review) rather than
        silently corrected."""
        tax = self.taxonomy
        warnings: list[str] = []

        category = data.get("category")
        subcategory = data.get("subcategory")
        if category not in tax.category_names:
            warnings.append(f"Unknown category {category!r}; sent to {UNCLASSIFIED}.")
            category, subcategory = UNCLASSIFIED, NEEDS_CLARIFICATION
        elif tax.parent_of(subcategory) != category:
            warnings.append(f"Subcategory {subcategory!r} does not belong to {category!r}.")

        priority = data.get("priority")
        if priority not in tax.priority_levels:
            warnings.append(f"Unknown priority {priority!r}; defaulted to Medium.")
            priority = "Medium"

        try:
            confidence = min(max(float(data.get("confidence")), 0.0), 1.0)
        except (TypeError, ValueError):
            warnings.append("Missing or non-numeric confidence.")
            confidence = 0.0

        needs_clarification = bool(data.get("needs_clarification")) or (
            category == UNCLASSIFIED and subcategory == NEEDS_CLARIFICATION
        )
        question = (data.get("clarifying_question") or "").strip()
        if needs_clarification and not question:
            question = DEFAULT_CLARIFYING_QUESTION

        secondary = [
            c
            for c in dict.fromkeys(data.get("secondary_categories") or [])
            if c in tax.category_names and c not in (category, UNCLASSIFIED)
        ]

        return self._result(
            category=category,
            subcategory=subcategory,
            priority=priority,
            confidence=round(confidence, 2),
            needs_clarification=needs_clarification,
            clarifying_question=question,
            secondary_categories=secondary,
            summary=(data.get("summary") or "").strip(),
            rationale=(data.get("rationale") or "").strip(),
            warnings=warnings,
        )

    def _result(
        self,
        *,
        category: str,
        subcategory: str,
        priority: str,
        confidence: float,
        needs_clarification: bool,
        clarifying_question: str,
        secondary_categories: list[str],
        summary: str,
        rationale: str,
        warnings: list[str],
    ) -> dict:
        return {
            "category": category,
            "subcategory": subcategory,
            "priority": priority,
            "confidence": confidence,
            "routed_to": self.taxonomy.routes_to(category),
            "needs_clarification": needs_clarification,
            "clarifying_question": clarifying_question if needs_clarification else None,
            "secondary_categories": secondary_categories,
            "summary": summary,
            "rationale": rationale,
            "needs_human_review": needs_clarification
            or confidence < REVIEW_CONFIDENCE_THRESHOLD
            or bool(warnings),
            "warnings": warnings,
        }
