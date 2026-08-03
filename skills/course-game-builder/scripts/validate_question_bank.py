#!/usr/bin/env python3
"""Validate source grounding, coverage, review status, and game fit of question JSON."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


TYPES = {"single_choice", "multiple_choice", "true_false", "matching", "classification", "ordering"}
STATUS = {"待审核", "通过", "需修改", "停用"}
IMPORTANCE = {"重点", "次重点", "拓展"}
DIFFICULTY = {"基础", "进阶", "综合"}
GAME_TYPES = {
    "whack-a-mole": {"single_choice"},
    "memory": {"matching"},
    "tictactoe": {"single_choice"},
    "flappy": {"true_false"},
    "shooter": {"single_choice"},
    "puzzle": {"multiple_choice"},
}
VAGUE_STEMS = {"以下哪项正确", "下列哪项正确", "请选择正确答案", "哪个是正确的", "判断正误", "以下说法正确的是"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a course question bank.")
    parser.add_argument("knowledge_json")
    parser.add_argument("question_json")
    parser.add_argument("--workflow-state")
    parser.add_argument("--require-approved", action="store_true")
    parser.add_argument("--allow-partial-coverage", action="store_true")
    args = parser.parse_args()
    knowledge_path = Path(args.knowledge_json).resolve()
    question_path = Path(args.question_json).resolve()
    knowledge = json.loads(knowledge_path.read_text(encoding="utf-8"))
    bank = json.loads(question_path.read_text(encoding="utf-8"))
    workflow = json.loads(Path(args.workflow_state).read_text(encoding="utf-8")) if args.workflow_state else {}
    errors: list[str] = []
    warnings: list[str] = []
    points = {str(point["id"]): point for point in knowledge.get("knowledge_points") or []}
    questions = bank.get("questions") or []
    expected_hash = sha256(knowledge_path)
    if bank.get("knowledge_sha256") != expected_hash:
        errors.append("Question bank knowledge_sha256 does not match the current knowledge JSON.")
    if bank.get("schema_version") != "1.0":
        errors.append("Question bank schema_version must be 1.0.")
    if str(bank.get("course_title", "")).strip() != str(knowledge.get("course_title", "")).strip():
        errors.append("Question bank course_title does not match knowledge JSON.")
    ids = [str(item.get("id", "")) for item in questions]
    if any(not value.strip() for value in ids):
        errors.append("Every question needs a non-empty id.")
    if len(ids) != len(set(ids)):
        errors.append("Question ids are not unique.")
    coverage: dict[str, list[str]] = defaultdict(list)
    focus_types: dict[str, set[str]] = defaultdict(set)
    type_counts: Counter[str] = Counter()
    stems: Counter[str] = Counter()

    for question in questions:
        qid = str(question.get("id") or "[missing]")
        qtype = question.get("type")
        if qtype not in TYPES:
            errors.append(f"{qid} has invalid type: {qtype}.")
            continue
        type_counts[qtype] += 1
        stems["".join(str(question.get("stem", "")).split()).lower()] += 1
        for field in ["topic", "importance", "difficulty", "stem", "explanation", "source_basis", "review_status"]:
            if not str(question.get(field, "")).strip():
                errors.append(f"{qid} missing required field: {field}.")
        if question.get("review_status") not in STATUS:
            errors.append(f"{qid} has invalid review_status.")
        if question.get("importance") not in IMPORTANCE:
            errors.append(f"{qid} has invalid importance.")
        if question.get("difficulty") not in DIFFICULTY:
            errors.append(f"{qid} has invalid difficulty.")
        if args.require_approved and question.get("review_status") not in {"通过", "停用"}:
            errors.append(f"{qid} is neither approved nor disabled.")
        if "..." in str(question.get("stem")) or "…" in str(question.get("stem")):
            errors.append(f"{qid} uses ellipsis in the stem.")
        normalized_stem = "".join(str(question.get("stem", "")).split()).strip("？?。.")
        if len(normalized_stem) < 8 or normalized_stem in VAGUE_STEMS:
            errors.append(f"{qid} stem is too short or vague to define an answerable target.")
        knowledge_ids = [str(value) for value in question.get("knowledge_ids") or []]
        if not knowledge_ids:
            errors.append(f"{qid} has no knowledge_ids.")
            continue
        unknown = [value for value in knowledge_ids if value not in points]
        if unknown:
            errors.append(f"{qid} references unknown knowledge ids: {', '.join(unknown)}.")
            continue
        source_basis = str(question.get("source_basis", "")).strip()
        valid_basis = {
            str(points[value].get(field, "")).strip()
            for value in knowledge_ids
            for field in ["statement", "evidence"]
        }
        if source_basis not in valid_basis:
            errors.append(f"{qid} source_basis is not an exact statement/evidence value from its knowledge ids.")
        point_refs = {
            (str(ref.get("source_id", "")), str(ref.get("locator", "")))
            for value in knowledge_ids
            for ref in points[value].get("source_refs") or []
        }
        question_refs = {
            (str(ref.get("source_id", "")), str(ref.get("locator", "")))
            for ref in question.get("source_refs") or []
        }
        if not question_refs or not question_refs.issubset(point_refs):
            errors.append(f"{qid} source_refs are missing or not inherited from bound knowledge points.")
        options = [str(value).strip() for value in question.get("options") or [] if str(value).strip()]
        answers = [str(value).strip() for value in question.get("answers") or [] if str(value).strip()]
        option_sources = [str(value).strip() for value in question.get("option_sources") or []]
        option_basis = [str(value).strip() for value in question.get("option_basis") or []]
        if len(options) != len(set(options)):
            errors.append(f"{qid} contains duplicate options.")
        if len(options) > 6:
            errors.append(f"{qid} has more than six options and cannot round-trip through the fixed workbook.")
        if any("..." in value or "…" in value for value in options):
            errors.append(f"{qid} uses ellipsis in an option.")
        if len(option_sources) != len(options) or any(not value for value in option_sources):
            errors.append(f"{qid} option_sources must align one-to-one with non-empty options.")
        if len(option_basis) != len(options) or any(not value for value in option_basis):
            errors.append(f"{qid} option_basis must align one-to-one with non-empty options.")
        else:
            for source, basis in zip(option_sources, option_basis):
                source_id = source.removeprefix("common_error:")
                if source_id not in points:
                    errors.append(f"{qid} option source references unknown knowledge id: {source}.")
                elif source.startswith("common_error:"):
                    if basis not in {str(value).strip() for value in points[source_id].get("common_errors") or []}:
                        errors.append(f"{qid} option basis is not an exact common_error value for {source_id}.")
                elif basis not in {str(points[source_id].get(field, "")).strip() for field in ["statement", "evidence"]}:
                    errors.append(f"{qid} option basis is not an exact statement/evidence value for {source_id}.")
        if not answers:
            errors.append(f"{qid} has no answers.")
        if qtype == "single_choice" and (len(options) < 4 or len(answers) != 1 or answers[0] not in options):
            errors.append(f"{qid} single-choice shape is invalid.")
        if qtype == "multiple_choice" and (len(options) < 4 or len(answers) < 2 or not set(answers).issubset(options)):
            errors.append(f"{qid} multiple-choice shape is invalid.")
        if qtype == "true_false" and (set(options) != {"正确", "错误"} or len(answers) != 1 or answers[0] not in options):
            errors.append(f"{qid} true/false shape is invalid.")
        if qtype in {"matching", "classification"} and (not options or any("=>" not in value for value in options) or set(answers) != set(options)):
            errors.append(f"{qid} mapping shape is invalid.")
        if qtype == "ordering" and (len(options) < 2 or len(answers) != len(options) or set(answers) != set(options)):
            errors.append(f"{qid} ordering shape is invalid.")
        modes = [str(value) for value in question.get("game_modes") or []]
        for mode in modes:
            if mode not in GAME_TYPES or qtype not in GAME_TYPES[mode]:
                errors.append(f"{qid} type {qtype} is not compatible with game {mode}.")
        limits = {"whack-a-mole": 18, "memory": 24, "tictactoe": 28, "shooter": 22, "puzzle": 18}
        for mode in modes:
            limit = limits.get(mode)
            display_values = options
            if mode == "memory":
                display_values = [part.strip() for value in options for part in value.split("=>", 1)]
            if limit and any(len(value) > limit for value in display_values):
                errors.append(f"{qid} has an option too long for {mode} (limit {limit}).")
        if "puzzle" in modes and (len(options) < 6 or len(answers) != 4):
            errors.append(f"{qid} puzzle questions require 6 options and exactly 4 answers.")
        if not args.require_approved or question.get("review_status") == "通过":
            for knowledge_id in knowledge_ids:
                coverage[knowledge_id].append(qid)
                focus_types[knowledge_id].add(str(qtype))

    if not args.allow_partial_coverage:
        missing = sorted(set(points) - set(coverage))
        if missing:
            errors.append(f"Knowledge points without questions: {', '.join(missing)}.")
    repeated_stems = [stem for stem, count in stems.items() if stem and count > 1]
    if repeated_stems:
        errors.append(f"Question bank contains {len(repeated_stems)} duplicate normalized stems.")
    focus_ids = workflow.get("focus", {}).get("knowledge_ids") or []
    if workflow and workflow.get("materials", {}).get("status") != "confirmed":
        errors.append("Course materials have not been confirmed by the user.")
    if workflow and workflow.get("focus", {}).get("status") != "confirmed":
        errors.append("Course focus has not been confirmed by the user.")
    if workflow.get("questions", {}).get("status") == "approved":
        if workflow["questions"].get("question_sha256") != sha256(question_path):
            errors.append("Question JSON does not match the exact bank approved by the user.")
        if workflow["questions"].get("knowledge_sha256") != sha256(knowledge_path):
            errors.append("Knowledge JSON does not match the exact version used during question approval.")
    for focus_id in focus_ids:
        if len(coverage.get(focus_id, [])) < 2 or len(focus_types.get(focus_id, set())) < 2:
            errors.append(f"Focus point {focus_id} needs at least two questions across two types.")

    if workflow.get("games", {}).get("status") == "selected":
        approved = [item for item in questions if item.get("review_status") == "通过"]
        selected = workflow.get("games", {}).get("selected") or []
        counts = {
            mode: sum(1 for item in approved if mode in (item.get("game_modes") or []))
            for mode in GAME_TYPES
        }
        counts["memory"] = sum(
            len(item.get("answers") or []) for item in approved if "memory" in (item.get("game_modes") or [])
        )
        minimums = {"whack-a-mole": 4, "memory": 6, "tictactoe": 9, "flappy": 4, "shooter": 3, "puzzle": 1}
        for mode in selected:
            if counts.get(mode, 0) < minimums[mode]:
                errors.append(f"Selected game {mode} needs at least {minimums[mode]} approved compatible question groups.")

    result = {
        "status": "fail" if errors else "pass",
        "errors": errors,
        "warnings": warnings,
        "questions": len(questions),
        "type_counts": dict(type_counts),
        "coverage": {key: value for key, value in sorted(coverage.items())},
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
