#!/usr/bin/env python3
"""Shared knowledge-to-game payload helpers for polished classic templates."""

from __future__ import annotations

import json
import hashlib
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


def load_question_bank(path: Path, knowledge_path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    expected_hash = hashlib.sha256(knowledge_path.read_bytes()).hexdigest()
    if data.get("knowledge_sha256") != expected_hash:
        raise ValueError("Question bank does not match the current knowledge JSON.")
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Question bank must contain a non-empty questions array.")
    unresolved = [
        str(item.get("id", "[missing]"))
        for item in questions
        if item.get("review_status") not in {"通过", "停用"}
    ]
    if unresolved:
        raise ValueError(f"Question review is incomplete: {', '.join(unresolved)}")
    data["questions"] = [item for item in questions if item.get("review_status") == "通过"]
    if not data["questions"]:
        raise ValueError("Question bank has no approved questions.")
    return data


def validate_workflow(workflow_path: Path, question_bank_path: Path, knowledge_path: Path, mode: str) -> dict[str, Any]:
    state = json.loads(workflow_path.read_text(encoding="utf-8"))
    for stage in ["materials", "focus", "questions"]:
        expected = "approved" if stage == "questions" else "confirmed"
        if state.get(stage, {}).get("status") != expected:
            raise ValueError(f"Workflow stage {stage} is not {expected}.")
    if state.get("games", {}).get("status") != "selected" or mode not in (state.get("games", {}).get("selected") or []):
        raise ValueError(f"Game mode {mode} was not selected by the user.")
    approved_hash = str(state.get("questions", {}).get("question_sha256", ""))
    actual_hash = hashlib.sha256(question_bank_path.read_bytes()).hexdigest()
    if approved_hash != actual_hash:
        raise ValueError("Question bank does not match the exact JSON approved by the user.")
    approved_knowledge_hash = str(state.get("questions", {}).get("knowledge_sha256", ""))
    actual_knowledge_hash = hashlib.sha256(knowledge_path.read_bytes()).hexdigest()
    if approved_knowledge_hash != actual_knowledge_hash:
        raise ValueError("Knowledge JSON does not match the exact version used during question approval.")
    return state


def short(text: Any, limit: int = 58) -> str:
    value = re.sub(r"\s+", " ", str(text)).strip()
    return value if len(value) <= limit else value[:limit].rstrip()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = re.sub(r"\s+", " ", str(value)).strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def explanation(point: dict[str, Any]) -> str:
    return str(point.get("teaching_value") or point.get("evidence") or point["statement"])


def question_prompt(point: dict[str, Any], mode: str) -> str:
    label = object_label(point, 24)
    source_prompt = str((point.get("assessment_prompts") or [""])[0]).strip()
    source_prompt = re.sub(r"\s+", " ", source_prompt)
    if 8 <= len(source_prompt) <= 48 and "..." not in source_prompt:
        return source_prompt
    prompts = {
        "whack": f"下列哪一项最准确对应“{label}”？",
        "tictactoe": f"选择与“{label}”最匹配的课程概念。",
        "shooter": f"击毁不属于“{label}”的干扰项，保留正确概念。",
        "puzzle": f"从 6 个拼图块中选出 4 个属于“{label}”的正确概念。",
    }
    return prompts.get(mode, f"请选择与“{label}”匹配的知识点。")


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
    decoys = dedupe([
        object_label(item) if compact_labels else str(item["statement"])
        for item in points
        if item["id"] != point["id"]
    ])
    rng.shuffle(decoys)
    choices = dedupe([correct, *decoys])[:count]
    if len(choices) < count:
        choices.extend(f"{point_label(point)}-{i + 1}" for i in range(count - len(choices)))
    rng.shuffle(choices)
    return choices


def true_false_item(point: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    make_false = bool(point.get("common_errors")) and rng.random() < 0.55
    if make_false:
        return {
            "id": point["id"],
            "text": str(point["common_errors"][0]),
            "answer": False,
            "why": f"正确表述是：{point['statement']}",
        }
    return {
        "id": point["id"],
        "text": str(point["statement"]),
        "answer": True,
        "why": explanation(point),
    }


def payload_from_question_bank(data: dict[str, Any], bank: dict[str, Any]) -> dict[str, Any]:
    questions = bank["questions"]
    by_type: dict[str, list[dict[str, Any]]] = {}
    for question in questions:
        by_type.setdefault(str(question.get("type")), []).append(question)

    def coverage(items: list[dict[str, Any]]) -> list[str]:
        return list(dict.fromkeys(
            str(knowledge_id)
            for item in items
            for knowledge_id in item.get("knowledge_ids") or []
        ))

    matching = [item for item in by_type.get("matching", []) if "memory" in (item.get("game_modes") or [])]
    memory = []
    for question in matching:
        for pair_index, pair in enumerate(question.get("answers") or []):
            left, separator, right = str(pair).partition("=>")
            if not separator:
                continue
            memory.append({
                "id": f"{question['id']}_{pair_index + 1}",
                "knowledgeIds": [str(value) for value in question.get("knowledge_ids") or []],
                "term": left.strip(),
                "definition": right.strip(),
                "why": str(question.get("explanation", "")),
            })

    single = by_type.get("single_choice", [])
    tictactoe_source = [item for item in single if "tictactoe" in (item.get("game_modes") or [])]
    shooter_source = [item for item in single if "shooter" in (item.get("game_modes") or [])]
    true_false_source = [item for item in by_type.get("true_false", []) if "flappy" in (item.get("game_modes") or [])]
    puzzle_source = [item for item in by_type.get("multiple_choice", []) if "puzzle" in (item.get("game_modes") or [])]
    puzzle = []
    for question in puzzle_source:
        answers = [str(value) for value in question.get("answers") or []]
        options = [str(value) for value in question.get("options") or []]
        ordered = [*answers, *[value for value in options if value not in answers]][:6]
        for option_index, option in enumerate(ordered):
            puzzle.append({
                "id": f"{question['id']}_{option_index + 1}",
                "knowledgeIds": [str(value) for value in question.get("knowledge_ids") or []],
                "type": str(question.get("topic", "课程概念")),
                "label": option,
                "text": str(question.get("topic", "课程概念")),
                "why": str(question.get("explanation", "")),
            })

    used_questions = [*matching, *tictactoe_source, *shooter_source, *true_false_source, *puzzle_source]
    return {
        "title": data.get("course_title") or bank.get("course_title") or "课程经典小游戏",
        "coverage": coverage(used_questions),
        "memory": memory,
        "tictactoe": [{
            "id": str(item["id"]),
            "knowledgeIds": [str(value) for value in item.get("knowledge_ids") or []],
            "prompt": str(item["stem"]),
            "answer": str(item["answers"][0]),
            "choices": [str(value) for value in item["options"]],
            "why": str(item["explanation"]),
        } for item in tictactoe_source],
        "flappy": [{
            "id": str(item["id"]),
            "knowledgeIds": [str(value) for value in item.get("knowledge_ids") or []],
            "text": str(item["stem"]),
            "answer": str(item["answers"][0]) == "正确",
            "why": str(item["explanation"]),
        } for item in true_false_source],
        "shooter": [{
            "id": str(item["id"]),
            "knowledgeIds": [str(value) for value in item.get("knowledge_ids") or []],
            "prompt": str(item["stem"]),
            "answer": str(item["answers"][0]),
            "choices": [str(value) for value in item["options"]],
            "why": str(item["explanation"]),
        } for item in shooter_source],
        "puzzle": puzzle,
    }


def build_payload(data: dict[str, Any], seed: int, question_bank: dict[str, Any] | None = None) -> dict[str, Any]:
    if question_bank is not None:
        return payload_from_question_bank(data, question_bank)
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
                "why": explanation(point),
            }
            for point in memory_points
        ],
        "tictactoe": [
            {
                "id": point["id"],
                "prompt": question_prompt(point, "tictactoe"),
                "answer": object_label(point),
                "choices": choices_for(point, all_points, rng, compact_labels=True),
                "why": explanation(point),
            }
            for point in ttt_points
        ],
        "flappy": [true_false_item(point, rng) for point in flappy_points],
        "shooter": [
            {
                "id": point["id"],
                "prompt": question_prompt(point, "shooter"),
                "answer": object_label(point),
                "choices": choices_for(point, all_points, rng, compact_labels=True),
                "why": explanation(point),
            }
            for point in shooter_points
        ],
        "puzzle": [
            {
                "id": point["id"],
                "type": str(point.get("type", "concept")),
                "label": object_label(point, 16),
                "text": str(point.get("type", "concept")),
                "why": explanation(point),
            }
            for point in puzzle_points
        ],
    }
