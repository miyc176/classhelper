import http from "node:http";
import { readFile } from "node:fs/promises";
import { existsSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || process.argv.find((arg) => arg.startsWith("--port="))?.split("=")[1] || 8787);
const host = process.env.HOST || process.argv.find((arg) => arg.startsWith("--host="))?.split("=")[1] || "0.0.0.0";

let activityData = {};
try {
  const sandbox = { window: {} };
  vm.runInNewContext(await readFile(path.join(root, "data.js"), "utf8"), sandbox);
  activityData = sandbox.window.LIVE_TEACHING_DATA || {};
} catch {
  activityData = {};
}

let state = {
  status: "setup",
  participants: [],
  updatedAt: Date.now(),
};
const clients = new Set();
let broadcastTimer = null;
let pendingBroadcastScope = null;

function groupCounts() {
  const counts = new Map((activityData.groups || []).map((group) => [group.id, 0]));
  for (const participant of state.participants) {
    counts.set(participant.groupId, (counts.get(participant.groupId) || 0) + 1);
  }
  return Array.from(counts, ([groupId, count]) => ({ groupId, count }));
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

function publicState(client = {}) {
  const base = {
    status: state.status,
    updatedAt: state.updatedAt,
    participantCount: state.participants.length,
    submittedCount: state.participants.filter((item) => item.submittedAt).length,
    groupCounts: groupCounts(),
  };
  if (client.role === "player") {
    const participant = client.participantId ? participantById(client.participantId) : null;
    const participants = participant ? [participantSummary(participant)] : [];
    return {
      ...base,
      participant: participant ? participantSummary(participant) : null,
      participants,
    };
  }
  return {
    ...base,
    participants: state.participants.map((item) => participantSummary(item)),
  };
}

function sendJson(response, status, body) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8" });
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
  for await (const chunk of request) chunks.push(chunk);
  if (!chunks.length) return {};
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
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
  if (!filePath.startsWith(root) || !existsSync(filePath)) {
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
      sendJson(response, 200, publicState({
        role: url.searchParams.get("role") || "host",
        participantId: url.searchParams.get("participantId") || "",
      }));
      return;
    }
    if (request.method === "GET" && url.pathname === "/events") {
      const client = {
        response,
        role: url.searchParams.get("role") || "host",
        participantId: url.searchParams.get("participantId") || "",
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
      const group = groupById(String(body.groupId || ""));
      if (!group) {
        sendJson(response, 400, { error: "请选择有效组别。" });
        return;
      }
      const memberNumber = nextMemberNumber(group.id);
      const nickname = String(body.nickname || "").trim().slice(0, 24);
      const participant = {
        id: `p_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`,
        name: `${group.name}-${memberNumber}号`,
        nickname,
        groupId: group.id,
        groupName: group.name,
        memberNumber,
        bids: {},
        joinedAt: Date.now(),
        submittedAt: null,
      };
      state.participants.push(participant);
      broadcastSoon({ includePlayers: true });
      sendJson(response, 200, { participant });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/bid") {
      const body = await readBody(request);
      if (state.status !== "open") {
        sendJson(response, 409, { error: "当前不在投金币阶段。" });
        return;
      }
      const participant = participantById(body.participantId);
      if (!participant) {
        sendJson(response, 404, { error: "参会人不存在，请重新加入。" });
        return;
      }
      const bids = Object.fromEntries(
        Object.entries(body.bids || {}).map(([key, value]) => [key, Math.max(0, Number(value || 0))])
      );
      const budget = Number(activityData.budget || 100);
      const used = Object.values(bids).reduce((sum, value) => sum + value, 0);
      if (used > budget) {
        sendJson(response, 400, { error: `金币不能超过 ${budget}。` });
        return;
      }
      participant.bids = bids;
      participant.submittedAt = Date.now();
      broadcastSoon({ participantIds: [participant.id] });
      sendJson(response, 200, { participant });
      return;
    }
    if (request.method === "POST" && url.pathname === "/api/control") {
      const body = await readBody(request);
      if (body.action === "open") state.status = "open";
      else if (body.action === "lock") state.status = "locked";
      else if (body.action === "reveal") state.status = "revealed";
      else if (body.action === "reset") state = { status: "setup", participants: [], updatedAt: Date.now() };
      else {
        sendJson(response, 400, { error: "未知控制命令。" });
        return;
      }
      broadcast({ all: true });
      sendJson(response, 200, publicState({ role: "host" }));
      return;
    }
    await serveStatic(request, response);
  } catch (error) {
    sendJson(response, 500, { error: error.message || String(error) });
  }
});

server.listen(port, host, () => {
  const urls = [`http://localhost:${port}`];
  for (const info of Object.values(os.networkInterfaces()).flat()) {
    if (info && info.family === "IPv4" && !info.internal) urls.push(`http://${info.address}:${port}`);
  }
  console.log("Teaching live platform running:");
  for (const url of urls) console.log(`  ${url}`);
  console.log("Host screen: append ?role=host");
  console.log("Player screen: append ?role=player");
});
