import http from "node:http";
import crypto from "node:crypto";
import { readFile, rename, writeFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || process.argv.find((arg) => arg.startsWith("--port="))?.split("=")[1] || 8787);
const host = process.env.HOST || process.argv.find((arg) => arg.startsWith("--host="))?.split("=")[1] || "0.0.0.0";
const hostKey = process.env.HOST_KEY
  || process.argv.find((arg) => arg.startsWith("--host-key="))?.split("=")[1]
  || crypto.randomBytes(18).toString("base64url");
const stateFile = path.join(root, ".live-session-state.json");
const maxParticipants = Math.max(1, Number(process.env.MAX_PARTICIPANTS || 500));

let activityData = {};
try {
  const sandbox = { window: {} };
  vm.runInNewContext(await readFile(path.join(root, "data.js"), "utf8"), sandbox);
  activityData = sandbox.window.LIVE_TEACHING_DATA || {};
} catch {
  activityData = {};
}

const emptyState = () => ({
  status: "setup",
  participants: [],
  updatedAt: Date.now(),
});
let state = emptyState();
try {
  const restored = JSON.parse(await readFile(stateFile, "utf8"));
  if (restored && Array.isArray(restored.participants) && ["setup", "open", "locked", "revealed"].includes(restored.status)) {
    restored.participants = restored.participants.map((participant) => ({
      ...participant,
      token: participant.token || crypto.randomBytes(24).toString("base64url"),
    }));
    state = restored;
  }
} catch {
  state = emptyState();
}
const clients = new Set();
let broadcastTimer = null;
let pendingBroadcastScope = null;
let persistTimer = null;

function aggregateResults() {
  return (activityData.candidates || []).map((candidate) => {
    const total = state.participants.reduce(
      (sum, participant) => sum + Number(participant.bids?.[candidate.id] || 0),
      0,
    );
    const bidders = state.participants.filter(
      (participant) => Number(participant.bids?.[candidate.id] || 0) > 0,
    ).length;
    return {
      id: candidate.id,
      total,
      bidders,
      average: bidders ? Math.round(total / bidders) : 0,
    };
  }).sort((a, b) => b.total - a.total);
}

function groupCounts() {
  const counts = new Map((activityData.groups || []).map((group) => [group.id, 0]));
  for (const participant of state.participants) {
    counts.set(participant.groupId, (counts.get(participant.groupId) || 0) + 1);
  }
  return Array.from(counts, ([groupId, count]) => ({ groupId, count }));
}

function playerJoinUrls() {
  if (["127.0.0.1", "localhost", "::1"].includes(host)) {
    return [`http://127.0.0.1:${port}/?role=player`];
  }
  if (!["0.0.0.0", "::"].includes(host)) {
    return [`http://${host}:${port}/?role=player`];
  }
  return Object.values(os.networkInterfaces()).flat()
    .filter((info) => info && info.family === "IPv4" && !info.internal)
    .map((info) => `http://${info.address}:${port}/?role=player`);
}

function participantSummary(item, includeBids = true) {
  return {
    id: item.id,
    name: item.name,
    nickname: item.nickname || "",
    groupId: item.groupId || "",
    groupName: item.groupName || "",
    memberNumber: item.memberNumber || 0,
    bids: includeBids ? item.bids || {} : {},
    joinedAt: item.joinedAt,
    submittedAt: item.submittedAt || null,
  };
}

function participantClientRecord(item) {
  return {
    ...participantSummary(item),
    token: item.token,
  };
}

function publicState(client = {}) {
  const base = {
    status: state.status,
    updatedAt: state.updatedAt,
    participantCount: state.participants.length,
    submittedCount: state.participants.filter((item) => item.submittedAt).length,
    groupCounts: groupCounts(),
    results: state.status === "revealed" ? aggregateResults() : [],
  };
  if (client.role === "player") {
    const participant = client.participantId ? participantById(client.participantId) : null;
    const authorizedParticipant = participant && client.participantToken === participant.token ? participant : null;
    const participants = authorizedParticipant ? [participantSummary(authorizedParticipant)] : [];
    return {
      ...base,
      participant: authorizedParticipant ? participantSummary(authorizedParticipant) : null,
      participants,
    };
  }
  return {
    ...base,
    participants: state.participants.map((item) => participantSummary(item)),
    joinUrls: playerJoinUrls(),
  };
}

function sendJson(response, status, body) {
  response.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(JSON.stringify(body));
}

function cloneScope(scope = {}) {
  scope ||= {};
  return {
    all: Boolean(scope.all),
    includePlayers: Boolean(scope.includePlayers),
    participantIds: new Set(scope.participantIds || []),
  };
}

