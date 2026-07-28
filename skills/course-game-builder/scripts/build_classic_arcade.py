#!/usr/bin/env python3
"""Generate a classic mini-game arcade from course knowledge JSON."""

from __future__ import annotations

import argparse
import html
import json
import random
import re
import shutil
import sys
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


def short(text: str, limit: int = 58) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def point_label(point: dict[str, Any]) -> str:
    statement = str(point.get("statement", ""))
    for token in ["CPU", "GPU", "SSD", "HDD", "USB", "Type-C", "DDR5", "DDR4", "DIMM", "SODIMM", "BGA", "Intel", "AMD", "NVIDIA"]:
        if token.lower() in statement.lower():
            return token
    cleaned = re.sub(r"[，。；：、,.()（）]", " ", statement).split()
    return short(cleaned[0] if cleaned else point["id"], 14)


def pick(points: list[dict[str, Any]], types: set[str] | None, count: int, rng: random.Random) -> list[dict[str, Any]]:
    pool = [point for point in points if not types or point.get("type") in types]
    if len(pool) < count:
        pool = points[:]
    rng.shuffle(pool)
    return pool[: min(count, len(pool))]


def choices_for(point: dict[str, Any], points: list[dict[str, Any]], rng: random.Random, count: int = 4) -> list[str]:
    correct = str(point["statement"])
    decoys = [str(item["statement"]) for item in points if item["id"] != point["id"]]
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
            "why": f"课件知识点 {point['id']} 的正确表述是：{point['statement']}",
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

    whack_points = pick(points, {"concept", "fact", "example", "visual_observation"}, 8, rng)
    memory_points = pick(points, {"concept", "fact", "example", "visual_observation", "relationship"}, 8, rng)
    ttt_points = pick(points, None, 9, rng)
    flappy_points = pick(points, {"misconception", "relationship", "fact", "concept"}, 10, rng)
    shooter_points = pick(points, {"concept", "relationship", "visual_observation", "example"}, 12, rng)
    puzzle_points = pick(points, {"concept", "relationship", "procedure", "visual_observation", "misconception"}, 12, rng)

    categories = []
    for category in ["concept", "relationship", "visual_observation", "misconception", "example"]:
        ids = [point["id"] for point in shooter_points if point.get("type") == category]
        if ids:
            categories.append({"name": category, "ids": ids})
    if not categories:
        categories = [{"name": "core", "ids": [point["id"] for point in shooter_points[:6]]}]

    return {
        "title": data.get("course_title") or "课程经典小游戏",
        "coverage": coverage,
        "whack": [
            {
                "id": point["id"],
                "prompt": str((point.get("assessment_prompts") or [f"选择符合 {point['id']} 的正确表述。"])[0]),
                "answer": str(point["statement"]),
                "choices": choices_for(point, all_points, rng),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in whack_points
        ],
        "memory": [
            {
                "id": point["id"],
                "term": point_label(point),
                "definition": short(point["statement"], 64),
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
        "shooter": {
            "categories": categories,
            "targets": [
                {
                    "id": point["id"],
                    "type": str(point.get("type", "concept")),
                    "label": point_label(point),
                    "text": short(point["statement"], 42),
                    "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
                }
                for point in shooter_points
            ],
        },
        "puzzle": [
            {
                "id": point["id"],
                "type": str(point.get("type", "concept")),
                "label": point_label(point),
                "text": short(point["statement"], 48),
                "why": str(point.get("teaching_value") or point.get("evidence") or point["statement"]),
            }
            for point in puzzle_points
        ],
    }


def write_index(out: Path, title: str) -> None:
    safe_title = html.escape(title)
    (out / "index.html").write_text(f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <main class="arcade-shell">
      <header class="hero">
        <div>
          <p class="eyebrow">Knowledge Arcade</p>
          <h1>{safe_title}</h1>
        </div>
        <div class="hud" aria-live="polite">
          <span id="mode-status">打地鼠</span>
          <span id="score">0 分</span>
          <span id="coverage">0 / 0</span>
        </div>
      </header>
      <nav class="mode-tabs" aria-label="小游戏模式">
        <button class="mode active" data-mode="whack" type="button">打地鼠</button>
        <button class="mode" data-mode="memory" type="button">翻牌</button>
        <button class="mode" data-mode="tictactoe" type="button">井字棋</button>
        <button class="mode" data-mode="flappy" type="button">飞翔小鸟</button>
        <button class="mode" data-mode="shooter" type="button">雷霆战机</button>
        <button class="mode" data-mode="puzzle" type="button">拼图</button>
      </nav>
      <section id="game" class="game-stage"></section>
    </main>
    <script src="./game-data.js"></script>
    <script src="./game.js"></script>
  </body>
</html>
""", encoding="utf-8")


def write_styles(out: Path) -> None:
    (out / "styles.css").write_text(r""":root {
  --ink: #10212b;
  --muted: #60707c;
  --paper: #f3f7f8;
  --panel: #ffffff;
  --line: #d4e0e6;
  --accent: #006d77;
  --accent2: #b45f06;
  --good: #147143;
  --bad: #a63a2d;
  --sky: #d9f2ff;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  background: radial-gradient(circle at top left, #e9f6f5, var(--paper) 38%);
  color: var(--ink);
  font-family: Arial, "Microsoft YaHei", sans-serif;
}
button {
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 0 14px;
  background: var(--panel);
  color: var(--ink);
  font: inherit;
  cursor: pointer;
}
button:hover, button:focus-visible { border-color: var(--accent); outline: 2px solid rgba(0, 109, 119, 0.18); }
button[disabled] { opacity: .66; cursor: not-allowed; }
.arcade-shell { width: min(1180px, calc(100vw - 24px)); margin: 0 auto; padding: 20px 0; }
.hero, .hud, .mode-tabs, .row, .actions { display: flex; align-items: center; gap: 10px; }
.hero { justify-content: space-between; border-bottom: 1px solid var(--line); padding-bottom: 14px; }
.eyebrow { margin: 0 0 4px; color: var(--accent2); font-size: 12px; font-weight: 800; text-transform: uppercase; }
h1, h2, p { margin-top: 0; }
h1 { margin-bottom: 0; font-size: 32px; line-height: 1.15; }
h2 { margin-bottom: 8px; font-size: 24px; }
.hud span { min-width: 82px; border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; text-align: center; background: var(--panel); }
.mode-tabs { margin: 16px 0; flex-wrap: wrap; }
.mode.active { border-color: var(--accent); background: #e2f4f3; color: #064f55; font-weight: 800; }
.game-stage { min-height: calc(100vh - 160px); }
.panel { display: grid; grid-template-columns: .9fr 1.1fr; gap: 18px; min-height: calc(100vh - 170px); }
.brief { border-left: 4px solid var(--accent); background: var(--panel); padding: 14px 16px; line-height: 1.45; }
.arena { position: relative; min-height: 440px; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: linear-gradient(#faffff, #e9f3f5); }
.side { display: grid; gap: 12px; align-content: start; }
.feedback { min-height: 76px; border: 1px solid var(--line); border-radius: 8px; padding: 12px 14px; background: var(--panel); line-height: 1.45; }
.mole-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px; padding: 18px; }
.mole { min-height: 132px; border-radius: 999px 999px 22px 22px; background: #fff7de; border: 2px solid #d6ad55; box-shadow: inset 0 -18px #c2873e; line-height: 1.3; padding: 14px 12px 24px; font-size: clamp(13px, 1.25vw, 16px); overflow-wrap: anywhere; }
.mole.correct { background: #e8f8ed; border-color: var(--good); }
.mole.wrong { background: #fff0ed; border-color: var(--bad); }
.card-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 16px; }
.flip { min-height: 92px; border: 1px solid var(--line); border-radius: 8px; background: #0c6870; color: #fff; font-weight: 700; }
.flip.open, .flip.matched { background: #fff; color: var(--ink); }
.flip.matched { border-color: var(--good); background: #e8f8ed; }
.ttt { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; padding: 16px; max-width: 460px; margin: 0 auto; }
.cell { aspect-ratio: 1; font-size: 42px; font-weight: 900; background: #fff; }
.quiz-options { display: grid; gap: 10px; }
.flappy-world { position: relative; min-height: 430px; background: linear-gradient(#d9f2ff, #f7fbff); }
.bird { position: absolute; left: 48px; top: 165px; width: 42px; height: 34px; border-radius: 50%; background: #ffcf33; border: 2px solid #9a6400; }
.gate { position: absolute; right: 70px; top: 75px; display: grid; gap: 170px; }
.gate button { width: 120px; background: #fff; font-weight: 800; }
.shooter-world { position: relative; min-height: 430px; background: linear-gradient(#111d2b, #163c50); color: #fff; }
.ship { position: absolute; bottom: 24px; left: calc(50% - 34px); width: 68px; height: 52px; clip-path: polygon(50% 0, 100% 100%, 50% 78%, 0 100%); background: #6ee7f2; }
.enemy-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; padding: 18px; }
.enemy { min-height: 82px; background: rgba(255,255,255,.94); color: var(--ink); border: 1px solid #8ac6d0; }
.puzzle-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; padding: 16px; }
.piece { min-height: 86px; background: #fff; border: 1px solid var(--line); text-align: left; line-height: 1.35; }
.piece.selected { border-color: var(--accent); background: #e2f4f3; }
.piece.placed { border-color: var(--good); background: #e8f8ed; }
.slots { display: grid; gap: 10px; }
.slot { min-height: 56px; border: 1px dashed var(--accent); border-radius: 8px; padding: 10px; background: #fff; }
@media (max-width: 860px) {
  .hero, .actions { align-items: stretch; flex-direction: column; }
  .hud { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .mode-tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .panel { grid-template-columns: 1fr; }
  .arena, .flappy-world, .shooter-world { min-height: 360px; }
  .mole-grid, .enemy-grid, .puzzle-board { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .mole { min-height: 150px; font-size: 14px; }
  .card-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  h1 { font-size: 25px; }
}
""", encoding="utf-8")


def write_js(out: Path, payload: dict[str, Any]) -> None:
    (out / "game-data.js").write_text(
        "window.COURSE_ARCADE_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
        "window.GAME_KNOWLEDGE_COVERAGE = window.COURSE_ARCADE_DATA.coverage;\n",
        encoding="utf-8",
    )
    (out / "game.js").write_text(r"""const data = window.COURSE_ARCADE_DATA;
let mode = "whack";
let score = 0;
let seen = new Set();
let round = 0;
let selected = null;
const stage = document.querySelector("#game");
const scoreEl = document.querySelector("#score");
const coverageEl = document.querySelector("#coverage");
const modeStatus = document.querySelector("#mode-status");
const labels = { whack: "打地鼠", memory: "翻牌", tictactoe: "井字棋", flappy: "飞翔小鸟", shooter: "雷霆战机", puzzle: "拼图" };

function updateHud() {
  scoreEl.textContent = `${score} 分`;
  coverageEl.textContent = `${seen.size} / ${data.coverage.length}`;
  modeStatus.textContent = labels[mode];
}
function esc(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
function mark(ids) {
  ids.forEach((id) => seen.add(id));
  updateHud();
}
function panel(title, brief, arena, side = "") {
  stage.innerHTML = `<section class="panel"><div class="arena">${arena}</div><aside class="side"><p class="eyebrow">${labels[mode]}</p><h2>${title}</h2><div class="brief">${brief}</div>${side}<div id="feedback" class="feedback">开始挑战。</div><div class="actions"><button id="next" type="button">下一轮</button><button id="reset" type="button">重置分数</button></div></aside></section>`;
  document.querySelector("#next").addEventListener("click", () => { round += 1; render(); });
  document.querySelector("#reset").addEventListener("click", () => { score = 0; seen = new Set(); round = 0; render(); });
}
function feedback(text) { document.querySelector("#feedback").textContent = text; }
function addScore(value) { score += value; updateHud(); }

function renderWhack() {
  const item = data.whack[round % data.whack.length];
  const arena = `<div class="mole-grid">${item.choices.map((choice) => `<button class="mole" data-choice="${esc(choice)}" type="button">${esc(choice)}</button>`).join("")}</div>`;
  panel("打中正确知识地鼠", esc(item.prompt), arena);
  document.querySelectorAll(".mole").forEach((button) => {
    button.setAttribute("data-knowledge-id", item.id);
    button.addEventListener("click", () => {
      const ok = button.dataset.choice === item.answer;
      button.classList.add(ok ? "correct" : "wrong");
      if (ok) { addScore(10); mark([item.id]); }
      feedback(`${ok ? "命中！" : "打偏了。"} ${item.why}`);
    });
  });
}

function renderMemory() {
  const pairs = data.memory.slice(0, 8);
  const cards = pairs.flatMap((item) => [
    { id: item.id, text: item.term, why: item.why },
    { id: item.id, text: item.definition, why: item.why },
  ]).sort((a, b) => (a.text > b.text ? 1 : -1));
  panel("翻出术语和定义", "翻开两张牌，找到同一知识点的术语和定义。", `<div class="card-grid">${cards.map((card, i) => `<button class="flip" data-index="${i}" data-id="${card.id}" data-text="${esc(card.text)}" type="button">?</button>`).join("")}</div>`);
  let open = [];
  document.querySelectorAll(".flip").forEach((button) => {
    button.addEventListener("click", () => {
      if (button.classList.contains("matched") || open.includes(button)) return;
      button.classList.add("open");
      button.textContent = button.dataset.text;
      open.push(button);
      if (open.length === 2) {
        const ok = open[0].dataset.id === open[1].dataset.id;
        if (ok) {
          open.forEach((item) => item.classList.add("matched"));
          addScore(8); mark([open[0].dataset.id]); feedback(`配对成功。覆盖 ${open[0].dataset.id}`);
          open = [];
        } else {
          feedback("这两张不属于同一知识点。");
          setTimeout(() => { open.forEach((item) => { item.classList.remove("open"); item.textContent = "?"; }); open = []; }, 650);
        }
      }
    });
  });
}

function renderTicTacToe() {
  const questions = data.tictactoe;
  panel("答对才能落子", "点击棋盘格，答对题目后才能放下 X。电脑会自动下一步 O。", `<div class="ttt">${Array.from({ length: 9 }, (_, i) => `<button class="cell" data-cell="${i}" type="button"></button>`).join("")}</div>`, `<div id="quiz" class="quiz-options"></div>`);
  const board = Array(9).fill("");
  function bot() {
    const empty = board.findIndex((v) => !v);
    if (empty >= 0) board[empty] = "O";
  }
  function draw() {
    document.querySelectorAll(".cell").forEach((cell, i) => { cell.textContent = board[i]; cell.disabled = Boolean(board[i]); });
  }
  document.querySelectorAll(".cell").forEach((cell) => {
    cell.addEventListener("click", () => {
      const i = Number(cell.dataset.cell);
      const q = questions[(round + i) % questions.length];
      document.querySelector("#quiz").innerHTML = `<div class="brief">${esc(q.prompt)}</div>${q.choices.map((choice) => `<button class="quiz-choice" data-cell="${i}" data-id="${q.id}" data-answer="${esc(q.answer)}" data-choice="${esc(choice)}" type="button">${esc(choice)}</button>`).join("")}`;
      document.querySelectorAll(".quiz-choice").forEach((button) => {
        button.addEventListener("click", () => {
          const ok = button.dataset.choice === button.dataset.answer;
          if (ok && !board[i]) { board[i] = "X"; addScore(10); mark([button.dataset.id]); bot(); }
          feedback(`${ok ? "答对，成功落子。" : "答错，本格暂不能落子。"} ${q.why}`);
          draw();
        });
      });
    });
  });
  draw();
}

function renderFlappy() {
  const item = data.flappy[round % data.flappy.length];
  panel("飞过真假门", esc(item.text), `<div class="flappy-world"><div class="bird"></div><div class="gate"><button data-answer="true" type="button">正确门</button><button data-answer="false" type="button">错误门</button></div></div>`);
  document.querySelectorAll(".gate button").forEach((button) => {
    button.addEventListener("click", () => {
      const ok = (button.dataset.answer === "true") === item.answer;
      if (ok) { addScore(10); mark([item.id]); }
      feedback(`${ok ? "顺利穿过。" : "撞到门了。"} ${item.why}`);
    });
  });
}

function renderShooter() {
  const category = data.shooter.categories[round % data.shooter.categories.length];
  const targets = data.shooter.targets.slice(0, 12);
  panel("只击落目标分类", `当前任务：击落类型为 ${esc(category.name)} 的目标。`, `<div class="shooter-world"><div class="enemy-grid">${targets.map((target) => `<button class="enemy" data-id="${target.id}" data-type="${target.type}" type="button">${esc(target.label)}<br><small>${esc(target.text)}</small></button>`).join("")}</div><div class="ship"></div></div>`);
  document.querySelectorAll(".enemy").forEach((button) => {
    button.addEventListener("click", () => {
      const ok = category.ids.includes(button.dataset.id) || button.dataset.type === category.name;
      if (ok) { addScore(7); mark([button.dataset.id]); button.disabled = true; button.classList.add("correct"); }
      else { button.classList.add("wrong"); }
      const target = targets.find((item) => item.id === button.dataset.id);
      feedback(`${ok ? "击落正确目标。" : "这是干扰目标。"} ${target?.why || ""}`);
    });
  });
}

function renderPuzzle() {
  const pieces = data.puzzle.slice(0, 9);
  const types = [...new Set(pieces.map((item) => item.type))].slice(0, 4);
  if (!types.length) types.push("concept");
  panel("整理知识拼图", "先点知识碎片，再点对应类型槽，把知识点整理成结构图。", `<div class="puzzle-board">${pieces.map((piece) => `<button class="piece" data-id="${piece.id}" data-type="${piece.type}" type="button"><strong>${esc(piece.label)}</strong><br>${esc(piece.text)}</button>`).join("")}</div>`, `<div class="slots">${types.map((type) => `<button class="slot" data-type="${type}" type="button">${type}</button>`).join("")}</div>`);
  selected = null;
  document.querySelectorAll(".piece").forEach((piece) => {
    piece.addEventListener("click", () => {
      selected = piece;
      document.querySelectorAll(".piece").forEach((item) => item.classList.remove("selected"));
      piece.classList.add("selected");
    });
  });
  document.querySelectorAll(".slot").forEach((slot) => {
    slot.addEventListener("click", () => {
      if (!selected) return;
      const ok = selected.dataset.type === slot.dataset.type;
      if (ok) { addScore(6); mark([selected.dataset.id]); selected.classList.add("placed"); selected.disabled = true; }
      feedback(ok ? `拼入 ${slot.dataset.type} 分类。` : `分类不对：这个碎片属于 ${selected.dataset.type}。`);
    });
  });
}

function render() {
  updateHud();
  if (mode === "whack") renderWhack();
  if (mode === "memory") renderMemory();
  if (mode === "tictactoe") renderTicTacToe();
  if (mode === "flappy") renderFlappy();
  if (mode === "shooter") renderShooter();
  if (mode === "puzzle") renderPuzzle();
  updateHud();
}
document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => {
    mode = button.dataset.mode;
    round = 0;
    document.querySelectorAll(".mode").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    render();
  });
});
render();
""", encoding="utf-8")


def copy_template(out: Path, template_dir: Path) -> None:
    if not template_dir.exists():
        raise FileNotFoundError(f"classic arcade template not found: {template_dir}")
    for item in template_dir.iterdir():
        if item.name == "sample-game-data.js":
            continue
        destination = out / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            shutil.copy2(item, destination)


def write_game_data(out: Path, payload: dict[str, Any]) -> None:
    game_json = json.dumps(payload, ensure_ascii=False, indent=2)
    coverage_json = json.dumps(payload["coverage"], ensure_ascii=False, indent=2)
    (out / "game-data.js").write_text(
        "window.COURSE_ARCADE_DATA = "
        + game_json
        + ";\nwindow.GAME_KNOWLEDGE_COVERAGE = "
        + coverage_json
        + ";\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a classic mini-game arcade from course knowledge JSON.")
    parser.add_argument("knowledge_json")
    parser.add_argument("--out", required=True)
    parser.add_argument("--title", help="HTML title")
    parser.add_argument("--seed", type=int, default=11)
    parser.add_argument("--template-dir", help="Override the fixed arcade template directory.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    data = load_knowledge(Path(args.knowledge_json).resolve())
    payload = build_payload(data, args.seed)
    title = args.title or f"{payload['title']}：经典小游戏"
    payload["title"] = title
    out = Path(args.out).resolve()
    if out.exists() and args.force:
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    template_dir = Path(args.template_dir).resolve() if args.template_dir else Path(__file__).resolve().parents[1] / "assets" / "classic-arcade-template"
    copy_template(out, template_dir)
    write_game_data(out, payload)
    print(json.dumps({"status": "pass", "out": str(out), "modes": ["whack", "memory", "tictactoe", "flappy", "shooter", "puzzle"], "knowledge_ids": payload["coverage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
