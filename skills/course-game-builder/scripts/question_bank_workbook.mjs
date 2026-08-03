#!/usr/bin/env node
import fs from "node:fs/promises";
import path from "node:path";
import crypto from "node:crypto";
import { createRequire } from "node:module";

const requireFromRunner = createRequire(path.join(process.cwd(), "artifact-runner.cjs"));
let artifactTool;
try {
  artifactTool = requireFromRunner("@oai/artifact-tool");
} catch (error) {
  throw new Error(`@oai/artifact-tool is unavailable from ${process.cwd()}/node_modules. Create the required workspace junction first. ${error.message}`);
}
const { FileBlob, SpreadsheetFile, Workbook } = artifactTool;

const TYPE_SHEETS = {
  single_choice: "单选题",
  multiple_choice: "多选题",
  true_false: "判断题",
  matching: "配对题",
  classification: "分类题",
  ordering: "排序题",
};
const SHEET_TYPES = Object.fromEntries(Object.entries(TYPE_SHEETS).map(([key, value]) => [value, key]));
const PREFIXES = {
  single_choice: "q_single",
  multiple_choice: "q_multi",
  true_false: "q_tf",
  matching: "q_match",
  classification: "q_class",
  ordering: "q_order",
};
const HEADERS = [
  "题目ID", "主题", "重点等级", "难度", "题干",
  "选项A", "选项B", "选项C", "选项D", "选项E", "选项F",
  "正确答案", "解析", "知识点ID", "依据原文", "选项依据", "选项原文依据", "来源定位",
  "适配游戏", "审核状态", "修改意见",
];

function parseArgs(argv) {
  const args = { command: argv[2] };
  for (let index = 3; index < argv.length; index += 1) {
    const key = argv[index];
    if (!key.startsWith("--")) continue;
    args[key.slice(2)] = argv[index + 1];
    index += 1;
  }
  return args;
}

function required(args, names) {
  for (const name of names) {
    if (!args[name]) throw new Error(`Missing --${name}`);
  }
}

function asList(value) {
  return Array.isArray(value) ? value.map(String) : [];
}

function refText(refs) {
  return (refs || []).map((ref) => `${ref.source_id}@${ref.locator}`).join("||");
}

function parseRefs(value) {
  return String(value || "").split("||").map((item) => item.trim()).filter(Boolean).map((item) => {
    const [sourceId, ...locator] = item.split("@");
    return { source_id: sourceId, locator: locator.join("@") };
  });
}

async function recordPerformance(filePath, stageName, durationSeconds, metrics) {
  if (!filePath) return;
  const resolved = path.resolve(filePath);
  const report = JSON.parse(await fs.readFile(resolved, "utf8"));
  if (report.completed_at) throw new Error("Performance run is already complete; initialize a new run first.");
  report.stages ||= {};
  const stage = report.stages[stageName] || { status: "pending", invocations: [] };
  const externallyStarted = stage.status === "running" && stage.active_started_timestamp;
  const measuredDuration = externallyStarted
    ? (Date.now() / 1000) - Number(stage.active_started_timestamp)
    : durationSeconds;
  stage.invocations.push({
    started_at: externallyStarted ? stage.active_started_at : null,
    completed_at: new Date().toISOString(),
    duration_seconds: Math.max(0, Number(measuredDuration.toFixed(3))),
    metrics,
  });
  stage.status = "completed";
  delete stage.active_started_at;
  delete stage.active_started_timestamp;
  report.stages[stageName] = stage;
  const invocations = Object.values(report.stages).flatMap((item) => item.invocations || []);
  const cacheHits = invocations.reduce((sum, item) => sum + Number(item.metrics?.cache_hits || 0), 0);
  const cacheMisses = invocations.reduce((sum, item) => sum + Number(item.metrics?.cache_misses || 0), 0);
  report.summary = {
    ...(report.summary || {}),
    elapsed_seconds: Number(((Date.now() / 1000) - Number(report.started_timestamp || Date.now() / 1000)).toFixed(3)),
    stage_seconds: Object.fromEntries(Object.entries(report.stages).map(([name, item]) => [
      name, Number((item.invocations || []).reduce((sum, invocation) => sum + Number(invocation.duration_seconds || 0), 0).toFixed(3)),
    ])),
    cache_hits: cacheHits,
    cache_misses: cacheMisses,
    cache_hit_rate: cacheHits + cacheMisses ? Number((cacheHits / (cacheHits + cacheMisses)).toFixed(4)) : null,
    stages_completed: Object.values(report.stages).filter((item) => item.status === "completed").length,
    active_stages: Object.entries(report.stages).filter(([, item]) => item.status === "running").map(([name]) => name),
    unrecorded_stages: Object.entries(report.stages).filter(([, item]) => item.status === "pending").map(([name]) => name),
  };
  const temporary = `${resolved}.${process.pid}.tmp`;
  await fs.writeFile(temporary, `${JSON.stringify(report, null, 2)}\n`);
  await fs.rename(temporary, resolved);
}

