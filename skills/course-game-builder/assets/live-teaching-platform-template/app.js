const DATA = window.LIVE_TEACHING_DATA;
const app = document.querySelector("#app");
const params = new URLSearchParams(location.search);
const role = params.get("role") || "host";
const storageKey = `live-teaching-player-${DATA.sessionCode || DATA.activity}`;

let state = null;
let player = JSON.parse(localStorage.getItem(storageKey) || "null");
let draftBids = {};
let eventSource = null;

const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[char]));

function api(path, options = {}) {
  return fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  }).then(async (response) => {
    const text = await response.text();
    const body = text ? JSON.parse(text) : {};
    if (!response.ok) throw new Error(body.error || response.statusText);
    return body;
  });
}

function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/events");
  eventSource.onmessage = (event) => {
    state = JSON.parse(event.data);
    render();
  };
  eventSource.onerror = () => {
    setTimeout(loadState, 1200);
  };
}

async function loadState() {
  state = await api("/api/state");
  if (player && !state.participants.some((item) => item.id === player.id)) {
    player = null;
    localStorage.removeItem(storageKey);
  }
  render();
}

function money(value) {
  return `${Number(value || 0).toLocaleString("zh-CN")} 金币`;
}

function getJoinUrl() {
  const url = new URL(location.href);
  url.searchParams.set("role", "player");
  return url.href;
}

function candidateTotals() {
  if (!state) return [];
  return DATA.candidates.map((candidate) => {
    const total = state.participants.reduce((sum, participant) => sum + Number(participant.bids?.[candidate.id] || 0), 0);
    const bidders = state.participants.filter((participant) => Number(participant.bids?.[candidate.id] || 0) > 0).length;
    const average = bidders ? Math.round(total / bidders) : 0;
    return { ...candidate, total, bidders, average };
  }).sort((a, b) => b.total - a.total);
}

function totalDraft() {
  return Object.values(draftBids).reduce((sum, value) => sum + Number(value || 0), 0);
}

function statusLabel(status) {
  return {
    setup: "准备中",
    open: "投金币中",
    locked: "已锁定",
    revealed: "已揭晓",
  }[status] || status;
}

function shell(content) {
  app.innerHTML = `
    <header class="topbar">
      <div>
        <p class="eyebrow">LIVE TEACHING</p>
        <h1>${esc(DATA.title)}</h1>
        <p>${esc(DATA.subtitle)}</p>
      </div>
      <div class="role-switch">
        <a class="${role === "host" ? "active" : ""}" href="?role=host">主持端</a>
        <a class="${role === "player" ? "active" : ""}" href="?role=player">参会端</a>
      </div>
    </header>
    ${content}
  `;
}

function render() {
  if (!state) {
    shell(`<main class="loading">正在连接课堂互动服务...</main>`);
    return;
  }
  if (role === "player") renderPlayer();
  else renderHost();
}

function renderHost() {
  const totals = candidateTotals();
  const submitted = state.participants.filter((item) => item.submittedAt).length;
  const top = totals.slice(0, DATA.topN || 5);
  shell(`
    <main class="host-layout">
      <section class="screen-panel hero-panel">
        <div>
          <p class="panel-label">课堂口令 ${esc(DATA.sessionCode || "LIVE")}</p>
          <h2>${esc(DATA.title)}</h2>
          <p>每位参会人有 ${DATA.budget} 个虚拟金币。请把金币投给最值得进入黄金评测集的候选样本。</p>
        </div>
        <div class="join-box">
          <span>参会入口</span>
          <strong>${esc(getJoinUrl())}</strong>
          <small>同一 Wi-Fi 下用手机打开。若打不开，检查电脑 IP、端口和防火墙。</small>
        </div>
      </section>

      <section class="stats-strip">
        <div><strong>${statusLabel(state.status)}</strong><span>当前状态</span></div>
        <div><strong>${state.participants.length}</strong><span>参会人数</span></div>
        <div><strong>${submitted}</strong><span>已提交</span></div>
        <div><strong>${money(totals.reduce((sum, item) => sum + item.total, 0))}</strong><span>总投入</span></div>
      </section>

      <section class="host-actions">
        <button data-action="open">开始投金币</button>
        <button data-action="lock">锁定投票</button>
        <button data-action="reveal">揭晓结果</button>
        <button data-action="reset" class="ghost">重置本局</button>
      </section>

      <section class="leaderboard">
        ${totals.map((item, index) => `
          <article class="rank-row ${top.some((winner) => winner.id === item.id) && state.status === "revealed" ? "winner" : ""}">
            <div class="rank-num">${index + 1}</div>
            <div class="rank-main">
              <div class="rank-title"><strong>${esc(item.title)}</strong><span>${esc(item.tag)}</span></div>
              <p>${esc(item.description)}</p>
              <div class="bar"><i style="width:${Math.min(100, item.total)}%"></i></div>
            </div>
            <div class="rank-price">
              <strong>${money(item.total)}</strong>
              <span>${item.bidders} 人投入 · 均 ${item.average}</span>
            </div>
          </article>
        `).join("")}
      </section>

      ${DATA.embeddedGames?.length ? `
        <section class="embedded-games">
          <h2>可嵌入活动</h2>
          ${DATA.embeddedGames.map((game) => `<a href="${esc(game.href)}">${esc(game.title)}</a>`).join("")}
        </section>
      ` : ""}
    </main>
  `);
  app.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = () => control(button.dataset.action);
  });
}

