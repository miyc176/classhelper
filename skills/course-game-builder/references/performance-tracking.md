# Pipeline Performance Tracking

Every course run must create `pipeline-performance.json` next to `workflow-state.json`.

## Stage Names

- `material_parsing`: inventory, file hashes, text/layout extraction, incremental cache.
- `rendering`: slide/page rendering and contact-sheet preparation.
- `ocr_visual_analysis`: OCR plus contextual multimodal inspection.
- `knowledge_engineering`: normalization, deduplication, source binding, focus candidates.
- `knowledge_report`: deterministic Markdown generation.
- `question_generation`: AI drafting and source grounding of the categorized bank.
- `excel_generation`: deterministic XLSX export/rendering.
- `game_generation`: selected HTML game builds.
- `validation`: knowledge, question, workbook, static game, and browser checks.

Use `start` immediately before an AI/manual stage and `finish` immediately after it. Deterministic scripts with `--performance-file` record themselves. Do not include time spent waiting for the user inside an active stage; finish the stage before asking a checkpoint question.

Useful metrics include `pages_total`, `pages_reprocessed`, `cache_hits`, `cache_misses`, `visual_occurrences`, `unique_visual_assets`, `knowledge_points`, `questions`, `mode`, and validation pass/fail.

Before delivery, run `complete` and report the slowest stage, cache hit rate, and pages reprocessed. Performance data diagnoses speed; it never permits skipping coverage or quality gates.
