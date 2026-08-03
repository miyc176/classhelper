#!/usr/bin/env python3
"""Run a deterministic end-to-end regression of the gated question pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(command: list[str]) -> dict:
    completed = subprocess.run(command, text=True, capture_output=True)
    return {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate course extraction, review, and game-selection gates.")
    parser.add_argument("--out", required=True)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists():
        if not args.force:
            raise FileExistsError(f"Output exists: {out}")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    script_dir = Path(__file__).resolve().parent

    inventory = [{
        "source_id": "src_001", "path": "fixture-course.pptx", "kind": "pptx", "sha1": "fixture-sha1",
        "page_or_slide_count": 12, "extraction_status": "complete", "notes": "",
    }]
    manifest = {
        "schema_version": "2.0",
        "extractor_version": "context-v4",
        "source_inventory": inventory,
        "text_units": [],
        "visual_units": [],
        "context_units": [
            {"source_id": "src_001", "locator": f"slide {index}", "modality": "slide_context", "elements": [], "relations": []}
            for index in range(1, 13)
        ],
        "coverage_audit": [
            {"source_id": "src_001", "unit": f"slide {index}", "status": "needs_knowledge_extraction", "knowledge_ids": [], "notes": ""}
            for index in range(1, 13)
        ],
    }
    manifest_path = out / "material-extraction.json"
    write_json(manifest_path, manifest)
    points = []
    for index in range(1, 13):
        point_id = f"kp_{index:03}"
        points.append({
            "id": point_id,
            "topic": f"模块 {(index - 1) // 4 + 1}",
            "type": "concept",
            "statement": f"课程概念 {index} 的规范定义",
            "scope_status": "in_scope",
            "importance": "重点" if index <= 2 else "次重点",
            "importance_basis": "课程目标与总结页明确强调" if index <= 2 else "课件正文明确讲授",
            "source_refs": [{"source_id": "src_001", "locator": f"slide {index}", "region": "body", "modality": "text"}],
            "evidence": f"第 {index} 页对课程概念 {index} 作出定义",
            "teaching_value": f"用于识别课程概念 {index}",
            "difficulty": "core",
            "prerequisites": [],
            "related_ids": [],
            "common_errors": [f"将课程概念 {index} 与相邻概念混淆"],
            "assessment_prompts": [f"识别课程概念 {index}"],
        })
    knowledge = {
        "course_title": "流水线验证课程",
        "audience": "测试学习者",
        "course_objectives": ["准确识别十二个课程概念"],
        "material_extraction_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "source_inventory": inventory,
        "coverage_audit": [
            {"source_id": "src_001", "unit": f"slide {index}", "status": "covered", "knowledge_ids": [f"kp_{index:03}"], "notes": ""}
            for index in range(1, 13)
        ],
        "knowledge_points": points,
    }
    knowledge_path = out / "knowledge.json"
    write_json(knowledge_path, knowledge)

    labels = [f"概念{index}" for index in range(1, 13)]
    questions = []
    for index, point in enumerate(points):
        indexes = [index, (index + 1) % 12, (index + 2) % 12, (index + 3) % 12]
        options = [labels[value] for value in indexes]
        modes = ["whack-a-mole"]
        if index < 9:
            modes.append("tictactoe")
        if index < 3:
            modes.append("shooter")
        questions.append({
            "id": f"q_single_{index + 1:03}", "type": "single_choice", "topic": point["topic"],
            "importance": point["importance"], "difficulty": "基础",
            "stem": f"根据课程定义，哪一项对应课程概念 {index + 1}？", "options": options, "answers": [options[0]],
            "explanation": point["teaching_value"], "knowledge_ids": [point["id"]], "source_basis": point["statement"],
            "option_sources": [points[value]["id"] for value in indexes],
            "option_basis": [points[value]["statement"] for value in indexes],
            "source_refs": point["source_refs"], "game_modes": modes, "review_status": "待审核", "review_notes": "",
        })
        questions.append({
            "id": f"q_tf_{index + 1:03}", "type": "true_false", "topic": point["topic"],
            "importance": point["importance"], "difficulty": "基础", "stem": f"判断课程概念 {index + 1} 的定义是否与课件一致：{point['statement']}。",
            "options": ["正确", "错误"], "answers": ["正确"], "explanation": point["teaching_value"],
            "knowledge_ids": [point["id"]], "source_basis": point["statement"], "option_sources": [point["id"], point["id"]],
            "option_basis": [point["statement"], point["statement"]], "source_refs": point["source_refs"],
            "game_modes": ["flappy"], "review_status": "待审核", "review_notes": "",
        })
    pair_points = points[:6]
    pairs = [f"{labels[index]}=>{point['statement']}" for index, point in enumerate(pair_points)]
    questions.append({
        "id": "q_match_001", "type": "matching", "topic": "综合复习", "importance": "重点", "difficulty": "进阶",
        "stem": "匹配六个课程概念与课件中的规范定义。", "options": pairs, "answers": pairs,
        "explanation": "依据课件逐项匹配概念和定义。", "knowledge_ids": [point["id"] for point in pair_points],
        "source_basis": pair_points[0]["statement"], "option_sources": [point["id"] for point in pair_points],
        "option_basis": [point["statement"] for point in pair_points], "source_refs": pair_points[0]["source_refs"],
        "game_modes": ["memory"], "review_status": "待审核", "review_notes": "",
    })
    puzzle_points = points[:6]
    questions.append({
        "id": "q_multi_001", "type": "multiple_choice", "topic": "综合复习", "importance": "重点", "difficulty": "综合",
        "stem": "选择课件中被列为第一组核心结构的四个概念。", "options": labels[:6], "answers": labels[:4],
        "explanation": "第一组结构由课件中的前四个概念组成。", "knowledge_ids": [point["id"] for point in puzzle_points[:4]],
        "source_basis": puzzle_points[0]["statement"], "option_sources": [point["id"] for point in puzzle_points],
        "option_basis": [point["statement"] for point in puzzle_points], "source_refs": puzzle_points[0]["source_refs"],
        "game_modes": ["puzzle"], "review_status": "待审核", "review_notes": "",
    })
    bank = {
        "schema_version": "1.0", "course_title": knowledge["course_title"],
        "knowledge_sha256": hashlib.sha256(knowledge_path.read_bytes()).hexdigest(), "questions": questions,
    }
    bank_path = out / "question-bank.json"
    approved_path = out / "approved-question-bank.json"
    write_json(bank_path, bank)

    bad_knowledge = dict(knowledge)
    bad_knowledge["coverage_audit"] = knowledge["coverage_audit"][:-1]
    bad_knowledge_path = out / "bad-missing-unit-knowledge.json"
    write_json(bad_knowledge_path, bad_knowledge)
    bad_bank = json.loads(json.dumps(bank, ensure_ascii=False))
    bad_bank["questions"][0]["option_basis"][0] = "模型自行补充的外部知识"
    bad_bank_path = out / "bad-ungrounded-question-bank.json"
    write_json(bad_bank_path, bad_bank)

    state = out / "workflow-state.json"
    workbook_path = out / "流水线验证课程课程题目.xlsx"
    workbook_path.write_bytes(b"fixture workbook marker")
    first_commands = [
        [sys.executable, str(script_dir / "course_pipeline.py"), "init", "--course-title", knowledge["course_title"], "--out", str(state)],
        [sys.executable, str(script_dir / "course_pipeline.py"), "confirm-materials", str(state), "--notes", "fixture confirmation"],
        [sys.executable, str(script_dir / "course_pipeline.py"), "confirm-focus", str(state), "--ids", "kp_001,kp_002", "--notes", "fixture focus"],
        [sys.executable, str(script_dir / "validate_course_knowledge.py"), str(knowledge_path), "--inventory-manifest", str(manifest_path), "--workflow-state", str(state)],
        [sys.executable, str(script_dir / "build_knowledge_report.py"), str(knowledge_path), "--workflow-state", str(state), "--out", str(out / "课件知识点提取.md")],
        [sys.executable, str(script_dir / "validate_question_bank.py"), str(knowledge_path), str(bank_path), "--workflow-state", str(state)],
    ]
    results = [run(command) for command in first_commands]
    negative_commands = [
        [sys.executable, str(script_dir / "course_pipeline.py"), "select-games", str(state), "--games", "whack-a-mole"],
        [sys.executable, str(script_dir / "validate_course_knowledge.py"), str(bad_knowledge_path), "--inventory-manifest", str(manifest_path), "--workflow-state", str(state)],
        [sys.executable, str(script_dir / "validate_question_bank.py"), str(knowledge_path), str(bad_bank_path), "--workflow-state", str(state)],
    ]
    negative_results = [run(command) for command in negative_commands]
    final_commands = [
        [sys.executable, str(script_dir / "approve_question_bank.py"), str(bank_path), "--out", str(approved_path)],
        [sys.executable, str(script_dir / "validate_question_bank.py"), str(knowledge_path), str(approved_path), "--workflow-state", str(state), "--require-approved"],
        [sys.executable, str(script_dir / "course_pipeline.py"), "approve-questions", str(state), "--workbook", str(workbook_path), "--question-json", str(approved_path), "--knowledge-json", str(knowledge_path)],
        [sys.executable, str(script_dir / "course_pipeline.py"), "select-games", str(state), "--games", "whack-a-mole,memory,tictactoe,flappy,shooter,puzzle"],
        [sys.executable, str(script_dir / "validate_question_bank.py"), str(knowledge_path), str(approved_path), "--workflow-state", str(state), "--require-approved"],
    ]
    results.extend(run(command) for command in final_commands)
    failures = [item for item in results if item["returncode"] != 0]
    missed_guards = [item for item in negative_results if item["returncode"] == 0]
    failed = bool(failures or missed_guards)
    print(json.dumps({
        "status": "fail" if failed else "pass", "out": str(out), "failures": failures,
        "missed_guards": missed_guards, "negative_guards": negative_results, "results": results,
    }, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
