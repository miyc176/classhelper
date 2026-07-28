window.WHACK_GAME_DATA = {
  title: "硬件知识打地鼠",
  duration: 60,
  visible_ms: 5200,
  coverage: ["kp_003", "kp_008", "kp_024"],
  questions: [
    {
      id: "kp_003",
      prompt: "CPU 在计算机中承担什么核心职责？",
      answer: "运算与控制",
      choices: ["运算与控制", "长期存储", "稳定供电", "图像输出"],
      why: "CPU 是计算机系统的运算和控制核心。"
    },
    {
      id: "kp_008",
      prompt: "哪一种硬件向电脑提供主存储器？",
      answer: "内存条",
      choices: ["内存条", "显卡", "电源", "机箱"],
      why: "内存条提供 Main Memory，供 CPU 高速交换数据。"
    },
    {
      id: "kp_024",
      prompt: "哪类硬件适合长期保存数据？",
      answer: "SSD 或 HDD",
      choices: ["SSD 或 HDD", "CPU", "内存条", "散热器"],
      why: "SSD 和 HDD 断电后仍能保留数据。"
    }
  ]
};
