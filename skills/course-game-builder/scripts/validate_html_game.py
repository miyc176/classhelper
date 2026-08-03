#!/usr/bin/env python3
"""Static checks for standalone HTML teaching games."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from pipeline_performance import record_stage


LOCAL_ATTRS = {
    "script": ["src"],
    "link": ["href"],
    "img": ["src"],
    "audio": ["src"],
    "video": ["src", "poster"],
    "source": ["src"],
}


class GameHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append((tag.lower(), {k.lower(): v or "" for k, v in attrs}))

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.text.append(data.strip())


def is_external(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https", "data", "mailto", "tel"}


def find_html(root: Path) -> Path:
    if root.is_file():
        return root
    index = root / "index.html"
    if index.exists():
        return index
    html_files = sorted(root.glob("*.html"))
    if html_files:
        return html_files[0]
    raise FileNotFoundError(f"No HTML file found in {root}")


def collect_files(game_root: Path) -> list[Path]:
    if game_root.is_file():
        game_root = game_root.parent
    return [
        path
        for path in game_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".html", ".css", ".js"}
    ]


def load_expected_ids(path: Path | None) -> set[str]:
    if path is None:
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    points = data.get("knowledge_points", [])
    return {str(point["id"]) for point in points if "id" in point}


def extract_declared_ids(text: str) -> set[str]:
    ids = set(re.findall(r"data-knowledge-id=[\"']([^\"']+)[\"']", text))
    coverage_matches = re.findall(
        r"GAME_KNOWLEDGE_COVERAGE\s*=\s*(\[[^\]]*\])",
        text,
        flags=re.DOTALL,
    )
    coverage_matches.extend(re.findall(r"\"coverage\"\s*:\s*(\[[^\]]*\])", text, flags=re.DOTALL))
    for coverage_text in coverage_matches:
        try:
            parsed = json.loads(coverage_text.replace("'", '"'))
            ids.update(str(item) for item in parsed)
        except json.JSONDecodeError:
            pass
    ids.update(re.findall(r"\bkp_\d+\b", text))
    return ids


def check_assets(html_path: Path, parser: GameHTMLParser) -> list[str]:
    errors: list[str] = []
    for tag, attrs in parser.tags:
        for attr in LOCAL_ATTRS.get(tag, []):
            value = attrs.get(attr)
            if not value or value.startswith("#") or is_external(value):
                continue
            clean = value.split("#", 1)[0].split("?", 1)[0]
            target = (html_path.parent / clean).resolve()
            if not target.exists():
                errors.append(f"Missing asset referenced by <{tag} {attr}>: {value}")
    return errors


def validate(args: argparse.Namespace) -> int:
    root = Path(args.game).resolve()
    html_path = find_html(root)
    game_root = html_path.parent
    html = html_path.read_text(encoding="utf-8")
    parser = GameHTMLParser()
    parser.feed(html)
    all_text = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in collect_files(game_root))

    errors: list[str] = []
    warnings: list[str] = []

    if not any(tag == "meta" and attrs.get("name") == "viewport" for tag, attrs in parser.tags):
        errors.append("Missing responsive viewport meta tag.")
    if not any(tag == "title" for tag, _ in parser.tags):
        errors.append("Missing <title>.")
    if "GAME_KNOWLEDGE_COVERAGE" not in all_text:
        errors.append("Missing window.GAME_KNOWLEDGE_COVERAGE declaration.")
    if re.search(r"lorem ipsum|\btodo\b|replace_me", all_text, flags=re.IGNORECASE):
        warnings.append("Found placeholder-like text.")

    buttons = [attrs for tag, attrs in parser.tags if tag == "button"]
    if not buttons and not re.search(r"<button\b", all_text, flags=re.IGNORECASE):
        errors.append("No <button> controls found.")
    if not any(tag == "main" for tag, _ in parser.tags):
        warnings.append("No <main> landmark found.")

    for attrs in [attrs for tag, attrs in parser.tags if tag == "img"]:
        if not attrs.get("alt"):
            errors.append(f"Image missing alt text: {attrs.get('src', '[no src]')}")

    errors.extend(check_assets(html_path, parser))

    declared_ids = extract_declared_ids(all_text)
    expected_ids = load_expected_ids(Path(args.knowledge_json).resolve() if args.knowledge_json else None)
    if expected_ids and not declared_ids:
        errors.append("No knowledge ids found in game files.")
    if expected_ids and args.require_all_knowledge:
        missing = sorted(expected_ids - declared_ids)
        if missing:
            errors.append(f"Knowledge ids not covered: {', '.join(missing)}")
    if expected_ids and not declared_ids.issubset(expected_ids):
        extra = sorted(declared_ids - expected_ids)
        warnings.append(f"Game declares ids not found in knowledge JSON: {', '.join(extra)}")

    result = {
        "html": str(html_path),
        "status": "fail" if errors else "pass",
        "declared_knowledge_ids": sorted(declared_ids),
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def main() -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Validate an HTML course mini-game.")
    parser.add_argument("game", help="Path to index.html or a game directory.")
    parser.add_argument("--knowledge-json", help="Path to extracted knowledge JSON.")
    parser.add_argument(
        "--require-all-knowledge",
        action="store_true",
        help="Fail if any knowledge point is not declared by the game.",
    )
    parser.add_argument("--performance-file")
    args = parser.parse_args()
    result = validate(args)
    if args.performance_file:
        record_stage(Path(args.performance_file).resolve(), "validation", time.perf_counter() - started, {"validator": "html_game", "passed": result == 0})
    return result


if __name__ == "__main__":
    sys.exit(main())
