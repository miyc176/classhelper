---
name: course-game-builder
description: Extract complete, source-traceable course knowledge from teaching materials and build polished standalone HTML teaching games. Use when Codex is asked to process PPT/PPTX, PDF, DOCX, images, screenshots, scans, handouts, or courseware; recover knowledge from text and visual content; create classic arcade learning games, quizzes, simulations, matching games, sorting games, puzzles, or review activities; and validate the generated game quality before delivery.
---

# Course Game Builder

## Operating Standard

Extract knowledge before designing. Treat every slide, page, image, chart, diagram, annotation, speaker note, table, and embedded media as possible course content. Never claim perfect coverage when an input cannot be opened, rendered, OCRed, or visually inspected; record the limitation and ask for the missing artifact when it affects correctness.

## Agent Contract

Use this skill as a gated production workflow, not as a prompt-writing aid. The mandatory order is: material confirmation, complete extraction, focus confirmation, question review, game selection, generation, validation. Never skip a user checkpoint because a game could be generated immediately.

Default behavior:

- If the user provides course materials, initialize `workflow-state.json`, inventory all files, and ask whether the material list is complete before final extraction.
- If the user provides an existing `knowledge.json`, validate it, generate the Markdown report and question workbook, and continue from the corresponding checkpoint. Existing JSON does not waive review.
- Treat supplied course materials as a closed world. Do not introduce facts, examples, terminology, constraints, answers, or distractors from model memory or the internet.
- Do not generate any game until the user has confirmed course focus, approved the question bank, and selected game modes.
- If the user asks for classic, arcade, creative, polished, or game-like outputs, prefer the fixed standalone polished templates and replace only generated data files unless a template bug is verified.
- If the user asks for a specific classic game, generate one standalone HTML game for that mechanic.
- If the user asks for multiple game types, generate separate standalone folders. If they explicitly ask for one HTML collection or launcher, create a fresh launcher that links to the standalone games; do not use an old shared arcade shell.
- Keep outputs self-contained and offline-friendly; do not add CDN or internet dependencies without approval.
- Generate standalone games that open directly from disk. Do not introduce accounts, rooms, servers, device synchronization, or network score reporting unless the user explicitly requests a separate non-default project.
- Do not deliver on appearance alone. Run static validation and a browser smoke check for every interactive HTML game where tooling is available.
- After changing any classic template, generator, or quality rule, run `scripts/validate_classic_template_set.py` with a representative `knowledge.json`.

Required output contract:

- `workflow-state.json` records all user confirmations and the next allowed action.
- `knowledge.json` is source-traceable and matches the exact `material-extraction.json` hash and unit inventory.
- `课件知识点提取.md` contains the full extraction, source coverage audit, proposed/confirmed focus, evidence, teaching value, common errors, and blocked content.
- `<课程名称>课程题目.xlsx` contains fixed-format sheets grouped by question type. `approved-question-bank.json` is re-imported from this workbook before game generation.
- `index.html` must open directly from disk or from a simple local server.
- `window.GAME_KNOWLEDGE_COVERAGE` must list the knowledge ids used in answer logic.
- Every core interactive object must carry course knowledge: moles, cards, cells, gates, enemies, puzzle pieces, labels, or targets.
- Feedback must explain the answer using source-derived teaching value, evidence, or the knowledge statement.
- The first viewport must be playable, not a landing page or instructions-only page.
- Question text and options must be clear, answerable classroom items. Every question and every option must carry exact course-source basis metadata; validation rejects ungrounded distractors.

Use the relevant file skills when available:

- PPT/PPTX or slide decks: use the presentations skill and render slides for visual inspection.
- PDF or scans: use the pdf skill and render pages for visual inspection/OCR.
- DOCX or handouts: use the documents skill.
- XLSX/CSV grade or item banks: use the spreadsheets skill.
- New browser-based experiences or deployable sites: use the sites skill when the project contains `.openai/hosting.json` or the user asks to deploy.

## Workflow

