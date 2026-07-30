const DATA = window.LIVE_TEACHING_DATA;
const app = document.querySelector("#app");
const params = new URLSearchParams(location.search);
const role = params.get("role") || "host";
const currentApp = params.get("app") || "";
const storageKey = `live-teaching-player-${DATA.sessionCode || DATA.activity}`;

let state = null;
let player = JSON.parse(sessionStorage.getItem(storageKey) || "null");
let draftBids = {};
let eventSource = null;
let renderPending = false;

const AUCTION_APP = "golden-sample-auction";

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

function participantIdentitySnapshot(item) {
  if (!item) return "";
  return JSON.stringify({
    id: item.id,
    groupId: item.groupId,
    memberNumber: item.memberNumber,
  });
}

function ownParticipantFrom(snapshot, participant) {
  if (!snapshot || !participant) return null;
  return snapshot.participants.find((item) => item.id === participant.id) || null;
}

function shouldRenderForStateChange(previousState, nextState, previousPlayer, nextPlayer) {
  if (!previousState) return true;
  if (role === "host") return true;
  if (previousState.status !== nextState.status) return true;
  if (!previousPlayer && nextPlayer) return true;
  if (previousPlayer && !nextPlayer) return true;
  if (role !== "player") return true;
  if (!nextPlayer) return true;

  const before = participantIdentitySnapshot(ownParticipantFrom(previousState, previousPlayer));
  const after = participantIdentitySnapshot(ownParticipantFrom(nextState, nextPlayer));
  if (before !== after) return true;

  if (currentApp === AUCTION_APP) return false;
  if (!currentApp) return false;
  return true;
}

function scheduleRender() {
  if (renderPending) return;
  renderPending = true;
  requestAnimationFrame(() => {
    renderPending = false;
    render();
  });
}

function connectEvents() {
  if (eventSource) eventSource.close();
  eventSource = new EventSource("/events");
  eventSource.onmessage = (event) => {
    const previousState = state;
    const previousPlayer = player;
    state = JSON.parse(event.data);
    syncPlayer();
    if (shouldRenderForStateChange(previousState, state, previousPlayer, player)) scheduleRender();
    else refreshLocalControls();
  };
  eventSource.onerror = () => setTimeout(loadState, 1200);
}

async function loadState() {
  const previousState = state;
  const previousPlayer = player;
  state = await api("/api/state");
  syncPlayer();
  if (shouldRenderForStateChange(previousState, state, previousPlayer, player)) scheduleRender();
  else refreshLocalControls();
}

function syncPlayer() {
  if (!player || !state) return;
  const fresh = state.participants.find((item) => item.id === player.id);
  if (!fresh) {
    player = null;
    sessionStorage.removeItem(storageKey);
    draftBids = {};
    return;
  }
  player = { ...player, ...fresh };
  sessionStorage.setItem(storageKey, JSON.stringify(player));
}

function navigate(nextParams) {
  const url = new URL(location.href);
  Object.entries(nextParams).forEach(([key, value]) => {
    if (value === null || value === "") url.searchParams.delete(key);
    else url.searchParams.set(key, value);
  });
  location.href = url.pathname + url.search;
}

function appUrl(appId, nextRole = role) {
  const url = new URL(location.href);
  url.searchParams.set("role", nextRole);
  if (appId) url.searchParams.set("app", appId);
  else url.searchParams.delete("app");
  return url.pathname + url.search;
}

function getJoinUrl() {
  const url = new URL(location.href);
  url.searchParams.set("role", "player");
  url.searchParams.delete("app");
  return url.href;
}

