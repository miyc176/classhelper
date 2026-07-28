const data = window.STANDALONE_GAME_DATA;
const $ = (selector) => document.querySelector(selector);
const stage = $("#stage");

let score = 0;
let index = 0;
let started = false;
let selectedCell = -1;
let board = Array(9).fill("");
let draggedId = null;
let animationFrame = 0;
let keys = {};
let shooterState = null;
let puzzleTargets = [];

window.GAME_KNOWLEDGE_COVERAGE = data.coverage;
document.title = data.title;
$("#title").textContent = data.title;
$("#app").classList.add(`mode-${data.mode}`);

function esc(value) {
  return String(value).replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[char]));
}

function update() {
  $("#score").textContent = String(score).padStart(4, "0");
  $("#progress").textContent = `${Math.min(index, data.total)}/${data.total}`;
}

function setMission(prompt, hint, tag) {
  $("#prompt").textContent = prompt;
  $("#hint").textContent = hint || "";
  $("#mission-tag").textContent = tag || "任务";
}

function feedback(text) {
  $("#feedback").textContent = text;
}

function showReview(title, body, onContinue) {
  const existing = stage.querySelector(".review-overlay");
  if (existing) existing.remove();
  const overlay = document.createElement("div");
  overlay.className = "review-overlay";
  overlay.innerHTML = `
    <div class="review-card">
      <strong>${esc(title)}</strong>
      <p>${esc(body)}</p>
      <button type="button">确认继续</button>
    </div>`;
  stage.appendChild(overlay);
  overlay.querySelector("button").onclick = () => {
    overlay.remove();
    onContinue();
  };
}

function stopAnimation() {
  cancelAnimationFrame(animationFrame);
  animationFrame = 0;
  keys = {};
  document.onkeydown = null;
  document.onkeyup = null;
  stage.onclick = null;
}

function finish() {
  stopAnimation();
  started = false;
  $("#action").disabled = false;
  $("#action").textContent = "重新开始";
  feedback(`挑战完成，最终得分 ${score}。`);
}

function start() {
  stopAnimation();
  score = 0;
  index = 0;
  started = true;
  board = Array(9).fill("");
  shooterState = null;
  $("#action").disabled = true;
  $("#action").textContent = "挑战中";
  render();
  update();
}

function renderMemory() {
  setMission("翻开卡牌，找出属于同一知识点的术语与解释", "连续匹配可以快速建立概念联系。", "记忆配对");
  const cards = data.items
    .flatMap((item) => [{ id: item.id, text: item.term }, { id: item.id, text: item.definition }])
    .sort(() => Math.random() - 0.5);
  stage.innerHTML = `<div class="memory-grid">${cards.map((card, cardIndex) => `
    <button class="memory-card" data-i="${cardIndex}" data-id="${card.id}">
      <span class="card-face card-back">K</span>
      <span class="card-face card-front">${esc(card.text)}</span>
    </button>`).join("")}</div>`;
  let open = [];
  stage.querySelectorAll(".memory-card").forEach((card) => {
    card.onclick = () => {
      if (card.classList.contains("open") || card.classList.contains("matched") || open.length === 2) return;
      card.classList.add("open");
      open.push(card);
      if (open.length === 2) {
        setTimeout(() => {
          const ok = open[0].dataset.id === open[1].dataset.id;
          if (ok) {
            open.forEach((item) => item.classList.add("matched"));
            score += 100;
            index += 1;
            feedback("配对成功，术语与解释属于同一个知识点。");
          } else {
            open.forEach((item) => item.classList.remove("open"));
            feedback("这两张牌不匹配，再观察它们的概念关系。");
          }
          open = [];
          update();
          if (index >= data.items.length) finish();
        }, 650);
      }
    };
  });
}

function renderTicTacToe() {
  setMission("选择一个棋格，答对题目后才能落下 X", "电脑会立即落下 O，先连成一线获胜。", "答题井字棋");
  stage.innerHTML = `<div class="ttt-board">${board.map((value, cellIndex) => `
    <button class="ttt-cell ${value.toLowerCase()}" data-i="${cellIndex}">${value}</button>`).join("")}</div>`;
  stage.querySelectorAll(".ttt-cell").forEach((cell) => {
    cell.onclick = () => {
      if (cell.textContent) return;
      selectedCell = Number(cell.dataset.i);
      openQuiz(data.items[(index + selectedCell) % data.items.length]);
    };
  });
}

