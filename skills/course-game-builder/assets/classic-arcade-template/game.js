const data = window.COURSE_ARCADE_DATA || {};
const modes = {
  whack: { label: "打地鼠", title: "题目在顶端，答案藏在地鼠肚子上" },
  memory: { label: "翻牌", title: "像经典记忆牌一样翻出术语配对" },
  tictactoe: { label: "井字棋", title: "答对题目才能在棋盘落子" },
  flappy: { label: "飞翔判断", title: "穿过 True 或 False 管道门" },
  shooter: { label: "雷霆战机", title: "在纵版战场中锁定正确知识目标" },
  puzzle: { label: "知识拼图", title: "把拼图块放回正确知识结构" }
};

let mode = "whack";
let score = 0;
let streak = 0;
let seen = new Set();
let state = {};
let timers = [];
let intervals = [];

const arena = document.querySelector("#arena");
const feedback = document.querySelector("#feedback");
const scoreEl = document.querySelector("#score");
const progressEl = document.querySelector("#progress");
const streakEl = document.querySelector("#streak");
const titleEl = document.querySelector("#game-title");
const modeLabelEl = document.querySelector("#mode-label");
const modeTitleEl = document.querySelector("#mode-title");

function clampArray(value) {
  return Array.isArray(value) ? value : [];
}

function shuffle(items) {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const swapIndex = Math.floor(Math.random() * (index + 1));
    [copy[index], copy[swapIndex]] = [copy[swapIndex], copy[index]];
  }
  return copy;
}

function clear() {
  clearTimers();
  document.onkeydown = null;
  arena.className = `arena arena-${mode}`;
  arena.replaceChildren();
}

function clearTimers() {
  timers.forEach((timer) => window.clearTimeout(timer));
  intervals.forEach((interval) => window.clearInterval(interval));
  timers = [];
  intervals = [];
}

function setTimer(callback, delay) {
  const timer = window.setTimeout(callback, delay);
  timers.push(timer);
  return timer;
}

