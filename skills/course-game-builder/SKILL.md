---
name: course-game-builder
description: Extract complete, source-traceable course knowledge from teaching materials and build polished HTML mini-games for classroom learning. Use when Codex is asked to process PPT/PPTX, PDF, DOCX, images, screenshots, scans, handouts, or courseware; recover knowledge from both text and visual content; create teaching games, interactive exercises, quizzes, simulations, matching games, sorting games, or review activities; and validate the generated HTML game quality before delivery.
---

# Course Game Builder

## Operating Standard

Extract knowledge before designing. Treat every slide, page, image, chart, diagram, annotation, speaker note, table, and embedded media as possible course content. Never claim perfect coverage when an input cannot be opened, rendered, OCRed, or visually inspected; record the limitation and ask for the missing artifact when it affects correctness.

## Agent Contract

Use this skill as a complete production workflow, not as a prompt-writing aid. A successful run produces source-traceable knowledge data, one or more playable HTML games, validation artifacts, and a concise delivery report.

Default behavior:

- If the user provides course materials, extract or update `knowledge.json` before building games.
- If the user provides an existing `knowledge.json`, validate its shape and generate games directly.
- If the user asks for classic, arcade, creative, polished, or game-like outputs, prefer the fixed standalone polished templates and replace only generated data files unless a template bug is verified.
- If the user asks for a specific classic game, generate one standalone HTML game for that mechanic.
- If the user asks for multiple game types, generate separate standalone folders. If they explicitly ask for one HTML collection or launcher, create a fresh launcher that links to the standalone games; do not use an old shared arcade shell.
- Keep outputs self-contained and offline-friendly; do not add CDN or internet dependencies without approval.
- Do not deliver on appearance alone. Run static validation and a browser smoke check for every interactive HTML game where tooling is available.

Required output contract:

- `index.html` must open directly from disk or from a simple local server.
- `window.GAME_KNOWLEDGE_COVERAGE` must list the knowledge ids used in answer logic.
- Every core interactive object must carry course knowledge: moles, cards, cells, gates, enemies, puzzle pieces, labels, or targets.
- Feedback must explain the answer using source-derived teaching value, evidence, or the knowledge statement.
- The first viewport must be playable, not a landing page or instructions-only page.

Use the relevant file skills when available:

- PPT/PPTX or slide decks: use the presentations skill and render slides for visual inspection.
- PDF or scans: use the pdf skill and render pages for visual inspection/OCR.
- DOCX or handouts: use the documents skill.
- XLSX/CSV grade or item banks: use the spreadsheets skill.
- New browser-based experiences or deployable sites: use the sites skill when the project contains `.openai/hosting.json` or the user asks to deploy.

## Workflow

1. Inventory all source files and assign each source a stable id.
2. Run `scripts/inventory_materials.py` to extract machine-readable text and embedded visual assets when local files are available.
3. Render visual pages/slides/images with the relevant file skill and inspect them for diagrams, labels, formulas, charts, arrows, spatial relationships, screenshots, handwritten marks, and callouts.
4. Build a source-traceable knowledge model using `references/knowledge-schema.md`.
5. Run a coverage audit: every source page/slide/image must have either extracted knowledge points or an explicit "no instructional content" note.
6. Design games from learning objectives, not from convenience. Read `references/game-patterns.md` before choosing mechanics for a new course/domain.
7. Build one or more self-contained HTML mini-games. Use `scripts/build_game_from_knowledge.py` for a reliable baseline game. When the user asks for creative, classic, arcade, or polished gameplay, read `references/classic-game-patterns.md`. Default to one standalone HTML game per classic mechanic. For whack-a-mole, use `scripts/build_whack_a_mole.py`, which copies `assets/whack-a-mole-template/` and replaces only `game-data.js`. For memory, tic-tac-toe, flappy, shooter, and puzzle, use `scripts/build_standalone_classic.py`, which copies `assets/standalone-classic-template/` and replaces only `game-data.js`.
8. Validate with `scripts/validate_html_game.py`, then run `scripts/browser_smoke_check.mjs` when the game uses JavaScript, layout, animation, drag/drop, canvas, or responsive UI. For classic games, also perform at least one real interaction smoke test for the core mechanic when Playwright is available.
9. Deliver the game files plus a concise coverage report: source coverage, knowledge-point coverage, game mapping, validation results, and any uncertainties.

## Command Path

Use this path for local course files:

```powershell
python scripts/inventory_materials.py path\to\course-materials --out path\to\work\extraction
```

Then inspect every entry in `material-extraction.json.visual_units` and rendered slide/page image before writing `knowledge.json`. Use `references/knowledge-schema.md` exactly; keep blocked or ambiguous material in `coverage_audit`.

