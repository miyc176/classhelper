#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const baseUrl = new URL(process.argv[2] || "http://127.0.0.1:8787/");
const outputDir = path.resolve(process.argv[3] || "live-platform-test");
fs.mkdirSync(outputDir, { recursive: true });

function endpoint(pathname) {
  return new URL(pathname, baseUrl).href;
}

async function request(pathname, options = {}) {
  const response = await fetch(endpoint(pathname), {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  let body = {};
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = { text };
    }
  }
  return { response, body };
}

async function post(pathname, body, headers = {}) {
  return request(pathname, { method: "POST", headers, body: JSON.stringify(body) });
}

async function launchBrowser() {
  const candidates = [
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  ].filter(Boolean).filter((candidate) => fs.existsSync(candidate));
  let lastError = null;
  for (const executablePath of candidates) {
    try {
      return await chromium.launch({ executablePath });
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError || new Error("No supported browser executable found.");
}

function check(condition, message, details = {}) {
  if (!condition) {
    const error = new Error(message);
    error.details = details;
    throw error;
  }
}

const report = {
  status: "fail",
  baseUrl: baseUrl.href,
  checks: [],
  screenshots: [],
  errors: [],
};

let browser;
try {
  const reset = await post("/api/control", { action: "reset" });
  check(reset.response.ok, "Unable to reset test session.", reset.body);
  const invalidTransition = await post("/api/control", { action: "reveal" });
  check(invalidTransition.response.status === 409, "Invalid setup-to-reveal transition was accepted.");
  const malformedJson = await request("/api/join", { method: "POST", body: "{" });
  check(malformedJson.response.status === 400, "Malformed JSON was not rejected as a client error.");
  const oversizedBody = await request("/api/join", {
    method: "POST",
    body: JSON.stringify({ groupId: "group_1", nickname: "x".repeat(70 * 1024) }),
  });
  check(oversizedBody.response.status === 413, "Oversized request body was not rejected.");
  const hiddenState = await request("/.live-session-state.json");
  check(hiddenState.response.status === 404, "Persisted state file was exposed as a static asset.");
  report.checks.push("phase transition guard", "malformed request guard", "request size guard", "state file privacy");

  browser = await launchBrowser();
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));

  await page.goto(new URL("?role=player&fresh=budget-test", baseUrl).href, { waitUntil: "networkidle" });
  await page.locator('[data-group="group_1"]').click();
  await page.locator("#join-form button[type=submit]").click();
  await page.waitForSelector(".app-grid");
  await page.goto(new URL("?role=player&app=golden-sample-auction&fresh=budget-test", baseUrl).href, {
    waitUntil: "networkidle",
  });

  const opened = await post("/api/control", { action: "open" });
  check(opened.response.ok, "Unable to open auction.", opened.body);
  await page.waitForFunction(() => document.querySelector('input[type="range"]')?.disabled === false);

  const ranges = page.locator('input[type="range"][data-id]');
  check(await ranges.count() >= 2, "Expected at least two candidate sliders.");
  await ranges.nth(0).fill("60");
  check(await ranges.nth(1).getAttribute("max") === "40", "Second slider did not inherit the remaining budget cap.");
  await ranges.nth(1).fill("40");

  const budgetState = await page.evaluate(() => ({
    remaining: document.querySelector("#remaining-budget")?.textContent || "",
    usage: document.querySelector("#usage-state")?.textContent || "",
    values: [...document.querySelectorAll('input[type="range"][data-id]')].map((input) => Number(input.value)),
    maxValues: [...document.querySelectorAll('input[type="range"][data-id]')].map((input) => Number(input.max)),
    meterWidth: document.querySelector("#budget-meter-fill")?.style.width || "",
  }));
  check(budgetState.remaining.includes("0"), "Remaining budget fell below or failed to reach zero.", budgetState);
  check(budgetState.values[0] === 60 && budgetState.values[1] === 40, "Second bid was not capped by remaining budget.", budgetState);
  check(budgetState.values.reduce((sum, value) => sum + value, 0) === 100, "Draft total is not exactly capped at 100.", budgetState);
  check(budgetState.maxValues[2] === 0, "Unused candidate slider was not capped at zero.", budgetState);
  report.checks.push("client budget cap", "dynamic slider limits", "budget meter");

  const disabledPlus = page.locator('[data-step="10"]').nth(2);
  check(!(await disabledPlus.isEnabled()), "Add button stayed enabled with no remaining budget.");
  const beforeDisabledClick = await ranges.nth(1).evaluate((input) => input.value);
  await disabledPlus.click({ force: true });
  check(await ranges.nth(1).evaluate((input) => input.value) === beforeDisabledClick, "Disabled add action changed the bid.");

  const submit = page.locator("#submit-bids");
  await Promise.allSettled([submit.click(), submit.click()]);
  await page.waitForFunction(() => document.querySelector("#usage-state")?.textContent.includes("已提交"));
  const hostState = await request("/api/state?role=host");
  check(hostState.body.submittedCount === 1, "Rapid submit created an invalid submission state.", hostState.body);
  report.checks.push("submit lock", "single participant submission");

  const participant = await page.evaluate(() => {
    const data = window.LIVE_TEACHING_DATA;
    const key = `live-teaching-player-${data.sessionCode || data.activity}`;
    return JSON.parse(sessionStorage.getItem(key));
  });
  const invalidCases = [
    { name: "negative bid", bids: { sample_high_freq: -5 } },
    { name: "unknown candidate", bids: { unknown_candidate: 5 } },
    { name: "invalid step", bids: { sample_high_freq: 3 } },
    { name: "unallocated budget", bids: { sample_high_freq: 95 } },
    { name: "over budget", bids: { sample_high_freq: 100, sample_low_freq_high_risk: 5 } },
  ];
  for (const testCase of invalidCases) {
    const result = await post("/api/bid", {
      participantId: participant.id,
      participantToken: participant.token,
      bids: testCase.bids,
    });
    check(result.response.status === 400, `${testCase.name} was not rejected.`, result.body);
    report.checks.push(`server rejects ${testCase.name}`);
  }

  const locked = await post("/api/control", { action: "lock" });
  check(locked.response.ok, "Unable to lock auction.", locked.body);
  await page.waitForFunction(() => document.querySelector('input[type="range"]')?.disabled === true, null, { timeout: 8000 });
  check(!(await ranges.nth(0).isEnabled()), "Slider stayed enabled after lock.");
  check(await page.locator("#submit-bids").count() === 0, "Submit bar stayed visible after lock.");
  report.checks.push("locked controls");

  const revealed = await post("/api/control", { action: "reveal" });
  check(revealed.response.ok, "Unable to reveal auction.", revealed.body);
  await page.waitForSelector(".player-results");
  check(await page.locator(".player-results li").count() > 0, "Participant did not receive revealed aggregate results.");
  report.checks.push("participant reveal results");

  const hostPage = await context.newPage();
  await hostPage.goto(new URL("?role=host&app=golden-sample-auction", baseUrl).href, { waitUntil: "domcontentloaded" });
  await hostPage.waitForSelector("#export-results");
  const downloadPromise = hostPage.waitForEvent("download");
  await hostPage.locator("#export-results").click();
  const download = await downloadPromise;
  check(download.suggestedFilename().endsWith(".csv"), "Host export did not produce a CSV file.");
  const hostLayout = await hostPage.evaluate(() => ({
    viewportWidth: window.innerWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  check(hostLayout.bodyWidth <= hostLayout.viewportWidth + 1, "Host desktop page has horizontal overflow.", hostLayout);
  const hostDesktopScreenshot = path.join(outputDir, "host-desktop.png");
  await hostPage.screenshot({ path: hostDesktopScreenshot, fullPage: true });
  report.screenshots.push(hostDesktopScreenshot);

  const hostMobile = await context.newPage();
  await hostMobile.setViewportSize({ width: 390, height: 844 });
  await hostMobile.goto(new URL("?role=host&app=golden-sample-auction", baseUrl).href, { waitUntil: "domcontentloaded" });
  await hostMobile.waitForSelector(".host-actions");
  const hostMobileLayout = await hostMobile.evaluate(() => ({
    viewportWidth: window.innerWidth,
    bodyWidth: document.body.scrollWidth,
  }));
  check(
    hostMobileLayout.bodyWidth <= hostMobileLayout.viewportWidth + 1,
    "Host mobile page has horizontal overflow.",
    hostMobileLayout,
  );
  const hostMobileScreenshot = path.join(outputDir, "host-mobile.png");
  await hostMobile.screenshot({ path: hostMobileScreenshot, fullPage: true });
  report.screenshots.push(hostMobileScreenshot);
  report.checks.push("host CSV export", "host desktop layout", "host mobile layout");

  const desktopScreenshot = path.join(outputDir, "student-desktop.png");
  await page.screenshot({ path: desktopScreenshot, fullPage: true });
  report.screenshots.push(desktopScreenshot);

  const mobile = await context.newPage();
  await mobile.setViewportSize({ width: 390, height: 844 });
  await mobile.goto(new URL("?role=player&fresh=mobile-test", baseUrl).href, { waitUntil: "networkidle" });
  const mobileJoin = await post("/api/join", { groupId: "group_2", nickname: "手机布局测试" });
  check(mobileJoin.response.ok, "Unable to create mobile test participant.", mobileJoin.body);
  await mobile.evaluate((participant) => {
    const data = window.LIVE_TEACHING_DATA;
    const key = `live-teaching-player-${data.sessionCode || data.activity}`;
    sessionStorage.setItem(key, JSON.stringify(participant));
  }, mobileJoin.body.participant);
  await mobile.goto(new URL("?role=player&app=golden-sample-auction&fresh=mobile-test", baseUrl).href, {
    waitUntil: "networkidle",
  });
  await mobile.waitForSelector(".bid-list");
  const mobileLayout = await mobile.evaluate(() => ({
    viewportWidth: window.innerWidth,
    bodyWidth: document.body.scrollWidth,
    overlap: [...document.querySelectorAll("button, input, a")].some((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && (rect.left < -1 || rect.right > window.innerWidth + 1);
    }),
  }));
  check(mobileLayout.bodyWidth <= mobileLayout.viewportWidth + 1, "Mobile page has horizontal overflow.", mobileLayout);
  check(!mobileLayout.overlap, "Mobile controls extend outside the viewport.", mobileLayout);
  const mobileScreenshot = path.join(outputDir, "student-mobile.png");
  await mobile.screenshot({ path: mobileScreenshot, fullPage: true });
  report.screenshots.push(mobileScreenshot);
  report.checks.push("mobile viewport");

  const burstReset = await post("/api/control", { action: "reset" });
  check(burstReset.response.ok, "Unable to reset before burst test.", burstReset.body);
  const burstOpen = await post("/api/control", { action: "open" });
  check(burstOpen.response.ok, "Unable to open burst test session.", burstOpen.body);
  const burstStartedAt = Date.now();
  const joins = await Promise.all(Array.from({ length: 30 }, (_, index) => (
    post("/api/join", {
      groupId: `group_${index % 6 + 1}`,
      nickname: `并发测试 ${index + 1}`,
    })
  )));
  check(joins.every((result) => result.response.ok), "At least one burst participant failed to join.");
  const submissions = await Promise.all(joins.map((result) => (
    post("/api/bid", {
      participantId: result.body.participant.id,
      participantToken: result.body.participant.token,
      bids: { sample_high_freq: 100 },
    })
  )));
  check(submissions.every((result) => result.response.ok), "At least one burst participant failed to submit.");
  const burstState = await request("/api/state?role=host");
  check(
    burstState.body.participantCount === 30 && burstState.body.submittedCount === 30,
    "Burst state counts are incorrect.",
    burstState.body,
  );
  const scopedState = await request(
    `/api/state?role=player&participantId=${joins[0].body.participant.id}`,
    { headers: { "X-Participant-Token": joins[0].body.participant.token } },
  );
  check(
    scopedState.body.participants?.length === 1
      && scopedState.body.participant?.id === joins[0].body.participant.id,
    "Participant state exposed another participant record.",
    scopedState.body,
  );
  const rejectedImpersonation = await request(
    `/api/state?role=player&participantId=${joins[0].body.participant.id}`,
    { headers: { "X-Participant-Token": "invalid-token" } },
  );
  check(
    rejectedImpersonation.body.participant === null && rejectedImpersonation.body.participants?.length === 0,
    "Invalid participant token exposed a participant record.",
    rejectedImpersonation.body,
  );
  report.burstDurationMs = Date.now() - burstStartedAt;
  report.checks.push("30 participant join and submit burst", "participant payload isolation", "participant token rejection");

  check(consoleErrors.length === 0, "Browser console errors detected.", { consoleErrors });
  report.status = "pass";
} catch (error) {
  report.errors.push({
    message: error.message,
    details: error.details || null,
    stack: error.stack,
  });
} finally {
  if (browser) await browser.close();
  try {
    await post("/api/control", { action: "reset" });
  } catch {
    // The service may already be stopped after a failed connectivity check.
  }
}

console.log(JSON.stringify(report, null, 2));
process.exit(report.status === "pass" ? 0 : 1);