function openQuiz(question) {
  $("#dialog-prompt").textContent = question.prompt;
  $("#dialog-options").innerHTML = question.choices
    .map((choice) => `<button data-choice="${esc(choice)}">${esc(choice)}</button>`)
    .join("");
  $("#quiz-dialog").showModal();
  $("#dialog-options").querySelectorAll("button").forEach((button) => {
    button.onclick = () => {
      const ok = button.dataset.choice === question.answer;
      if (ok) {
        board[selectedCell] = "X";
        score += 100;
        index += 1;
        const empty = board.map((value, cellIndex) => (value ? "" : cellIndex)).filter((value) => value !== "");
        if (empty.length) board[empty[Math.floor(Math.random() * empty.length)]] = "O";
        feedback(`落子成功。${question.why}`);
      } else {
        feedback(`回答错误，本次不能落子。${question.why}`);
      }
      $("#quiz-dialog").close();
      renderTicTacToe();
      update();
      if (index >= data.total) finish();
    };
  });
}

function renderFlappy() {
  stopAnimation();
  const getQuestion = () => data.items[index % data.items.length];
  const setRoundText = () => {
    const question = getQuestion();
    setMission(question.text, "点击画面或按空格上升，从正确的“是/否”通道飞过去。", "飞翔判断");
  };
  setRoundText();
  stage.innerHTML = `
    <div class="flappy-cloud cloud-one"></div>
    <div class="flappy-cloud cloud-two"></div>
    <div class="scroll-hills"></div>
    <div class="bird" role="button" tabindex="0" aria-label="点击或按空格让小鸟上升"></div>
    <div class="judge-wall">
      <div class="judge-door door-yes" data-value="true"><span>是</span></div>
      <div class="judge-door door-no" data-value="false"><span>否</span></div>
    </div>`;
  const bird = stage.querySelector(".bird");
  const wall = stage.querySelector(".judge-wall");
  if (!started) {
    bird.style.transform = `translateY(${Math.round(stage.clientHeight * 0.32)}px) rotate(-4deg)`;
    wall.style.transform = `translateX(${Math.max(260, stage.clientWidth - 180)}px)`;
    return;
  }

  let y = stage.clientHeight * 0.47;
  let velocity = 0;
  let wallX = stage.clientWidth + 150;
  let last = performance.now();
  let resolving = false;
  let pausedForReview = false;

  const flap = () => {
    if (resolving) return;
    velocity = -360;
  };

  stage.onclick = flap;
  document.onkeydown = (event) => {
    if (event.code === "Space") {
      event.preventDefault();
      flap();
    }
  };

  function resetWall() {
    wall.classList.remove("wall-pass", "wall-hit", "wall-exit");
    wallX = stage.clientWidth + 150;
    setRoundText();
  }

  function resolve(passValue) {
    if (resolving) return;
    resolving = true;
    const question = getQuestion();
    const ok = passValue === question.answer;
    if (ok) {
      score += 120;
      index += 1;
      wall.classList.add("wall-pass", "wall-exit");
      bird.classList.add("passed");
      feedback(`通过正确通道。${question.why}`);
      update();
      if (index >= data.items.length) {
        setTimeout(finish, 420);
        return;
      }
      setTimeout(() => {
        bird.classList.remove("passed");
        resolving = false;
        resetWall();
      }, 360);
      return;
    }

    bird.classList.add("crashed");
    wall.classList.add("wall-hit");
    feedback("判断错误，先看解析，再继续飞。");
    pausedForReview = true;
    update();
    showReview("判断解析", question.why, () => {
      index += 1;
      update();
      if (index >= data.items.length) {
        finish();
        return;
      }
      bird.classList.remove("crashed");
      wall.classList.remove("wall-hit");
      y = stage.clientHeight * 0.47;
      velocity = 0;
      resolving = false;
      pausedForReview = false;
      resetWall();
      feedback("继续飞行，选择下一道判断的正确通道。");
    });
  }

  function frame(now) {
    const dt = Math.min((now - last) / 1000, 0.032);
    last = now;
    if (pausedForReview) {
      if (started && data.mode === "flappy") animationFrame = requestAnimationFrame(frame);
      return;
    }
    velocity += 920 * dt;
    y += velocity * dt;
    if (!resolving) wallX -= 205 * dt;

    const minY = 8;
    const maxY = stage.clientHeight - 70;
    if (y < minY) {
      y = minY;
      velocity = 40;
    }
    if (y > maxY) {
      y = maxY;
      resolve(null);
    }

    bird.style.transform = `translateY(${y}px) rotate(${Math.max(-18, Math.min(30, velocity * 0.055))}deg)`;
    wall.style.transform = `translateX(${wallX}px)`;

    const birdX = stage.clientWidth * 0.16 + 72;
    if (!resolving && wallX <= birdX && wallX + 120 >= birdX) {
      const center = y + 27;
      const yesY = stage.clientHeight * 0.3;
      const noY = stage.clientHeight * 0.7;
      if (Math.abs(center - yesY) < 68) resolve(true);
      else if (Math.abs(center - noY) < 68) resolve(false);
      else resolve(null);
    }

    if (!resolving && wallX < -150) resolve(null);
    if (started && data.mode === "flappy") animationFrame = requestAnimationFrame(frame);
  }

  animationFrame = requestAnimationFrame(frame);
}

