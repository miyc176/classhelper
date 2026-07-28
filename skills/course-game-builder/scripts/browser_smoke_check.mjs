#!/usr/bin/env node
import { createRequire } from "module";
import { pathToFileURL } from "url";
import fs from "fs";
import path from "path";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

function findHtml(inputPath) {
  const resolved = path.resolve(inputPath);
  const stat = fs.statSync(resolved);
  if (stat.isFile()) return resolved;
  const index = path.join(resolved, "index.html");
  if (fs.existsSync(index)) return index;
  const html = fs.readdirSync(resolved).find((file) => file.endsWith(".html"));
  if (!html) throw new Error(`No HTML file found in ${resolved}`);
  return path.join(resolved, html);
}

function parseArgs(argv) {
  const args = { game: null, out: null };
  for (let index = 2; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--out") {
      args.out = argv[index + 1];
      index += 1;
    } else if (!args.game) {
      args.game = value;
    }
  }
  if (!args.game) throw new Error("Usage: node browser_smoke_check.mjs <game-dir-or-html> [--out screenshots-dir]");
  return args;
}

const args = parseArgs(process.argv);
const htmlPath = findHtml(args.game);
const outputDir = path.resolve(args.out || path.join(path.dirname(htmlPath), "smoke-screenshots"));
fs.mkdirSync(outputDir, { recursive: true });

const viewports = [
  { name: "desktop", width: 1280, height: 800 },
  { name: "mobile", width: 390, height: 844 }
];

async function launchBrowser() {
  const executableCandidates = [
    process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE,
    "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
    "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  ].filter(Boolean).filter((candidate) => fs.existsSync(candidate));
  const optionCandidates = [
    ...executableCandidates.map((executablePath) => ({ executablePath })),
    { channel: "msedge" },
    { channel: "chrome" },
    {}
  ];
  let lastError = null;
  for (const options of optionCandidates) {
    try {
      return await chromium.launch(options);
    } catch (error) {
      lastError = error;
    }
  }
  throw lastError;
}

const browser = await launchBrowser();
const results = [];
const errors = [];

for (const viewport of viewports) {
  const page = await browser.newPage({ viewport });
  const consoleErrors = [];
  const pageErrors = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => pageErrors.push(error.message));

  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });

  const state = await page.evaluate(() => {
    const visibleButtons = [...document.querySelectorAll("button")].filter((button) => {
      const rect = button.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0;
    });
    const coverage = Array.isArray(window.GAME_KNOWLEDGE_COVERAGE)
      ? window.GAME_KNOWLEDGE_COVERAGE
      : null;
    const body = document.body.getBoundingClientRect();
    const overflowing = [...document.querySelectorAll("body *")].some((element) => {
      const rect = element.getBoundingClientRect();
      return rect.width > 0 && rect.height > 0 && (rect.right < -4 || rect.left > window.innerWidth + 4);
    });
    const textFrames = [...document.querySelectorAll(".answer, .card-front, .piece-label, .enemy-craft span, .pipe-label, .gate-label, .cell")].filter((element) => {
      const rect = element.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return false;
      return element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1;
    }).map((element) => ({
      tag: element.tagName.toLowerCase(),
      className: element.className,
      text: element.textContent.trim().slice(0, 80),
      clientWidth: element.clientWidth,
      scrollWidth: element.scrollWidth,
      clientHeight: element.clientHeight,
      scrollHeight: element.scrollHeight
    }));
    return {
      title: document.title,
      textLength: document.body.innerText.trim().length,
      visibleButtonCount: visibleButtons.length,
      hasMain: Boolean(document.querySelector("main")),
      coverage,
      bodyWidth: body.width,
      overflowing,
      textFrames
    };
  });

  const screenshot = path.join(outputDir, `${viewport.name}.png`);
  await page.screenshot({ path: screenshot, fullPage: true });
  await page.close();

  if (consoleErrors.length) errors.push(`${viewport.name}: console errors: ${consoleErrors.join("; ")}`);
  if (pageErrors.length) errors.push(`${viewport.name}: page errors: ${pageErrors.join("; ")}`);
  if (!state.title) errors.push(`${viewport.name}: missing document title`);
  if (state.textLength < 20) errors.push(`${viewport.name}: page appears blank or nearly blank`);
  if (state.visibleButtonCount === 0) errors.push(`${viewport.name}: no visible button controls`);
  if (!state.hasMain) errors.push(`${viewport.name}: missing main landmark`);
  if (!state.coverage || state.coverage.length === 0) errors.push(`${viewport.name}: missing GAME_KNOWLEDGE_COVERAGE array`);
  if (state.overflowing) errors.push(`${viewport.name}: detected horizontally overflowing element`);
  if (state.textFrames.length) errors.push(`${viewport.name}: text spills inside ${state.textFrames.length} control frame(s)`);

  results.push({ viewport, screenshot, state, consoleErrors, pageErrors });
}

await browser.close();

const report = {
  html: htmlPath,
  status: errors.length ? "fail" : "pass",
  outputDir,
  results,
  errors
};

console.log(JSON.stringify(report, null, 2));
process.exit(errors.length ? 1 : 0);
