// Replace this sample data with source-traceable items from knowledge.json.
const rounds = [
  {
    id: "kp_001",
    prompt: "Which statement best matches this knowledge point?",
    choices: [
      "Correct source-grounded statement",
      "Plausible misconception",
      "Unrelated detail",
      "Overgeneralized version"
    ],
    answer: 0,
    feedback: "kp_001: Explain the concept using the source-grounded statement."
  }
];

window.GAME_KNOWLEDGE_COVERAGE = rounds.map((round) => round.id);

let current = 0;
let score = 0;
let answered = false;

const promptEl = document.querySelector("#prompt");
const choicesEl = document.querySelector("#choices");
const feedbackEl = document.querySelector("#feedback");
const progressEl = document.querySelector("#progress");
const scoreEl = document.querySelector("#score");
const nextButton = document.querySelector("#next");
const resetButton = document.querySelector("#reset");

function renderRound() {
  const round = rounds[current];
  answered = false;
  promptEl.textContent = round.prompt;
  feedbackEl.textContent = "Choose an answer.";
  progressEl.textContent = `${current + 1} / ${rounds.length}`;
  scoreEl.textContent = `${score} pts`;
  choicesEl.innerHTML = "";

  round.choices.forEach((choice, index) => {
    const button = document.createElement("button");
    button.className = "choice";
    button.type = "button";
    button.textContent = choice;
    button.dataset.knowledgeId = round.id;
    button.addEventListener("click", () => choose(index, button));
    choicesEl.appendChild(button);
  });
}

function choose(index, selectedButton) {
  if (answered) return;
  answered = true;
  const round = rounds[current];
  const correct = index === round.answer;
  if (correct) score += 10;

  [...choicesEl.children].forEach((button, choiceIndex) => {
    button.disabled = true;
    if (choiceIndex === round.answer) button.classList.add("correct");
  });

  if (!correct) selectedButton.classList.add("wrong");
  feedbackEl.textContent = correct
    ? `Correct. ${round.feedback}`
    : `Not quite. ${round.feedback}`;
  scoreEl.textContent = `${score} pts`;
}

function nextRound() {
  current = (current + 1) % rounds.length;
  renderRound();
}

function resetGame() {
  current = 0;
  score = 0;
  renderRound();
}

nextButton.addEventListener("click", nextRound);
resetButton.addEventListener("click", resetGame);
renderRound();