Generate the baseline game:

```powershell
python scripts/build_game_from_knowledge.py path\to\knowledge.json --out path\to\game --title "Course Review" --force
```

Generate the preferred standalone whack-a-mole game:

```powershell
python scripts/build_whack_a_mole.py path\to\knowledge.json --out path\to\whack-game --title "Course Whack-a-Mole" --force
```

Generate any other standalone classic game with `memory`, `tictactoe`, `flappy`, `shooter`, or `puzzle`:

```powershell
python scripts/build_standalone_classic.py path\to\knowledge.json --mode memory --out path\to\memory-game --title "Course Memory" --force
```

Preserve the fixed standalone visual shell unless the user explicitly asks for a redesign. To adapt a new course, regenerate `game-data.js` from `knowledge.json`; do not rewrite `index.html`, `styles.css`, or `game.js` by hand unless a validation issue requires a template fix. If a single collection page is requested, build it as a launcher around generated standalone games rather than merging mechanics into one shared dashboard.

Mode selection shortcuts:

- `whack-a-mole`: use `scripts/build_whack_a_mole.py`; best for single-choice recall and fast classroom warmups.
- `memory`: use `scripts/build_standalone_classic.py --mode memory`; best for terms, definitions, labels, and examples.
- `tictactoe`: use `--mode tictactoe`; best for mixed review where a correct answer unlocks a board move.
- `flappy`: use `--mode flappy`; best for true/false, misconceptions, compatibility, and rule judgment.
- `shooter`: use `--mode shooter`; best for eliminating wrong options while preserving the correct answer.
- `puzzle`: use `--mode puzzle`; best for organizing related concepts into a small spatial structure.

Validate:

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

## Game-Build Rules

Before coding, map each target knowledge point to a mechanic:

- Recall or vocabulary: quick cards, timed prompts, clue reveal.
- Classification: drag/drop bins, sorting lanes, odd-one-out.
- Process or sequence: ordering, timeline repair, state-machine puzzle.
- Cause/effect or systems: small simulation with adjustable variables.
- Formulas: calculator challenge with generated cases and feedback.
- Diagrams: label placement, hotspot identification, relationship tracing.
- Misconceptions: diagnose-the-error or choose-the-fix rounds.
- Classic arcade requests: read `references/classic-game-patterns.md`; map whack-a-mole to single-choice recall, memory cards to term-definition pairs, tic-tac-toe to answer-gated moves, flappy bird to true/false judgment, thunder shooter to classification, and puzzles to knowledge organization.
- Preserve the original control loop of a recognizable classic game whenever possible. Embed knowledge into targets, gates, collision outcomes, enemy rules, and spatial pieces; do not replace movement, aiming, shooting, collision, or assembly with ordinary answer buttons.

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

## Resources

- `references/knowledge-schema.md`: canonical extraction schema and coverage report format.
- `references/game-patterns.md`: mechanics selection guide and game design constraints.
- `references/classic-game-patterns.md`: classic mini-game mapping rules for whack-a-mole, memory cards, tic-tac-toe quiz, flappy judge, thunder shooter, and knowledge puzzles.
- `references/quality-rubric.md`: acceptance gates for extraction and HTML game quality.
- `assets/html-game-template/`: standalone HTML/CSS/JS template with knowledge coverage metadata.
- `assets/whack-a-mole-template/`: standalone arcade-cabinet whack-a-mole template with timed pop/hide, mallet feedback, combo, lives, and course answers on the moles.
- `assets/standalone-classic-template/`: standalone engine with separate visual identities and mechanics for memory, tic-tac-toe, flappy judgment, shooter, and knowledge puzzle outputs.
- `scripts/inventory_materials.py`: local material inventory and text/embedded-image extraction for PPTX, PDF, DOCX, text, Markdown, and standalone images.
- `scripts/build_game_from_knowledge.py`: deterministic baseline HTML game generator from `knowledge.json`.
- `scripts/classic_payload.py`: shared deterministic data shaping helpers for standalone classic game generators.
- `scripts/build_whack_a_mole.py`: deterministic standalone whack-a-mole generator and the preferred default for whack-a-mole requests.
- `scripts/build_standalone_classic.py`: deterministic generator for the five other independent classic game formats.
- `scripts/validate_html_game.py`: static validator for required game structure, local asset references, accessibility basics, and declared knowledge coverage.
- `scripts/browser_smoke_check.mjs`: Playwright smoke test for browser runtime errors, desktop/mobile rendering, screenshots, and basic interaction presence.
- `scripts/validate_skill_no_deps.py`: dependency-free skill validator for environments where the official validator lacks PyYAML.