function renderPlayer() {
  if (!player) {
    shell(`
      <main class="player-layout">
        <section class="screen-panel join-panel">
          <p class="panel-label">加入课堂</p>
          <h2>${esc(DATA.title)}</h2>
          <form id="join-form">
            <label>你的名字或小组名</label>
            <input name="name" maxlength="24" autocomplete="name" placeholder="例如：第 3 组" required />
            <button type="submit">进入拍卖</button>
          </form>
        </section>
      </main>
    `);
    app.querySelector("#join-form").onsubmit = join;
    return;
  }

  const used = totalDraft();
  const remaining = DATA.budget - used;
  const canSubmit = remaining >= 0 && state.status === "open";
  shell(`
    <main class="player-layout">
      <section class="wallet">
        <div>
          <p class="panel-label">${esc(player.name)}</p>
          <h2>剩余 ${money(remaining)}</h2>
          <p>把 ${DATA.budget} 金币分配给你认为最值得进入黄金评测集的样本。</p>
        </div>
        <button id="leave" class="ghost">换人</button>
      </section>
      <section class="bid-list">
        ${DATA.candidates.map((candidate) => {
          const value = Number(draftBids[candidate.id] || 0);
          return `
            <article class="bid-card">
              <div class="bid-head">
                <strong>${esc(candidate.title)}</strong>
                <span>${esc(candidate.tag)}</span>
              </div>
              <p>${esc(candidate.description)}</p>
              <dl>
                <div><dt>样本例子</dt><dd>${esc(candidate.example)}</dd></div>
                <div><dt>入选价值</dt><dd>${esc(candidate.value)}</dd></div>
                <div><dt>忽略风险</dt><dd>${esc(candidate.risk)}</dd></div>
              </dl>
              <div class="bid-control">
                <button data-step="-10" data-id="${esc(candidate.id)}">-10</button>
                <input type="range" min="0" max="${DATA.budget}" step="5" value="${value}" data-id="${esc(candidate.id)}" />
                <button data-step="10" data-id="${esc(candidate.id)}">+10</button>
                <output>${value}</output>
              </div>
            </article>
          `;
        }).join("")}
      </section>
      <footer class="submit-bar">
        <span>${statusLabel(state.status)} · 已用 ${used}/${DATA.budget}</span>
        <button id="submit-bids" ${canSubmit ? "" : "disabled"}>${state.status === "open" ? "提交金币" : "等待主持人开始"}</button>
      </footer>
    </main>
  `);
  app.querySelector("#leave").onclick = () => {
    player = null;
    localStorage.removeItem(storageKey);
    draftBids = {};
    render();
  };
  app.querySelectorAll("input[type=range]").forEach((input) => {
    input.oninput = () => updateBid(input.dataset.id, Number(input.value));
  });
  app.querySelectorAll("[data-step]").forEach((button) => {
    button.onclick = () => updateBid(button.dataset.id, Number(draftBids[button.dataset.id] || 0) + Number(button.dataset.step));
  });
  app.querySelector("#submit-bids").onclick = submitBids;
}

async function join(event) {
  event.preventDefault();
  const formData = new FormData(event.currentTarget);
  const result = await api("/api/join", {
    method: "POST",
    body: JSON.stringify({ name: formData.get("name") }),
  });
  player = result.participant;
  draftBids = { ...(player.bids || {}) };
  localStorage.setItem(storageKey, JSON.stringify(player));
  await loadState();
}

function updateBid(id, value) {
  draftBids[id] = Math.max(0, Math.min(DATA.budget, Math.round(value / 5) * 5));
  renderPlayer();
}

async function submitBids() {
  const used = totalDraft();
  if (used > DATA.budget) {
    alert("金币不能超过预算。");
    return;
  }
  const result = await api("/api/bid", {
    method: "POST",
    body: JSON.stringify({ participantId: player.id, bids: draftBids }),
  });
  player = result.participant;
  localStorage.setItem(storageKey, JSON.stringify(player));
  await loadState();
}

async function control(action) {
  if (action === "reset" && !confirm("确定重置本局？所有参会人投入都会清空。")) return;
  await api("/api/control", { method: "POST", body: JSON.stringify({ action }) });
  await loadState();
}

loadState().then(connectEvents).catch((error) => {
  shell(`<main class="loading error">无法连接服务：${esc(error.message)}。请确认 server.mjs 正在运行。</main>`);
});
