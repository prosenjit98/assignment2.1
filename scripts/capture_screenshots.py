"""Capture screenshots of the web UI with a headless Chromium browser (Edge or Chrome).

    python scripts/capture_screenshots.py                  # home page + sample classifications
    python scripts/capture_screenshots.py --home-only      # no API calls
    python scripts/capture_screenshots.py --browser "C:/path/to/chrome.exe"

The app runs in-process; each classification screenshot calls the live model
through /?text=..., so CLASSIFIER_MODEL (and LLM_API_KEY for a remote endpoint)
must be set, except with --home-only.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from werkzeug.serving import make_server  # noqa: E402

from app import create_app  # noqa: E402
from classifier.taxonomy import PROJECT_ROOT  # noqa: E402

OUT_DIR = PROJECT_ROOT / "docs" / "screenshots"
# (file name, test case id)
SHOTS = [
    ("01-standard-network", "TC01"),
    ("02-critical-outage", "TC04"),
    ("03-ambiguous-lost-laptop", "TC23"),
    ("04-ambiguous-shouting-low-priority", "TC27"),
    ("05-edge-needs-clarification", "TC29"),
    ("06-edge-non-english", "TC32"),
    ("07-edge-prompt-injection", "TC33"),
]
# Chrome first: on some managed Windows machines Edge's headless mode hangs without
# writing a screenshot.
BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser(explicit: str | None) -> str:
    if explicit:
        return explicit
    for candidate in BROWSER_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome", "msedge"):
        if found := shutil.which(name):
            return found
    raise SystemExit("No Chromium-based browser found; pass --browser PATH")


def screenshot(browser: str, url: str, target: Path, height: int) -> None:
    with tempfile.TemporaryDirectory() as profile:
        subprocess.run(
            [
                browser,
                "--headless=new",
                "--disable-gpu",
                "--hide-scrollbars",
                "--no-first-run",
                f"--user-data-dir={profile}",
                f"--window-size=1280,{height}",
                "--virtual-time-budget=3000",
                f"--screenshot={target}",
                url,
            ],
            check=True,
            capture_output=True,
            timeout=180,
        )
    print(f"  saved {target.relative_to(PROJECT_ROOT).as_posix()}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--browser", help="Path to a Chromium-based browser")
    parser.add_argument("--port", type=int, default=5055)
    parser.add_argument("--home-only", action="store_true", help="Only capture the landing page")
    args = parser.parse_args()

    browser = find_browser(args.browser)
    cases = {c["id"]: c for c in json.loads((PROJECT_ROOT / "data" / "test_cases.json").read_text(encoding="utf-8"))}
    server = make_server("127.0.0.1", args.port, create_app(), threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{args.port}/"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        print(f"Capturing with {browser}", flush=True)
        screenshot(browser, base, OUT_DIR / "00-home.png", 900)
        if not args.home_only:
            for name, case_id in SHOTS:
                screenshot(browser, f"{base}?text={quote(cases[case_id]['text'])}", OUT_DIR / f"{name}.png", 1400)
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