function mergeScope(previous, next) {
  const merged = cloneScope(previous);
  const incoming = cloneScope(next);
  merged.all = merged.all || incoming.all;
  merged.includePlayers = merged.includePlayers || incoming.includePlayers;
  for (const id of incoming.participantIds) merged.participantIds.add(id);
  return merged;
}

function shouldSendToClient(client, scope) {
  if (scope.all) return true;
  if (client.role === "host") return true;
  if (scope.includePlayers && client.role === "player") return true;
  return client.participantId && scope.participantIds.has(client.participantId);
}

function broadcast(scope = { all: true }) {
  if (broadcastTimer) {
    clearTimeout(broadcastTimer);
    broadcastTimer = null;
  }
  pendingBroadcastScope = null;
  state.updatedAt = Date.now();
  const normalizedScope = cloneScope(scope);
  for (const client of Array.from(clients)) {
    if (!shouldSendToClient(client, normalizedScope)) continue;
    try {
      client.response.write(`data: ${JSON.stringify(publicState(client))}\n\n`);
    } catch {
      clients.delete(client);
    }
  }
  schedulePersist();
}

function broadcastSoon(scope = { all: true }) {
  pendingBroadcastScope = mergeScope(pendingBroadcastScope, scope);
  if (broadcastTimer) return;
  broadcastTimer = setTimeout(() => {
    const scopeToSend = pendingBroadcastScope || { all: true };
    broadcastTimer = null;
    pendingBroadcastScope = null;
    broadcast(scopeToSend);
  }, 60);
}

async function readBody(request) {
  const chunks = [];
  let size = 0;
  for await (const chunk of request) {
    size += chunk.length;
    if (size > 64 * 1024) {
      const error = new Error("请求内容过大。");
      error.statusCode = 413;
      throw error;
    }
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  try {
    return JSON.parse(Buffer.concat(chunks).toString("utf8"));
  } catch {
    const error = new Error("请求内容不是有效 JSON。");
    error.statusCode = 400;
    throw error;
  }
}

function schedulePersist() {
  if (persistTimer) return;
  persistTimer = setTimeout(async () => {
    persistTimer = null;
    const tempFile = `${stateFile}.tmp`;
    try {
      await writeFile(tempFile, JSON.stringify(state, null, 2), "utf8");
      await rename(tempFile, stateFile);
    } catch (error) {
      console.error(`Unable to persist classroom state: ${error.message}`);
    }
  }, 80);
}

function isLoopback(request) {
  const address = String(request.socket.remoteAddress || "");
  return address === "::1" || address === "127.0.0.1" || address === "::ffff:127.0.0.1";
}

function hostAuthorized(request, url) {
  const supplied = String(request.headers["x-host-key"] || url.searchParams.get("key") || "");
  return isLoopback(request) || supplied === hostKey;
}

function denyHost(response) {
  sendJson(response, 403, { error: "老师端授权无效，请在教师电脑上打开老师入口。" });
}

function participantById(id) {
  return state.participants.find((item) => item.id === id);
}

function groupById(id) {
  return (activityData.groups || []).find((item) => item.id === id);
}

function nextMemberNumber(groupId) {
  return state.participants
    .filter((item) => item.groupId === groupId)
    .reduce((max, item) => Math.max(max, Number(item.memberNumber || 0)), 0) + 1;
}

async function serveStatic(request, response) {
  const url = new URL(request.url, `http://${request.headers.host}`);
  const pathname = decodeURIComponent(url.pathname === "/" ? "/index.html" : url.pathname);
  const filePath = path.normalize(path.join(root, pathname));
  const relativePath = path.relative(root, filePath);
  if (
    !relativePath
    || relativePath.startsWith("..")
    || path.isAbsolute(relativePath)
    || path.basename(filePath).startsWith(".")
    || filePath === stateFile
    || !existsSync(filePath)
  ) {
    response.writeHead(404);
    response.end("Not found");
    return;
  }
  const ext = path.extname(filePath).toLowerCase();
  const types = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".svg": "image/svg+xml",
  };
  response.writeHead(200, {
    "Content-Type": types[ext] || "application/octet-stream",
    "Cache-Control": "no-store",
  });
  response.end(await readFile(filePath));
}

