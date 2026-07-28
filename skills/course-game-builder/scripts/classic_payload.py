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


def object_label(point: dict[str, Any], limit: int = 22) -> str:
    statement = re.sub(r"\s+", " ", str(point.get("statement", ""))).strip()
    phrase_rules = [
        ("断电后数据仍会保留", "断电后仍保留数据"),
        ("长期保存数据", "长期保存数据"),
        ("M.2/NVMe", "SSD常见形态"),
        ("2.5英寸SATA", "SSD常见形态"),
        ("内存条是", "电脑主存储器"),
        ("读写速度", "内存读写更快"),
        ("基础硬件", "六类基础硬件"),
        ("主板通常是", "主板是电路板"),
        ("独立显卡", "独显外观特征"),
        ("Type-C", "Type-C多协议"),
        ("接口与协议", "USB接口与协议"),
        ("插头公头", "USB公头/插座"),
        ("CPU是中央处理器", "CPU运算控制核心"),
        ("Intel和AMD", "Intel/AMD厂商"),
        ("电源是", "电脑供电部件"),
        ("全模组", "电源模组类型"),
        ("不同代数版本", "内存代数不混插"),
        ("DIMM", "DIMM/SODIMM"),
        ("SODIMM", "DIMM/SODIMM"),
        ("BGA", "BGA封装"),
        ("GPU", "图形与并行计算"),
        ("HDD", "机械硬盘HDD"),
        ("SSD", "固态硬盘SSD"),
    ]
    for needle, label in phrase_rules:
        if needle in statement and len(label) <= limit:
            return label
    for separator in ["；", "，", "。", ";", ",", "."]:
        statement = statement.split(separator, 1)[0]
    replacements = {
        "通常": "",
        "主要": "",
        "包括": "含",
        "可以": "可",
        "课件": "",
        "硬件": "",
    }
    for source, target in replacements.items():
        statement = statement.replace(source, target)
    statement = statement.strip(" ：:，,。.;；")
    if len(statement) <= limit:
        return statement
    base = point_label(point)
    suffix = str(point.get("type") or "要点")
    fallback = f"{base}{suffix}"
    return fallback if len(fallback) <= limit else base[:limit]


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


def choices_for(
    point: dict[str, Any],
    points: list[dict[str, Any]],
    rng: random.Random,
    count: int = 4,
    *,
    compact_labels: bool = False,
) -> list[str]:
    correct = object_label(point) if compact_labels else str(point["statement"])
    decoys = [
        object_label(item) if compact_labels else str(item["statement"])
        for item in points
        if item["id"] != point["id"]
    ]
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
                "definition": object_label(point, 24),
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
                "answer": object_label(point),
                "choices": choices_for(point, all_points, rng, compact_labels=True),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in ttt_points
        ],
        "puzzle": [
            {
                "id": point["id"],
                "type": str(point.get("type", "concept")),
                "label": object_label(point, 16),
                "text": str(point.get("type", "concept")),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in puzzle_points
        ],
    }
