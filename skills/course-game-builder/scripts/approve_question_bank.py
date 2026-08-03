#!/usr/bin/env python3
"""Apply an explicit whole-bank user approval to a validated question JSON file."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Mark pending question rows approved after explicit user confirmation.")
    parser.add_argument("question_json")
    parser.add_argument("--out", help="Output path; defaults to replacing the input file.")
    args = parser.parse_args()
    source = Path(args.question_json).resolve()
    target = Path(args.out).resolve() if args.out else source
    bank = json.loads(source.read_text(encoding="utf-8"))
    questions = bank.get("questions") or []
    needs_changes = [str(item.get("id")) for item in questions if item.get("review_status") == "需修改"]
    if needs_changes:
        raise ValueError("Cannot approve while rows still need changes: " + ", ".join(needs_changes))
    changed = 0
    for item in questions:
        if item.get("review_status") == "待审核":
            item["review_status"] = "通过"
            changed += 1
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(bank, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "out": str(target), "approved": changed, "questions": len(questions)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
