"""Web UI and JSON API for the classifier.

    python app.py            # http://127.0.0.1:5000
"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from classifier import ClassificationError, ConfigurationError, InputValidationError, TextClassifier
from classifier.taxonomy import PROJECT_ROOT

load_dotenv(PROJECT_ROOT / ".env")

# Test cases shown as one-click examples in the UI.
EXAMPLE_IDS = ["TC01", "TC04", "TC09", "TC23", "TC24", "TC27", "TC28", "TC29", "TC32", "TC33"]


def _load_examples() -> list[dict]:
    cases = json.loads((PROJECT_ROOT / "data" / "test_cases.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in cases}
    return [{"id": i, "type": by_id[i]["type"], "text": by_id[i]["text"]} for i in EXAMPLE_IDS]


def create_app(classifier: TextClassifier | None = None) -> Flask:
    app = Flask(__name__)
    # Keep the result's field order (category first, meta last) in the API and the page.
    app.json.sort_keys = False
    app.jinja_env.policies["json.dumps_kwargs"] = {"sort_keys": False}
    clf = classifier or TextClassifier()
    examples = _load_examples()

    def classify_or_error(text: str) -> tuple[dict, int]:
        try:
            return clf.classify(text), 200
        except InputValidationError as exc:
            return {"error": str(exc)}, 400
        except ConfigurationError as exc:
            return {"error": str(exc)}, 503
        except ClassificationError as exc:
            return {"error": str(exc)}, 502

    @app.get("/")
    def index():
        # /?text=... classifies on the server so a result can be linked to or screenshotted.
        text = request.args.get("text", "")
        initial = None
        if text:
            body, status = classify_or_error(text)
            initial = {"status": status, "body": body}
        return render_template("index.html", examples=examples, initial_text=text, initial=initial, model=clf.model)

    @app.post("/api/classify")
    def api_classify():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            return jsonify(error='Send a JSON body like {"text": "My laptop won\'t connect to Wi-Fi"}'), 400
        body, status = classify_or_error(payload["text"])
        return jsonify(body), status

    @app.get("/api/categories")
    def api_categories():
        return jsonify(clf.taxonomy.data)

    @app.get("/api/health")
    def api_health():
        return jsonify(status="ok", model=clf.model, effort=clf.effort)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=os.getenv("FLASK_DEBUG") == "1")
