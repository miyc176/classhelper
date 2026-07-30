#!/usr/bin/env python3
"""Build a local multiplayer teaching platform from a fixed template."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any


DEFAULT_CANDIDATES = [
    {
        "id": "sample_high_freq",
        "title": "高频用户问题",
        "tag": "频率",
        "description": "真实使用中最常出现的问题，能快速暴露基础能力短板。",
        "example": "反复询问功能入口、流程、限制条件或常见售后政策。",
        "value": "覆盖面大，适合做回归评测基线。",
        "risk": "只看高频会忽略低频高风险场景。",
    },
    {
        "id": "sample_low_freq_high_risk",
        "title": "低频但高风险问题",
        "tag": "风险",
        "description": "出现不多，但一旦答错会造成合规、品牌、交付或业务损失。",
        "example": "资质、退款、数据安全、医疗金融边界或承诺类问法。",
        "value": "能提前发现严重 Badcase。",
        "risk": "需要专家判断，样本构造成本较高。",
    },
    {
        "id": "sample_leadership_report",
        "title": "领导汇报场景",
        "tag": "汇报",
        "description": "面向管理层的总结、归因、风险说明和下一步建议。",
        "example": "请用三句话说明本周问题趋势、关键风险和需要资源。",
        "value": "检验表达结构、优先级判断和业务可读性。",
        "risk": "容易出现空泛结论或遗漏关键风险。",
    },
    {
        "id": "sample_complaint_badcase",
        "title": "投诉类 Badcase",
        "tag": "情绪",
        "description": "用户带有负面情绪、追责或投诉诉求的对话。",
        "example": "用户质疑处理不公、要求升级、要求补偿或威胁曝光。",
        "value": "检验安抚、边界、升级路径和事实核对能力。",
        "risk": "答错会放大舆情和客户体验问题。",
    },
    {
        "id": "sample_noisy_expression",
        "title": "边界表达 / 错别字 / 口语输入",
        "tag": "鲁棒",
        "description": "包含错别字、省略、口语、混杂符号或语义边界不清的问题。",
        "example": "这个能不能搞一下、上次那个咋还不行、权限是不是没开。",
        "value": "检验真实输入鲁棒性，避免只会答标准题。",
        "risk": "模型可能误解意图或给出过度确定答案。",
    },
    {
        "id": "sample_multi_turn_followup",
        "title": "多轮追问场景",
        "tag": "上下文",
        "description": "用户连续追问、修正条件或要求沿用前文上下文。",
        "example": "那如果我是管理员呢？刚才第二种情况能不能走绿色通道？",
        "value": "检验上下文保持、追问澄清和条件更新能力。",
        "risk": "容易遗忘前文或把旧条件错误延续到新问题。",
    },
    {
        "id": "sample_permission_compliance",
        "title": "权限 / 合规敏感问题",
        "tag": "合规",
        "description": "涉及权限、隐私、数据使用、合规边界或敏感承诺的问题。",
        "example": "能不能帮我查某个人的记录？是否可以绕过审批先处理？",
        "value": "检验红线识别、拒答边界和替代方案。",
        "risk": "答错可能产生合规事故。",
    },
    {
        "id": "sample_fixed_history",
        "title": "历史已修复问题",
        "tag": "回归",
        "description": "过去出现过、已经修复过的典型问题或线上缺陷。",
        "example": "上个版本曾经答错的权限判断、流程节点或话术边界。",
        "value": "防止问题回归，沉淀版本质量基线。",
        "risk": "如果不进评测集，同类问题可能反复出现。",
    },
    {
        "id": "sample_cross_domain",
        "title": "跨模块 / 跨部门协作场景",
        "tag": "协作",
        "description": "需要连接多个流程、角色或系统边界才能回答的问题。",
        "example": "客服、运营、技术、法务分别要做什么，谁先处理？",
        "value": "检验复杂业务链路和责任划分。",
        "risk": "容易给出单点答案，忽略上下游约束。",
    },
    {
        "id": "sample_business_critical",
        "title": "业务关键路径问题",
        "tag": "关键",
        "description": "影响成交、交付、审批、故障恢复或核心体验的问题。",
        "example": "下单失败、审批卡住、系统告警、客户无法继续关键流程。",
        "value": "优先保障最影响结果的路径。",
        "risk": "样本少会导致评测分数好看但业务风险仍高。",
    },
]


def load_knowledge(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_embedded(values: list[str]) -> list[dict[str, str]]:
    games = []
    for value in values:
        if "=" not in value:
            continue
        title, href = value.split("=", 1)
        games.append({"title": title.strip(), "href": href.strip()})
    return games


def build_groups(count: int) -> list[dict[str, str]]:
    return [{"id": f"group_{index}", "name": f"第 {index} 组"} for index in range(1, count + 1)]


def build_payload(data: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    title = args.title or "黄金样本拍卖"
    subtitle = args.subtitle or "用 100 个虚拟金币决定哪些样本进入黄金评测集"
    if data.get("course_title") and not args.title:
        subtitle = f"基于《{data['course_title']}》构建课堂互动与评测样本拍卖"
    return {
        "platformTitle": args.platform_title,
        "platformSubtitle": args.platform_subtitle,
        "title": title,
        "subtitle": subtitle,
        "sessionCode": args.session_code,
        "activity": "golden-sample-auction",
        "budget": args.budget,
        "bidStep": args.bid_step,
        "topN": args.top_n,
        "groups": build_groups(args.group_count),
        "knowledgeCoverage": [str(point.get("id")) for point in data.get("knowledge_points", []) if point.get("id")],
        "candidates": DEFAULT_CANDIDATES[: args.count],
        "applications": [
            {
                "id": "golden-sample-auction",
                "title": title,
                "kicker": "多人联机",
                "description": "每人 100 金币，选择最值得进入黄金评测集的样本类型。",
            },
            *[
                {
                    "id": f"embedded_{index}",
                    "title": game["title"],
                    "href": game["href"],
                    "kicker": "小游戏",
                    "description": "从课堂主页进入的外部小游戏或练习。",
                }
                for index, game in enumerate(parse_embedded(args.embed_game), start=1)
            ],
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local multiplayer teaching live platform.")
    parser.add_argument("knowledge_json", nargs="?")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title")
    parser.add_argument("--subtitle")
    parser.add_argument("--platform-title", default="课堂互动平台")
    parser.add_argument("--platform-subtitle", default="选择组别、进入活动、把小游戏和多人任务挂到同一主页")
    parser.add_argument("--session-code", default="GOLD")
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--bid-step", type=int, default=5)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--group-count", type=int, default=6)
    parser.add_argument("--embed-game", action="append", default=[], help="Add a launcher link as title=href.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.budget < 1:
        parser.error("--budget must be at least 1")
    if args.bid_step < 1:
        parser.error("--bid-step must be at least 1")
    if args.budget % args.bid_step:
        parser.error("--budget must be divisible by --bid-step")

    data = load_knowledge(Path(args.knowledge_json).resolve() if args.knowledge_json else None)
    payload = build_payload(data, args)
    out = Path(args.out).resolve()
    if out.exists():
        if not args.force:
            raise FileExistsError(out)
        shutil.rmtree(out)
    template = Path(__file__).resolve().parents[1] / "assets" / "live-teaching-platform-template"
    shutil.copytree(template, out)
    (out / "data.js").write_text(
        "window.LIVE_TEACHING_DATA = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + ";\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "pass", "out": str(out), "candidates": len(payload["candidates"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
