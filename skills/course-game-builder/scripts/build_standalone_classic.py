#!/usr/bin/env python3
"""Build one standalone classic knowledge game from the polished template."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from classic_payload import build_payload, load_knowledge, load_question_bank, validate_workflow
from pipeline_performance import record_stage


LABELS = {
    "memory": "知识翻牌",
    "tictactoe": "答题井字棋",
    "flappy": "飞翔判断",
    "shooter": "雷霆战机",
    "puzzle": "知识拼图",
}
MIN_ITEMS = {"memory": 6, "tictactoe": 9, "flappy": 4, "shooter": 3, "puzzle": 6}


def main() -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser(description="Build one polished standalone classic knowledge game.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--question-bank", required=True, help="Reviewed question-bank JSON imported from the standard workbook.")
    parser.add_argument("--workflow-state", required=True, help="Confirmed workflow-state.json.")
    parser.add_argument("--mode", required=True, choices=LABELS)
    parser.add_argument("--out", required=True)
    parser.add_argument("--title")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--performance-file")
    args = parser.parse_args()

    knowledge_path = Path(args.knowledge_json).resolve()
    question_bank_path = Path(args.question_bank).resolve()
    validate_workflow(Path(args.workflow_state).resolve(), question_bank_path, knowledge_path, args.mode)
    data = load_knowledge(knowledge_path)
    question_bank = load_question_bank(question_bank_path, knowledge_path)
    payload_set = build_payload(data, args.seed, question_bank)
    mode = args.mode
    content = payload_set[mode]
    if len(content) < MIN_ITEMS[mode]:
        raise ValueError(f"{mode} needs at least {MIN_ITEMS[mode]} approved compatible items; found {len(content)}.")
    if mode == "puzzle":
        content = content[:12]

    covered_ids = [
        str(knowledge_id)
        for item in content
        for knowledge_id in item.get("knowledgeIds", [item.get("id")])
        if knowledge_id
    ]
    payload = {
        "title": args.title or f"{data.get('course_title', '课程')}：{LABELS[mode]}",
        "mode": mode,
        "coverage": list(dict.fromkeys(covered_ids)),
        "items": content,
        "total": max(4, (len(content) // 6) * 4) if mode == "puzzle" else (9 if mode == "tictactoe" else len(content)),
    }

    out = Path(args.out).resolve()
    if out.exists():
        if not args.force:
            raise FileExistsError(out)
        shutil.rmtree(out)

    template = Path(__file__).resolve().parents[1] / "assets" / "standalone-classic-template"
    shutil.copytree(template, out)
    (out / "game-data.js").write_text(
        "window.STANDALONE_GAME_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\nwindow.GAME_KNOWLEDGE_COVERAGE = "
        + json.dumps(payload["coverage"], ensure_ascii=False)
        + ";\n",
        encoding="utf-8",
    )
    if args.performance_file:
        record_stage(Path(args.performance_file).resolve(), "game_generation", time.perf_counter() - started, {"mode": mode, "items": len(content)})
    print(json.dumps({"status": "pass", "mode": mode, "out": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