function renderShooter() {
  stopAnimation();
  const question = data.items[index % data.items.length];
  setMission(question.prompt, "WASD 移动，空格开火；击毁三个错误选项，保留正确答案。", "雷霆战机");
  const positions = [[12, 14], [62, 12], [23, 38], [67, 40]];
  stage.innerHTML = `<div class="battlefield">${question.choices.map((choice, choiceIndex) => `
    <button class="enemy-craft" data-i="${choiceIndex}" data-choice="${esc(choice)}" style="left:${positions[choiceIndex][0]}%;top:${positions[choiceIndex][1]}%">
      <span>${esc(choice)}</span>
    </button>`).join("")}<div class="player-ship" style="left:46%;top:76%"></div></div>`;
  if (!started) return;

  shooterState = {
    x: 46,
    y: 76,
    wrongLeft: question.choices.filter((choice) => choice !== question.answer).length,
    cooldown: 0,
    lasers: [],
    last: performance.now(),
  };
  const field = stage.querySelector(".battlefield");
  const ship = stage.querySelector(".player-ship");

  document.onkeydown = (event) => {
    keys[event.code] = true;
    if (event.code === "Space") {
      event.preventDefault();
      fire();
    }
  };
  document.onkeyup = (event) => {
    keys[event.code] = false;
  };
  stage.querySelectorAll(".enemy-craft").forEach((enemy) => {
    enemy.onclick = () => shootEnemy(enemy);
  });

  function shootEnemy(enemy) {
    if (enemy.classList.contains("destroyed") || enemy.classList.contains("protected")) return;
    const choice = enemy.dataset.choice;
    if (choice === question.answer) {
      enemy.classList.add("protected");
      score = Math.max(0, score - 80);
      feedback(`误伤了正确答案，不能击毁它。${question.why}`);
      setTimeout(() => enemy.classList.remove("protected"), 700);
    } else {
      enemy.classList.add("destroyed");
      shooterState.wrongLeft -= 1;
      score += 100;
      feedback(`击毁错误选项，还剩 ${shooterState.wrongLeft} 个。`);
      if (shooterState.wrongLeft === 0) {
        index += 1;
        update();
        feedback(`清除完成，正确答案是：${question.answer}。${question.why}`);
        setTimeout(() => (index >= data.items.length ? finish() : renderShooter()), 950);
      }
    }
    update();
  }

  function fire() {
    if (shooterState.cooldown > 0) return;
    shooterState.cooldown = 0.25;
    const laser = document.createElement("i");
    laser.className = "shot";
    laser.style.left = `${shooterState.x + 4}%`;
    laser.style.top = `${shooterState.y}%`;
    field.appendChild(laser);
    shooterState.lasers.push({ el: laser, x: shooterState.x + 4, y: shooterState.y });
  }

  function frame(now) {
    const dt = Math.min((now - shooterState.last) / 1000, 0.032);
    shooterState.last = now;
    shooterState.cooldown = Math.max(0, shooterState.cooldown - dt);
    const speed = 38;
    if (keys.KeyA || keys.ArrowLeft) shooterState.x -= speed * dt;
    if (keys.KeyD || keys.ArrowRight) shooterState.x += speed * dt;
    if (keys.KeyW || keys.ArrowUp) shooterState.y -= speed * dt;
    if (keys.KeyS || keys.ArrowDown) shooterState.y += speed * dt;
    if (keys.Space) fire();
    shooterState.x = Math.max(1, Math.min(88, shooterState.x));
    shooterState.y = Math.max(52, Math.min(82, shooterState.y));
    ship.style.left = `${shooterState.x}%`;
    ship.style.top = `${shooterState.y}%`;
    shooterState.lasers.forEach((laser) => {
      laser.y -= 74 * dt;
      laser.el.style.top = `${laser.y}%`;
      stage.querySelectorAll(".enemy-craft:not(.destroyed)").forEach((enemy) => {
        const enemyRect = enemy.getBoundingClientRect();
        const laserRect = laser.el.getBoundingClientRect();
        if (
          laserRect.left < enemyRect.right &&
          laserRect.right > enemyRect.left &&
          laserRect.top < enemyRect.bottom &&
          laserRect.bottom > enemyRect.top
        ) {
          laser.el.remove();
          laser.y = -99;
          shootEnemy(enemy);
        }
      });
    });
    shooterState.lasers = shooterState.lasers.filter((laser) => laser.y > -10);
    if (started && data.mode === "shooter") animationFrame = requestAnimationFrame(frame);
  }

  animationFrame = requestAnimationFrame(frame);
}

