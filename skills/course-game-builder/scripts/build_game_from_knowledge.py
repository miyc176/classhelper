#!/usr/bin/env python3
"""Generate a polished standalone HTML review game from extracted knowledge JSON."""

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


def slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-").lower()
    return value or "course-game"


def ui_strings(lang: str) -> dict[str, Any]:
    if lang.lower().startswith("zh"):
        return {
            "eyebrow": "课程小游戏",
            "modes": {"match": "匹配", "source": "溯源", "review": "复习"},
            "check": "检查",
            "next": "下一题",
            "reset": "重置",
            "matchTagline": "选择与目标知识点匹配的正确表述。",
            "sourceTagline": "把知识点和来源证据连起来，避免脱离课件。",
            "reviewTagline": "根据解释复习这个教学要点。",
            "selectPrompt": "选择能准确概括 {id} 的表述。",
            "chooseThenCheck": "先选择一个选项，再检查答案。",
            "correct": "正确。",
            "review": "再看一下。",
            "sourcePrefix": "来源：",
            "sourceFallback": "来源细节记录在 knowledge.json 中。",
            "differentSource": "另一处课程来源或无关说明。",
            "genericDistractors": [
                "这个说法看似相关，但忽略了关键条件。",
                "这个说法把原因和结果混在了一起。",
                "这个说法过度概括，不能准确代表该知识点。",
            ],
        }
    return {
        "eyebrow": "Course Mini Game",
        "modes": {"match": "Match", "source": "Source", "review": "Review"},
        "check": "Check",
        "next": "Next",
        "reset": "Reset",
        "matchTagline": "Choose the statement that matches the target knowledge point.",
        "sourceTagline": "Connect knowledge to evidence so classroom explanations stay grounded.",
        "reviewTagline": "Use the explanation to rehearse the teaching point.",
        "selectPrompt": "Select the statement that correctly captures {id}.",
        "chooseThenCheck": "Select an option, then check your answer.",
        "correct": "Correct.",
        "review": "Review this.",
        "sourcePrefix": "Source: ",
        "sourceFallback": "Source details are recorded in the knowledge JSON.",
        "differentSource": "A different course source or unrelated note.",
        "genericDistractors": [
            "This statement seems related, but misses a key condition.",
            "This statement mixes up cause and effect.",
            "This statement is too broad to represent the knowledge point.",
        ],
    }


