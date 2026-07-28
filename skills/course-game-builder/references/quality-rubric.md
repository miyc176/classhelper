# Quality Rubric

Critical gates must pass before delivery unless explicitly reported as blocked.

## Extraction Gates

- Critical: Every provided source is inventoried.
- Critical: Every page, slide, or standalone image is either covered or marked no instructional content/blocked.
- Critical: Image-only knowledge is inspected visually or OCRed; it is not ignored because text extraction succeeded.
- Critical: Each knowledge point has at least one source reference.
- Critical: Unreadable, missing, or ambiguous content is reported with exact file and locator.
- Strong: Duplicates are normalized without losing exceptions or examples.
- Strong: Concepts, procedures, formulas, examples, and misconceptions are typed separately.

## Game Gates

- Critical: The generated HTML opens without runtime errors in a browser.
- Critical: Answer logic matches the extracted knowledge.
- Critical: `window.GAME_KNOWLEDGE_COVERAGE` lists the knowledge ids used by the game.
- Critical: Feedback explains why an answer is correct or incorrect.
- Critical: The first viewport contains playable teaching interaction, not a marketing page.
- Critical: Local assets referenced by HTML/CSS/JS exist.
- Critical: For classic games, each core interactive object is knowledge-bound: mole, card, tic-tac-toe cell question, flappy gate, shooter enemy, or puzzle piece.
- Critical: Polished classic games are generated from the fixed `assets/classic-arcade-template/` shell, with course-specific content isolated in `game-data.js`, unless the user explicitly asks for a new visual format.
- Critical: Classic modes visually resemble their source genre before the knowledge layer is applied; a generic button grid with game names is not sufficient.
- Critical: Classic modes preserve core gameplay semantics, not just surface labels: timed popping for whack-a-mole, flip/match state for memory, answer-gated board moves for tic-tac-toe, pipe timing for flappy judge, aim/fire for shooter, and spatial placement for puzzle.
- Strong: The game works at common desktop and mobile widths.
- Strong: Controls are keyboard reachable where practical.
- Strong: Visual design is clean, readable, and domain-appropriate.
- Strong: The game has reset/retry and progress state.
- Strong: A deterministic baseline can be regenerated from `knowledge.json` with `scripts/build_game_from_knowledge.py`.
- Strong: A creative arcade can be regenerated from `knowledge.json` with `scripts/build_classic_arcade.py` when classic mini-games are requested.

## Delivery Checklist

Report:

- Output file paths.
- Source coverage summary.
- Knowledge ids covered by each game.
- Validator result and browser check result.
- Known limitations or assumptions.

Do not call the extraction "complete" if the report still contains `needs_visual_review`, `needs_rendered_page_inspection`, or unexamined `blocked` units.