function puzzlePath(edge, x, y, width, height) {
  const tab = 18;
  const midX = x + width / 2;
  const midY = y + height / 2;
  const right = x + width;
  const bottom = y + height;
  const sign = (value) => (value >= 0 ? 1 : -1);
  return [
    `M ${x} ${y}`,
    edge.top ? `L ${midX - 30} ${y} C ${midX - 22} ${y} ${midX - 18} ${y + tab * sign(edge.top)} ${midX} ${y + tab * sign(edge.top)} C ${midX + 18} ${y + tab * sign(edge.top)} ${midX + 22} ${y} ${midX + 30} ${y}` : "",
    `L ${right} ${y}`,
    edge.right ? `L ${right} ${midY - 30} C ${right} ${midY - 22} ${right + tab * sign(edge.right)} ${midY - 18} ${right + tab * sign(edge.right)} ${midY} C ${right + tab * sign(edge.right)} ${midY + 18} ${right} ${midY + 22} ${right} ${midY + 30}` : "",
    `L ${right} ${bottom}`,
    edge.bottom ? `L ${midX + 30} ${bottom} C ${midX + 22} ${bottom} ${midX + 18} ${bottom + tab * sign(edge.bottom)} ${midX} ${bottom + tab * sign(edge.bottom)} C ${midX - 18} ${bottom + tab * sign(edge.bottom)} ${midX - 22} ${bottom} ${midX - 30} ${bottom}` : "",
    `L ${x} ${bottom}`,
    edge.left ? `L ${x} ${midY + 30} C ${x} ${midY + 22} ${x + tab * sign(edge.left)} ${midY + 18} ${x + tab * sign(edge.left)} ${midY} C ${x + tab * sign(edge.left)} ${midY - 18} ${x} ${midY - 22} ${x} ${midY - 30}` : "",
    "Z",
  ].filter(Boolean).join(" ");
}

function pieceMarkup(item, slotIndex, filled = false, showLabel = true) {
  const colors = ["#f7c84f", "#5ec2d8", "#f06f59", "#8fd16c"];
  const edges = [
    { top: 0, right: 1, bottom: 1, left: 0 },
    { top: 0, right: 0, bottom: -1, left: -1 },
    { top: -1, right: 1, bottom: 0, left: 0 },
    { top: 1, right: 0, bottom: 0, left: -1 },
  ];
  const path = puzzlePath(edges[slotIndex % edges.length], 26, 22, 188, 136);
  const fill = filled ? colors[slotIndex % colors.length] : "#faf8f0";
  return `
    <svg class="piece-svg" viewBox="0 0 240 180" aria-hidden="true">
      <path d="${path}" fill="${fill}" stroke="${filled ? "#263238" : "#6d756f"}" stroke-width="${filled ? 4 : 3}" />
      <path d="${path}" fill="none" stroke="rgba(255,255,255,.55)" stroke-width="2" transform="translate(-3 -3)" />
    </svg>
    ${showLabel ? `<span class="piece-label"><strong>${esc(item.label)}</strong><small>${esc(item.text)}</small></span>` : ""}`;
}

function buildPuzzleRounds() {
  const source = data.items.slice();
  const rounds = [];
  for (let start = 0; start + 3 < source.length; start += 6) {
    const targets = source.slice(start, start + 4);
    let distractors = source.slice(start + 4, start + 6);
    if (distractors.length < 2) {
      distractors = [
        ...distractors,
        ...source.filter((item) => !targets.some((target) => target.id === item.id) && !distractors.some((decoy) => decoy.id === item.id)),
      ].slice(0, 2);
    }
    rounds.push({ targets, distractors });
  }
  return rounds;
}