async function fileHash(filePath) {
  return crypto.createHash("sha256").update(await fs.readFile(filePath)).digest("hex");
}

function styleTitle(sheet, title, subtitle) {
  sheet.mergeCells("A1:U1");
  sheet.getRange("A1").values = [[title]];
  sheet.getRange("A1:U1").format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    verticalAlignment: "center",
  };
  sheet.getRange("A1:U1").format.rowHeight = 30;
  sheet.mergeCells("A2:U2");
  sheet.getRange("A2").values = [[subtitle]];
  sheet.getRange("A2:U2").format = {
    fill: "#EAF2F8",
    font: { color: "#334E68", italic: true },
    wrapText: true,
  };
  sheet.getRange("A2:U2").format.rowHeight = 34;
}

function formatQuestionSheet(sheet, rowCount) {
  const lastRow = Math.max(4, rowCount + 3);
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(3);
  sheet.freezePanes.freezeColumns(5);
  sheet.getRange("A3:U3").format = {
    fill: "#147D78",
    font: { bold: true, color: "#FFFFFF" },
    horizontalAlignment: "center",
    verticalAlignment: "center",
    wrapText: true,
    borders: { preset: "outside", style: "thin", color: "#0E5D59" },
  };
  sheet.getRange(`A4:U${lastRow}`).format = {
    verticalAlignment: "top",
    wrapText: true,
    borders: { preset: "inside", style: "thin", color: "#D9E2EC" },
  };
  sheet.getRange(`A4:U${lastRow}`).format.rowHeight = 58;
  const widths = {
    A: 15, B: 16, C: 10, D: 9, E: 36,
    F: 22, G: 22, H: 22, I: 22, J: 22, K: 22,
    L: 24, M: 42, N: 19, O: 46, P: 30, Q: 46, R: 28, S: 22, T: 11, U: 30,
  };
  for (const [column, width] of Object.entries(widths)) {
    sheet.getRange(`${column}:${column}`).format.columnWidth = width;
  }
  sheet.getRange(`C4:C503`).dataValidation = { rule: { type: "list", values: ["重点", "次重点", "拓展"] } };
  sheet.getRange(`D4:D503`).dataValidation = { rule: { type: "list", values: ["基础", "进阶", "综合"] } };
  sheet.getRange(`T4:T503`).dataValidation = { rule: { type: "list", values: ["待审核", "通过", "需修改", "停用"] } };
  sheet.getRange(`T4:T503`).conditionalFormats.add("containsText", { text: "通过", format: { fill: "#D7F2E3", font: { color: "#176B45", bold: true } } });
  sheet.getRange(`T4:T503`).conditionalFormats.add("containsText", { text: "需修改", format: { fill: "#FDE4E1", font: { color: "#A33A2B", bold: true } } });
}

function questionRow(question) {
  const options = asList(question.options).slice(0, 6);
  while (options.length < 6) options.push("");
  return [
    question.id || "",
    question.topic || "",
    question.importance || "",
    question.difficulty || "",
    question.stem || "",
    ...options,
    asList(question.answers).join("||"),
    question.explanation || "",
    asList(question.knowledge_ids).join("||"),
    question.source_basis || "",
    asList(question.option_sources).join("||"),
    asList(question.option_basis).join("||"),
    refText(question.source_refs),
    asList(question.game_modes).join("||"),
    question.review_status || "待审核",
    question.review_notes || "",
  ];
}

