window.LIVE_TEACHING_DATA = {
  platformTitle: "课堂互动平台",
  platformSubtitle: "选择组别、进入活动、把小游戏和多人任务挂到同一主页",
  title: "黄金样本拍卖",
  subtitle: "用 100 个虚拟金币决定哪些样本进入黄金评测集",
  sessionCode: "GOLD",
  activity: "golden-sample-auction",
  budget: 100,
  topN: 5,
  groups: [
    { id: "group_1", name: "第 1 组" },
    { id: "group_2", name: "第 2 组" },
    { id: "group_3", name: "第 3 组" },
    { id: "group_4", name: "第 4 组" },
    { id: "group_5", name: "第 5 组" },
    { id: "group_6", name: "第 6 组" }
  ],
  applications: [
    {
      id: "golden-sample-auction",
      title: "黄金样本拍卖",
      kicker: "多人联机",
      description: "每人 100 金币，选择最值得进入黄金评测集的样本类型。"
    }
  ],
  candidates: [
    {
      id: "sample_high_freq",
      title: "高频用户问题",
      tag: "频率",
      description: "代表真实使用中最常出现的问题，能快速暴露基础能力短板。",
      example: "用户反复询问同一功能入口、流程、限制或售后政策。",
      value: "覆盖面大，适合做回归评测基线。",
      risk: "只看高频会忽略低频高风险场景。"
    },
    {
      id: "sample_high_risk",
      title: "低频但高风险问题",
      tag: "风险",
      description: "出现不多，但一旦答错会造成合规、品牌或业务损失。",
      example: "资质、退款、数据安全、医疗金融类边界问法。",
      value: "能提前发现严重 Badcase。",
      risk: "需要专家判断，样本构造成本较高。"
    }
  ],
  embeddedGames: []
};
