#!/usr/bin/env python3
"""Build a standalone educational whack-a-mole game from knowledge JSON."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any


def compact(text: Any, limit: int = 24) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[: limit - 1] + "…"


def load_points(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    points = [
        point for point in data.get("knowledge_points", [])
        if point.get("id") and point.get("statement") and point.get("assessment_prompts")
    ]
    if len(points) < 4:
        raise ValueError("At least four assessable knowledge points are required.")
    return data, points


def build_questions(points: list[dict[str, Any]], seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected = points[:]
    rng.shuffle(selected)
    selected = selected[: min(count, len(selected))]
    questions = []
    for point in selected:
        answer = compact(point["statement"], 18)
        decoys = [compact(item["statement"], 18) for item in points if item["id"] != point["id"]]
        rng.shuffle(decoys)
        choices = [answer, *decoys[:3]]
        rng.shuffle(choices)
        questions.append({
            "id": str(point["id"]),
            "prompt": str(point["assessment_prompts"][0]),
            "answer": answer,
            "choices": choices,
            "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
        })
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone educational whack-a-mole game.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = Path(args.knowledge_json).resolve()
    out = Path(args.out).resolve()
    data, points = load_points(source)
    questions = build_questions(points, args.seed, args.count)
    payload = {
        "title": args.title or f"{data.get('course_title', '课程')}：知识打地鼠",
        "duration": max(20, args.duration),
        "visible_ms": 5200,
        "coverage": [item["id"] for item in questions],
        "questions": questions,
    }
    if out.exists():
        if not args.force:
            raise FileExistsError(f"Output already exists: {out}")
        shutil.rmtree(out)
    template = Path(__file__).resolve().parents[1] / "assets" / "whack-a-mole-template"
    shutil.copytree(template, out)
    game_json = json.dumps(payload, ensure_ascii=False, indent=2)
    (out / "game-data.js").write_text(
        f"window.WHACK_GAME_DATA = {game_json};\n"
        f"window.GAME_KNOWLEDGE_COVERAGE = {json.dumps(payload['coverage'], ensure_ascii=False)};\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "pass", "out": str(out), "questions": len(questions)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
