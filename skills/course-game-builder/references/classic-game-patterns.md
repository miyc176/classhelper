# Classic Game Pattern Guide

Use this reference when the user wants polished, creative classic mini-games rather than a simple quiz. The goal is to make the mechanic operate on the knowledge shape.

## Required Arcade Patterns

| Pattern | Knowledge fit | Fusion rule |
| --- | --- | --- |
| Whack-a-mole | single-choice recall, identify the correct statement | Show one prompt and 4-6 popping choices across multiple holes. The learner clicks only the mole belly containing the source-grounded answer before time runs out. Wrong moles must be plausible distractors from the same course. |
| Memory flip cards | vocabulary, part-function, term-example pairs | Use a facedown card grid with real flip state. Pair hardware terms, formulas, diagram labels, or process names with concise definitions or examples. A match is correct only when both cards share a knowledge id or relationship. |
| Tic-tac-toe quiz | mixed review and classroom competition | A learner may place a mark only after answering a course question correctly. Wrong answers lose the move; the bot or second player responds. |
| Flappy judge | true/false, misconceptions, compatibility rules | Preserve Flappy-style vertical control and forward scrolling. Put Yes/No openings in an approaching wall; the learner must physically steer through the correct opening. On a correct pass, remove/fade the wall and continue flying into the next statement without rebuilding the whole scene; a wrong opening or wall hit causes a collision. |
| Thunder shooter | multiple choice and error elimination | Preserve free ship movement and firing. Use WASD or arrow keys to move and Space to fire. Enemy craft carry answer options; the learner destroys wrong options while protecting the correct answer. |
| Knowledge puzzle | structure, sequence, hierarchy, visual organization | Use a finite puzzle frame with a small number of large interlocking pieces, usually 4 correct pieces plus 1-2 distractors. Pieces should look like real jigsaw parts with tabs/blanks or Z/T/L/S-like silhouettes, and the learner drags correct concepts into matching slots until the frame is full. |

## Arcade Quality Rules

- Build the playable experience as the first screen.
- Default to one independent HTML game per classic mechanic. If the user requests one combined deliverable, create a launcher page that links to the standalone games; do not merge unlike mechanics into one shared dashboard.
- If the user says "all games" or names several games without saying "one HTML", still generate separate standalone folders.
- Do not force different genres into one shared dashboard layout. Each independent game must own its full visual language, scene composition, HUD, controls, motion, and pacing.
- Use a genre-specific standalone template as the canonical format. Course generation should replace `game-data.js` only; edit template files only when improving the shared game or fixing a verified bug.
- Preserve each classic game's recognizable silhouette before adding knowledge content: whack-a-mole needs holes, popping moles, and a mallet cue; memory needs a facedown card grid and card-flip rhythm; tic-tac-toe needs a dominant 3x3 board; flappy judge needs a bird and paired pipe gates; thunder shooter needs a vertical space battlefield, player ship, and enemy targets; puzzle needs loose interlocking pieces plus sorting trays or a board.
- Self-check rule fidelity, not just clickability: whack-a-mole must have timed pop/hide pressure; flappy judge must have an approaching-gate or collision rhythm; thunder shooter must have aim/fire semantics; puzzle must support drag/drop or an equivalent spatial placement interaction.
- Preserve the source game's control loop whenever it can carry the teaching task. Do not replace movement, collision, aiming, shooting, or spatial assembly with direct answer buttons.
- Use canvas only when it improves motion or arcade feel; keep fallback text DOM controls for accessibility where practical.
- Keep each mode short: 4-8 rounds for focused play, or a complete flash/puzzle mode that covers all knowledge ids.
- Every mode must show explanatory feedback after success or failure.
- Every mode must contribute to `window.GAME_KNOWLEDGE_COVERAGE`.
- Do not create a mechanically pretty game that ignores the source knowledge. Each object, target, card, gate, enemy, or puzzle piece must carry a knowledge id.
- Use course images, rendered slides, or domain-specific visuals when available. If no source visual is available, create polished CSS/canvas visuals directly.
- Validate both code and browser rendering. Inspect desktop and mobile screenshots.
- Preserve mode identity and high production value: knowledge should live on the game objects themselves, such as text on a mole belly, card faces, chess move gates, pipe labels, enemy bodies, or puzzle pieces. Avoid generic quiz cards floating in a decorative shell.

## Whack-a-Mole Visual Baseline

Use `assets/whack-a-mole-template/` and preserve these non-negotiable traits:

- A full-field arcade composition rather than an app dashboard.
- A 3x3 field of dark holes with moles physically rising from and sinking into them.
- The prompt fixed above the field and each answer printed on a sign/belly attached to a visible mole.
- Random staggered appearance, finite exposure time, miss penalty, score, combo, lives, and a visible mallet strike.
- Only risen moles may be hit. Hitting an empty hole or hidden mole must never count as an answer.
- Keep answer text concise enough to remain readable on the game object. Rewrite a statement into a short source-faithful option instead of shrinking paragraphs into a mole.
- Do not use ellipsis as the default solution for mole answers. Put a complete short label on the mole sign and keep the full explanation in feedback.

## Mapping Checklist

Before coding, make a mode map:

- Whack-a-mole: 4-8 high-value concept/fact/example points.
- Memory: 6-10 term-definition or item-function pairs.
- Tic-tac-toe: 9 mixed questions with varied difficulty.
- Flappy judge: 8-12 true/false statements, including misconceptions.
- Thunder shooter: 3-5 categories with targets and decoys.
- Puzzle: 6-12 pieces organized into a hierarchy, sequence, or category board.

When knowledge is sparse, generate fewer modes with better integration rather than forcing all six. When knowledge is rich enough, include all six.