1. Initialize `workflow-state.json`. Inventory all source files with stable ids and hashes using `scripts/inventory_materials.py`.
2. **Stop and ask:** “这些是否是本课程全部材料？” List files and counts. If files are missing, add them and rerun inventory. Record confirmation with `confirm-materials`.
3. Extract text, notes, tables, formulas, and visual knowledge. Render and inspect every slide/page/image. Preserve atomic conditions, exceptions, examples, relationships, common errors, and assessment cues in `knowledge.json` using `references/knowledge-schema.md`.
4. Compare final coverage keys against `material-extraction.json` with `validate_course_knowledge.py`. Every PPT/PDF page and every extracted image must be `covered` or have a concrete `no_instructional_content` note. Any blocked unit stops the workflow.
5. Generate `课件知识点提取.md`. Propose focus only from source signals such as objectives, headings, repetition, summaries, emphasis, or teacher wording.
6. **Stop and ask:** show the focus table and ask the user to confirm, add, remove, or reprioritize knowledge ids. Record the confirmed ids with `confirm-focus`; do not decide course重点 from general knowledge.
7. Draft `question-bank.json` using `references/question-engineering.md`. Cover every knowledge point; cover each confirmed focus point at least twice across two types. Every option must include aligned `option_sources` and an exact `option_basis` copied from course knowledge or an extracted common error.
8. Validate, then export `<课程名称>课程题目.xlsx` with `question_bank_workbook.mjs`. Initial rows remain `待审核`.
9. **Stop and ask:** “这些题目是否可以使用？” If no, accept edits/additions in chat or let the user edit Excel. Re-import the fixed workbook and repeat validation. If yes, apply explicit approval and require all active rows to be `通过`.
10. **Stop and ask:** let the user select one or more existing games: 打地鼠、知识翻牌、答题井字棋、飞翔判断、雷霆战机、知识拼图.
11. Generate only selected standalone games from `approved-question-bank.json`, never directly from loose knowledge text. Validate every game statically and in a browser, including one real core interaction.
12. Deliver the Markdown, Excel, approved JSON, selected games, coverage mapping, validation results, and explicit limitations.

## Command Path

Initialize and inventory:

```powershell
python scripts/course_pipeline.py init --course-title "课程名称" --out path\to\work\workflow-state.json
python scripts/inventory_materials.py path\to\course-materials --out path\to\work\extraction
python scripts/course_pipeline.py confirm-materials path\to\work\workflow-state.json --notes "用户确认材料齐全"
```

Then inspect every `text_units` and `visual_units` entry plus every rendered slide/page before writing `knowledge.json`. Set `material_extraction_sha256` to the exact SHA-256 of the manifest. Keep the manifest unit keys unchanged.

Validate extraction, generate the detailed report, and record user-confirmed focus:

```powershell
python scripts/validate_course_knowledge.py path\to\knowledge.json --inventory-manifest path\to\extraction\material-extraction.json --workflow-state path\to\workflow-state.json
python scripts/build_knowledge_report.py path\to\knowledge.json --workflow-state path\to\workflow-state.json --out path\to\课件知识点提取.md
python scripts/course_pipeline.py confirm-focus path\to\workflow-state.json --ids kp_001,kp_004 --notes "用户确认"
```

Create `question-bank.json` only after focus confirmation. Validate it, export the fixed workbook, and optionally render previews. Run the Node script from a workspace with `@oai/artifact-tool` available as described by the spreadsheets skill.

```powershell
python scripts/validate_question_bank.py path\to\knowledge.json path\to\question-bank.json --workflow-state path\to\workflow-state.json
node scripts/question_bank_workbook.mjs export --knowledge path\to\knowledge.json --questions path\to\question-bank.json --workflow-state path\to\workflow-state.json --out path\to\课程名称课程题目.xlsx --preview-dir path\to\previews
```

After user edits Excel, import and validate again:

```powershell
node scripts/question_bank_workbook.mjs import --input path\to\课程名称课程题目.xlsx --out path\to\question-bank-reviewed.json
python scripts/validate_question_bank.py path\to\knowledge.json path\to\question-bank-reviewed.json --workflow-state path\to\workflow-state.json
```

After the user explicitly approves the questions, mark pending rows approved, require the approved gate, record it, and ask for game selection:

```powershell
python scripts/approve_question_bank.py path\to\question-bank-reviewed.json --out path\to\approved-question-bank.json
python scripts/validate_question_bank.py path\to\knowledge.json path\to\approved-question-bank.json --workflow-state path\to\workflow-state.json --require-approved
python scripts/course_pipeline.py approve-questions path\to\workflow-state.json --workbook path\to\课程名称课程题目.xlsx --question-json path\to\approved-question-bank.json --knowledge-json path\to\knowledge.json --notes "用户确认可用"
python scripts/course_pipeline.py select-games path\to\workflow-state.json --games whack-a-mole,memory
```

Generate the selected game only after all gates pass:

```powershell
python scripts/build_whack_a_mole.py path\to\knowledge.json --question-bank path\to\approved-question-bank.json --workflow-state path\to\workflow-state.json --out path\to\whack-game --title "课程打地鼠" --force
python scripts/build_standalone_classic.py path\to\knowledge.json --question-bank path\to\approved-question-bank.json --workflow-state path\to\workflow-state.json --mode memory --out path\to\memory-game --title "课程知识翻牌" --force
```

