# 阶段性交接归档：悦享资源库 / crawler-worker / 上线前收口

更新时间：2026-06-14  
项目目录：`/Users/yiyi/Desktop/Desktop/vedo-project/myproject`  
当前分支：`feature/yuexiang-stage2-mvp`  
后端生产目录：`/opt/pythonvideo`  
服务器：`81.70.84.35`，用户 `ubuntu`，SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`

---

## 1. 项目背景与目标

当前项目从原视频下载 / 互动宝业务，转向 **悦享资源库 / 网盘资源互助 MVP**。

核心目标：

- 用户用积分获取网盘资源。
- 用户通过上传资源、补链、邀请、任务、小游戏等方式赚积分。
- 找不到资源时可以发布求资源 / 悬赏。
- 资源失效后可以投诉、补链、审核、隐藏、追缴，形成运营闭环。
- PC 后台服务运营人员，统一处理资源投诉、补链审核、反馈工单、积分异常、采集待审核。
- 爬虫采集负责持续补充资源库，但不能拖垮小程序主接口和后台主服务。

当前产品优先级：

```text
稳定资源库数据
  -> 稳定小程序资源获取 / 积分 / 反馈 / 支付链路
  -> 稳定采集 worker 和服务器兜底保护
  -> 清理旧代码、脏数据、重复资源
  -> 上线测试虚拟支付和真实用户路径