const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, `http://${request.headers.host}`);
    if (request.method === "GET" && url.pathname === "/api/state") {
      const requestedRole = url.searchParams.get("role") === "player" ? "player" : "host";
      if (requestedRole === "host" && !hostAuthorized(request, url)) {
        denyHost(response);
        return;
      }
      sendJson(response, 200, publicState({
        role: requestedRole,
        participantId: url.searchParams.get("participantId") || "",
        participantToken: String(request.headers["x-participant-token"] || ""),
      }));
      return;
    }
    if (request.method === "GET" && url.pathname === "/events") {
      const requestedRole = url.searchParams.get("role") === "player" ? "player" : "host";
      if (requestedRole === "host" && !hostAuthorized(request, url)) {
        denyHost(response);
        return;
      }
      const client = {
        response,
        role: requestedRole,
        participantId: url.searchParams.get("participantId") || "",
        participantToken: String(url.searchParams.get("participantToken") || ""),
      };
      response.writeHead(200, {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache",
        Connection: "keep-alive",
      });
      response.write(`data: ${JSON.stringify(publicState(client))}\n\n`);
      clients.add(client);
      request.on("close", () => clients.delete(client));
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/join") {
      const body = await readBody(request);
      if (state.participants.length >= maxParticipants) {
        sendJson(response, 429, { error: `课堂人数已达到上限 ${maxParticipants}。` });
        return;
      }
      const group = groupById(String(body.groupId || ""));
      if (!group) {
        sendJson(response, 400, { error: "请选择有效组别。" });
        return;
      }
      const memberNumber = nextMemberNumber(group.id);
      const nickname = String(body.nickname || "")
        .replace(/[\u0000-\u001f\u007f]/g, "")
        .trim()
        .slice(0, 24);
      const participant = {
        id: `p_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
        name: `${group.name}-${memberNumber}号`,
        nickname,
        groupId: group.id,
        groupName: group.name,
        memberNumber,
        token: crypto.randomBytes(24).toString("base64url"),
        bids: {},
        joinedAt: Date.now(),
        submittedAt: null,
      };
      state.participants.push(participant);
      broadcastSoon({ includePlayers: true });
      sendJson(response, 200, { participant: participantClientRecord(participant) });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/bid") {
      const body = await readBody(request);
      if (state.status !== "open") {
        sendJson(response, 409, { error: "当前不在投金币阶段。" });
        return;
      }
      const participant = participantById(body.participantId);
      const participantToken = String(request.headers["x-participant-token"] || body.participantToken || "");
      if (!participant || participant.token !== participantToken) {
        sendJson(response, 404, { error: "参会人不存在，请重新加入。" });
        return;
      }
      if (!body.bids || typeof body.bids !== "object" || Array.isArray(body.bids)) {
        sendJson(response, 400, { error: "投币数据格式无效。" });
        return;
      }
      const candidateIds = new Set((activityData.candidates || []).map((candidate) => String(candidate.id)));
      const budget = Math.max(1, Number(activityData.budget ?? 100));
      const bidStep = Math.max(1, Number(activityData.bidStep ?? 5));
      const bids = {};
      for (const [key, rawValue] of Object.entries(body.bids)) {
        const value = Number(rawValue);
        if (!candidateIds.has(key)) {
          sendJson(response, 400, { error: "投币数据包含未知候选项。" });
          return;
        }
        if (!Number.isFinite(value) || !Number.isInteger(value) || value < 0 || value > budget || value % bidStep !== 0) {
          sendJson(response, 400, { error: `每项金币必须是 0 到 ${budget} 之间、且以 ${bidStep} 为步长的整数。` });
          return;
        }
        bids[key] = value;
      }
      const used = Object.values(bids).reduce((sum, value) => sum + value, 0);
      if (used > budget) {
        sendJson(response, 400, { error: `金币不能超过 ${budget}。` });
        return;
      }
      if (used !== budget) {
        sendJson(response, 400, { error: `请分配完全部 ${budget} 金币后再提交。` });
        return;
      }
      participant.bids = bids;
      participant.submittedAt = Date.now();
      broadcastSoon({ participantIds: [participant.id] });
      sendJson(response, 200, { participant: participantClientRecord(participant) });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/control") {
      if (!hostAuthorized(request, url)) {
        denyHost(response);
        return;
      }
      const body = await readBody(request);
      if (body.action === "open" && ["setup", "locked", "revealed"].includes(state.status)) state.status = "open";
      else if (body.action === "lock" && state.status === "open") state.status = "locked";
      else if (body.action === "reveal" && state.status === "locked") state.status = "revealed";
      else if (body.action === "reset") state = emptyState();
      else {
        sendJson(response, 409, { error: "当前课堂阶段不允许执行该操作。" });
        return;
      }
      broadcast({ all: true });
      sendJson(response, 200, publicState({ role: "host" }));
      return;
    }
    await serveStatic(request, response);
  } catch (error) {
    sendJson(response, Number(error.statusCode || 500), { error: error.message || String(error) });
  }
});

server.listen(port, host, () => {
  const urls = [`http://localhost:${port}`];
  for (const info of Object.values(os.networkInterfaces()).flat()) {
    if (info && info.family === "IPv4" && !info.internal) urls.push(`http://${info.address}:${port}`);
  }
  console.log("Teaching live platform running:");
  for (const url of urls) console.log(`  ${url}`);
  console.log("Host screen (teacher computer): append ?role=host");
  console.log(`Remote host key: ${hostKey}`);
  console.log("Player screen: append ?role=player");
});
