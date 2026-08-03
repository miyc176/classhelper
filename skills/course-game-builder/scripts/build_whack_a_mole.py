#!/usr/bin/env python3
"""Build a standalone educational whack-a-mole game from knowledge JSON."""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path
from typing import Any

from classic_payload import load_knowledge, load_question_bank, validate_workflow


def compact(text: Any, limit: int = 24) -> str:
    value = " ".join(str(text).split())
    return value if len(value) <= limit else value[:limit].rstrip()


def dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = " ".join(str(value).split())
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def answer_label(text: Any, limit: int = 16) -> str:
    value = " ".join(str(text).split())
    phrase_rules = [
        ("插头公头", "USB公头/插座"),
        ("全模组", "电源模组类型"),
        ("读写速度", "内存读写更快"),
        ("接口与协议", "USB接口与协议"),
        ("Type-C", "USB Type-C"),
        ("LGA1700", "LGA1700/AM5平台"),
        ("AM5", "LGA1700/AM5平台"),
        ("DIMM", "DIMM/SODIMM"),
        ("SODIMM", "DIMM/SODIMM"),
        ("BGA", "BGA封装"),
    ]
    for needle, label in phrase_rules:
        if needle in value and len(label) <= limit:
            return label
    for separator in ["；", "，", "。", ";", ",", "."]:
        value = value.split(separator, 1)[0]
    replacements = {
        "通常": "",
        "主要": "",
        "包括": "含",
        "区分": "分",
        "为什么": "为何",
        "正确": "",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = value.strip(" ：:，,。.;；")
    candidate = value or str(text)
    return candidate if len(candidate) <= limit else candidate[:limit]


def question_prompt(point: dict[str, Any], answer: str) -> str:
    source_prompt = str((point.get("assessment_prompts") or [""])[0]).strip()
    source_prompt = " ".join(source_prompt.split())
    if 8 <= len(source_prompt) <= 48 and "..." not in source_prompt and "…" not in source_prompt:
        return source_prompt
    return f"下列哪一项最准确对应“{answer}”？"


def build_questions(bank: dict[str, Any], seed: int, count: int) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    selected = [
        item for item in bank["questions"]
        if item.get("type") == "single_choice" and "whack-a-mole" in (item.get("game_modes") or [])
    ]
    if len(selected) < 4:
        raise ValueError("At least four approved whack-a-mole single-choice questions are required.")
    rng.shuffle(selected)
    selected = selected[: min(count, len(selected))]
    questions = []
    for item in selected:
        questions.append({
            "id": str(item["id"]),
            "knowledgeIds": [str(value) for value in item.get("knowledge_ids") or []],
            "prompt": str(item["stem"]),
            "answer": str(item["answers"][0]),
            "choices": [str(value) for value in item["options"]],
            "why": str(item["explanation"]),
        })
    return questions


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone educational whack-a-mole game.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--question-bank", required=True, help="Reviewed question-bank JSON imported from the standard workbook.")
    parser.add_argument("--workflow-state", required=True, help="Confirmed workflow-state.json.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title")
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    source = Path(args.knowledge_json).resolve()
    out = Path(args.out).resolve()
    data = load_knowledge(source)
    question_bank_path = Path(args.question_bank).resolve()
    validate_workflow(Path(args.workflow_state).resolve(), question_bank_path, source, "whack-a-mole")
    bank = load_question_bank(question_bank_path, source)
    questions = build_questions(bank, args.seed, args.count)
    payload = {
        "title": args.title or f"{data.get('course_title', '课程')}：知识打地鼠",
        "duration": max(20, args.duration),
        "visible_ms": 5200,
        "coverage": list(dict.fromkeys(
            knowledge_id
            for item in questions
            for knowledge_id in item.get("knowledgeIds", [])
        )),
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
