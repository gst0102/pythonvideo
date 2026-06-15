# 阶段性交接归档：悦享资源库上线前收口与运营后台增强

更新时间：2026-06-15 09:15（北京时间）  
主项目根目录：`/Users/yiyi/Desktop/Desktop/vedo-project`  
后端仓库：`/Users/yiyi/Desktop/Desktop/vedo-project/myproject`，分支 `feature/yuexiang-stage2-mvp`  
小程序仓库：`/Users/yiyi/Desktop/Desktop/vedo-project/video-ts`，分支 `feature/yuexiang-stage2-mvp`  
PC 后台仓库：`/Users/yiyi/Desktop/Desktop/vedo-project/adminVideo`，分支 `main`  
服务器：`ubuntu@81.70.84.35`  
SSH key：`/Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem`  
后端生产目录：`/opt/pythonvideo`  
PC 后台生产目录：`/opt/pc-frontend`  
生产 API：`https://api.lifelove.top`  
PC 后台：`https://admin.lifelove.top`

---

## 1. 项目背景与目标

当前项目已经从早期视频下载 / 互动宝方向，收敛为 **悦享资源库 / 网盘资源互助 MVP**。

核心目标：

- 用户用积分解锁网盘资源。
- 用户通过签到、小游戏、邀请、充值、上传资源、补链、反馈共建等路径获得积分。
- 运营侧通过 PC 后台处理资源审核、采集入库、用户反馈、积分异常、充值订单、资源删除、追更订阅等事项。
- 资源库通过 KDocs、LinuxDo、本地 CSV/JSON 导入等方式持续补充。
- 上线前优先保证：积分一致、支付到账、资源可获取、订阅追更可排查、后台可运营。

重要仓库说明：

- **小程序只使用 `video-ts`。**
- 旧目录 `myproject/miniprogram-netdisk` 已被用户明确否定，不要再往里面改。
- 旧实验目录、旧包、旧静态产物不要重新引入主流程。

---

## 2. 当前阶段目标

当前阶段是 **小程序审核 / 上线前 P0-P1 收口**，不是大规模重构。

优先级顺序：

1. P0：支付到账、积分流水、签到、小游戏、邀请返利、后台统计一致。
2. P0：资源解锁、资源复制、订阅消息授权、资源更新推送可验证。
3. P1：PC 后台运营闭环，包括用户看板、充值订单、反馈奖励、采集待审核池、资源删除、资源订阅管理。
4. P1：资源数据质量，包括重复清理、隐藏资源解释、未完结更新标签、今日更新口径。
5. P2：小程序分享图、邀请页、积分到账动效、签到动效、文案 polish。

用户偏好：

- 快速 MVP，先让系统跑通。
- 商业闭环优先，不要过度架构。
- 解释要直接，少空话。
- 涉及积分、支付、邀请、分销时必须按 P0 风险处理。

---

## 3. 已完成的功能

### 3.1 小程序端

已完成并经过多轮真机 / 体验版反馈：

- 首页资源展示、今日精选、资源总数、今日更新数展示逻辑。
- 资源列表筛选：网盘、标签、分类、时间、积分排序。
- “未完结更新”标签已恢复，后端筛选兼容 `未完结更新`、`未更新完结`、`更新中`。
- 资源详情页：
  - 解锁积分提示优化为用户能看懂的文案。
  - 复制资源链接后接入一次性订阅消息授权。
  - 订阅模板使用老番剧 / 影视更新同类模板。
- 我的页：
  - 可用积分、总积分、待验证积分等展示多轮修正。
  - 我的收藏、我的上传、补链记录入口。
- 赚积分任务中心：
  - 已接真实后端任务状态。
  - 签到、小游戏按钮状态不再完全写死。
  - 今日可赚分子已改为动态口径，签到 +1 后应显示 1/60，小游戏继续加分后累加。
- 签到：
  - 普通用户签到 +1 分。
  - 会员签到 +2 分。
  - 会员标准目前按用户会员状态，不是“充值一次即会员”。
- 小游戏：
  - 石头剪刀布。
  - 今日次数当前保留 10 次，后续可接 PC 后台配置。
  - 文案已调整为更直接的输赢积分规则。
  - 积分流水中英文开发味文案已清理过。
- 充值积分：
  - iOS 端已实际测试成功。
  - 支付成功后积分已到账。
  - 订单时间口径已修正为北京时间。
- 邀请：
  - 邀请页不展示邀请码，改为“分享邀请链接，自带邀请关系”。
  - 一级返利 50%，二级返利 5% 的规则已讨论并确认。
  - 固定邀请奖励与充值返利不冲突：固定奖励偏拉新，返利偏后续充值激励。