def read_knowledge(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    points = data.get("knowledge_points")
    if not isinstance(points, list) or not points:
        raise ValueError("knowledge_json must contain a non-empty knowledge_points array.")
    for point in points:
        if "id" not in point or "statement" not in point:
            raise ValueError("Every knowledge point must include id and statement.")
    return data


def make_rounds(points: list[dict[str, Any]], seed: int, ui: dict[str, Any]) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    rounds = []
    statements = [str(point.get("statement", "")) for point in points]
    for point in points:
        other = [text for text in statements if text != point.get("statement")]
        distractors = rng.sample(other, k=min(3, len(other))) if other else []
        for item in ui["genericDistractors"]:
            if len(distractors) >= 3:
                break
            if item != point.get("statement") and item not in distractors:
                distractors.append(item)
        choices = [str(point["statement"]), *distractors[:3]]
        rng.shuffle(choices)
        answer = choices.index(str(point["statement"]))
        source_refs = point.get("source_refs") or []
        source_text = "; ".join(
            f"{ref.get('source_id', 'source')} {ref.get('locator', '')} {ref.get('region', '')}".strip()
            for ref in source_refs[:2]
        )
        explanation = point.get("teaching_value") or point.get("evidence") or str(point["statement"])
        rounds.append({
            "id": str(point["id"]),
            "type": str(point.get("type", "concept")),
            "difficulty": str(point.get("difficulty", "core")),
            "prompt": ui["selectPrompt"].format(id=point["id"]),
            "choices": choices,
            "answer": answer,
            "explanation": str(explanation),
            "source": source_text,
            "commonErrors": point.get("common_errors") or [],
        })
    rng.shuffle(rounds)
    return rounds


def write_index(out_dir: Path, title: str, lang: str, ui: dict[str, Any]) -> None:
    safe_title = html.escape(title)
    (out_dir / "index.html").write_text(f"""<!doctype html>
<html lang="{html.escape(lang)}">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{safe_title}</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <main class="app" aria-labelledby="game-title">
      <section class="stage">
        <header class="topbar">
          <div>
            <p class="eyebrow">{html.escape(ui["eyebrow"])}</p>
            <h1 id="game-title">{safe_title}</h1>
          </div>
          <div class="status" aria-live="polite">
            <span id="round-status">0 / 0</span>
            <span id="score-status">0 pts</span>
          </div>
        </header>

        <nav class="modes" aria-label="Game modes">
          <button type="button" class="mode active" data-mode="match">{html.escape(ui["modes"]["match"])}</button>
          <button type="button" class="mode" data-mode="source">{html.escape(ui["modes"]["source"])}</button>
          <button type="button" class="mode" data-mode="review">{html.escape(ui["modes"]["review"])}</button>
        </nav>

        <section class="play-area">
          <div class="question-panel">
            <p id="tagline"></p>
            <h2 id="prompt"></h2>
          </div>
          <div id="choices" class="choices"></div>
          <div id="feedback" class="feedback" aria-live="polite"></div>
        </section>

        <footer class="actions">
          <button id="check" type="button">{html.escape(ui["check"])}</button>
          <button id="next" type="button">{html.escape(ui["next"])}</button>
          <button id="reset" type="button">{html.escape(ui["reset"])}</button>
        </footer>
      </section>
    </main>
    <script src="./game-data.js"></script>
    <script src="./game.js"></script>
  </body>
</html>
""", encoding="utf-8")


def write_styles(out_dir: Path) -> None:
    (out_dir / "styles.css").write_text(""" :root {
  --ink: #17212b;
  --muted: #5f6f7c;
  --paper: #f4f7f8;
  --panel: #ffffff;
  --line: #d5e0e5;
  --accent: #006d77;
  --accent-2: #8a5a00;
  --good: #177245;
  --bad: #a73d32;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  min-height: 100vh;
  background: var(--paper);
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

button:hover, button:focus-visible {
  border-color: var(--accent);
  outline: 2px solid rgba(0, 109, 119, 0.18);
}

button[disabled] { cursor: not-allowed; opacity: 0.68; }

.app {
  width: min(1100px, calc(100vw - 24px));
  margin: 0 auto;
  padding: 20px 0;
}

.stage {
  min-height: calc(100vh - 40px);
  display: grid;
  grid-template-rows: auto auto 1fr auto;
  gap: 16px;
}

.topbar, .status, .modes, .actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.topbar {
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: 14px;
}

.eyebrow {
  margin: 0 0 4px;
  color: var(--accent-2);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
}

h1, h2, p { margin-top: 0; }

h1 { margin-bottom: 0; font-size: 30px; line-height: 1.15; }

.status span {
  min-width: 82px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 8px 10px;
  background: var(--panel);
  text-align: center;
}

.modes {
  flex-wrap: wrap;
}

.mode.active {
  border-color: var(--accent);
  background: #e6f4f3;
  color: #064f55;
  font-weight: 700;
}

.play-area {
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 14px;
}

.question-panel {
  border-left: 4px solid var(--accent);
  padding: 14px 16px;
  background: var(--panel);
}

#tagline {
  margin-bottom: 8px;
  color: var(--muted);
  font-size: 14px;
}

#prompt {
  margin-bottom: 0;
  font-size: 22px;
  line-height: 1.35;
}

.choices {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  align-content: start;
}

.choice {
  min-height: 78px;
  text-align: left;
  line-height: 1.35;
  white-space: normal;
}

.choice.selected { border-color: var(--accent); background: #edf8f7; }
.choice.correct { border-color: var(--good); background: #eaf6ef; }
.choice.wrong { border-color: var(--bad); background: #fff0ed; }

.feedback {
  min-height: 78px;
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 12px 14px;
  background: var(--panel);
  line-height: 1.45;
}

.actions { justify-content: flex-end; }

@media (max-width: 680px) {
  .topbar, .actions { align-items: stretch; flex-direction: column; }
  .status, .choices { display: grid; grid-template-columns: 1fr; }
  .status { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .modes { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); }
  h1 { font-size: 24px; }
  #prompt { font-size: 19px; }
}
""".lstrip(), encoding="utf-8")


def write_js(out_dir: Path, payload: dict[str, Any]) -> None:
    (out_dir / "game-data.js").write_text(
        "window.COURSE_GAME_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n"
        "window.GAME_KNOWLEDGE_COVERAGE = window.COURSE_GAME_DATA.coverage;\n",
        encoding="utf-8",
    )
    (out_dir / "game.js").write_text("""const data = window.COURSE_GAME_DATA;
const modes = {
  match: {
    label: data.ui.modes.match,
    tagline: data.ui.matchTagline,
    getPrompt: (round) => `${round.id} - ${round.type} - ${round.difficulty}`,
    getChoices: (round) => round.choices,
    getAnswer: (round) => round.answer,
    explain: (round) => `${round.explanation}${round.source ? " " + data.ui.sourcePrefix + round.source : ""}`
  },
  source: {
    label: data.ui.modes.source,
    tagline: data.ui.sourceTagline,
    getPrompt: (round) => round.choices[round.answer],
    getChoices: (round) => makeSourceChoices(round),
    getAnswer: () => 0,
    explain: (round) => round.source || data.ui.sourceFallback
  },
  review: {
    label: data.ui.modes.review,
    tagline: data.ui.reviewTagline,
    getPrompt: (round) => round.explanation,
    getChoices: (round) => [round.choices[round.answer], ...round.choices.filter((_, index) => index !== round.answer).slice(0, 3)],
    getAnswer: () => 0,
    explain: (round) => `${round.id}: ${round.choices[round.answer]}`
  }
};

let mode = "match";
let index = 0;
let selected = null;
let score = 0;
let checked = false;

const roundStatus = document.querySelector("#round-status");
const scoreStatus = document.querySelector("#score-status");
const tagline = document.querySelector("#tagline");
const prompt = document.querySelector("#prompt");
const choices = document.querySelector("#choices");
const feedback = document.querySelector("#feedback");
const checkButton = document.querySelector("#check");
const nextButton = document.querySelector("#next");
const resetButton = document.querySelector("#reset");

function makeSourceChoices(round) {
  const correct = round.source || data.ui.sourceFallback;
  const others = data.rounds
    .filter((item) => item.id !== round.id)
    .map((item) => item.source)
    .filter(Boolean)
    .slice(0, 3);
  while (others.length < 3) others.push(data.ui.differentSource);
  return [correct, ...others.slice(0, 3)];
}

function activeRound() {
  return data.rounds[index % data.rounds.length];
}

function render() {
  const round = activeRound();
  const config = modes[mode];
  selected = null;
  checked = false;
  tagline.textContent = config.tagline;
  prompt.textContent = config.getPrompt(round);
  roundStatus.textContent = `${index + 1} / ${data.rounds.length}`;
  scoreStatus.textContent = `${score} pts`;
  feedback.textContent = data.ui.chooseThenCheck;
  checkButton.disabled = false;
  choices.innerHTML = "";

  config.getChoices(round).forEach((choice, choiceIndex) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "choice";
    button.textContent = choice;
    button.dataset.knowledgeId = round.id;
    button.addEventListener("click", () => {
      if (checked) return;
      selected = choiceIndex;
      [...choices.children].forEach((item) => item.classList.remove("selected"));
      button.classList.add("selected");
    });
    choices.appendChild(button);
  });
}

function check() {
  if (selected === null || checked) return;
  checked = true;
  const round = activeRound();
  const answer = modes[mode].getAnswer(round);
  const correct = selected === answer;
  if (correct) score += 10;
  [...choices.children].forEach((button, choiceIndex) => {
    button.disabled = true;
    if (choiceIndex === answer) button.classList.add("correct");
    if (choiceIndex === selected && !correct) button.classList.add("wrong");
  });
  feedback.textContent = `${correct ? data.ui.correct : data.ui.review} ${modes[mode].explain(round)}`;
  scoreStatus.textContent = `${score} pts`;
  checkButton.disabled = true;
}

function next() {
  index = (index + 1) % data.rounds.length;
  render();
}

function reset() {
  index = 0;
  score = 0;
  render();
}

document.querySelectorAll(".mode").forEach((button) => {
  button.addEventListener("click", () => {
    mode = button.dataset.mode;
    document.querySelectorAll(".mode").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    reset();
  });
});

checkButton.addEventListener("click", check);
nextButton.addEventListener("click", next);
resetButton.addEventListener("click", reset);
render();
""", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone HTML game from course knowledge JSON.")
    parser.add_argument("knowledge_json", help="Knowledge JSON using references/knowledge-schema.md.")
    parser.add_argument("--out", required=True, help="Output directory for the game.")
    parser.add_argument("--title", help="Game title. Defaults to course_title or Knowledge Quest.")
    parser.add_argument("--lang", default="zh-CN", help="HTML lang attribute.")
    parser.add_argument("--seed", type=int, default=7, help="Deterministic shuffle seed.")
    parser.add_argument("--force", action="store_true", help="Replace output directory if it exists.")
    args = parser.parse_args()

    knowledge_path = Path(args.knowledge_json).resolve()
    out_dir = Path(args.out).resolve()
    if out_dir.exists() and args.force:
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = read_knowledge(knowledge_path)
    points = data["knowledge_points"]
    title = args.title or data.get("course_title") or "Knowledge Quest"
    ui = ui_strings(args.lang)
    payload = {
        "title": title,
        "courseTitle": data.get("course_title", ""),
        "ui": ui,
        "coverage": [str(point["id"]) for point in points],
        "rounds": make_rounds(points, args.seed, ui),
    }

    write_index(out_dir, title, args.lang, ui)
    write_styles(out_dir)
    write_js(out_dir, payload)
    print(json.dumps({"status": "pass", "out": str(out_dir), "knowledge_ids": payload["coverage"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