Preserve the fixed standalone visual shell unless the user explicitly asks for a redesign. Course adaptation changes question data, not template code. If a collection page is explicitly requested, build it as a launcher around standalone games.

Mode selection shortcuts:

- `whack-a-mole`: use `scripts/build_whack_a_mole.py`; best for single-choice recall and fast classroom warmups.
- `memory`: use `scripts/build_standalone_classic.py --mode memory`; best for terms, definitions, labels, and examples.
- `tictactoe`: use `--mode tictactoe`; best for mixed review where a correct answer unlocks a board move.
- `flappy`: use `--mode flappy`; best for true/false, misconceptions, compatibility, and rule judgment.
- `shooter`: use `--mode shooter`; best for eliminating wrong options while preserving the correct answer.
- `puzzle`: use `--mode puzzle`; best for organizing related concepts into a small spatial structure.

Validate each generated game:

```powershell
python scripts/validate_html_game.py path\to\game --knowledge-json path\to\knowledge.json --require-all-knowledge
```

## Extraction Rules

Prefer structured extraction over prose summaries. Each knowledge point must have:

- `id`: stable identifier such as `kp_001`.
- `type`: concept, fact, procedure, formula, example, misconception, vocabulary, relationship, visual_observation, or assessment_item.
- `statement`: concise teachable statement.
- `source_refs`: file id plus slide/page/image/region details.
- `evidence`: short paraphrase of what supports it.
- `teaching_value`: why it matters for instruction.
- `prerequisites` and `related_ids` when useful.

For image-derived content, include a `visual_observation` point or attach visual evidence to the related concept. Capture labels, legend meanings, axes, arrows, process order, UI states, geometric relations, colors with semantic meaning, and before/after comparisons.

When source material is dense, create a knowledge map first, then normalize duplicates. Do not merge two points if they differ by condition, exception, example, or assessment implication.

Use a three-pass extraction to reduce omissions:

1. **Unit pass:** process every manifest unit independently and record all candidate facts, definitions, procedures, formulas, examples, exceptions, contrasts, relationships, visual observations, and stated misconceptions.
2. **Cross-unit pass:** join repeated or continued content across slides/pages while preserving every source reference and all differing conditions.
3. **Reverse audit:** for every source unit, prove where each instructional element landed; for every knowledge point, prove its source. Zero-knowledge units require a concrete non-instructional explanation.

Do not silently “improve” course wording with outside knowledge. If the material appears wrong, contradictory, or incomplete, record the uncertainty and ask the user; do not repair it from memory.

## Game-Build Rules

Before coding, map each target knowledge point to a mechanic:

- Recall or vocabulary: quick cards, timed prompts, clue reveal.
- Classification: drag/drop bins, sorting lanes, odd-one-out.
- Process or sequence: ordering, timeline repair, state-machine puzzle.
- Cause/effect or systems: small simulation with adjustable variables.
- Formulas: calculator challenge with generated cases and feedback.
- Diagrams: label placement, hotspot identification, relationship tracing.
- Misconceptions: diagnose-the-error or choose-the-fix rounds.
- Classic arcade requests: read `references/classic-game-patterns.md`; map whack-a-mole to approved single-choice items, memory cards to approved matching items, tic-tac-toe to approved single-choice items, flappy bird to approved true/false items, thunder shooter to approved single-choice items, and puzzles to approved six-option/four-answer multiple-choice items.
- Preserve the original control loop of a recognizable classic game whenever possible. Embed knowledge into targets, gates, collision outcomes, enemy rules, and spatial pieces; do not replace movement, aiming, shooting, collision, or assembly with ordinary answer buttons.
- Use only approved question-bank rows. Each prompt asks one defined thing; options are complete and parallel; every correct answer and distractor has exact course basis; feedback explains the result from that basis.

Every generated game must include:

- Clear learning objective embedded in code comments or metadata.
- `window.GAME_KNOWLEDGE_COVERAGE = [...]` listing covered knowledge ids.
- Feedback that explains the correct answer, not just right/wrong.
- Keyboard-accessible controls for core actions where practical.
- Responsive layout for desktop and mobile.
- No hidden dependency on internet access unless the user approves it.
- A reset/retry path and visible progress/state.
- For classic games, each mole/card/cell/gate/enemy/puzzle piece must carry one or more knowledge ids and must not be decorative-only.
- For polished classic games, use the matching standalone template as the canonical format: `assets/whack-a-mole-template/` for whack-a-mole and `assets/standalone-classic-template/` for memory, tic-tac-toe, flappy, shooter, and puzzle. Improve shared template files when quality is insufficient, then reuse them across courses through generated data.
- Do not use ellipsis as a substitute for fitting text on cards, moles, enemies, or puzzle pieces. Generate shorter complete labels and keep long statements in feedback or explanations.