```

---

## 2. 当前阶段目标

当前阶段不是继续堆新页面，而是做上线前收口：

1. **crawler-worker 独立化和稳定化**
   - 当前已经是单独 Docker 容器，但仍在主仓库内。
   - 今天目标是继续把它做成更清晰的采集平台 / PC 可监控入口。
   - 重点是浏览器进程关闭、超时、失败隔离、手动重启、日志查看、导入兜底。

2. **服务器监控与进程关闭机制**
   - 防止 Chromium / Playwright / 爬虫任务残留导致内存和 swap 被占满。
   - 需要有主动清理、健康检查、任务超时、兜底重启策略。

3. **资源数据恢复与去重**
   - 昨天/今天发现 KDocs 历史资源被误隐藏。
   - 已恢复历史资源，并按唯一网盘链接隐藏重复数据。
   - 仍需要后续做更细的标题规范化去重和跨来源合并。

4. **本地、服务器、GitHub 仓库脏数据清理**
   - 本地仓库有大量未提交改动和未跟踪目录。
   - 用户倾向：系统稳定运行一周后，旧版和无用代码可以彻底删除。
   - 当前不要误删，先列清单、分类、再让用户确认。

---

## 3. 已完成的功能

### 3.1 小程序核心功能

已完成并经过用户多轮人工体验反馈：

- 首页资源展示、资源列表、资源详情。
- 我的页登录体验。
- 微信一键登录 / 静默登录。
- 我的收藏、我的上传独立页面入口。
- 积分明细页展示新增流水类型。
- 信用分展示与信用恢复说明。
- 我的上传增强：展示审核奖励、7 天有效奖励、失效 / 投诉状态。
- 充值积分页接入微信虚拟支付参数流。
- 支付页增加测试单、1 元测试套餐需求已进入后端。
- 猜拳小游戏奖励规则：
  - 赢了加分。
  - 输了扣分。
  - UI 展示输赢规则。
- 资源获取激励广告：
  - 获取网盘信息时触发激励广告。
  - 用户关闭广告后不再弹英文提示。
  - 广告不是“不看不给链接”的硬拦截；当前业务口径是看广告提升收益，但用户最终仍能拿链接。
- 首页、我的页、赚积分页的今日可赚积分展示做过多轮统一。
- 问题反馈 / 客服助手页面：
  - 聊天壳子的工单系统。
  - 资源问题、积分问题、上传资源问题、功能建议。
  - 最近工单状态和后台回复展示。
- 首页视觉优化：
  - 口号：“让每一份资源，都有价值”。
  - 快速入口图标化。
  - tabbar、首页卡片、我的页布局做过多轮微调。

仍需注意：

- 小程序前端有些改动还在本地未提交状态。
- 用户说“前端基本功能问题都解决了”，但 P0 上线支付仍需人工真机测试。

### 3.2 积分与信用体系

已落地的核心方向：

- 解锁资源扣积分。
- 上传者分成。
- 平台回收。
- 上传审核奖励。
- 7 天有效奖励规划。
- 失效处罚。
- 积分明细展示新增流水类型。
- 信用分影响排序、审核和风控，不是可消费积分。
- 信用恢复说明已前端展示：
  - 上传审核通过加信用。
  - 有效满 7 天恢复信用。
  - 补链通过恢复信用。
  - 投诉被驳回恢复信用。
  - 7 天内失效、7-30 天失效、30 天后失效按档扣信用。

仍需注意：

- 用户多次强调“总积分 / 可用积分 / 今日可赚”不能混乱。
- 今日可赚应按当天实际赚取每日清零，不应写死成固定已赚值。
- 充值成功、广告奖励、小游戏奖励、邀请奖励都必须统一刷新 Pinia/全局状态。

### 3.3 求资源 / 悬赏闭环

已完成并自测过 P0：

- 发布悬赏冻结积分。
- 上传者投稿。
- 采纳后转积分。
- 取消 / 过期退回。
- 重复采纳不能重复发分。

用户反馈：他本地暂时测试不了采纳；如果我方自测没问题，后续上线后由用户再测。

### 3.4 PC 后台运营能力

已完成：

- 运营看板首页化。
- 待处理中心。
- 侧边栏小红点 / 数量提示。
- 反馈工单处理。
- 资源投诉。
- 补链审核。
- 积分异常。
- 采集结果待审核池：
  - LinuxDo 低置信资源。
  - 疑似重复资源。
  - 新增网盘补充资源。
  - 一键通过 / 跳过 / 合并。
- 批量导入：
  - 导入记录列表。
  - 失败明细下载。
  - 成功 / 部分失败 / 失败状态。

用户确认：PC 端人工看过，基本没有大问题。

### 3.5 采集与资源入库

已完成：

- KDocs 影视剧 / 电影 / 4K 采集规则文档。
- LinuxDo 混合分类方案：
  - 规则库优先。
  - DeepSeek 兜底。
  - 高置信自动入库。
  - 低置信进入待审核池。
- 影视去重规则：
  - KDocs 官方同步资源优先。
  - LinuxDo 只补缺口。
  - 同链接 / 同标题重复默认跳过。
  - 同片名但新增网盘类型可作为补充。
- 影视积分规则：
  - 普通 / 更新中影视：5 分。
  - 完结 / 全集 / 合集 / 珍藏版：20 分。
- 资源卡增加上架时间字段。
- PC 文件导入作为长期兜底方案：
  - 本地采集 LinuxDo，导出 JSON/CSV。
  - PC 后台导入。
  - 后端去重、分类、入库或进待审核池。

### 3.6 服务器数据恢复与爬虫保护

2026-06-14 已完成紧急处理：

- 服务器因内存 / swap 占满变慢，用户从云控制台重启。
- 重启后先停止 crawler-worker，排查日志。
- 日志显示主要是 KDocs Playwright / Chromium 启动或跳转超时，不是 LinuxDo。
- 修复浏览器清理机制：
  - worker 启动时清理浏览器残留。
  - worker 关闭时清理。
  - 每次任务结束后清理。
  - 不再只依赖 `pgrep`，增加 `/proc` 扫描兜底。
  - KDocs / LinuxDo 浏览器启动超时改为 45 秒。
- 修复 KDocs 同步误隐藏历史资源：
  - KDocs 每次只同步最新一小段，不能把没同步到的历史资源当作已删除。
  - 已取消这类误隐藏逻辑。
- 恢复历史资源并去重：
  - 原始资源表：`10904` 条。
  - 恢复后前台可见：`2152` 条。
  - 隐藏重复数据：`8752` 条。
  - 当前 `/netdisk/resources` 返回总数：`2152`。
- 当前服务器状态：
  - `video-service-app` healthy。
  - `video-service-crawler-worker` healthy。
  - `video-service-postgres` healthy。
  - `video-service-redis` healthy。
  - worker 健康检查：`browser_processes=0`。

服务器当前部署版本：

```text
6cd7093 fix: reduce crawler browser launch timeout
```

相关提交：

```text
8f1990e fix: harden crawler worker and restore kdocs resources
be19d79 fix: avoid crawler worker memory limit conflict
647a32c fix: keep crawler worker compose limits compatible
6cd7093 fix: reduce crawler browser launch timeout
```

---

## 4. 已修改 / 新增的文件

### 4.1 最近已提交并部署的关键文件

```text
controllers/admin.py
controllers/vip.py
core/browser_guard.py
core/kdocs_service.py
docker-compose.yml
scripts/crawler_worker.py
services/netdisk_resource_service.py
services/sync_service.py
services/linuxdo_resource_service.py
```

核心作用：

- `core/browser_guard.py`
  - 增加浏览器进程统计和清理。
  - 增加 `/proc` 兜底扫描。
- `scripts/crawler_worker.py`
  - worker 启动 / 关闭 / 任务结束后清理浏览器。
  - `/health` 返回 `browser_processes`。
- `core/kdocs_service.py`
  - 关闭 page/context/browser 更稳。
  - 缩短 Chromium 启动超时。
- `services/linuxdo_resource_service.py`
  - 缩短 Chromium 启动超时。
- `services/sync_service.py`
  - KDocs 同步不再误隐藏历史资源。
- `services/netdisk_resource_service.py`
  - 增加恢复隐藏 KDocs 资源并按链接去重的能力。
- `controllers/admin.py`
  - 增加恢复隐藏 KDocs 资源的后台接口。
- `controllers/vip.py`
  - 增加 1 元 / 10 积分套餐。

### 4.2 采集 worker 文档

```text
docs/crawler-worker/README.md
docs/crawler-worker/采集规则说明.md
docs/crawler-worker/PC导入与服务器入库流程.md
docs/crawler-worker/故障处理.md
docs/crawler-worker/后续拆仓建议.md
```

### 4.3 当前本地未提交改动

当前本地 `git status --short` 显示还有这些未提交 / 未跟踪内容，接手前必须先确认，不要误删：

```text
 M controllers/game.py
 M controllers/netdisk.py
 M miniprogram-netdisk/package.json
 M miniprogram-netdisk/src/App.vue
 M miniprogram-netdisk/src/pages.json
 M miniprogram-netdisk/src/pages/home/index.vue
 M miniprogram-netdisk/src/pages/messages/index.vue
 M miniprogram-netdisk/src/pages/mine/index.vue
 M miniprogram-netdisk/src/pages/resources/detail.vue
 M miniprogram-netdisk/src/pages/resources/list.vue
 M miniprogram-netdisk/src/utils/api.ts
 M schemas/game.py
 M schemas/mine.py
 M schemas/netdisk.py
 M scripts/verify_game_ad_flow.py
 M services/game_task_service.py
 M services/mine_assets_service.py
 M services/points_summary_service.py