function styleSimpleSheet(sheet, range, headerRange) {
  sheet.showGridLines = false;
  sheet.freezePanes.freezeRows(1);
  sheet.getRange(headerRange).format = {
    fill: "#17324D",
    font: { bold: true, color: "#FFFFFF" },
    wrapText: true,
  };
  sheet.getRange(range).format.wrapText = true;
  sheet.getRange(range).format.verticalAlignment = "top";
  sheet.getUsedRange().format.autofitRows();
  sheet.getUsedRange().format.rowHeight = 30;
}

async function exportWorkbook(args) {
  const startedAt = performance.now();
  required(args, ["knowledge", "questions", "workflow-state", "out"]);
  const knowledgePath = path.resolve(args.knowledge);
  const questionsPath = path.resolve(args.questions);
  const workflowPath = path.resolve(args["workflow-state"]);
  const outPath = path.resolve(args.out);
  const previewDir = args["preview-dir"] ? path.resolve(args["preview-dir"]) : null;
  const signature = {
    knowledge: await fileHash(knowledgePath), questions: await fileHash(questionsPath),
    workflow: await fileHash(workflowPath), format: "question-workbook-v2",
  };
  const cachePath = `${outPath}.build.json`;
  const previewNames = ["使用说明", "课程重点", "覆盖检查", ...Object.values(TYPE_SHEETS)];
  let cached = null;
  try { cached = JSON.parse(await fs.readFile(cachePath, "utf8")); } catch {}
  const previewsReady = !previewDir || (await Promise.all(previewNames.map(async (name) => {
    try { await fs.access(path.join(previewDir, `${name}.png`)); return true; } catch { return false; }
  }))).every(Boolean);
  try {
    await fs.access(outPath);
    if (JSON.stringify(cached) === JSON.stringify(signature) && previewsReady) {
      await recordPerformance(args["performance-file"], "excel_generation", (performance.now() - startedAt) / 1000, { cache_hits: 1, cache_misses: 0, questions: 0 });
      console.log(JSON.stringify({ status: "pass", out: outPath, cache_hit: true }, null, 2));
      return;
    }
  } catch {}
  const knowledge = JSON.parse(await fs.readFile(knowledgePath, "utf8"));
  const bank = JSON.parse(await fs.readFile(questionsPath, "utf8"));
  const workflow = JSON.parse(await fs.readFile(workflowPath, "utf8"));
  if (workflow.focus?.status !== "confirmed") throw new Error("Course focus must be confirmed before workbook export.");
  const workbook = Workbook.create();
  const questions = bank.questions || [];
  const pointMap = new Map((knowledge.knowledge_points || []).map((point) => [String(point.id), point]));

  const instructions = workbook.worksheets.add("使用说明");
  instructions.getRange("A1:B10").values = [
    ["课程题库审核说明", "内容"],
    ["审核顺序", "先确认课程重点，再逐题检查题干、答案、解析和来源。"],
    ["通过", "题目可以进入游戏；只有标记为“通过”的题目会被读取。"],
    ["需修改", "在“修改意见”填写要求，或直接修改本行内容后改为“通过”。"],
    ["新增题目", "可在对应题型工作表末尾添加；题目ID留空时导入脚本自动生成。"],
    ["多值分隔", "正确答案、知识点ID、选项依据、选项原文依据、适配游戏使用 || 分隔。"],
    ["配对/分类", "选项使用 左项=>右项 或 项目=>类别。"],
    ["来源约束", "依据原文必须与绑定知识点的 statement 或 evidence 完全一致。"],
    ["选项约束", "选项依据和选项原文依据须与非空选项逐项对齐；来源只允许知识点ID或 common_error:知识点ID。"],
    ["下一步", "全部可用题目设为“通过”后重新导入并校验，再选择游戏。"],
  ];
  styleSimpleSheet(instructions, "A1:B10", "A1:B1");
  instructions.getRange("A:A").format.columnWidth = 18;
  instructions.getRange("B:B").format.columnWidth = 72;

  const focus = workbook.worksheets.add("课程重点");
  focus.getRange("A1:E1").values = [["知识点ID", "主题", "重点内容", "重点依据", "确认状态"]];
  const focusIds = new Set(workflow.focus?.knowledge_ids || []);
  const focusRows = (knowledge.knowledge_points || []).filter((point) => focusIds.has(String(point.id))).map((point) => [
    point.id, point.topic, point.statement, point.importance_basis, "用户已确认",
  ]);
  if (focusRows.length) focus.getRangeByIndexes(1, 0, focusRows.length, 5).values = focusRows;
  styleSimpleSheet(focus, `A1:E${Math.max(2, focusRows.length + 1)}`, "A1:E1");
  focus.getRange(`A2:E${Math.max(2, focusRows.length + 1)}`).format.rowHeight = 46;
  for (const [column, width] of Object.entries({ A: 14, B: 18, C: 54, D: 38, E: 22 })) focus.getRange(`${column}:${column}`).format.columnWidth = width;

  const coverage = workbook.worksheets.add("覆盖检查");
  coverage.getRange("A1:E1").values = [["知识点ID", "主题", "重点等级", "知识点", "题目数量"]];
  const counts = new Map();
  for (const question of questions) for (const id of asList(question.knowledge_ids)) counts.set(id, (counts.get(id) || 0) + 1);
  const coverageRows = (knowledge.knowledge_points || []).map((point) => [point.id, point.topic, point.importance, point.statement, counts.get(String(point.id)) || 0]);
  if (coverageRows.length) coverage.getRangeByIndexes(1, 0, coverageRows.length, 5).values = coverageRows;
  styleSimpleSheet(coverage, `A1:E${Math.max(2, coverageRows.length + 1)}`, "A1:E1");
  for (const [column, width] of Object.entries({ A: 14, B: 18, C: 10, D: 60, E: 12 })) coverage.getRange(`${column}:${column}`).format.columnWidth = width;
  coverage.getRange(`E2:E${Math.max(2, coverageRows.length + 1)}`).conditionalFormats.add("cellIs", { operator: "equal", formula: 0, format: { fill: "#FDE4E1", font: { color: "#A33A2B", bold: true } } });

  for (const [type, sheetName] of Object.entries(TYPE_SHEETS)) {
    const sheet = workbook.worksheets.add(sheetName);
    const rows = questions.filter((question) => question.type === type).map(questionRow);
    styleTitle(sheet, `${bank.course_title || knowledge.course_title || "课程"}：${sheetName}`, "请逐题审核；只读取审核状态为“通过”的题目。可直接修改或在末尾新增。" );
    sheet.getRange("A3:U3").values = [HEADERS];
    if (rows.length) sheet.getRangeByIndexes(3, 0, rows.length, HEADERS.length).values = rows;
    formatQuestionSheet(sheet, rows.length);
  }

  const metadata = workbook.worksheets.add("_元数据");
  metadata.getRange("A1:B6").values = [
    ["键", "值"],
    ["schema_version", bank.schema_version || "1.0"],
    ["course_title", bank.course_title || knowledge.course_title || "课程"],
    ["knowledge_sha256", bank.knowledge_sha256 || ""],
    ["workflow_focus_ids", [...focusIds].join("||")],
    ["format", "course-game-builder-question-bank"],
  ];
  styleSimpleSheet(metadata, "A1:B6", "A1:B1");
  metadata.getRange("A:A").format.columnWidth = 24;
  metadata.getRange("B:B").format.columnWidth = 72;

  await fs.mkdir(path.dirname(outPath), { recursive: true });
  const output = await SpreadsheetFile.exportXlsx(workbook);
  await output.save(outPath);

  const previews = [];
  if (previewDir) {
    await fs.mkdir(previewDir, { recursive: true });
    for (const name of previewNames) {
      const preview = await workbook.render({ sheetName: name, autoCrop: "all", scale: 1, format: "png" });
      const previewPath = path.join(previewDir, `${name}.png`);
      await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
      previews.push(previewPath);
    }
  }
  await fs.writeFile(cachePath, JSON.stringify(signature, null, 2));
  await recordPerformance(args["performance-file"], "excel_generation", (performance.now() - startedAt) / 1000, { cache_hits: 0, cache_misses: 1, questions: questions.length });
  const inspection = await workbook.inspect({ kind: "table", sheetId: "覆盖检查", range: `A1:E${Math.min(12, coverageRows.length + 1)}`, include: "values,formulas", tableMaxRows: 12, tableMaxCols: 5 });
  console.log(JSON.stringify({ status: "pass", out: outPath, questions: questions.length, previews, cache_hit: false, inspection: inspection.ndjson }, null, 2));
}

