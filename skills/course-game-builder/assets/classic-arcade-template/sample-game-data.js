window.COURSE_ARCADE_DATA = {
  "title": "课程精美小游戏合集",
  "coverage": ["kp_001"],
  "whack": [
    {
      "id": "kp_001",
      "prompt": "选择正确表述。",
      "answer": "知识点用于驱动游戏交互。",
      "choices": ["知识点用于驱动游戏交互。", "游戏只展示装饰内容。", "题目不需要反馈。", "素材不需要验证。"],
      "why": "每个核心对象都应绑定课程知识点。"
    }
  ],
  "memory": [
    {"id": "kp_001", "term": "知识绑定", "definition": "交互对象携带对应知识点", "why": "保证玩法服务教学目标。"}
  ],
  "tictactoe": [
    {
      "id": "kp_001",
      "prompt": "什么决定学生是否能落子？",
      "answer": "答对课程题目",
      "choices": ["答对课程题目", "随机落子", "只看速度", "关闭反馈"],
      "why": "井字棋用答题门槛连接知识和棋局。"
    }
  ],
  "flappy": [
    {"id": "kp_001", "text": "判断门应来自课程知识点。", "answer": true, "why": "真伪判断必须可追溯。"}
  ],
  "shooter": {
    "categories": [{"name": "concept", "ids": ["kp_001"]}],
    "targets": [{"id": "kp_001", "type": "concept", "label": "知识绑定", "text": "每个目标都映射知识点", "why": "避免纯装饰射击。"}]
  },
  "puzzle": [
    {"id": "kp_001", "type": "concept", "label": "知识绑定", "text": "将知识块放入正确结构", "why": "拼图用于整理知识网络。"}
  ]
};
window.GAME_KNOWLEDGE_COVERAGE = ["kp_001"];