- 共建反馈：
  - 新增“悦享共建计划”页面。
  - 首页接入共建入口 / banner。
  - 奖励规则改为更短、更清晰的积分奖励池规则。

### 3.2 后端

已完成并部分部署验证：

- 积分账户统一口径：可用积分用于解锁资源、发悬赏、小游戏、功能消费等；不再强调“可提现积分”。
- 充值订单：
  - PC 后台充值订单页。
  - 商户订单号、微信/苹果单号、用户、金额、套餐、订单状态、积分到账、到账流水、支付时间。
  - 支付时间按北京时间展示。
  - 重复回调幂等已重点处理，用户后续测试两笔到账正常。
- 签到、小游戏、支付、邀请返利专项验证脚本多次调整。
- 反馈工单奖励：
  - 后台处理反馈时可填写奖励积分。
  - 只有处理为 `resolved` 且奖励大于 0 才发可用积分。
  - 使用 `feedback_reward:{feedback.id}` 做幂等，避免重复发放。
  - 反馈表记录 `reward_points`、`reward_ledger_id`。
- 资源订阅推送：
  - 已有资源订阅表 `netdisk_resource_subscriptions`。
  - 新增推送记录表 `netdisk_resource_subscription_push_logs`。
  - 推送成功 / 失败 / 跳过都会写入记录。
  - 失败原因包括：微信 access_token 不可用、缺少模板 ID、缺少 openid、微信接口返回错误、请求异常。
  - 推送成功后订阅状态从 `accept` 改为 `sent`，符合微信一次授权一次推送的限制。
- 资源时间口径：
  - 资源列表的今日、昨天、今日更新等口径改为北京时间。
  - 后台订阅相关时间也改为北京时间字符串。
- 采集去重：
  - 同链接旧逻辑从“直接跳过”调整为可更新主资源标题，避免“上周 201、本周 202、链接一样但标题不更新”的问题。
  - KDocs 历史资源误隐藏逻辑已处理过。
- 资源删除：
  - PC 后台资源库增加“删除”按钮。
  - 当前是安全隐藏 `is_active=false`，不是物理删除。
  - 隐藏后小程序不展示，可从隐藏资源恢复。
- 隐藏重复资源清理：
  - PC 后台已有“清理隐藏重复资源”预览和执行能力。
  - 只清理隐藏且同链接已有可见主资源的重复记录。
  - 有收藏、解锁、投诉、质量记录等关联的数据受保护。
- CSV/JSON 导入：
  - 支持本地爬虫 / LaunchAgent 每天定时上传资源数据到后端。
  - 已生成过给 agent 使用的接口文档。

### 3.3 PC 后台

已完成并部署：

- 用户看板：
  - 用户列表、搜索、用户详情、积分明细。
  - 支持管理员给用户新增积分 / 消耗积分。
- 运营看板：
  - 今日新增用户、今日发放积分、今日消耗积分、当前可用积分、隐藏资源等。
  - 已修正积分指标口径，不再把错误的大额调整长期混入展示。
- 充值订单：
  - 订单列表、支付时间、到账流水。
- 规则配置：
  - 邀请返利配置入口。
  - 任务 / 小游戏部分配置正在逐步接入。
  - 共建计划配置入口。
- 采集待审核池：
  - 待审核资源列表。
  - 单条通过、跳过、合并。
  - 批量处理 / 全部匹配处理。
  - 文件导入、导入批次、失败明细下载。
- 资源库：
  - 列表展示资源标题、链接、网盘、提取码、解压码、积分、状态。
  - 删除 / 恢复。
  - 清理隐藏重复资源。
- 反馈工单：
  - 处理反馈、回复用户。
  - 支持填写奖励积分，发放后展示奖励。
- 追更订阅：
  - 新增菜单 `追更订阅`。
  - 地址：`https://admin.lifelove.top/resource-subscriptions`
  - 可查看订阅用户、资源、授权状态、订阅次数、最近授权、最近推送。
  - 可查看推送记录、成功 / 失败 / 跳过、错误码、失败原因、模板 ID。

### 3.4 部署与生产验证

最近已部署：

- 后端镜像：`pythonvideo-app:stage2-codex-20260615-subscriptions-bjtime`
- PC 后台镜像：`pc-frontend-admin:latest`

生产容器状态最近验证：

- `video-service-app`：healthy
- `video-admin`：running

最近验证过的接口：

- `GET /admin/netdisk/resource-subscriptions?page=1&page_size=5`
- `GET /admin/netdisk/resource-subscription-push-logs?page=1&page_size=5`
- `https://admin.lifelove.top/resource-subscriptions` 返回 200

