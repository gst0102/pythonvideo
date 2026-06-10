# 阶段性交接归档

生成时间：2026-06-11
主项目目录：`D:\Desktop\vedo-project`
后端/文档仓库：`D:\Desktop\vedo-project\myproject`
实际小程序工程：`D:\Desktop\vedo-project\video-ts`

## 1. 项目背景与目标

项目原先围绕“悦享互动宝”阶段二能力推进，已经沉淀了 FastAPI 后端基础能力，包括用户登录、积分账户、积分流水、签到、小游戏、激励广告、会员支付、邀请关系、二级分销、提现、后台基础接口和 QA 验收流程。

当前产品方向已调整为“网盘资料互助 + 积分解锁资源”的微信小程序 MVP。用户可以通过签到、小游戏、广告、上传资源、补链、完成求资源任务等方式获得积分，也可以消耗积分获取网盘资源链接、提取码、解压码等信息。

对外表达应尽量使用低风险定位，例如：

- 网盘资料互助平台
- 学习资料库
- 办公模板库
- 自媒体素材库
- 团长资料库
- 短视频素材/好内容收藏工具
- 求资源悬赏平台

仍需避免在产品名、首页文案、审核材料中突出“盗版影视”“最新影视资源”“盗版课程”“会员资源共享”“返佣暴利”等高风险表达。

## 2. 当前阶段目标

当前阶段目标是先完成微信小程序前端静态原型和体验确认，使用 mock 数据，不接真实后端。

当前明确目标：

1. 保留现有后端商业底座，不重新另起完整后端项目。
2. 后端旧 `/anime` 影视资源模块暂不硬改为万能资源库。
3. 后续新增通用 `resources` 资源域，用于网盘资料、资源解锁、上传审核、求资源、投诉失效、补链和后台管理。
4. 小游戏保留，作为“赚积分页”的固定入口。
5. 支付、会员、邀请关系、二级分销、提现保留，但前端文案建议收敛为“邀请奖励/收益记录”。
6. 当前 `video-ts` 小程序静态原型主流程已串联，下一步进入整体预览、QA 测试清单和后端资源域设计准备。

## 3. 已完成的功能

### 3.1 后端/文档仓库 `myproject`

已提交：

```text
0b83d7c feat: add netdisk miniapp static prototype
```

该提交包含：

- 新方向交接文档 `docs/handoff-latest.md`。
- 新方向产品/架构文档：
  - `docs/new-docs/netdisk-resource-mutual-aid-mvp.md`
  - `docs/new-docs/netdisk_miniapp_codex_delivery.md`
  - `docs/new-docs/网盘资源互助MVP_基于当前项目重构方案.md`
- Codex 自测报告：
  - `docs/qa/网盘资源互助MVP_Codex自测报告.md`
- 独立静态原型目录：
  - `miniprogram-netdisk/`

说明：`miniprogram-netdisk/` 是先前按文档新增的独立原型目录，但用户实际预览的小程序工程是 `video-ts`。因此后续前端 UI 迭代已转移到 `video-ts`。

### 3.2 实际小程序工程 `video-ts`

最近已提交的小程序原型相关提交：

```text
7b163d5 feat: add netdisk repair mock flow
586a4cc feat: add netdisk upload mock form
6e7ac2b feat: refine earn points task center
25dcf79 feat: add netdisk request publish mock
181074b feat: add netdisk resource detail mock
8674766 feat: refine netdisk home and favorites mock
6c79b8c feat: add netdisk mid tab prototype
846c4cd fix: restore visible earn points tab
bb42331 feat: add floating custom netdisk tabbar
94f396d style: refine netdisk tab and categories
7dd9a65 fix: stack custom tab labels under icons
f66ce55 fix: align earn tab label style
```

已完成并可在 `video-ts` 预览到：

1. 新增“互助资源库”首页静态原型，并完成首页信息架构收敛。
2. 首页顶部积分卡放大高亮，显示“我的积分 100分”。
3. 首页副标题已改为：

   ```text
   资料、短视频、好内容，一站收藏
   ```

4. 新增资源 mock 数据和页面：
   - `src/pages/netdisk/index.vue`
   - `src/pages/netdisk/requests.vue`
   - `src/pages/netdisk/earn.vue`
   - `src/pages/netdisk/favorites.vue`
   - `src/pages/netdisk/detail.vue`
   - `src/pages/netdisk/request-publish.vue`
   - `src/pages/netdisk/upload.vue`
   - `src/pages/netdisk/repair.vue`
   - `src/pages/netdisk/mock.ts`
