#!/usr/bin/env python3
"""Generate and statically validate every fixed classic game template."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

from classic_payload import object_label


MODES = ["memory", "tictactoe", "flappy", "shooter", "puzzle"]


def approved_fixture(knowledge_json: Path, out_path: Path) -> None:
    data = json.loads(knowledge_json.read_text(encoding="utf-8"))
    points = data["knowledge_points"]
    if len(points) < 12:
        raise ValueError("Template validation needs at least 12 knowledge points.")

    def refs(point: dict) -> list[dict[str, str]]:
        return [
            {"source_id": str(item["source_id"]), "locator": str(item["locator"])}
            for item in point.get("source_refs") or []
        ]

    def base(point: dict, qid: str, qtype: str, stem: str, options: list[str], answers: list[str], modes: list[str]) -> dict:
        return {
            "id": qid,
            "type": qtype,
            "topic": str(point.get("topic") or "模板检查"),
            "importance": str(point.get("importance") or "次重点"),
            "difficulty": "基础",
            "stem": stem,
            "options": options,
            "answers": answers,
            "explanation": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            "knowledge_ids": [str(point["id"])],
            "source_basis": str(point.get("statement")),
            "option_sources": [str(point["id"])] * len(options),
            "option_basis": [str(point["statement"])] * len(options),
            "source_refs": refs(point),
            "game_modes": modes,
            "review_status": "通过",
            "review_notes": "",
        }

    labels = []
    for index, point in enumerate(points):
        label = object_label(point, 16)
        if label in labels:
            label = f"{label}{index + 1}"[:18]
        labels.append(label)
    questions = []
    for index, point in enumerate(points[:9]):
        option_indexes = [index, (index + 1) % len(labels), (index + 2) % len(labels), (index + 3) % len(labels)]
        options = [labels[value] for value in option_indexes]
        item = base(point, f"q_single_{index + 1:03}", "single_choice", f"请选择与知识点 {point['id']} 对应的课程概念。", options, [options[0]], ["whack-a-mole", "tictactoe", "shooter"])
        item["option_sources"] = [str(points[value]["id"]) for value in option_indexes]
        item["option_basis"] = [str(points[value]["statement"]) for value in option_indexes]
        questions.append(item)
    for index, point in enumerate(points[:10]):
        questions.append(base(point, f"q_tf_{index + 1:03}", "true_false", str(point["statement"]), ["正确", "错误"], ["正确"], ["flappy"]))
    for group in range(2):
        point = points[group * 4]
        pairs = [f"{labels[group * 4 + offset]}=>{object_label(points[group * 4 + offset], 24)}" for offset in range(4)]
        item = base(point, f"q_match_{group + 1:03}", "matching", f"匹配第 {group + 1} 组课程概念与对应说明。", pairs, pairs, ["memory"])
        item["knowledge_ids"] = [str(value["id"]) for value in points[group * 4:group * 4 + 4]]
        item["option_sources"] = list(item["knowledge_ids"])
        item["option_basis"] = [str(value["statement"]) for value in points[group * 4:group * 4 + 4]]
        questions.append(item)
    for group in range(2):
        point = points[group * 6]
        options = labels[group * 6:group * 6 + 6]
        item = base(point, f"q_multi_{group + 1:03}", "multiple_choice", f"选出第 {group + 1} 组课程结构中的四个概念。", options, options[:4], ["puzzle"])
        item["option_sources"] = [str(value["id"]) for value in points[group * 6:group * 6 + 6]]
        item["option_basis"] = [str(value["statement"]) for value in points[group * 6:group * 6 + 6]]
        questions.append(item)
    out_path.write_text(json.dumps({
        "schema_version": "1.0",
        "course_title": data.get("course_title") or "模板检查课程",
        "knowledge_sha256": hashlib.sha256(knowledge_json.read_bytes()).hexdigest(),
        "questions": questions,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the full polished classic game template set.")
    parser.add_argument("knowledge_json", help="Path to a representative knowledge.json file.")
    parser.add_argument("--out", required=True, help="Output directory for generated validation games.")
    parser.add_argument("--force", action="store_true", help="Replace the output directory if it exists.")
    args = parser.parse_args()

    script_dir = Path(__file__).resolve().parent
    knowledge_json = Path(args.knowledge_json).resolve()
    out_root = Path(args.out).resolve()
    if out_root.exists():
        if not args.force:
            raise FileExistsError(f"Output already exists: {out_root}")
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    question_bank = out_root / "approved-question-bank.json"
    approved_fixture(knowledge_json, question_bank)
    workflow_state = out_root / "workflow-state.json"
    workflow_state.write_text(json.dumps({
        "schema_version": "1.0",
        "materials": {"status": "confirmed"},
        "focus": {"status": "confirmed", "knowledge_ids": []},
        "questions": {
            "status": "approved",
            "question_json": str(question_bank),
            "question_sha256": hashlib.sha256(question_bank.read_bytes()).hexdigest(),
            "knowledge_json": str(knowledge_json),
            "knowledge_sha256": hashlib.sha256(knowledge_json.read_bytes()).hexdigest(),
        },
        "games": {"status": "selected", "selected": ["whack-a-mole", *MODES]},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    whack_out = out_root / "whack-a-mole"
    results.append(run([
        sys.executable,
        str(script_dir / "build_whack_a_mole.py"),
        str(knowledge_json),
        "--question-bank",
        str(question_bank),
        "--workflow-state",
        str(workflow_state),
        "--out",
        str(whack_out),
        "--title",
        "Template Check Whack",
        "--force",
    ]))
    results.append(run([
        sys.executable,
        str(script_dir / "validate_html_game.py"),
        str(whack_out),
        "--knowledge-json",
        str(knowledge_json),
    ]))

    for mode in MODES:
        mode_out = out_root / mode
        results.append(run([
            sys.executable,
            str(script_dir / "build_standalone_classic.py"),
            str(knowledge_json),
            "--question-bank",
            str(question_bank),
            "--workflow-state",
            str(workflow_state),
            "--mode",
            mode,
            "--out",
            str(mode_out),
            "--title",
            f"Template Check {mode}",
            "--force",
        ]))
        results.append(run([
            sys.executable,
            str(script_dir / "validate_html_game.py"),
            str(mode_out),
            "--knowledge-json",
            str(knowledge_json),
        ]))

    failures = [item for item in results if item["returncode"] != 0]
    print(json.dumps({
        "status": "fail" if failures else "pass",
        "out": str(out_root),
        "checked": ["whack-a-mole", *MODES],
        "failures": failures,
        "results": results,
    }, ensure_ascii=False, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
