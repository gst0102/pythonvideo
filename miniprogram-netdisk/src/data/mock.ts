export interface ResourceItem {
  id: string;
  title: string;
  category: string;
  pan: string;
  level: "普通" | "精选" | "官方";
  points: number;
  verifiedAt: string;
  downloads: number;
  favorites: number;
  size: string;
  files: string;
  uploader: string;
  credit: number;
  description: string;
  unlocked?: boolean;
  link?: string;
  extractCode?: string;
  unzipCode?: string;
}

export interface RequestItem {
  id: string;
  title: string;
  category: string;
  bounty: number;
  pans: string;
  submissions: number;
  deadline: string;
  description: string;
}

export interface EarnTask {
  title: string;
  desc: string;
  reward: string;
  action: string;
}

export const userProfile = {
  nickname: "资料整理员",
  points: 100,
  credit: 80,
  uploads: 6,
  accesses: 18,
  requests: 3
};

export const panFilters = ["全部", "夸克", "百度", "迅雷", "阿里", "123网盘", "蓝奏云", "其他"];

export const categories = ["学习资料", "办公模板", "自媒体素材", "团长资料", "软件工具", "电子书", "公开索引", "其他"];

export const resources: ResourceItem[] = [
  {
    id: "r1",
    title: "社区团购接龙模板与群公告话术合集",
    category: "团长资料",
    pan: "夸克",
    level: "精选",
    points: 10,
    verifiedAt: "2小时前",
    downloads: 128,
    favorites: 33,
    size: "约 180MB",
    files: "约 42 个模板",
    uploader: "团长小助手",
    credit: 92,
    description: "包含接龙表格、群公告、促销提醒和售后沟通模板，适合社区团购日常运营。",
    unlocked: false,
    link: "https://pan.example.com/s/mock-quark",
    extractCode: "A8K2"
  },
  {
    id: "r2",
    title: "Excel 进销存台账与库存预警模板",
    category: "办公模板",
    pan: "百度",
    level: "普通",
    points: 5,
    verifiedAt: "今天",
    downloads: 46,
    favorites: 9,
    size: "约 24MB",
    files: "12 个表格",
    uploader: "效率资料站",
    credit: 86,
    description: "适合小店、团购和仓储场景，包含库存、采购、销售和利润汇总表。",
    unlocked: true,
    link: "https://pan.example.com/s/mock-baidu",
    extractCode: "9M3Q"
  },
  {
    id: "r3",
    title: "自媒体账号运营选题库与脚本结构模板",
    category: "自媒体素材",
    pan: "阿里",
    level: "官方",
    points: 20,
    verifiedAt: "昨天",
    downloads: 221,
    favorites: 68,
    size: "约 320MB",
    files: "约 80 个文档",
    uploader: "官方整理",
    credit: 100,
    description: "覆盖账号定位、爆款拆解、脚本文案、封面标题和发布复盘表。",
    unlocked: false,
    link: "https://pan.example.com/s/mock-aliyun",
    extractCode: "G7P1",
    unzipCode: "open"
  }
];

export const requests: RequestItem[] = [
  {
    id: "q1",
    title: "求社区团购群接龙模板和售后话术",
    category: "团长资料",
    bounty: 20,
    pans: "夸克 / 百度",
    submissions: 3,
    deadline: "2天后",
    description: "需要能直接修改使用的模板，最好包含商品接龙、团购公告和售后处理话术。"
  },
  {
    id: "q2",
    title: "求 Excel 小店进销存模板",
    category: "办公模板",
    bounty: 15,
    pans: "百度",
    submissions: 1,
    deadline: "1天后",
    description: "适合小店日常进货、出货和库存预警。"
  },
  {
    id: "q3",
    title: "求短视频脚本拆解表和选题库",
    category: "自媒体素材",
    bounty: 30,
    pans: "夸克 / 阿里",
    submissions: 0,
    deadline: "3天后",
    description: "希望有可复用的表格或文档结构。"
  }
];

export const earnTasks: EarnTask[] = [
  { title: "每日签到", desc: "今日可随机获得 1-3 分", reward: "+1-3分", action: "立即签到" },
  { title: "小游戏赚积分", desc: "玩一把并完成激励广告，今日剩余 3 次", reward: "+2分", action: "开始游戏" },
  { title: "上传资源", desc: "审核通过后获得基础奖励，被获取后继续得分", reward: "+5分", action: "上传资源" },
  { title: "完成求资源", desc: "提交资源被采纳后获得悬赏积分", reward: "悬赏分", action: "去看看" },
  { title: "补充失效链接", desc: "提交有效补链并审核通过", reward: "+5分", action: "去补链" }
];