5. 新增自定义底部导航组件：
   - `src/components/NetdiskTabBar.vue`
6. 当前自定义 tabBar 入口为：

   ```text
   资源 / 求资源 / 赚积分 / 收藏 / 我的
   ```

7. 自定义 tabBar 会调用 `uni.hideTabBar()` 隐藏原生 tabBar。
8. 中间“赚积分”当前处理结果：
   - 不再使用 uni-app `midButton`。
   - 不再使用橙色渐变和阴影。
   - 图标约为普通 tab 图标的 1.3 倍。
   - 文字样式与其他 tab 统一：未选中灰色，选中绿色。
   - 图标在上，文字在正下方。
9. 首页信息架构已调整：
   - 搜索框文案为“搜索资源、视频、资料关键词”。
   - 网盘筛选收敛为：全部 / 夸克 / 百度 / 迅雷 / 阿里。
   - Banner Slogan 为“找资源，看内容，用积分解锁更多”。
   - 一级分类收敛为：影视娱乐 / 学习办公 / 自媒体素材 / 软件工具。
   - 内容流为：今日精选 / 热门求资源 / 最新上传。
10. 资源详情闭环已完成：
   - 首页资源卡可进入详情页。
   - 未解锁资源隐藏网盘链接、提取码、解压码。
   - 已解锁资源展示 mock 链接、提取码、解压码。
   - 支持“模拟解锁”，不真实扣积分。
11. 收藏闭环已完成：
   - 首页资源卡支持“收藏 / 已收藏”。
   - 收藏状态保存到本地 `uni` storage。
   - 收藏页读取本地收藏记录展示。
12. 求资源发布闭环已完成：
   - 求资源页可进入发布页。
   - 发布页支持需求标题、期望网盘、分类、悬赏积分、补充说明。
   - 提交后保存到本地 mock，不冻结真实积分。
13. 赚积分任务中心已完成：
   - 任务卡展示签到、小游戏、上传资源、完成求资源、补链。
   - 支持“可领取 / 已完成 / 今日已达上限”三种 mock 状态。
   - 可领取任务点击后写入本地状态并回显已完成。
14. 上传资源闭环已完成：
   - 上传页支持资源标题、一级分类、网盘类型、链接、提取码、解压码、资源说明。
   - 提交后保存为本地 mock “待审核”记录。
   - 页面展示“待审核 / 审核通过 / 驳回”三种 mock 审核状态。
15. 补链/投诉失效闭环已完成：
   - 资源详情页提供“链接失效 / 我要补链”入口。
   - 补链页支持关联资源、处理类型、网盘类型、新链接、提取码、解压码、问题说明。
   - 提交后保存为本地 mock 记录，并展示“待审核 / 补链通过 / 驳回”状态。
   - 从任务中心进入补链页并提交补链后，会把“补充失效链接”任务标记为已完成。

### 3.3 已验证事项

最近连续原型提交均已执行：

```text
npm run type-check
```

截至 `7b163d5 feat: add netdisk repair mock flow`，类型检查通过。

## 4. 已修改/新增的文件

### 4.1 `myproject`

已提交新增/修改：

- `docs/handoff-latest.md`
- `docs/new-docs/netdisk-resource-mutual-aid-mvp.md`
- `docs/new-docs/netdisk_miniapp_codex_delivery.md`
- `docs/new-docs/网盘资源互助MVP_基于当前项目重构方案.md`
- `docs/qa/网盘资源互助MVP_Codex自测报告.md`
- `docs/悦享互动宝 MVP 产品开发文档.md`
- `miniprogram-netdisk/`

本次交接归档正在更新：

- `docs/handoff-latest.md`

### 4.2 `video-ts`

已提交新增/修改的原型相关文件：

- `src/components/NetdiskTabBar.vue`
- `src/pages/netdisk/index.vue`
- `src/pages/netdisk/requests.vue`
- `src/pages/netdisk/earn.vue`
- `src/pages/netdisk/favorites.vue`
- `src/pages/netdisk/detail.vue`
- `src/pages/netdisk/request-publish.vue`
- `src/pages/netdisk/upload.vue`
- `src/pages/netdisk/repair.vue`
- `src/pages/netdisk/mock.ts`
- `src/pages/mine/mine.vue`
- `src/pages.json`
- `src/main.ts`
- `src/static/tab/dianying-a.png`
- `src/static/tab/dianying-b.png`
- `src/static/tab/game-a.png`
- `src/static/tab/game-b.png`
- `src/static/tab/shoucang-a.png`
- `src/static/tab/shoucang-b.png`

