# Question Engineering Protocol

Use this reference after knowledge extraction and before any game generation.

## Non-Negotiable Grounding

- The course materials are the closed world. Do not add facts, examples, terminology, constraints, or distractors from model memory or the internet.
- Every question binds to one or more `knowledge_ids`, an exact source locator, and one `source_basis` copied exactly from a bound knowledge point's `statement` or `evidence`.
- The correct answer must be directly entailed by the bound knowledge point. Application questions may recombine only explicitly related points.
- Distractors come only from another in-scope course point or a bound point's `common_errors`. Record their knowledge origin while drafting; discard any distractor without a course origin.
- Never write questions from `blocked`, `uncertain`, or no-instructional-content units.
- Do not use vague stems such as “以下哪项正确” without a defined target. Do not use “以上都对/都不对”. Do not hide incomplete text with ellipsis.

## Coverage Rules

- Every in-scope knowledge point must appear in at least one question.
- Every user-confirmed focus point must appear in at least two questions across at least two suitable question types.
- Question counts follow the material, not a fixed quota. Do not force a type when the source cannot support it.
- Keep an explicit coverage matrix from knowledge id to question ids. Zero-coverage points block approval.

## Standard Question JSON

```json
{
  "schema_version": "1.0",
  "course_title": "",
  "knowledge_sha256": "",
  "questions": [
    {
      "id": "q_single_001",
      "type": "single_choice|multiple_choice|true_false|matching|classification|ordering",
      "topic": "",
      "importance": "重点|次重点|拓展",
      "difficulty": "基础|进阶|综合",
      "stem": "",
      "options": [],
      "answers": [],
      "explanation": "",
      "knowledge_ids": ["kp_001"],
      "source_basis": "必须逐字等于某个绑定知识点的 statement 或 evidence",
      "option_sources": ["kp_001", "kp_002", "common_error:kp_003", "kp_004"],
      "option_basis": ["对应知识点原文依据1", "对应知识点原文依据2", "对应常见误区原文", "对应知识点原文依据4"],
      "source_refs": [{"source_id": "src_001", "locator": "slide 1"}],
      "game_modes": ["whack-a-mole"],
      "review_status": "待审核|通过|需修改|停用",
      "review_notes": ""
    }
  ]
}
```

Type conventions:

- `single_choice`: 4-6 complete options; exactly one answer.
- `multiple_choice`: 4-6 complete options; at least two answers.
- `true_false`: options are `正确`, `错误`; exactly one answer.
- `matching`: each option is `左项=>右项`; answers repeat all correct pairs.
- `classification`: each option is `项目=>类别`; answers repeat all correct mappings.
- `ordering`: options are the unordered steps; answers contain the correct order.

## Standard Workbook

The workbook name is `<课程名称>课程题目.xlsx`. It contains:

- `使用说明`: review workflow and delimiter rules.
- `课程重点`: confirmed focus ids and source-derived reasons.
- `覆盖检查`: every knowledge point and its question count.
- `单选题`, `多选题`, `判断题`, `配对题`, `分类题`, `排序题`: editable question rows in one fixed column schema.
- `_元数据`: schema version, course title, and source knowledge hash.

Editable rows use these columns: `题目ID`, `主题`, `重点等级`, `难度`, `题干`, `选项A` through `选项F`, `正确答案`, `解析`, `知识点ID`, `依据原文`, `选项依据`, `选项原文依据`, `来源定位`, `适配游戏`, `审核状态`, `修改意见`.

`选项依据`与非空选项逐项对齐，使用 `||` 分隔。每项填写课程内知识点 ID；若选项来自已提取的常见误区，填写 `common_error:知识点ID`。不得留空，也不得填写课程资料以外的知识。

`选项原文依据`也必须逐项对齐。普通知识点必须逐字等于对应知识点的 `statement` 或 `evidence`；常见误区必须逐字等于对应 `common_errors` 中的一项。选项可以为了清晰和版面做忠实短写，但不得改变该依据的含义。

Use `||` between multiple answers or ids. Users may edit cells, add rows, set `审核状态` to `通过`, or set `需修改` and explain changes in `修改意见`.

## User Interaction Gates

1. After inventory: ask whether all course files are present.
2. After `课件知识点提取.md`: show proposed focus points and ask for confirmation/additions/removals.
3. After `<课程名称>课程题目.xlsx`: ask whether questions are usable.
4. If not usable: accept question text in chat or ask the user to edit the workbook; re-import and revalidate.
5. If usable: ask the user to choose from `打地鼠`, `知识翻牌`, `答题井字棋`, `飞翔判断`, `雷霆战机`, `知识拼图`.
6. Generate only the selected games and only from rows marked `通过`.