当前生产订阅数据观察：

- 目前有 1 条订阅。
- 用户 openid：`oFK2h6y0soeRkA6GkiCGo1kQHXz4`
- 资源：`灵魂摆渡·十年.1080P更 24【超前完结】`
- 微信授权状态：`reject`
- 说明：该用户这次没有允许订阅，所以不会触发追更推送。
- 推送记录目前为空，因为新推送记录表是本次部署后开始记录，历史失败不会补录。

---

## 4. 已修改 / 新增的文件

下面是当前本地工作区仍显示为脏文件的清单。注意：其中包含多轮已部署但未提交的改动，不要随意回退。

### 4.1 后端 `myproject`

当前分支：`feature/yuexiang-stage2-mvp`

已修改：

```text
controllers/admin.py
controllers/netdisk.py
models/__init__.py
models/netdisk_feedback.py
schemas/netdisk.py
scripts/verify_checkin_ad_bonus_flow.py
scripts/verify_checkin_flow.py
scripts/verify_game_settlement_flow.py
scripts/verify_invite_rebate_flow.py
scripts/verify_payment_refund_flow.py
services/checkin_service.py
services/commission_service.py
services/config_service.py
services/game_settlement_service.py
services/linuxdo_resource_service.py
services/netdisk_resource_service.py
services/payment_service.py
services/points_account_service.py
services/resource_classification_service.py
services/sync_service.py
```

新增未跟踪：

```text
migrations/versions/018_netdisk_resource_subscriptions.py
migrations/versions/025_netdisk_feedback_rewards.py
migrations/versions/026_netdisk_subscription_push_logs.py
models/netdisk_resource_subscription.py
models/netdisk_resource_subscription_push_log.py
scripts/verify_feedback_reward_flow.py
services/netdisk_subscription_push_service.py
```

这些新增文件不是垃圾文件，属于当前业务功能：

- `018`：资源订阅表。
- `025`：反馈奖励字段。
- `026`：订阅推送记录表。
- `netdisk_resource_subscription.py`：资源订阅模型。
- `netdisk_resource_subscription_push_log.py`：推送记录模型。
- `netdisk_subscription_push_service.py`：资源更新订阅消息推送服务。
- `verify_feedback_reward_flow.py`：反馈奖励幂等验证脚本。

### 4.2 小程序 `video-ts`

当前分支：`feature/yuexiang-stage2-mvp`

已修改：

```text
src/api/request.ts
src/components/GameZone.vue
src/pages.json
src/pages/mine/mine.vue
src/pages/netdisk/detail.vue
src/pages/netdisk/earn.vue
src/pages/netdisk/favorites.vue
src/pages/netdisk/feedback.vue
src/pages/netdisk/index.vue
src/pages/netdisk/invite.vue
src/pages/netdisk/mine.vue
src/pages/netdisk/points-detail.vue
src/pages/netdisk/resource-list.vue
src/pages/netdisk/signin.vue
src/pages/netdisk/upload.vue
src/types/index.d.ts
```

新增未跟踪：

```text
src/pages/netdisk/co-build.vue
src/static/share-invite.png
```

这些改动包含：

- 共建计划页面。
- 资源详情订阅授权入口。
- 资源列表今日更新 / 标签 / 数量展示。
- 赚积分任务真实状态。
- 小游戏页面与文案。
- 邀请返利页面文案和分享图。
- 积分流水展示清理。

### 4.3 PC 后台 `adminVideo`

当前分支：`main`

已修改：

```text
src/layout/index.vue
src/router/index.ts
src/utils/api.ts
src/views/netdisk/collected-resources.vue
src/views/netdisk/config.vue
src/views/netdisk/feedbacks.vue
src/views/netdisk/resources.vue
```

新增未跟踪：

```text
pnpm-workspace.yaml
src/views/netdisk/resource-subscriptions.vue
```

这些改动包含：

- 追更订阅菜单和页面。
- 资源订阅 / 推送记录 API 封装。
- 资源库删除 / 恢复。
- 采集待审核池批量操作。
- 共建计划配置。
- 反馈奖励处理。

---

## 5. 当前代码状态

### 5.1 Git 状态

三个仓库当前都有未提交改动：

- `myproject`：后端多轮业务改动、迁移、验证脚本仍未提交。
- `video-ts`：小程序多轮体验优化仍未提交。
- `adminVideo`：PC 后台多轮运营功能仍未提交。

用户之前已经多次说过“可以提交 / push / 继续开发”，但当前时点这些最新改动仍处于本地脏状态。新会话接手时不要直接 reset，也不要删除这些文件。

### 5.2 部署状态