function setIntervalSafe(callback, delay) {
  const interval = window.setInterval(callback, delay);
  intervals.push(interval);
  return interval;
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function button(className, text, onClick) {
  const element = node("button", className, text);
  element.type = "button";
  element.addEventListener("click", onClick);
  return element;
}

function mark(id, delta, message) {
  if (id) seen.add(id);
  score = Math.max(0, score + delta);
  streak = delta > 0 ? streak + 1 : 0;
  feedback.textContent = message;
  updateHud();
}

function updateHud() {
  const total = clampArray(data.coverage).length;
  scoreEl.textContent = String(score);
  progressEl.textContent = `${seen.size}/${total}`;
  streakEl.textContent = String(streak);
}

function setModeHeader() {
  const current = modes[mode];
  titleEl.textContent = data.title || "课程精美小游戏合集";
  document.title = data.title || "Course Arcade";
  modeLabelEl.textContent = current.label;
  modeTitleEl.textContent = current.title;
}

function promptCard(text) {
  const card = node("section", "prompt-card");
  const p = node("p", "", text);
  card.append(p);
  return card;
}

function renderWhack() {
  const rounds = clampArray(data.whack);
  state.whackIndex = state.whackIndex || 0;
  const item = rounds[state.whackIndex % Math.max(rounds.length, 1)];
  clear();
  if (!item) {
    arena.append(promptCard("知识点不足，无法生成打地鼠题目。"));
    return;
  }
  const cabinet = node("section", "whack-cabinet");
  const prompt = promptCard(item.prompt);
  const timer = node("span", "round-timer", "6");
  prompt.append(timer);
  cabinet.append(prompt);
  const mallet = node("div", "mallet", "HAMMER");
  const grid = node("div", "whack-grid");
  const holes = Array.from({ length: 9 }, (_, index) => index);
  const activeHoles = shuffle(holes).slice(0, Math.min(6, (item.choices || []).length || 6));
  const choices = shuffle(item.choices || []).slice(0, activeHoles.length);
  holes.forEach((holeIndex) => {
    const choiceIndex = activeHoles.indexOf(holeIndex);
    const choice = choices[choiceIndex];
    const hole = node("div", "mole-hole");
    const mole = button(`mole mole-${holeIndex % 3} ${choice ? "pop" : ""}`, "", () => {
      if (!choice) return;
      const ok = choice === item.answer;
      grid.querySelectorAll("button").forEach((buttonEl) => {
        buttonEl.disabled = true;
      });
      mole.classList.add(ok ? "correct" : "wrong");
      mark(item.id, ok ? 12 : -4, ok ? `命中：${item.why}` : `没打准。正确答案是：${item.answer}`);
      state.whackIndex += 1;
      setTimer(renderWhack, 620);
    });
    mole.dataset.knowledgeId = item.id;
    mole.append(node("span", "mole-face", ""), node("span", "mole-belly", choice || ""));
    if (!choice) {
      mole.disabled = true;
      mole.setAttribute("aria-hidden", "true");
    }
    hole.append(mole);
    grid.append(hole);
  });
  cabinet.append(mallet, grid);
  arena.append(cabinet);
  let seconds = 6;
  setIntervalSafe(() => {
    seconds -= 1;
    timer.textContent = String(Math.max(0, seconds));
  }, 1000);
  setTimer(() => {
    mark(item.id, -4, `时间到。正确答案是：${item.answer}`);
    state.whackIndex += 1;
    renderWhack();
  }, 6200);
}

function renderMemory() {
  const pairs = clampArray(data.memory).slice(0, 8);
  clear();
  if (!state.memoryDeck || state.memoryModeSeed !== pairs.length) {
    state.memoryModeSeed = pairs.length;
    state.memoryOpen = [];
    state.memoryMatched = new Set();
    state.memoryDeck = shuffle(pairs.flatMap((item) => [
      { id: item.id, text: item.term, side: "term", why: item.why },
      { id: item.id, text: item.definition, side: "definition", why: item.why }
    ]));
  }
  const table = node("section", "memory-table");
  table.append(promptCard("翻开两张牌：术语和含义属于同一个知识点才算配对。"));
  const grid = node("div", "memory-grid");
  state.memoryDeck.forEach((card, index) => {
    const isOpen = state.memoryOpen.includes(index) || state.memoryMatched.has(card.id);
    const tile = button(`tile ${isOpen ? "face-up" : "card-back"} ${state.memoryMatched.has(card.id) ? "matched" : ""}`, isOpen ? card.text : "", () => {
      if (state.memoryMatched.has(card.id) || state.memoryOpen.includes(index)) return;
      state.memoryOpen.push(index);
      if (state.memoryOpen.length === 2) {
        const [first, second] = state.memoryOpen.map((deckIndex) => state.memoryDeck[deckIndex]);
        const ok = first.id === second.id && first.side !== second.side;
        if (ok) {
          state.memoryMatched.add(first.id);
          mark(first.id, 10, `配对成功：${first.why}`);
        } else {
          mark(second.id, -3, "这两张不是一组，记住位置再试。");
        }
        window.setTimeout(() => {
          state.memoryOpen = [];
          renderMemory();
        }, ok ? 460 : 850);
      } else {
        renderMemory();
      }
    });
    tile.dataset.knowledgeId = card.id;
    if (!isOpen) tile.setAttribute("aria-label", "未翻开的记忆牌");
    grid.append(tile);
  });
  table.append(grid);
  arena.append(table);
}

function winner(board) {
  const lines = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  for (const line of lines) {
    const [a, b, c] = line;
    if (board[a] && board[a] === board[b] && board[a] === board[c]) return { mark: board[a], line };
  }
  return null;
}

function botMove() {
  const empty = state.tttBoard.map((value, index) => value ? null : index).filter((value) => value !== null);
  if (!empty.length || winner(state.tttBoard)) return;
  const index = empty[Math.floor(Math.random() * empty.length)];
  state.tttBoard[index] = "O";
}

function renderTictactoe() {
  const questions = clampArray(data.tictactoe);
  clear();
  if (!state.tttBoard) {
    state.tttBoard = Array(9).fill("");
    state.tttCell = null;
  }
  const wrap = node("div", "tictactoe-wrap");
  const boardShell = node("section", "chalkboard");
  const board = node("div", "board");
  const win = winner(state.tttBoard);
  state.tttBoard.forEach((value, index) => {
    const cell = button(`cell ${value === "X" ? "x-mark" : ""} ${value === "O" ? "o-mark" : ""} ${win && win.line.includes(index) ? "win" : ""}`, value || "", () => {
      if (value || winner(state.tttBoard)) return;
      state.tttCell = index;
      renderTictactoe();
    });
    board.append(cell);
  });
  boardShell.append(board);
  const side = node("section", "quiz-panel");
  const q = questions[(state.tttCell ?? state.tttBoard.filter(Boolean).length) % Math.max(questions.length, 1)];
  side.append(promptCard(win ? `${win.mark} 获胜。重置后可再来一局。` : "先点棋盘空格，再答题。答对才能放下 X。"));
  if (q && state.tttCell !== null && !win) {
    const choices = node("div", "choice-grid");
    shuffle(q.choices || []).slice(0, 4).forEach((choice) => {
      const choiceButton = button("choice", choice, () => {
        const ok = choice === q.answer;
        if (ok) {
          state.tttBoard[state.tttCell] = "X";
          mark(q.id, 14, `落子成功：${q.why}`);
          state.tttCell = null;
          if (!winner(state.tttBoard)) botMove();
        } else {
          mark(q.id, -5, `落子失败。正确答案：${q.answer}`);
          state.tttCell = null;
          botMove();
        }
        renderTictactoe();
      });
      choiceButton.dataset.knowledgeId = q.id;
      choices.append(choiceButton);
    });
    side.append(promptCard(q.prompt), choices);
  }
  wrap.append(boardShell, side);
  arena.append(wrap);
}

function renderFlappy() {
  const rounds = clampArray(data.flappy);
  state.flappyIndex = state.flappyIndex || 0;
  const item = rounds[state.flappyIndex % Math.max(rounds.length, 1)];
  clear();
  if (!item) {
    arena.append(promptCard("知识点不足，无法生成判断题。"));
    return;
  }
  const world = node("section", "flappy-world");
  const prompt = promptCard(item.text);
  prompt.append(node("span", "round-hint", "按 T/F 或点击管道"));
  world.append(prompt);
  const lane = node("div", "flight-lane");
  lane.append(node("div", "bird", "判断"));
  let answered = false;
  const chooseGate = (value) => {
    if (answered) return;
    answered = true;
    const ok = value === item.answer;
    mark(item.id, ok ? 10 : -4, ok ? `穿越成功：${item.why}` : `撞到管道：${item.why}`);
    state.flappyIndex += 1;
    setTimer(renderFlappy, 700);
  };
  [
    { label: "TRUE", value: true, className: "gate true" },
    { label: "FALSE", value: false, className: "gate false" }
  ].forEach((gate) => {
    const gateButton = button(gate.className, "", () => chooseGate(gate.value));
    gateButton.dataset.knowledgeId = item.id;
    gateButton.append(node("span", "pipe-top", ""), node("span", "pipe-label", gate.label), node("span", "pipe-bottom", ""));
    lane.append(gateButton);
  });
  world.append(lane);
  arena.append(world);
  document.onkeydown = (event) => {
    if (event.key.toLowerCase() === "t") chooseGate(true);
    if (event.key.toLowerCase() === "f") chooseGate(false);
  };
  setTimer(() => {
    if (!answered) {
      mark(item.id, -4, `来不及避让。正确判断是：${item.answer ? "TRUE" : "FALSE"}。${item.why}`);
      state.flappyIndex += 1;
      renderFlappy();
    }
  }, 5200);
}

function renderShooter() {
  const shooter = data.shooter || {};
  const categories = clampArray(shooter.categories);
  const targets = clampArray(shooter.targets);
  state.shooterCategory = state.shooterCategory || 0;
  const category = categories[state.shooterCategory % Math.max(categories.length, 1)];
  clear();
  if (!category || !targets.length) {
    arena.append(promptCard("知识点不足，无法生成雷霆战机目标。"));
    return;
  }
  const screen = node("section", "shooter-screen");
  screen.append(promptCard(`本轮锁定类别：${category.name}。只击中属于这个类别的敌机。`));
  const grid = node("div", "target-grid");
  if (!state.shooterDeck || state.shooterDeckCategory !== category.name) {
    state.shooterDeckCategory = category.name;
    state.shooterDeck = shuffle(targets).slice(0, 9);
  }
  const visibleTargets = state.shooterDeck;
  if (state.shooterAim === undefined || state.shooterAim >= visibleTargets.length) state.shooterAim = 0;
  const fireTarget = (target, targetButton) => {
      const ok = category.ids.includes(target.id);
      targetButton.classList.add(ok ? "hit" : "miss");
      mark(target.id, ok ? 11 : -4, ok ? `目标确认：${target.why}` : `误伤目标。它属于 ${target.type}，不是 ${category.name}。`);
      if (ok) {
        state.shooterCategory += 1;
        state.shooterDeck = null;
      }
      setTimer(renderShooter, 620);
  };
  visibleTargets.forEach((target, index) => {
    const targetButton = button(`target enemy-${index % 3} ${index === state.shooterAim ? "locked" : ""}`, "", () => fireTarget(target, targetButton));
    targetButton.dataset.knowledgeId = target.id;
    targetButton.append(node("strong", "", target.label), node("span", "", target.text));
    grid.append(targetButton);
  });
  const player = node("div", "player-ship");
  player.setAttribute("aria-label", "玩家战机，使用左右方向键锁定，空格发射");
  screen.append(grid, player);
  arena.append(screen);
  document.onkeydown = (event) => {
    if (event.key === "ArrowLeft") {
      state.shooterAim = Math.max(0, state.shooterAim - 1);
      renderShooter();
    }
    if (event.key === "ArrowRight") {
      state.shooterAim = Math.min(visibleTargets.length - 1, state.shooterAim + 1);
      renderShooter();
    }
    if (event.code === "Space") {
      event.preventDefault();
      const targetButton = arena.querySelectorAll(".target")[state.shooterAim];
      if (targetButton && visibleTargets[state.shooterAim]) fireTarget(visibleTargets[state.shooterAim], targetButton);
    }
  };
}

function renderPuzzle() {
  const pieces = clampArray(data.puzzle);
  const types = [...new Set(pieces.map((piece) => piece.type))].slice(0, 6);
  clear();
  if (!pieces.length || !types.length) {
    arena.append(promptCard("知识点不足，无法生成拼图。"));
    return;
  }
  state.puzzleSolved = state.puzzleSolved || new Set();
  state.puzzleSelected = state.puzzleSelected || null;
  const table = node("section", "jigsaw-table");
  table.append(promptCard("先选择散落的拼图块，再放入正确托盘。拼图内容就是课程知识结构。"));
  const bins = node("div", "bin-grid");
  types.forEach((type) => {
    const count = pieces.filter((piece) => piece.type === type && state.puzzleSolved.has(piece.id)).length;
    const placePiece = () => {
      const piece = state.puzzleSelected;
      if (!piece) {
        feedback.textContent = "先点一个知识拼图块，或直接拖到托盘。";
        return;
      }
      const ok = piece.type === type;
      if (ok) state.puzzleSolved.add(piece.id);
      state.puzzleSelected = null;
      mark(piece.id, ok ? 9 : -3, ok ? `归位成功：${piece.why}` : `分类不对。这个知识块更接近 ${piece.type}。`);
      renderPuzzle();
    };
    const bin = button(`bin ${state.puzzleSelected && state.puzzleSelected.type === type ? "active" : ""}`, `${type}\n已归位 ${count}`, () => {
      placePiece();
    });
    bin.addEventListener("dragover", (event) => {
      event.preventDefault();
      bin.classList.add("active");
    });
    bin.addEventListener("dragleave", () => bin.classList.remove("active"));
    bin.addEventListener("drop", (event) => {
      event.preventDefault();
      const id = event.dataTransfer.getData("text/plain");
      state.puzzleSelected = pieces.find((piece) => piece.id === id) || state.puzzleSelected;
      placePiece();
    });
    bins.append(bin);
  });
  const board = node("div", "puzzle-board");
  pieces.slice(0, 12).forEach((piece, index) => {
    const solved = state.puzzleSolved.has(piece.id);
    const selected = state.puzzleSelected && state.puzzleSelected.id === piece.id;
    const pieceButton = button(`piece piece-${index % 4} ${solved ? "solved" : ""} ${selected ? "selected" : ""}`, `${piece.label}：${piece.text}`, () => {
      if (solved) return;
      state.puzzleSelected = piece;
      feedback.textContent = `已选择：${piece.label}`;
      renderPuzzle();
    });
    pieceButton.dataset.knowledgeId = piece.id;
    pieceButton.draggable = !solved;
    pieceButton.addEventListener("dragstart", (event) => {
      state.puzzleSelected = piece;
      event.dataTransfer.setData("text/plain", piece.id);
      event.dataTransfer.effectAllowed = "move";
    });
    board.append(pieceButton);
  });
  table.append(bins, board);
  arena.append(table);
}

function resetCurrentMode() {
  if (mode === "memory") delete state.memoryDeck;
  if (mode === "tictactoe") {
    delete state.tttBoard;
    state.tttCell = null;
  }
  if (mode === "puzzle") {
    state.puzzleSolved = new Set();
    state.puzzleSelected = null;
  }
  if (mode === "whack") state.whackIndex = 0;
  if (mode === "flappy") state.flappyIndex = 0;
  if (mode === "shooter") state.shooterCategory = 0;
  if (mode === "shooter") {
    state.shooterAim = 0;
    state.shooterDeck = null;
    state.shooterDeckCategory = null;
  }
  feedback.textContent = "本局已重置。";
  render();
}

function render() {
  setModeHeader();
  updateHud();
  if (mode === "whack") renderWhack();
  if (mode === "memory") renderMemory();
  if (mode === "tictactoe") renderTictactoe();
  if (mode === "flappy") renderFlappy();
  if (mode === "shooter") renderShooter();
  if (mode === "puzzle") renderPuzzle();
}

document.querySelectorAll(".mode-button").forEach((buttonEl) => {
  buttonEl.addEventListener("click", () => {
    mode = buttonEl.dataset.mode;
    document.querySelectorAll(".mode-button").forEach((item) => item.classList.remove("active"));
    buttonEl.classList.add("active");
    feedback.textContent = `已切换到${modes[mode].label}。`;
    render();
  });
});

document.querySelector("#reset").addEventListener("click", resetCurrentMode);
render();