function cell(row, headerMap, name) {
  const index = headerMap.get(name);
  return index === undefined ? "" : row[index];
}

function splitCell(value) {
  return String(value || "").split("||").map((item) => item.trim()).filter(Boolean);
}

async function importWorkbook(args) {
  required(args, ["input", "out"]);
  const inputPath = path.resolve(args.input);
  const input = await FileBlob.load(inputPath);
  const workbook = await SpreadsheetFile.importXlsx(input);
  const metadataValues = workbook.worksheets.getItem("_元数据").getUsedRange().values;
  const metadata = Object.fromEntries(metadataValues.slice(1).map((row) => [String(row[0] || ""), String(row[1] || "")]));
  if (metadata.format !== "course-game-builder-question-bank") throw new Error("Workbook format marker is missing or invalid.");
  const questions = [];
  for (const [sheetName, type] of Object.entries(SHEET_TYPES)) {
    const sheet = workbook.worksheets.getItem(sheetName);
    const values = sheet.getUsedRange().values;
    const headers = values[2] || [];
    const headerMap = new Map(headers.map((value, index) => [String(value || ""), index]));
    let sequence = 1;
    for (const row of values.slice(3)) {
      const stem = String(cell(row, headerMap, "题干") || "").trim();
      if (!stem) continue;
      const options = ["选项A", "选项B", "选项C", "选项D", "选项E", "选项F"].map((name) => String(cell(row, headerMap, name) || "").trim()).filter(Boolean);
      const id = String(cell(row, headerMap, "题目ID") || "").trim() || `${PREFIXES[type]}_${String(sequence).padStart(3, "0")}`;
      sequence += 1;
      questions.push({
        id,
        type,
        topic: String(cell(row, headerMap, "主题") || "").trim(),
        importance: String(cell(row, headerMap, "重点等级") || "").trim(),
        difficulty: String(cell(row, headerMap, "难度") || "").trim(),
        stem,
        options,
        answers: splitCell(cell(row, headerMap, "正确答案")),
        explanation: String(cell(row, headerMap, "解析") || "").trim(),
        knowledge_ids: splitCell(cell(row, headerMap, "知识点ID")),
        source_basis: String(cell(row, headerMap, "依据原文") || "").trim(),
        option_sources: splitCell(cell(row, headerMap, "选项依据")),
        option_basis: splitCell(cell(row, headerMap, "选项原文依据")),
        source_refs: parseRefs(cell(row, headerMap, "来源定位")),
        game_modes: splitCell(cell(row, headerMap, "适配游戏")),
        review_status: String(cell(row, headerMap, "审核状态") || "待审核").trim(),
        review_notes: String(cell(row, headerMap, "修改意见") || "").trim(),
      });
    }
  }
  const bank = {
    schema_version: metadata.schema_version || "1.0",
    course_title: metadata.course_title || "课程",
    knowledge_sha256: metadata.knowledge_sha256 || "",
    questions,
  };
  const outPath = path.resolve(args.out);
  await fs.mkdir(path.dirname(outPath), { recursive: true });
  await fs.writeFile(outPath, `${JSON.stringify(bank, null, 2)}\n`, "utf8");
  console.log(JSON.stringify({ status: "pass", out: outPath, questions: questions.length }, null, 2));
}

const args = parseArgs(process.argv);
if (args.command === "export") await exportWorkbook(args);
else if (args.command === "import") await importWorkbook(args);
else throw new Error("Usage: question_bank_workbook.mjs export|import [options]");
