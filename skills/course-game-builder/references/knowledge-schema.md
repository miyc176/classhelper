# Knowledge Extraction Schema

Use this schema for the extracted course model. Store it as JSON when building games from course materials.

## Minimal JSON Shape

```json
{
  "course_title": "",
  "audience": "",
  "source_inventory": [
    {
      "source_id": "src_001",
      "path": "",
      "kind": "pptx|pdf|docx|image|spreadsheet|other",
      "page_or_slide_count": 0,
      "extraction_status": "complete|partial|blocked",
      "notes": ""
    }
  ],
  "coverage_audit": [
    {
      "source_id": "src_001",
      "unit": "slide 1",
      "status": "covered|no_instructional_content|blocked",
      "knowledge_ids": ["kp_001"],
      "notes": ""
    }
  ],
  "knowledge_points": [
    {
      "id": "kp_001",
      "type": "concept",
      "statement": "",
      "source_refs": [
        {
          "source_id": "src_001",
          "locator": "slide 1",
          "region": "top-right chart",
          "modality": "text|image|chart|diagram|table|notes|ocr"
        }
      ],
      "evidence": "",
      "teaching_value": "",
      "difficulty": "intro|core|advanced",
      "prerequisites": [],
      "related_ids": [],
      "common_errors": [],
      "assessment_prompts": []
    }
  ]
}
```

## Extraction Notes

- Treat `scripts/inventory_materials.py` output as a staging artifact, not the final knowledge model.
- Convert every `text_units` entry into one or more atomic knowledge points, unless it contains no instructional content.
- Inspect every `visual_units` entry before finalizing. Add either visual-derived knowledge points or a `coverage_audit` note explaining why it is not instructional.
- Use `visual_observation` for information only visible in diagrams, charts, screenshots, or pictures.
- Use `relationship` when the important learning target is how two concepts connect.
- Use `procedure` for ordered steps, decision paths, algorithms, workflows, or lab instructions.
- Use `misconception` when a slide highlights a common mistake or contrast.
- Keep `statement` atomic. Split compound statements that would need different feedback in a game.
- Preserve source references through every merge and rewrite.

## Blocking Rules

Do not proceed to game generation when:

- A source cannot be opened and the user expects full-course coverage.
- A visual unit is likely instructional but has not been visually inspected.
- A slide/page is ambiguous enough that a game answer could teach the wrong idea.

When proceeding with known limitations, keep the limitation in `coverage_audit` and exclude the uncertain knowledge point from answer logic.

## Coverage Report

After extraction, report:

- Count of sources, pages/slides/images inspected.
- Count of knowledge points by type and difficulty.
- Any blocked or partial sources, with concrete reason.
- Duplicate or near-duplicate points that were merged.
- Knowledge ids selected for each generated game.
