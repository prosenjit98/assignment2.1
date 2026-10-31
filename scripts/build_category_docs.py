"""Regenerate docs/CATEGORIES.md from data/categories.json.

    python scripts/build_category_docs.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from classifier.taxonomy import PROJECT_ROOT, Taxonomy  # noqa: E402

OUTPUT = PROJECT_ROOT / "docs" / "CATEGORIES.md"

if __name__ == "__main__":
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(Taxonomy.load().to_markdown(), encoding="utf-8")
    print(f"Wrote {OUTPUT.relative_to(PROJECT_ROOT).as_posix()}")
