# Context-Preserving Extraction

Use this protocol for PPT/PPTX, PDF, DOCX, screenshots, and image-heavy courseware.

## Unit Of Meaning

- The primary visual unit is the complete slide, page, document section, or standalone image.
- An extracted picture is a zoomable child of its `parent_unit`, never an independent page.
- Read title, body text, captions, labels, arrows, connectors, legends, tables, charts, relative position, grouping, and nearby pictures together before creating knowledge points.
- Preserve multi-image semantics such as comparison, sequence, cause/effect, before/after, component/whole, and example/counterexample.
- Use `context_units.elements` for geometry and z-order, and `context_units.relations` for spatial/group/connector evidence. Confirm inferred relations against the rendered whole page.
- A picture with no meaningful relation after full-page inspection may be marked decorative; never decide this from the isolated image alone.

## Fast Inspection Strategy

1. Read `material-extraction.json` once and group all work by `context_units`.
2. Inspect rendered pages/slides in ordered batches or contact sheets. Use 6-12 pages per batch when text remains readable.
3. Open an extracted child image only when the whole-page rendering is too small, occluded, or ambiguous.
4. Draft all knowledge points for one topic/chapter in one structured pass; do not run one model turn per image or per knowledge point.
5. Reuse unchanged source results when `sha1` matches. On rerun, process only cache misses and then update affected topics, coverage rows, questions, and games.
6. Keep deterministic operations deterministic: inventory, hashing, coverage checks, Markdown rendering, Excel export/import, approval, and game generation should use scripts rather than repeated model reasoning.

## Relationship Evidence

Represent visual relationships explicitly in knowledge evidence, for example:

- `slide 6 elements s0006-e004 -> s0006-e007 via connector s0006-e006`
- `slide 8 images 1 and 2 form a before/after comparison under caption ...`
- `page 4 chart legend maps blue to ... and orange to ...`

If a relation is only suggested by proximity and not confirmed by text, arrows, grouping, or the rendered layout, record it as uncertain and do not turn it into a scored question.

## Performance Rules

- Default to `inventory_materials.py --workers 4`; increase only when local storage and source libraries remain stable.
- Do not use `--no-cache` unless source parsing logic changed or cached output is suspected corrupt.
- Do not rerender, re-OCR, regenerate Markdown, or rebuild Excel when their input hash is unchanged.
- Keep only the three required user stops: material completeness, course focus, and question approval/game selection. Machine validation messages are not extra user checkpoints unless they reveal a blocker.
