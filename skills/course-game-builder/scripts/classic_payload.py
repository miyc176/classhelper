#!/usr/bin/env python3
"""Shared knowledge-to-game payload helpers for polished classic templates."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path
from typing import Any


def load_knowledge(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    points = data.get("knowledge_points")
    if not isinstance(points, list) or not points:
        raise ValueError("knowledge_json must contain a non-empty knowledge_points array.")
    for point in points:
        if "id" not in point or "statement" not in point:
            raise ValueError("Every knowledge point must include id and statement.")
    return data


def short(text: Any, limit: int = 58) -> str:
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value if len(value) <= limit else value[: limit - 1] + "..."


def point_label(point: dict[str, Any]) -> str:
    statement = str(point.get("statement", ""))
    for token in ["CPU", "GPU", "SSD", "HDD", "USB", "Type-C", "DDR5", "DDR4", "DIMM", "SODIMM", "BGA", "Intel", "AMD", "NVIDIA"]:
        if token.lower() in statement.lower():
            return token
    cleaned = re.sub(r"[,.;:?!()，。；：？！（）]", " ", statement).split()
    return short(cleaned[0] if cleaned else point["id"], 14)


def pick(points: list[dict[str, Any]], types: set[str] | None, count: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = [point for point in points if not types or point.get("type") in types]
    if len(pool) < count:
        pool = points[:]
    rng.shuffle(pool)
    return pool[: min(count, len(pool))]


def choices_for(point: dict[str, Any], points: list[dict[str, Any]], rng: random.Random, count: int = 4) -> list[str]:
    correct = str(point["statement"])
    decoys = [str(item["statement"]) for item in points if item["id"] != point["id"]]
    rng.shuffle(decoys)
    choices = [correct, *decoys[: count - 1]]
    rng.shuffle(choices)
    return choices


def true_false_item(point: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    make_false = bool(point.get("common_errors")) and rng.random() < 0.55
    if make_false:
        return {
            "id": point["id"],
            "text": str(point["common_errors"][0]),
            "answer": False,
            "why": f"课程知识点 {point['id']} 的正确表述是：{point['statement']}",
        }
    return {
        "id": point["id"],
        "text": str(point["statement"]),
        "answer": True,
        "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
    }


def build_payload(data: dict[str, Any], seed: int) -> dict[str, Any]:
    rng = random.Random(seed)
    points = [point for point in data["knowledge_points"] if point.get("assessment_prompts") or point.get("type") != "fact"]
    if not points:
        points = data["knowledge_points"]
    all_points = data["knowledge_points"]
    coverage = [str(point["id"]) for point in all_points]

    memory_points = pick(points, {"concept", "fact", "example", "visual_observation", "relationship"}, 8, rng)
    ttt_points = pick(points, None, 9, rng)
    flappy_points = pick(points, {"misconception", "relationship", "fact", "concept"}, 10, rng)
    shooter_points = pick(points, {"concept", "relationship", "visual_observation", "example"}, 12, rng)
    puzzle_points = pick(points, {"concept", "relationship", "procedure", "visual_observation", "misconception"}, 12, rng)

    return {
        "title": data.get("course_title") or "课程经典小游戏",
        "coverage": coverage,
        "memory": [
            {
                "id": point["id"],
                "term": point_label(point),
                "definition": short(point["statement"], 64),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in memory_points
        ],
        "tictactoe": [
            {
                "id": point["id"],
                "prompt": str((point.get("assessment_prompts") or [f"{point['id']} 的正确表述是什么？"])[0]),
                "answer": str(point["statement"]),
                "choices": choices_for(point, all_points, rng),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in ttt_points
        ],
        "flappy": [true_false_item(point, rng) for point in flappy_points],
        "shooter": [
            {
                "id": point["id"],
                "prompt": str((point.get("assessment_prompts") or [f"击落不符合 {point['id']} 的选项。"])[0]),
                "answer": str(point["statement"]),
                "choices": choices_for(point, all_points, rng),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in ttt_points
        ],
        "puzzle": [
            {
                "id": point["id"],
                "type": str(point.get("type", "concept")),
                "label": point_label(point),
                "text": short(point["statement"], 48),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in puzzle_points
        ],
    }