其中 `src/main.ts` 的 `midButton` 监听已在 `846c4cd` 中移除，当前不再依赖 uni-app `midButton`。

## 5. 当前代码状态

### 5.1 `myproject`

当前分支：

```text
feature/yuexiang-stage2-mvp
```

当前状态：

```text
ahead 1
```

最近提交：

```text
0b83d7c feat: add netdisk miniapp static prototype
```

说明：`myproject` 当前比远端多 1 个提交。本次更新 `docs/handoff-latest.md` 后，工作区会出现该文档未提交修改。

### 5.2 `video-ts`

当前分支：

```text
feature/yuexiang-stage2-mvp
```

最近小程序相关提交：

```text
7b163d5 feat: add netdisk repair mock flow
586a4cc feat: add netdisk upload mock form
6e7ac2b feat: refine earn points task center
25dcf79 feat: add netdisk request publish mock
181074b feat: add netdisk resource detail mock
8674766 feat: refine netdisk home and favorites mock
f66ce55 fix: align earn tab label style
7dd9a65 fix: stack custom tab labels under icons
94f396d style: refine netdisk tab and categories
bb42331 feat: add floating custom netdisk tabbar
846c4cd fix: restore visible earn points tab
```

当前 `video-ts` 工作区仍有大量历史/用户未提交改动，主要包括但不限于：

- `package.json`
- `pnpm-lock.yaml`
- `shims-uni.d.ts`
- `src/App.vue`
- `src/pages/anime/anime.vue`
- `src/pages/content/video_info.vue`
- `src/pages/mine/compent/*`
- `src/pages/user-login/login.vue`
- `src/services/anime.ts`
- `src/services/config.ts`
- `src/store/*`
- `src/types/index.d.ts`
- 若干 `src/static/*` 删除/修改
- 若干未跟踪文档和工具文件

重要：这些未提交改动大多不是本轮原型任务新增，后续不要随意回滚或覆盖。

## 6. 已知问题和风险

### 6.1 当前 UI/前端风险

1. 自定义 tabBar 通过前端组件实现，并调用 `uni.hideTabBar()` 隐藏原生 tabBar。需要在微信开发者工具和真机上继续确认：
   - 是否所有 tab 页面都成功隐藏原生 tabBar。
   - 底部安全区是否合适。
   - 中间“赚积分”是否仍然过大或过小。
2. 当前资源、详情解锁、收藏、求资源发布、赚积分任务、上传资源、补链/投诉均为 mock 静态原型，不接真实后端。
3. “我的”页面仍是旧业务页面，只是挂载了自定义 `NetdiskTabBar`；其内部收益、提现、会员等旧逻辑没有重构为新资源业务。
4. `video-ts` 工作区较脏，后续提交必须谨慎暂存，避免把无关历史改动混进 commit。

### 6.2 产品和合规风险

1. 网盘资源项目核心风险是内容合规和资源质量。
2. 当前分类中加入了“影视剧”，后续上线文案、种子资源和审核材料必须谨慎，避免触碰盗版影视传播风险。
3. 未解锁前不得泄露完整网盘链接、提取码、解压码、备用链接。
4. 上传资源、补链、投诉失效后续必须进入审核流，不能让用户提交后直接对外可见。

### 6.3 后端 P0 风险

以下后端能力尚未实现，不能视为完成：

- 通用资源域数据表和接口。
- 资源获取扣积分。
- 资源获取记录。
- 上传审核。
- 求资源悬赏冻结、采纳、退回。
- 投诉失效。
- 补链奖励。
- 后台资源审核。
- 用户收藏记录。
- 任务中心每日次数、领取状态和奖励发放。

后续一旦进入真实后端开发，以下全部按 P0：

- 获取资源重复扣积分。
- 获取资源重复奖励上传者。
- 扣积分成功但未展示链接。
- 展示链接成功但未扣积分。
- 求资源冻结/采纳/退回不一致。
- 补链奖励重复发放。
- 上传资源审核通过后奖励重复发放。
- 投诉失效误伤有效资源，或补链审核通过后未更新资源可用链接。
- 小游戏或广告重复发积分。
- 支付回调重复导致重复发积分或邀请奖励。
- 退款后奖励未失效或未处理。
- 后台数据和前端展示不一致。