?? docs/handoff-latest-1.md
?? docs/qa/猜拳小游戏奖励规则_Codex自测报告.md
?? docs/qa/猜拳小游戏奖励规则_测试清单与验收标准.md
?? docs/qa/猜拳小游戏奖励规则_验收报告.md
?? docs/qa/积分广告反馈解锁收尾回归_验收报告.md
?? docs/qa/资源列表筛选与广告提示中文化_Codex自测报告.md
?? docs/qa/资源获取激励广告_Codex自测报告.md
?? docs/qa/资源获取激励广告_测试清单与验收标准.md
?? linuxdo_resource_crawler/
?? miniprogram-netdisk/pnpm-lock.yaml
?? miniprogram-netdisk/pnpm-workspace.yaml
?? miniprogram-netdisk/src/pages/favorites/
?? miniprogram-netdisk/src/pages/points/
?? miniprogram-netdisk/src/pages/uploads/
?? test- python/
```

说明：

- 这些改动大多来自小程序前端、小游戏、广告、积分同步、反馈页、LinuxDo 本地脚本等阶段。
- 不要直接 `git reset` 或删除。
- 今天清理脏数据时，应先把它们分类成：
  - 必须保留并提交。
  - 可以归档但不进入主流程。
  - 旧版 / 重复 / 废弃，等用户确认后删除。

---

## 5. 当前代码状态

### 5.1 Git 状态

- 当前分支：`feature/yuexiang-stage2-mvp`
- 最近生产部署提交：`6cd7093`
- 服务器已拉取并运行该提交。
- 本地仍有大量未提交改动。
- 用户明确规则：不要自动提交，除非他说“提交”。
- 用户此前已多次要求提交并推送过，最近一次服务器修复已提交并部署。

### 5.2 服务器状态

生产目录：

```text
/opt/pythonvideo
```

当前容器：

```text
video-service-app
video-service-crawler-worker
video-service-postgres
video-service-redis
```

当前健康状态：

- app healthy。
- crawler-worker healthy。
- postgres healthy。
- redis healthy。
- crawler-worker `/health` 返回 `browser_processes=0`。

注意：

- 服务器上还有一个僵尸 Chromium 进程，但它属于另一个容器 `backend-girl-app-1`，不是当前悦享资源库 worker。
- 它本身不消耗内存，但会导致系统提示有 1 个 zombie process。
- 如果要清理，需要重启 `backend-girl-app-1`，但这可能影响另一个旧项目，尚未执行。

### 5.3 数据状态

资源表当前重点数据：

```text
总资源行数：10904
前台可见：2152
隐藏重复：8752
```

去重口径：

- 当前紧急恢复按唯一网盘链接去重。
- `source_type=kdocs` 的重复数据大量存在，但已隐藏。
- 后续还需要做标题规范化去重、同片名多网盘合并、LinuxDo 与 KDocs 跨来源合并。

---

## 6. 已知问题和风险

### 6.1 爬虫 worker 仍需加强

已修复基础清理，但今天仍建议继续做：

- 任务级超时控制。
- 浏览器进程数量上限。
- 内存 / swap 监控。
- 连续失败自动熔断。
- 失败后自动关闭浏览器。
- PC 后台展示 worker 状态、最后任务、失败日志、浏览器进程数。
- 一键停止 / 重启 worker。

### 6.2 crawler-worker 还没有真正拆成独立平台

当前状态：

- 已经是单独 Docker 容器。
- 仍在主项目仓库里。
- 仍复用主项目数据库模型和服务。

用户最新倾向：

- 今天争取把 crawler-worker 爬虫平台独立出去。
- 如果来不及拆仓，也可以先做成 PC 端平台，方便监控处理。
- 后续其他项目也要复用爬虫能力。

建议：

- 先做“逻辑独立 + PC 监控 + 稳定兜底”。
- 等稳定运行一周后，再考虑单独 Git 仓库。

### 6.3 虚拟支付仍需上线真机测试

已做过多次调参，但微信虚拟支付返回过：

- `15001`
- `15005`
- `15006`
- `15009`
- `15011`
- 错误码 `4`，App Store 暂无法完成充值

用户判断：

- 可能与当前测试环境 / 手机 / App Store 状态有关。
- 先上线，用其他手机继续测试。

已确认需求：

- 支付套餐选中态要明显。
- 新增 `1元 = 10积分` 测试套餐。
- 测试单 / 低价测试保留。

风险：

- 支付成功回调、重复回调、失败不发积分、积分流水一致性仍是 P0。

### 6.4 积分显示一致性仍是高风险

用户多次指出：

- 首页 / 我的 / 赚积分 的 `今日可赚 x/60` 必须一致。
- 今日已赚每天清零，并根据真实奖励增加。
- 可用积分、总积分、冻结积分要清楚，不要互相混淆。
- 解锁时提示积分不足，必须用后端真实可用积分判断。

接手后必须重点回归：

- 充值成功后首页 / 我的 / 赚积分同步刷新。
- 游戏奖励后同步刷新。
- 广告奖励后同步刷新。
- 邀请奖励后同步刷新。
- 解锁扣分后同步刷新。

### 6.5 前端仍有未提交改动

本地小程序有大量未提交前端改动，包括：

- 首页视觉。
- 我的页视觉。
- 资源详情广告提示。
- 支付页选中态。
- 反馈页。
- 积分同步。
- 资源列表筛选。

清理前必须先确认哪些是用户已经满意的最新版。

### 6.6 资源重复数据仍需更细治理

已隐藏 8752 条重复链接数据，但还不代表彻底干净：

- 同资源不同链接需要合并为多网盘资源。
- 同标题不同画质 / 标点 / 更新集数需要规范化判断。
- KDocs 和 LinuxDo 跨来源重复需要继续治理。
- 历史 1 万条里大概率仍有标题重复，只是链接不同或格式不同。

---

## 7. 用户已经确认过的产品 / 技术决策

### 7.1 产品方向

- 悦享资源库是核心，不再继续扩展旧版视频下载系统。
- 旧版可以等系统稳定一周后清理删除。
- 产品重点是商业闭环：积分、资源、广告、充值、邀请、悬赏、反馈。
- 用户更关心闭环和变现，不希望过度架构。

### 7.2 积分与信用

- 信用分不是可消费积分。
- 信用分影响排序、审核和风控。
- 信用分不能比积分更抢眼。
- 资源卡上要显示上传者信用相关标识。
- 信用恢复规则要让用户看得懂，表格展示比长文好。

### 7.3 广告

- 获取网盘资源时触发激励广告。
- 给过 5 个广告 ID：
  - `adunit-0eae76b6a64cabbb`
  - `adunit-5983ee0404c414fc`
  - `adunit-c08be6f761c3b0a7`
  - `adunit-a921c4e0383a451f`
  - `adunit-7c61b0922792ddc9`
- 激励广告 ID 需要每个实例化，不要做成简单插件。
- 用户关闭广告时不要弹英文提示。
- 资源链接最终仍要展示，不要因为广告关闭导致拿不到链接。

### 7.4 采集

- KDocs 是影视资源主来源。
- LinuxDo 是补充来源。
- LinuxDo 国内服务器可能访问不了，可以本地采集后通过 PC 后台导入。
- PC 文件导入是长期方案，不是临时补丁。
- 影视剧：
  - 完结 / 全集 / 合集等 20 分。
  - 普通更新中 5 分。
- KDocs 文档不能简单取前 20 条，要尽量识别日期。
- 如果最新日期只有 10 条，就同步 10 条，不补旧数据。
- 每次采集后必须关闭浏览器，不能让服务器被拖死。

### 7.5 crawler-worker

- 用户希望 crawler-worker 独立出去，以后其他项目也复用。
- 当前可以先做 PC 端监控平台，方便运营/维护。
- 服务器 Docker 中 crawler-worker 应该是单独容器。
- PC 后台不应该因为爬虫需求而安装 Chromium。

### 7.6 反馈 / 客服

- 不做聊天客服。
- 做“聊天壳子的工单系统”。
- 用户提交 -> 记录 -> 后台处理 -> 状态反馈。
- PC 后台处理后，小程序最近工单要显示回复内容和状态。

---

## 8. 下一步建议执行顺序

### 第一步：先做服务器与 crawler-worker 稳定性收口

目标：不能再出现浏览器残留把服务器拖死。

建议任务：

1. 增加 worker 任务运行表或状态文件：
   - 当前任务。
   - 开始时间。
   - 超时时间。
   - 最后成功时间。
   - 最后失败原因。
   - 浏览器进程数。
2. 增加任务级超时和熔断：
   - 单任务超时自动失败。
   - 连续失败 N 次暂停该来源。
3. 增加浏览器进程硬上限：
   - 超过阈值自动清理。
   - 清理失败则重启 worker。
4. PC 后台增加 crawler-worker 监控入口：
   - 健康状态。
   - 浏览器进程数。
   - 最近任务。
   - 最近错误。
   - 一键清理浏览器。
   - 一键重启 worker。
5. 增加服务器侧兜底脚本或 cron：
   - 检查 Chromium 残留。
   - 检查 swap / memory。
   - 超阈值记录日志并重启 worker。

### 第二步：梳理本地脏文件清单

目标：不要让旧代码和未提交改动继续混淆。

建议输出三张表：

| 类型 | 处理建议 |
|---|---|
| 必须保留并提交 | 用户已确认的最新前端/后端能力 |
| 暂时归档 | 本地脚本、测试文件、迁移辅助 |
| 等稳定一周后删除 | 旧版、重复、废弃功能 |

禁止直接删除。

### 第三步：修小程序上线前 P0 体验点

优先修：

- 支付套餐选中态加粗、加底色。
- 资源解锁广告关闭后不要出现英文 toast。
- 首页 / 我的 / 赚积分 `今日可赚 x/60` 统一从后端或 Pinia 刷新。
- 可用积分 / 总积分 / 冻结积分口径统一。
- 解锁积分不足判断必须以后端真实可用积分为准。

### 第四步：资源去重与导入治理

继续做：

- 标题规范化去重。
- 同片名多网盘合并。
- KDocs / LinuxDo 跨来源重复过滤。
- 采集候选待审核池支持批量合并。
- 导入记录保留失败明细。

### 第五步：上线测试虚拟支付

用户准备上线后用其他手机测试。

必须回归：

- 支付成功到账。
- 支付失败不发积分。
- 重复回调不重复发积分。
- 积分明细有充值流水。
- 首页 / 我的 / 赚积分同步刷新。

---

## 9. 新 Codex 会话接手时的第一条提示词

请把下面这段直接发给新 Codex 会话：

```text
请先读取：
1. /Users/yiyi/Desktop/Desktop/vedo-project/AGENTS.md
2. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/handoff-latest-1.md
3. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/crawler-worker/README.md
4. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/crawler-worker/故障处理.md
5. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/crawler-worker/采集规则说明.md

然后先不要改代码，先执行：
1. 查看 myproject 的 git status 和最近提交。
2. 检查服务器 /opt/pythonvideo 当前容器状态、app 健康、crawler-worker 健康、browser_processes。
3. 输出当前你理解的项目目标、已完成内容、当前风险、下一步执行顺序。

接下来优先做：
1. crawler-worker 爬虫平台独立化/监控化。
2. 服务器浏览器进程关闭和兜底重启机制。
3. 本地、服务器、GitHub 仓库脏数据清单整理。

注意：
- 不要直接删除旧代码。
- 不要重置 git。
- 不要泄露 .env 或密钥。
- 涉及生产数据库删除/清空/重置必须先确认。
- 当前重点是稳定上线前收口，不要继续发散新功能。
```