## Quality Gates

Read `references/quality-rubric.md` before final delivery. Do not deliver a game that fails a critical gate. Fix it or explicitly report the blocker.

Minimum validation:

```powershell
python scripts/validate_html_game.py path\to\game --knowledge-json path\to\knowledge.json
```

If the system `python` is unavailable, use the bundled Codex Python runtime. Also run `scripts/validate_skill_no_deps.py` after editing this skill when the official `quick_validate.py` cannot import PyYAML. For substantial games, open the HTML in a browser or local dev server and verify:

- The first viewport is the actual game, not a landing page.
- No text overlaps or spills from buttons/cards at mobile and desktop sizes.
- All images/media render and have teaching purpose.
- Interactions work after reset and across at least two rounds.
- Scoring and answer logic match the extracted knowledge.
- Text on game objects fits inside its object frame at desktop and mobile sizes. For whack-a-mole, answer labels must be short, complete labels on the mole sign; keep longer explanations in feedback.
- The generated prompts, correct answers, and distractors are understandable without seeing the original slide. Reject vague stems such as "which is correct" when the visible options do not clearly define the task.

Interaction smoke examples:

- Whack-a-mole: start the game, wait for the correct risen mole, click it, and verify score/feedback changes.
- Shooter: start the game, move the ship with WASD or arrow keys, fire with Space, and verify a wrong enemy can be destroyed.
- Flappy: start the game and verify the bird moves with Space/click and gates resolve answer logic.
- Puzzle: drag or click a correct piece into a slot and verify the slot fills.
- Memory/tic-tac-toe: verify at least one successful match or answer-gated move.

When Node and Playwright are available, use:

```powershell
$env:NODE_PATH="path\to\node_modules"
node scripts/browser_smoke_check.mjs path\to\game
```

After editing classic templates or generators, run the full deterministic template set check:

```powershell
python scripts/validate_classic_template_set.py path\to\knowledge.json --out path\to\classic-template-check --force
```

## Resources

- `references/knowledge-schema.md`: canonical extraction schema and coverage report format.
- `references/question-engineering.md`: closed-world question schema, option grounding, type rules, Excel format, and user approval gates.
- `references/game-patterns.md`: mechanics selection guide and game design constraints.
- `references/classic-game-patterns.md`: classic mini-game mapping rules for whack-a-mole, memory cards, tic-tac-toe quiz, flappy judge, thunder shooter, and knowledge puzzles.
- `references/quality-rubric.md`: acceptance gates for extraction and HTML game quality.
- `assets/whack-a-mole-template/`: standalone arcade-cabinet whack-a-mole template with timed pop/hide, mallet feedback, combo, lives, and course answers on the moles.
- `assets/standalone-classic-template/`: standalone engine with separate visual identities and mechanics for memory, tic-tac-toe, flappy judgment, shooter, and knowledge puzzle outputs.
- `scripts/inventory_materials.py`: local material inventory and text/embedded-image extraction for PPTX, PDF, DOCX, text, Markdown, and standalone images.
- `scripts/course_pipeline.py`: deterministic workflow state and user-checkpoint manager.
- `scripts/validate_course_knowledge.py`: strict source hash, unit completeness, knowledge grounding, and focus validation.
- `scripts/build_knowledge_report.py`: deterministic detailed `课件知识点提取.md` generator.
- `scripts/validate_question_bank.py`: strict question coverage, source basis, option basis, review state, and game-fit validator.
- `scripts/question_bank_workbook.mjs`: fixed-format categorized Excel export/import utility.
- `scripts/approve_question_bank.py`: applies an explicit whole-bank user approval to pending question rows.
- `scripts/validate_question_pipeline.py`: deterministic regression for extraction, review, approval, game selection, and game-specific item thresholds.
- `scripts/classic_payload.py`: shared deterministic data shaping helpers for standalone classic game generators.
- `scripts/build_whack_a_mole.py`: deterministic standalone whack-a-mole generator and the preferred default for whack-a-mole requests.
- `scripts/build_standalone_classic.py`: deterministic generator for the five other independent classic game formats.
- `scripts/validate_html_game.py`: static validator for required game structure, local asset references, accessibility basics, and declared knowledge coverage.
- `scripts/validate_classic_template_set.py`: deterministic generation and static validation check for whack-a-mole, memory, tic-tac-toe, flappy, shooter, and puzzle templates.
- `scripts/browser_smoke_check.mjs`: Playwright smoke test for browser runtime errors, desktop/mobile rendering, screenshots, and basic interaction presence.
- `scripts/validate_skill_no_deps.py`: dependency-free skill validator for environments where the official validator lacks PyYAML.