## 7. 用户已经确认过的产品/技术决策

用户已确认或通过连续修改表达过以下决策：

1. 产品方向从旧视频/影视订阅方向转向“网盘资料互助 + 积分解锁资源”。
2. 优先在现有项目基础上继续，不重新开发完整后端。
3. 真实小程序工程是 `D:\Desktop\vedo-project\video-ts`，不是 `myproject/miniprogram-netdisk`。
4. 首页标题保留“互助资源库”。
5. 首页副标题使用：

   ```text
   资料、短视频、好内容，一站收藏
   ```

6. 首页积分要更大、更明显、高亮，让用户一眼知道自己有多少积分。
7. 底部导航需要包含“收藏”。
8. 中间“赚积分”要比其他 tab 更突出，但不使用橙色渐变和阴影。
9. 当前中间“赚积分”图标保持约 1.3 倍，文字样式与其他 tab 统一。
10. 首页一级分类不要铺太多，MVP 首页只保留 4 个一级分类。
11. 当前首页一级分类为：影视娱乐 / 学习办公 / 自媒体素材 / 软件工具。
12. “本地生活”暂不进入 MVP 首页一级分类，后续需要时再加。
13. 二级分类不放首页，后续放到分类页或筛选弹层。
14. 底部 tab 第一个继续保留“资源”，不改成“首页”。

## 8. 下一步建议执行顺序

建议下一步按以下顺序执行：

1. 用户重新编译并完整走查 `video-ts` 静态原型：
   - 首页搜索/筛选/分类/内容流。
   - 资源详情未解锁/已解锁展示。
   - 收藏与收藏页。
   - 求资源发布。
   - 赚积分任务中心。
   - 上传资源和审核状态。
   - 补链/投诉失效和审核状态。
   - 底部 tab 安全区和真机视觉。
2. 走查通过后，调用 `ai-qa-acceptance` 生成：

   ```text
   docs/qa/网盘资源互助MVP_测试清单与验收标准.md
   ```

3. 测试清单完成后，再进入后端资源域设计和开发，建议顺序：
   - 资源表。
   - 资源列表/详情接口。
   - 用户收藏接口。
   - 上传审核接口。
   - 获取资源扣积分接口。
   - 资源获取记录。
   - 求资源悬赏冻结/采纳/退回接口。
   - 投诉失效与补链接口。
   - 任务中心每日次数和奖励发放接口。
   - 后台资源审核与补链审核。
4. 最后再接支付、会员、邀请奖励、提现等高风险能力。

## 9. 新 Codex 会话接手时的第一条提示词

建议新会话第一条提示词如下：

```text
请先读取并遵循：
1. D:\Desktop\vedo-project\AGENTS.md
2. D:\Desktop\vedo-project\myproject\docs\handoff-latest.md

当前实际小程序工程：
D:\Desktop\vedo-project\video-ts

当前后端/文档仓库：
D:\Desktop\vedo-project\myproject

请先检查：
1. video-ts 的 git status
2. myproject 的 git status
3. video-ts 最近提交：
   - 7b163d5 feat: add netdisk repair mock flow
   - 586a4cc feat: add netdisk upload mock form
   - 6e7ac2b feat: refine earn points task center
   - 25dcf79 feat: add netdisk request publish mock
   - 181074b feat: add netdisk resource detail mock
   - 8674766 feat: refine netdisk home and favorites mock

当前任务背景：
用户正在确认“互助资源库”微信小程序静态原型。真实预览工程是 video-ts。当前已新增自定义 NetdiskTabBar，入口包括资源、求资源、赚积分、收藏、我的。首页、详情解锁、收藏、求资源发布、赚积分任务、上传资源、补链/投诉失效均已串联为 mock 静态闭环。

请不要修改后端业务代码，不要接真实接口，不要改支付/二级分销/提现逻辑。下一步优先根据用户反馈微调 video-ts 的 UI，尤其是：
1. src/components/NetdiskTabBar.vue
2. src/pages/netdisk/index.vue
3. src/pages/netdisk/mock.ts
4. src/pages/netdisk/detail.vue
5. src/pages/netdisk/earn.vue
6. src/pages/netdisk/upload.vue
7. src/pages/netdisk/repair.vue

注意：
video-ts 工作区有大量历史/用户未提交改动。提交时必须只暂存当前任务相关文件，不要回滚或覆盖其它改动。
```