本地未提交不代表未部署。最近一批后端与 PC 后台改动已同步并部署到生产：

- 后端已部署到 `/opt/pythonvideo`。
- PC 后台已部署到 `/opt/pc-frontend`。
- 数据库迁移 `026_netdisk_subscription_push_logs` 已在生产执行成功。

### 5.3 最近验证结果

已通过：

```text
后端：python3 -m py_compile 相关服务、模型、控制器
PC：./node_modules/.bin/vue-tsc --noEmit
PC：./node_modules/.bin/vite build
生产：订阅列表接口 200
生产：推送记录接口 200
生产：PC 追更订阅页面入口 200
生产：video-service-app healthy
生产：video-admin running
```

注意：

- 本地 `pnpm exec vue-tsc --noEmit` 曾被 pnpm 构建脚本白名单拦截，改用 `./node_modules/.bin/vue-tsc --noEmit` 后通过。
- 本地没有全局 `alembic` 命令，迁移验证放在服务器 Docker 容器里执行。

---

## 6. 已知问题和风险

### 6.1 P0 风险

1. **积分链路必须继续回归**
   - 用户多次遇到“积分不到账 / 前端显示不一致”。
   - 重点回归：签到、小游戏、充值、反馈奖励、邀请返利、积分流水、我的页可用积分、运营看板统计。

2. **支付链路仍需生产真机抽测**
   - iOS 已有成功付款并到账案例。
   - 仍需继续确认：重复回调、失败不发放、pending 补单、北京时间订单展示。

3. **订阅推送真实触发还未完成最终闭环**
   - 后台管理页和失败记录已完成。
   - 生产当前唯一订阅状态是 `reject`，无法验证真实推送送达。
   - 需要用户或测试号重新点资源复制并允许订阅，再模拟资源标题更新，确认收到老番剧模板推送。

4. **当前大量改动未提交**
   - 已部署但未提交会影响后续追踪。
   - 建议下一步优先整理提交，至少按后端、小程序、PC 后台拆批。

### 6.2 P1 风险

1. **资源今日更新口径**
   - 后端已改为北京时间。
   - 当前“今日新入库”和“今日验证更新”没有完全拆开，用户表示这块暂时问题不大。

2. **未完结更新标签数据量**
   - 标签筛选已恢复。
   - 若仍显示 0，应检查数据表 `tags` 字段里是否真的有 `未完结更新 / 未更新完结 / 更新中`。

3. **采集导入数据质量**
   - 用户要求过滤影视剧、不完整、求助、失效、无链接等内容。
   - 后续如果扩大导入，需要继续确认分类规则和低置信待审核策略。

4. **PC 后台权限**
   - 一些高危操作依赖 `X-Admin-Role: supervisor`。
   - 前端登录角色切换 / 权限显示需要继续确认真实运营习惯。

### 6.3 P2 风险

1. 分享海报、邀请页视觉还有继续优化空间。
2. 积分到账动效、签到动效未作为当前最高优先级全部完成。
3. PC 后台大屏统计和图表还可以继续 polish。

---

## 7. 用户已经确认过的产品 / 技术决策

### 7.1 产品决策

- 小程序主仓库是 `video-ts`，不要再改 `miniprogram-netdisk`。
- 上线前可以先清理明显游离内容，不采用“稳定一周后再删”的旧规则。
- 资源删除在 PC 后台需要有，当前采用隐藏下架，后续必要时再做物理删除。
- 资源说明不要写“资源采集来源”等后台味内容，用户只需要知道解锁要多少分。
- “可提现积分”概念暂不作为产品主线，统一改为“可用积分”。
- 退款功能暂时不做，不是当前需求场景。
- 提现接口可以保留，但当前积分主要用于站内消费，不是给用户提现吗。
- 邀请页不展示邀请码，用户分享链接自动带邀请码。
- 邀请返利：
  - 一级 50%。
  - 二级 5%。
  - 返的是支付金额对应积分 / 充值积分价值，不是现金。
  - 固定拉新奖励和充值返利不冲突。
- 小游戏次数保持 10 次，后续接 PC 后台配置。
- 签到规则：
  - 普通用户 +1 分。
  - 会员 +2 分。
- 资源订阅：
  - 复制资源链接时顺手申请一次订阅授权。
  - 微信订阅只能一次授权一次推送，所以每次复制都可再次引导授权。
  - 订阅弹窗不能完全无提示，这是微信限制；可放在复制链接动作里。
- 未完结更新标签需要保留。
- 今日更新为 0 时要优先查接口和北京时间口径。
- 共建反馈奖励规则采用短规则 / 表格形式，不要大段文字。