function renderPuzzle() {
  stopAnimation();
  const rounds = buildPuzzleRounds();
  if (!rounds.length) {
    setMission("知识点不足，无法生成拼图。", "至少需要 4 个可用知识点。", "知识拼图");
    stage.innerHTML = `<div class="empty-state">知识点不足，无法生成拼图。</div>`;
    return;
  }
  const roundIndex = Math.min(Math.floor(index / 4), rounds.length - 1);
  const round = rounds[roundIndex];
  puzzleTargets = round.targets;
  const pieces = [...round.targets, ...round.distractors].sort(() => Math.random() - 0.5);
  setMission(`第 ${roundIndex + 1}/${rounds.length} 题：选出 4 个正确概念拼满拼图框`, "拼图板只显示空白形状，不给答案；从 6 块中排除 2 个干扰概念。", "知识拼图");
  stage.innerHTML = `
    <div class="jigsaw-workbench">
      <div class="loose-pieces">${pieces.map((item, pieceIndex) => `
        <button draggable="true" class="jigsaw-piece" data-id="${item.id}" data-slot="${puzzleTargets.findIndex((target) => target.id === item.id)}" style="--tilt:${[-5, 3, -2, 5, -4, 2][pieceIndex % 6]}deg">
          ${pieceMarkup(item, puzzleTargets.findIndex((target) => target.id === item.id) >= 0 ? puzzleTargets.findIndex((target) => target.id === item.id) : pieceIndex % 4)}
        </button>`).join("")}</div>
      <div class="puzzle-board" aria-label="拼图框">
        ${puzzleTargets.map((item, targetIndex) => `
          <button class="puzzle-slot slot-${targetIndex}" data-id="${item.id}" data-slot="${targetIndex}">
            ${pieceMarkup(item, targetIndex, false, false)}
          </button>`).join("")}
      </div>
    </div>`;

  stage.querySelectorAll(".jigsaw-piece").forEach((piece) => {
    piece.ondragstart = (event) => {
      draggedId = piece.dataset.id;
      event.dataTransfer.setData("text/plain", draggedId);
    };
    piece.onclick = () => {
      draggedId = piece.dataset.id;
      stage.querySelectorAll(".jigsaw-piece").forEach((item) => item.classList.toggle("selected", item === piece));
    };
  });

  stage.querySelectorAll(".puzzle-slot").forEach((slot) => {
    slot.ondragover = (event) => {
      event.preventDefault();
      slot.classList.add("over");
    };
    slot.ondragleave = () => slot.classList.remove("over");
    slot.ondrop = (event) => {
      event.preventDefault();
      draggedId = event.dataTransfer.getData("text/plain") || draggedId;
      place(slot);
    };
    slot.onclick = () => place(slot);
  });

  function place(slot) {
    if (slot.classList.contains("filled") || !draggedId) return;
    const piece = stage.querySelector(`.jigsaw-piece[data-id="${draggedId}"]`);
    if (!piece) return;
    if (slot.dataset.id === draggedId) {
      const targetIndex = Number(slot.dataset.slot);
      slot.classList.add("filled");
      slot.innerHTML = pieceMarkup(puzzleTargets[targetIndex], targetIndex, true);
      piece.classList.add("placed");
      score += 100;
      index += 1;
      feedback("吸附成功，拼图框填入了一块正确知识点。");
      update();
      if (stage.querySelectorAll(".puzzle-slot.filled").length === puzzleTargets.length) {
        if (index >= data.total || roundIndex >= rounds.length - 1) {
          finish();
        } else {
          feedback("本题拼图完成，进入下一组概念。");
          setTimeout(renderPuzzle, 850);
        }
      }
    } else {
      slot.classList.add("reject");
      feedback("这块概念与该位置不匹配，换一块再试。");
      setTimeout(() => slot.classList.remove("reject"), 450);
    }
    draggedId = null;
    stage.querySelectorAll(".jigsaw-piece").forEach((item) => item.classList.remove("selected"));
  }
}

function render() {
  stopAnimation();
  if (data.mode === "memory") renderMemory();
  if (data.mode === "tictactoe") renderTicTacToe();
  if (data.mode === "flappy") renderFlappy();
  if (data.mode === "shooter") renderShooter();
  if (data.mode === "puzzle") renderPuzzle();
}

$("#action").onclick = start;
$("#dialog-close").onclick = () => $("#quiz-dialog").close();
update();
render();
