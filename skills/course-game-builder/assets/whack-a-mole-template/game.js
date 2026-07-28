const data = window.WHACK_GAME_DATA;
const $ = (selector) => document.querySelector(selector);
const holesEl = $("#holes");
const scoreEl = $("#score");
const comboEl = $("#combo");
const timeEl = $("#time");
const promptEl = $("#prompt");
const roundLabelEl = $("#round-label");
const feedbackEl = $("#feedback");
const livesEl = $("#lives");
const startEl = $("#start");
const malletEl = $("#mallet");
const dialogEl = $("#result");
let score = 0;
let combo = 0;
let lives = 3;
let seconds = 60;
let round = 0;
let running = false;
let roundLocked = false;
let tickTimer = null;
let popTimer = null;
let hideTimer = null;
let malletTimer = null;

document.title = data.title;
$("#game-title").textContent = data.title;
window.GAME_KNOWLEDGE_COVERAGE = data.coverage;

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function shuffle(values) {
  return [...values].sort(() => Math.random() - .5);
}
function fitChoiceLabel(label) {
  label.style.fontSize = "";
  requestAnimationFrame(() => {
    let size = parseFloat(getComputedStyle(label).fontSize);
    while ((label.scrollHeight > label.clientHeight || label.scrollWidth > label.clientWidth) && size > 7) {
      size -= 0.5;
      label.style.fontSize = `${size}px`;
    }
  });
}
function renderLives() {
  livesEl.innerHTML = [0, 1, 2].map((i) => `<span class="heart ${i >= lives ? "lost" : ""}"></span>`).join("");
}
function updateHud() {
  scoreEl.textContent = String(Math.max(0, score)).padStart(4, "0");
  comboEl.textContent = `x${Math.max(1, combo)}`;
  timeEl.textContent = String(seconds).padStart(2, "0");
  renderLives();
}
function createHoles() {
  holesEl.innerHTML = Array.from({ length: 9 }, (_, index) => `
    <div class="hole">
      <button class="mole" type="button" data-hole="${index}" aria-label="地鼠洞 ${index + 1}">
        <span class="ear left"></span><span class="ear right"></span>
        <span class="mole-face">
          <span class="eye left"></span><span class="eye right"></span>
          <span class="snout"><span class="nose"></span><span class="tooth left"></span><span class="tooth right"></span></span>
        </span>
        <span class="answer"></span>
      </button>
    </div>`).join("");
  document.querySelectorAll(".mole").forEach((mole) => mole.addEventListener("click", hitMole));
}
function clearRoundTimers() {
  clearTimeout(popTimer);
  clearTimeout(hideTimer);
}
function hideAll() {
  document.querySelectorAll(".mole").forEach((mole) => mole.classList.remove("up"));
}
function currentItem() {
  return data.questions[round % data.questions.length];
}
function showQuestion() {
  if (!running) return;
  clearRoundTimers();
  hideAll();
  roundLocked = false;
  const item = currentItem();
  roundLabelEl.textContent = `第 ${round + 1} 题 · 共 ${data.questions.length} 题`;
  promptEl.textContent = item.prompt;
  feedbackEl.textContent = "看准答案再出手，地鼠马上就会缩回去。";
  const choices = shuffle(item.choices).slice(0, 4);
  const holes = shuffle([...document.querySelectorAll(".mole")]).slice(0, choices.length);
  holes.forEach((mole, index) => {
    mole.dataset.choice = choices[index];
    mole.dataset.answer = item.answer;
    mole.dataset.knowledgeId = item.id;
    const label = mole.querySelector(".answer");
    label.textContent = choices[index];
    label.title = choices[index];
    fitChoiceLabel(label);
    mole.classList.remove("correct", "wrong", "hit");
  });
  let appearIndex = 0;
  function popNext() {
    if (!running || roundLocked || appearIndex >= holes.length) return;
    holes[appearIndex].classList.add("up");
    appearIndex += 1;
    popTimer = setTimeout(popNext, 180);
  }
  popNext();
  hideTimer = setTimeout(() => {
    if (!roundLocked && running) resolveMiss("来不及了，正确答案是：" + item.answer);
  }, data.visible_ms || 5200);
}
function swingAt(event) {
  const rect = $("#field").getBoundingClientRect();
  malletEl.style.left = `${event.clientX - rect.left}px`;
  malletEl.style.top = `${event.clientY - rect.top}px`;
  clearTimeout(malletTimer);
  malletEl.classList.remove("swing");
  void malletEl.offsetWidth;
  malletEl.classList.add("swing");
  malletTimer = setTimeout(() => malletEl.classList.remove("swing"), 320);
}
function hitMole(event) {
  if (!running || roundLocked || !event.currentTarget.classList.contains("up")) return;
  swingAt(event);
  const mole = event.currentTarget;
  const item = currentItem();
  roundLocked = true;
  clearRoundTimers();
  mole.classList.add("hit");
  const correct = mole.dataset.choice === item.answer;
  if (correct) {
    combo += 1;
    score += 100 + Math.min(combo - 1, 9) * 20;
    mole.classList.add("correct");
    feedbackEl.textContent = `命中！${item.why}`;
  } else {
    combo = 0;
    lives -= 1;
    score = Math.max(0, score - 50);
    mole.classList.add("wrong");
    feedbackEl.textContent = `打错了。正确答案：${item.answer}。${item.why}`;
  }
  updateHud();
  setTimeout(advanceRound, 1050);
}
function resolveMiss(message) {
  roundLocked = true;
  combo = 0;
  lives -= 1;
  feedbackEl.textContent = message;
  updateHud();
  setTimeout(advanceRound, 900);
}
function advanceRound() {
  hideAll();
  round += 1;
  if (lives <= 0 || seconds <= 0 || round >= data.questions.length) finishGame();
  else setTimeout(showQuestion, 250);
}
function startGame() {
  clearInterval(tickTimer);
  clearRoundTimers();
  score = 0;
  combo = 0;
  lives = 3;
  seconds = data.duration || 60;
  round = 0;
  running = true;
  startEl.disabled = true;
  startEl.textContent = "游戏中";
  updateHud();
  showQuestion();
  tickTimer = setInterval(() => {
    seconds -= 1;
    updateHud();
    if (seconds <= 0) finishGame();
  }, 1000);
}
function finishGame() {
  if (!running) return;
  running = false;
  clearInterval(tickTimer);
  clearRoundTimers();
  clearTimeout(malletTimer);
  malletEl.classList.remove("swing");
  hideAll();
  startEl.disabled = false;
  startEl.textContent = "重新开始";
  $("#result-title").textContent = lives > 0 ? "挑战完成" : "机会用完";
  $("#result-summary").textContent = `最终得分 ${score}，完成 ${Math.min(round, data.questions.length)} / ${data.questions.length} 道题。`;
  dialogEl.showModal();
}
startEl.addEventListener("click", startGame);
$("#replay").addEventListener("click", () => { dialogEl.close(); startGame(); });
createHoles();
updateHud();