### 7.2 技术决策

- PC 后台 `admin.lifelove.top` 指向 `video-admin:8081`。
- 服务器 Nginx 由公网域名转发到 PC 后台容器。
- 后端容器名：`video-service-app`。
- PC 后台容器名：`video-admin`。
- KDocs / LinuxDo 采集平台先在现有服务上做运营入口，不另开新域名。
- LinuxDo 因服务器无 VPN，用户倾向本地采集后上传到服务器。
- 本地定时上传可用 LaunchAgent 调用后端导入接口。
- 资源更新推送使用微信老番剧模板同类型模板。
- 推送记录从部署后开始记录，不补历史。
- 所有业务时间口径必须使用北京时间。

---

## 8. 下一步建议执行顺序

### 8.1 立即做

1. **整理并提交当前三仓改动**
   - 后端一批：积分 / 反馈奖励 / 资源订阅 / 资源导入 / 资源删除。
   - PC 一批：用户看板、反馈奖励、资源库、采集池、规则配置、追更订阅。
   - 小程序一批：资源详情订阅、共建页、赚积分、邀请页、资源列表和文案清理。
   - 提交前先 `git diff` 快速确认没有旧实验文件、密钥、无关产物。

2. **做一次生产 P0 回归**
   - 登录。
   - 签到到账。
   - 小游戏赢 / 输 / 平积分流水。
   - 充值 1 元测试到账。
   - 邀请返利流水。
   - 我的页积分与 PC 用户详情一致。
   - 运营看板积分统计大方向一致。

3. **做订阅真实触发验证**
   - 用真机进入资源详情。
   - 点击复制资源链接。
   - 微信弹出订阅授权时点允许。
   - 后台 `追更订阅` 应看到该记录 `accept`。
   - 模拟资源标题更新。
   - 确认收到订阅消息。
   - 后台 `推送记录` 应出现 `成功` 或明确失败原因。

### 8.2 然后做

4. **资源数据质量收口**
   - 检查 `未完结更新` 标签实际数据。
   - 检查隐藏资源数量和原因。
   - 对明显失效 / 无链接 / 求助 / 重复数据继续清理。

5. **PC 后台运营体验补齐**
   - 资源删除操作增加更清晰的筛选：隐藏、失效、低质量、重复。
   - 用户详情增加更好看的积分流水 / 充值 / 邀请关系入口。
   - 订阅页后续可增加“按资源看订阅人数”和“最近失败原因排行”。

6. **小程序审核前 polish**
   - 邀请海报、分享图、分享文案。
   - 签到 / 积分到账动效。
   - 清理所有用户可见的后台味、开发味文案。

### 8.3 暂不建议做

- 暂不做退款入口，用户已明确暂无该需求场景。
- 暂不做提现产品闭环，当前积分定位是站内可用积分。
- 暂不重构采集平台为完整独立系统，先保持能采、能导、能审、能监控。

---

## 9. 新 Codex 会话接手时的第一条提示词

建议复制下面整段给新 Codex：

```text
请先读取并遵守：
1. /Users/yiyi/Desktop/Desktop/vedo-project/AGENTS.md
2. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/handoff-latest-2.md
3. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/project-memory.md
4. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/decisions.md
5. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/pitfalls.md
6. /Users/yiyi/Desktop/Desktop/vedo-project/myproject/docs/dev-log.md

注意：
- 小程序仓库只用 /Users/yiyi/Desktop/Desktop/vedo-project/video-ts，不要再改 miniprogram-netdisk。
- 后端仓库是 /Users/yiyi/Desktop/Desktop/vedo-project/myproject。
- PC 后台仓库是 /Users/yiyi/Desktop/Desktop/vedo-project/adminVideo。
- 三个仓库当前都有已部署但未提交的脏改动，禁止 reset、checkout、删除这些业务文件。
- 先查看三个仓库的 git status 和 git diff，整理当前改动分批提交建议。
- 当前优先任务是：提交当前已部署改动，然后做生产 P0 回归，特别是积分、支付到账、签到、小游戏、邀请返利、资源订阅推送。
- 服务器是 ubuntu@81.70.84.35，key 是 /Users/yiyi/Desktop/Desktop/vedo-project/vidoekey.pem。
- 后端生产目录 /opt/pythonvideo，PC 后台生产目录 /opt/pc-frontend。
- admin 地址 https://admin.lifelove.top，API 地址 https://api.lifelove.top。

请先输出：
1. 你理解的当前目标
2. 当前三仓代码状态
3. 已完成但未提交的关键改动
4. 当前最高风险
5. 你建议下一步执行顺序

先不要改代码，等我确认。
```