function money(value) {
  return `${Number(value || 0).toLocaleString("zh-CN")} 金币`;
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

function participantLabel(item) {
  if (!item) return "未加入";
  return `${item.groupName} · ${item.memberNumber}号`;
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

function groupCounts() {
  const counts = new Map(DATA.groups.map((group) => [group.id, 0]));
  (state?.participants || []).forEach((item) => counts.set(item.groupId, (counts.get(item.groupId) || 0) + 1));
  return counts;
}

function shell(content) {
  app.innerHTML = `
    <header class="topbar">
      <div>
        <p class="eyebrow">LIVE TEACHING</p>
        <h1>${esc(DATA.platformTitle || DATA.title)}</h1>
        <p>${esc(DATA.platformSubtitle || DATA.subtitle)}</p>
      </div>
      <div class="role-switch">
        <a class="${role === "host" ? "active" : ""}" href="${appUrl("", "host")}">老师端</a>
        <a class="${role === "player" ? "active" : ""}" href="${appUrl("", "player")}">学生端</a>
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
  if (role === "player" && currentApp === AUCTION_APP && player) renderPlayerAuction();
  else if (role === "host" && currentApp === AUCTION_APP) renderHostAuction();
  else if (role === "player") renderPlayerHome();
  else renderHostHome();
}

function applicationCards(nextRole) {
  return `
    <section class="app-grid">
      ${DATA.applications.map((item) => `
        <a class="app-card ${item.id === AUCTION_APP ? "primary-app" : ""}" href="${esc(item.href || appUrl(item.id, nextRole))}">
          <span>${esc(item.kicker || "APP")}</span>
          <strong>${esc(item.title)}</strong>
          <p>${esc(item.description)}</p>
        </a>
      `).join("")}
    </section>
  `;
}

function groupRoster() {
  const groups = DATA.groups.map((group) => ({
    ...group,
    members: state.participants.filter((item) => item.groupId === group.id).sort((a, b) => a.memberNumber - b.memberNumber),
  }));
  return `
    <section class="group-roster">
      ${groups.map((group) => `
        <article>
          <h3>${esc(group.name)} <span>${group.members.length} 人</span></h3>
          <div class="member-list">
            ${group.members.length ? group.members.map((member) => `
              <span>${member.memberNumber}号 ${esc(member.nickname || member.name || "")}</span>
            `).join("") : `<small>等待加入</small>`}
          </div>
        </article>
      `).join("")}
    </section>
  `;
}

function renderHostHome() {
  const submitted = state.participants.filter((item) => item.submittedAt).length;
  shell(`
    <main class="host-layout">
      <section class="screen-panel hero-panel">
        <div>
          <p class="panel-label">课堂主页 ${esc(DATA.sessionCode || "LIVE")}</p>
          <h2>选择一个教学应用</h2>
          <p>学生先在主页选择组别，系统会按加入顺序自动分配组内序号。老师端可以从这里进入任意教学活动。</p>
        </div>
        <div class="join-box">
          <span>学生入口</span>
          <strong>${esc(getJoinUrl())}</strong>
          <small>同一 Wi-Fi 下用手机打开。每个学生选择组别后会自动获得 1号、2号、3号...</small>
        </div>
      </section>
      <section class="stats-strip">
        <div><strong>${state.participants.length}</strong><span>已加入学生</span></div>
        <div><strong>${submitted}</strong><span>已提交拍卖</span></div>
        <div><strong>${DATA.groups.length}</strong><span>可选组别</span></div>
        <div><strong>${DATA.applications.length}</strong><span>可用应用</span></div>
      </section>
      ${applicationCards("host")}
      ${groupRoster()}
    </main>
  `);
}

function renderPlayerHome() {
  if (!player) {
    const counts = groupCounts();
    shell(`
      <main class="player-layout">
        <section class="screen-panel join-panel">
          <p class="panel-label">加入课堂</p>
          <h2>先选择你的组别</h2>
          <p>系统会根据加入先后，自动给你分配组内序号，例如“第 1 组 · 1号”。</p>
          <form id="join-form">
            <label>昵称，可不填</label>
            <input name="nickname" maxlength="24" autocomplete="name" placeholder="例如：小明 / 设备名" />
            <input type="hidden" name="groupId" required />
            <div class="group-picker">
              ${DATA.groups.map((group) => `
                <button type="button" data-group="${esc(group.id)}">
                  <strong>${esc(group.name)}</strong>
                  <span>当前 ${counts.get(group.id) || 0} 人</span>
                </button>
              `).join("")}
            </div>
            <button type="submit">进入课堂主页</button>
          </form>
        </section>
      </main>
    `);
    const form = app.querySelector("#join-form");
    app.querySelectorAll("[data-group]").forEach((button) => {
      button.onclick = () => {
        form.groupId.value = button.dataset.group;
        app.querySelectorAll("[data-group]").forEach((item) => item.classList.toggle("selected", item === button));
      };
    });
    form.onsubmit = join;
    return;
  }

  shell(`
    <main class="player-layout">
      <section class="wallet home-wallet">
        <div>
          <p class="panel-label">${esc(participantLabel(player))}</p>
          <h2>课堂应用主页</h2>
          <p>${esc(player.nickname || player.name || "同学")}，你可以从这里进入老师开启的活动。</p>
        </div>
        <button id="leave" class="ghost">重新选组</button>
      </section>
      ${applicationCards("player")}
    </main>
  `);
  app.querySelector("#leave").onclick = () => {
    player = null;
    sessionStorage.removeItem(storageKey);
    draftBids = {};
    render();
  };
}

function renderHostAuction() {
  const totals = candidateTotals();
  const submitted = state.participants.filter((item) => item.submittedAt).length;
  const top = totals.slice(0, DATA.topN || 5);
  shell(`
    <main class="host-layout">
      <a class="back-link" href="${appUrl("", "host")}">返回应用主页</a>
      <section class="screen-panel hero-panel">
        <div>
          <p class="panel-label">课堂口令 ${esc(DATA.sessionCode || "LIVE")}</p>
          <h2>${esc(DATA.title)}</h2>
          <p>每位学生有 ${DATA.budget} 个虚拟金币。请把金币投给最值得进入黄金评测集的候选样本。</p>
        </div>
        <div class="join-box">
          <span>学生入口</span>
          <strong>${esc(getJoinUrl())}</strong>
          <small>学生先选组别并获得组内序号，再进入拍卖应用。</small>
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
      ${groupRoster()}
    </main>
  `);
  app.querySelectorAll("[data-action]").forEach((button) => {
    button.onclick = () => control(button.dataset.action);
  });
}

function renderPlayerAuction() {
  const used = totalDraft();
  const remaining = DATA.budget - used;
  const canSubmit = remaining >= 0 && state.status === "open";
  const submitLabel = state.status === "open" ? (player?.submittedAt ? "更新金币" : "提交金币") : "等待老师开始";
  shell(`
    <main class="player-layout">
      <a class="back-link" href="${appUrl("", "player")}">返回应用主页</a>
      <section class="wallet">
        <div>
          <p class="panel-label">${esc(participantLabel(player))}</p>
          <h2 id="remaining-budget">剩余 ${money(remaining)}</h2>
          <p>把 ${DATA.budget} 金币分配给你认为最值得进入黄金评测集的样本。</p>
        </div>
        <button id="leave" class="ghost">重新选组</button>
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
                <output data-output="${esc(candidate.id)}">${value}</output>
              </div>
            </article>
          `;
        }).join("")}
      </section>
      <footer class="submit-bar">
        <span id="usage-state">${statusLabel(state.status)} · 已用 ${used}/${DATA.budget}</span>
        <button id="submit-bids" ${canSubmit ? "" : "disabled"}>${submitLabel}</button>
      </footer>
    </main>
  `);
  app.querySelector("#leave").onclick = () => {
    player = null;
    sessionStorage.removeItem(storageKey);
    draftBids = {};
    navigate({ role: "player", app: "" });
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
  if (!formData.get("groupId")) {
    alert("请先选择组别。");
    return;
  }
  const result = await api("/api/join", {
    method: "POST",
    body: JSON.stringify({
      groupId: formData.get("groupId"),
      nickname: formData.get("nickname"),
    }),
  });
  player = result.participant;
  draftBids = { ...(player.bids || {}) };
  sessionStorage.setItem(storageKey, JSON.stringify(player));
  await loadState();
}

function updateBid(id, value) {
  const normalized = Math.max(0, Math.min(DATA.budget, Math.round(value / 5) * 5));
  draftBids[id] = normalized;

  const input = app.querySelector(`input[type=range][data-id="${CSS.escape(id)}"]`);
  if (input && Number(input.value) !== normalized) input.value = String(normalized);

  const output = app.querySelector(`output[data-output="${CSS.escape(id)}"]`);
  if (output) output.textContent = String(normalized);

  updateBudgetUi();
}

function updateBudgetUi() {
  const used = totalDraft();
  const remaining = DATA.budget - used;
  const remainingEl = app.querySelector("#remaining-budget");
  if (remainingEl) remainingEl.textContent = `剩余 ${money(remaining)}`;

  const usageEl = app.querySelector("#usage-state");
  const submitted = player?.submittedAt ? " · 已提交" : "";
  if (usageEl) usageEl.textContent = `${statusLabel(state.status)} · 已用 ${used}/${DATA.budget}${submitted}`;

  const submit = app.querySelector("#submit-bids");
  if (submit) {
    submit.disabled = !(remaining >= 0 && state.status === "open");
    submit.textContent = state.status === "open" ? (player?.submittedAt ? "更新金币" : "提交金币") : "等待老师开始";
  }
}

function refreshLocalControls() {
  if (role === "player" && currentApp === AUCTION_APP) updateBudgetUi();
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
  sessionStorage.setItem(storageKey, JSON.stringify(player));
  updateBudgetUi();
}

async function control(action) {
  if (action === "reset" && !confirm("确定重置本局？所有学生身份和投入都会清空。")) return;
  await api("/api/control", { method: "POST", body: JSON.stringify({ action }) });
  await loadState();
}

loadState().then(connectEvents).catch((error) => {
  shell(`<main class="loading error">无法连接服务：${esc(error.message)}。请确认 server.mjs 正在运行。</main>`);
});
