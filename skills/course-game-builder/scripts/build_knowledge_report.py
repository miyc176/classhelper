#!/usr/bin/env python3
"""Render detailed source-traceable course knowledge as Markdown."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def refs_text(refs: list[dict]) -> str:
    return "；".join(
        f"{item.get('source_id')} {item.get('locator')} {item.get('region', '')} [{item.get('modality', '')}]".strip()
        for item in refs
    )


def md_cell(value: object) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", "<br>")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build 课件知识点提取.md from knowledge JSON.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--workflow-state")
    args = parser.parse_args()
    data = json.loads(Path(args.knowledge_json).read_text(encoding="utf-8"))
    workflow = json.loads(Path(args.workflow_state).read_text(encoding="utf-8")) if args.workflow_state else {}
    points = data.get("knowledge_points") or []
    focus_ids = set(workflow.get("focus", {}).get("knowledge_ids") or [])
    proposed_focus = [point for point in points if point.get("importance") == "重点"]
    topics: dict[str, list[dict]] = defaultdict(list)
    for point in points:
        topics[str(point.get("topic") or "未分组")].append(point)
    types = Counter(str(point.get("type", "unknown")) for point in points)
    levels = Counter(str(point.get("importance", "unknown")) for point in points)
    audit = data.get("coverage_audit") or []

    lines = [
        f"# {data.get('course_title', '课程')}：课件知识点提取",
        "",
        "> 本文档只整理课件材料中可定位、可举证的内容。未确认或无法读取的内容不会进入题库。",
        "",
        "## 一、课程范围",
        "",
        f"- 适用对象：{data.get('audience') or '课件未注明'}",
        f"- 课程目标：{'；'.join(data.get('course_objectives') or []) or '课件未明确列出'}",
        f"- 材料确认：{workflow.get('materials', {}).get('status', '未记录')}",
        f"- 重点确认：{workflow.get('focus', {}).get('status', '待用户确认')}",
        "",
        "## 二、材料与覆盖审计",
        "",
        "| 来源ID | 文件 | 类型 | 页/幻灯片数 | 提取状态 | 备注 |",
        "| --- | --- | --- | ---: | --- | --- |",
    ]
    for item in data.get("source_inventory") or []:
        lines.append(f"| {md_cell(item.get('source_id'))} | {md_cell(item.get('path'))} | {md_cell(item.get('kind'))} | {item.get('page_or_slide_count', 0)} | {md_cell(item.get('extraction_status'))} | {md_cell(item.get('notes', ''))} |")
    lines.extend([
        "",
        f"- 覆盖单元：{len(audit)}",
        f"- 已覆盖：{sum(item.get('status') == 'covered' for item in audit)}",
        f"- 无教学内容：{sum(item.get('status') == 'no_instructional_content' for item in audit)}",
        f"- 未解决/阻塞：{sum(item.get('status') not in {'covered', 'no_instructional_content'} for item in audit)}",
        "",
        "### 覆盖单元明细",
        "",
        "| 来源ID | 单元 | 状态 | 知识点ID | 审计说明 |",
        "| --- | --- | --- | --- | --- |",
    ])
    for item in audit:
        lines.append(
            f"| {md_cell(item.get('source_id'))} | {md_cell(item.get('unit'))} | {md_cell(item.get('status'))} | "
            f"{md_cell('、'.join(item.get('knowledge_ids') or []))} | {md_cell(item.get('notes', ''))} |"
        )
    lines.extend([
        "",
        "## 三、知识点统计",
        "",
        f"- 知识点总数：{len(points)}",
        f"- 类型：{'；'.join(f'{key} {value}' for key, value in sorted(types.items()))}",
        f"- 重点等级：{'；'.join(f'{key} {value}' for key, value in sorted(levels.items()))}",
        "",
        "## 四、课程重点确认",
        "",
    ])
    focus_pool = [point for point in points if point.get("id") in focus_ids] if focus_ids else proposed_focus
    if focus_pool:
        lines.append("| 知识点ID | 主题 | 重点内容 | 判定依据 | 状态 |")
        lines.append("| --- | --- | --- | --- | --- |")
        for point in focus_pool:
            status = "用户已确认" if point.get("id") in focus_ids else "候选，待用户确认"
            lines.append(f"| {md_cell(point.get('id'))} | {md_cell(point.get('topic'))} | {md_cell(point.get('statement'))} | {md_cell(point.get('importance_basis'))} | {status} |")
    else:
        lines.append("当前没有重点候选，必须请用户指定后才能生成题库。")

    lines.extend(["", "## 五、完整知识点", ""])
    for topic, topic_points in topics.items():
        lines.extend([f"### {topic}", ""])
        for point in topic_points:
            lines.extend([
                f"#### {point.get('id')} [{point.get('importance')}] {point.get('statement')}",
                "",
                f"- 类型/难度：{point.get('type')} / {point.get('difficulty', '未标注')}",
                f"- 课件证据：{point.get('evidence')}",
                f"- 来源定位：{refs_text(point.get('source_refs') or [])}",
                f"- 教学价值：{point.get('teaching_value')}",
                f"- 重点依据：{point.get('importance_basis')}",
                f"- 前置知识：{'、'.join(point.get('prerequisites') or []) or '无'}",
                f"- 相关知识：{'、'.join(point.get('related_ids') or []) or '无'}",
                f"- 常见错误：{'；'.join(point.get('common_errors') or []) or '课件未提供'}",
                f"- 可考提示：{'；'.join(point.get('assessment_prompts') or []) or '待题目工程生成'}",
                "",
            ])
    lines.extend([
        "## 六、不能进入题库的内容",
        "",
    ])
    blocked = [item for item in audit if item.get("status") not in {"covered", "no_instructional_content"}]
    if blocked:
        for item in blocked:
            lines.append(f"- {item.get('source_id')} {item.get('unit')}：{item.get('status')}；{item.get('notes', '')}")
    else:
        lines.append("- 无。所有教学单元均已覆盖。")

    out = Path(args.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"status": "pass", "out": str(out), "knowledge_points": len(points), "focus_candidates": len(focus_pool)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
