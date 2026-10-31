"""Classify a message from the command line and print the JSON result.

    python classify.py "My laptop is not connecting to the office Wi-Fi."
    echo "printer is jammed" | python classify.py -
    python classify.py --show-prompt
"""

from __future__ import annotations

import argparse
import json
import sys

from dotenv import load_dotenv

from classifier import ClassificationError, InputValidationError, TextClassifier
from classifier.taxonomy import PROJECT_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify a service-desk message with an LLM.")
    parser.add_argument("text", nargs="?", help="Message to classify, or '-' to read it from stdin")
    parser.add_argument("--show-prompt", action="store_true", help="Print the rendered system prompt and exit")
    args = parser.parse_args(argv)

    sys.stdout.reconfigure(encoding="utf-8")
    load_dotenv(PROJECT_ROOT / ".env")
    classifier = TextClassifier()

    if args.show_prompt:
        print(classifier.system_prompt)
        return 0
    if args.text is None:
        parser.error("give the text to classify, or '-' to read from stdin")

    text = sys.stdin.read() if args.text == "-" else args.text
    try:
        result = classifier.classify(text)
    except (InputValidationError, ClassificationError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
