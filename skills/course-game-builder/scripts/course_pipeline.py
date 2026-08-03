#!/usr/bin/env python3
"""Persist user confirmations for the fixed course-to-game workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline_performance import empty_report, save as save_performance


GAME_NAMES = {"whack-a-mole", "memory", "tictactoe", "flappy", "shooter", "puzzle"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def split_values(value: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in value.split(",") if item.strip()))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def next_action(state: dict) -> str:
    if state["materials"]["status"] != "confirmed":
        return "请用户确认材料清单完整。"
    if state["focus"]["status"] != "confirmed":
        return "生成课件知识点提取.md，并请用户确认课程重点。"
    if state["questions"]["status"] != "approved":
        return "生成或重新导入课程题目.xlsx，并请用户审核题目。"
    if state["games"]["status"] != "selected":
        return "请用户从已有六种游戏中选择要生成的游戏。"
    return "可以从审核通过的题库生成所选游戏。"


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage course-game-builder user checkpoints.")
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--course-title", required=True)
    init.add_argument("--out", required=True)
    init.add_argument("--performance-out", help="Defaults to pipeline-performance.json beside workflow state.")
    for command in ["confirm-materials", "confirm-focus", "approve-questions", "select-games", "status"]:
        item = sub.add_parser(command)
        item.add_argument("state")
        if command == "confirm-focus":
            item.add_argument("--ids", required=True, help="Comma-separated confirmed knowledge ids.")
            item.add_argument("--notes", default="")
        elif command == "approve-questions":
            item.add_argument("--workbook", required=True)
            item.add_argument("--question-json", required=True)
            item.add_argument("--knowledge-json", required=True)
            item.add_argument("--notes", default="")
        elif command == "select-games":
            item.add_argument("--games", required=True, help="Comma-separated game mode ids.")
        elif command == "confirm-materials":
            item.add_argument("--notes", default="")
    args = parser.parse_args()

    if args.command == "init":
        path = Path(args.out).resolve()
        performance_path = Path(args.performance_out).resolve() if args.performance_out else path.with_name("pipeline-performance.json")
        save_performance(performance_path, empty_report(args.course_title))
        state = {
            "schema_version": "1.0",
            "course_title": args.course_title,
            "performance_file": str(performance_path),
            "materials": {"status": "pending", "confirmed_at": None, "notes": ""},
            "focus": {"status": "pending", "confirmed_at": None, "knowledge_ids": [], "notes": ""},
            "questions": {"status": "pending", "approved_at": None, "workbook": "", "question_json": "", "question_sha256": "", "knowledge_json": "", "knowledge_sha256": "", "notes": ""},
            "games": {"status": "pending", "selected_at": None, "selected": []},
        }
        save(path, state)
    else:
        path = Path(args.state).resolve()
        state = load(path)
        if args.command == "confirm-materials":
            state["materials"] = {"status": "confirmed", "confirmed_at": now(), "notes": args.notes}
            state["focus"] = {"status": "pending", "confirmed_at": None, "knowledge_ids": [], "notes": ""}
            state["questions"] = {"status": "pending", "approved_at": None, "workbook": "", "question_json": "", "question_sha256": "", "knowledge_json": "", "knowledge_sha256": "", "notes": ""}
            state["games"] = {"status": "pending", "selected_at": None, "selected": []}
        elif args.command == "confirm-focus":
            ids = split_values(args.ids)
            if not ids:
                parser.error("--ids must contain at least one knowledge id")
            state["focus"] = {"status": "confirmed", "confirmed_at": now(), "knowledge_ids": ids, "notes": args.notes}
            state["questions"] = {"status": "pending", "approved_at": None, "workbook": "", "question_json": "", "question_sha256": "", "knowledge_json": "", "knowledge_sha256": "", "notes": ""}
            state["games"] = {"status": "pending", "selected_at": None, "selected": []}
        elif args.command == "approve-questions":
            if state["focus"]["status"] != "confirmed":
                raise ValueError("Course focus must be confirmed before question approval.")
            workbook = Path(args.workbook).resolve()
            question_json = Path(args.question_json).resolve()
            knowledge_json = Path(args.knowledge_json).resolve()
            if workbook.suffix.lower() != ".xlsx" or not workbook.is_file():
                raise FileNotFoundError(f"Reviewed .xlsx workbook not found: {workbook}")
            if not question_json.is_file():
                raise FileNotFoundError(f"Approved question JSON not found: {question_json}")
            if not knowledge_json.is_file():
                raise FileNotFoundError(f"Knowledge JSON not found: {knowledge_json}")
            validation = subprocess.run([
                sys.executable,
                str(Path(__file__).resolve().with_name("validate_question_bank.py")),
                str(knowledge_json),
                str(question_json),
                "--workflow-state",
                str(path),
                "--require-approved",
            ], text=True, capture_output=True)
            if validation.returncode != 0:
                raise ValueError("Question approval validation failed:\n" + (validation.stdout or validation.stderr))
            state["questions"] = {
                "status": "approved", "approved_at": now(), "workbook": str(workbook),
                "question_json": str(question_json), "question_sha256": sha256(question_json),
                "knowledge_json": str(knowledge_json), "knowledge_sha256": sha256(knowledge_json), "notes": args.notes,
            }
            state["games"] = {"status": "pending", "selected_at": None, "selected": []}
        elif args.command == "select-games":
            if state["questions"]["status"] != "approved":
                raise ValueError("Questions must be approved before game selection.")
            games = split_values(args.games)
            if not games:
                parser.error("--games must contain at least one game mode id")
            unknown = sorted(set(games) - GAME_NAMES)
            if unknown:
                raise ValueError(f"Unknown games: {', '.join(unknown)}")
            state["games"] = {"status": "selected", "selected_at": now(), "selected": games}
        save(path, state)

    state = load(path)
    print(json.dumps({"status": "pass", "state": str(path), "next_action": next_action(state), "workflow": state}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
