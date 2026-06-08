# 07-mini-game-playbook.md

# 悦享互动宝小游戏玩法、广告轮换、邀请正反馈与积分绑定设计 v0.2

## 1. 文档定位

本文档是悦享互动宝阶段二文档包的扩展核心文档，用于指导 Codex 或开发人员在原项目基础上落地小游戏相关能力。

本文件覆盖：

1. 小游戏玩法设计。
2. 广告实例配置与多广告 ID 轮换逻辑。
3. 用户广告点击限制与广告幂等。
4. 小游戏任务与积分绑定规则。
5. 普通用户与会员用户的任务次数差异。
6. 数据结构补充。
7. Codex 渐进式落地要求。
8. 邀请会员返利正反馈与每日结算提醒。
9. 个人任务积分到账视觉反馈。

本文件不替代：

- `01-product-plan.md`
- `02-task-breakdown.md`
- `03-tech-spec.md`
- `04-acceptance.md`
- `06-data-structure.md`

而是作为小游戏和广告收益核心链路的补充设计。

---

## 2. 核心判断

悦享互动宝当前不是重度游戏产品，而是：

> 工具/资源入口 + 互动任务 + 积分奖励 + 会员权益 + 广告变现的小程序。

小游戏模块的核心目标不是做强娱乐性，而是服务以下业务目标：

1. 让用户每天有理由回来。
2. 让用户快速完成任务并获得积分反馈。
3. 给激励广告提供自然触发场景。
4. 用普通用户与会员用户的任务次数差异推动会员转化。
5. 为后续独立游戏小程序验证模型。
6. 强化邀请推广正反馈，让用户愿意主动分享到朋友圈、微信群和好友。

---

## 3. 目标用户

小游戏模块主要面向：

1. 薅羊毛用户。
2. 积分福利用户。
3. 想通过碎片时间获得小额奖励的人群。
4. 普通微信群用户。
5. 大学生用户。
6. 中老年轻度用户。
7. 影视资源用户中被积分任务吸引的用户。

这类用户的核心特点：

- 不愿研究复杂规则。
- 更关注能不能快速拿到积分。
- 喜欢直接、简单、反馈快的玩法。
- 对“会员可以做更多任务”容易理解。
- 对复杂游戏、长流程、剧情、装备、等级兴趣不高。

---

## 4. 小游戏设计原则

### 4.1 必须遵守

1. 一局游戏最好 3–10 秒内完成。
2. 操作不超过 2 步。
3. 规则必须一眼看懂。
4. 积分反馈必须即时。
5. 广告触发点必须自然。
6. 普通用户也能玩，但次数有限。
7. 会员能看到明显次数优势。
8. 游戏失败不能让用户产生强烈挫败感。
9. 页面表达统一为“互动任务”“积分奖励”“会员解锁更多次数”。
10. 前台不表达固定收益、不承诺回本。

### 4.2 不建议做

1. 斗地主。
2. 麻将。
3. 棋牌游戏对战。
4. 用户之间积分输赢。
5. 充值购买积分再参与游戏。
6. 现金余额参与输赢。
7. 长流程闯关。
8. 复杂装备、等级、养成。
9. 强现金化的转盘、赌博式抽奖。
10. 明示“看广告赚钱”。

---

## 5. MVP 游戏范围

### 5.1 P0：本轮必须落地

本轮只要求完整落地：

> 石头剪刀布 + 积分任务 + 广告加倍 + 会员任务次数差异 + 多广告 ID 轮换 + 邀请会员返利正反馈。

P0 范围：

1. 游戏页从“休闲小游戏”升级为“互动任务中心”。
2. 保留并优化石头剪刀布。
3. 完成游戏后发放积分。
4. 支持看激励广告加倍或领取额外积分。
5. 支持普通用户每日 10 次互动任务。
6. 支持月卡会员每日 100 次互动任务。
7. 支持季卡会员每日 150 次互动任务。
8. 支持年卡会员每日 200 次互动任务。
9. 支持多广告 ID 实例配置和轮换。
10. 支持用户维度的单广告 ID 点击/展示限制。
11. 所有积分发放写入积分流水。
12. 广告完成事件必须幂等。
13. 好友开通会员后，邀请人生成一级/二级奖励流水。
14. 邀请奖励需要有站内提醒或下次打开弹窗提示。

### 5.2 P1：预留配置，不强制开发

以下游戏只做配置预留或占位入口，不要求本轮完整实现：

1. 猜数字。
2. 幸运翻牌。
3. 每日答题。
4. 连点挑战。
5. 2048 简版。
6. 每日邀请收益战报。
7. 邀请奖励数字动效。
8. 个人任务积分到账动效。

### 5.3 P2：后续扩展

1. 更多轻量小游戏。
2. 排行榜。
3. 连续任务奖励。
4. 任务宝箱。
5. 积分兑换权益。
6. 独立游戏小程序。
7. 邀请排行榜。
8. 推广战报海报。

---

## 6. 游戏页结构建议

游戏页不再只是单个游戏页面，而是：

> 互动任务中心。

### 6.1 普通用户视图

展示内容：

```text
互动任务
今日已得积分：xx
今日任务：已完成 2 / 10

普通任务
- 石头剪刀布：完成互动得积分
- 每日签到：签到领积分
- 看广告加倍：领取更多积分

会员任务
- 会员每日可解锁 100 次互动任务
- 签到积分加成
- 更多影视高清权益
- 邀请奖励加成

[开通会员解锁更多任务]
```

### 6.2 会员用户视图

展示内容：

```text
互动任务
今日已得积分：xx
今日任务：已完成 12 / 100

会员任务
- 石头剪刀布
- 每日签到
- 广告加倍
- 影视权益任务
- 邀请好友任务

[继续做任务]
```

### 6.3 页面模块

1. 今日积分统计。
2. 今日任务次数进度。
3. 当前会员状态。
4. 任务入口区。
5. 小游戏入口区。
6. 广告加倍入口。
7. 会员权益提示区。
8. 积分到账反馈。

---

## 7. P0 游戏：石头剪刀布

### 7.1 游戏定位

石头剪刀布是 MVP 默认小游戏，目标是让用户快速完成一局互动并获得积分反馈。

优势：

1. 用户认知成本低。
2. 操作简单。
3. 开发成本低。
4. 适合承接广告奖励。
5. 适合做每日高频任务。

### 7.2 操作流程

1. 用户进入游戏页。
2. 点击“石头剪刀布”。
3. 用户选择石头、剪刀或布。
4. 系统随机生成结果。
5. 展示胜负结果。
6. 发放基础积分。
7. 提示“看广告加倍”或“继续下一局”。
8. 用户选择看广告后，广告完成则发放额外积分。

### 7.3 胜负规则

```text
石头 > 剪刀
剪刀 > 布
布 > 石头
相同为平局
```

### 7.4 积分规则 v0.1

默认规则：

| 结果 | 基础积分 | 是否可广告加倍 |
| ---- | -------: | -------------- |
| 胜利 |   2 积分 | 是             |
| 平局 |   1 积分 | 是             |
| 失败 |   1 积分 | 是             |

说明：

1. 失败也给少量积分，避免用户挫败。
2. 积分值必须后台可配置。
3. 看广告加倍后，额外积分可以为基础积分的 1–2 倍。
4. 广告加倍必须在广告完成回调成功后发放。

### 7.5 广告触发点

广告触发点建议：

1. 游戏结束后提示“看广告加倍积分”。
2. 当用户今日任务次数用完时，提示“完成互动解锁额外机会”。
3. 会员可拥有更多广告加倍机会。

不建议：

1. 游戏开始前强制广告。
2. 每次点击都弹广告。
3. 页面加载即弹广告。

### 7.6 任务次数规则

默认配置：

| 用户类型 | 每日互动任务次数 |
| -------- | ---------------: |
| 普通用户 |            10 次 |
| 月卡会员 |           100 次 |
| 季卡会员 |           150 次 |
| 年卡会员 |           200 次 |

注意：

> 任务次数是用户可参与的互动任务机会，不等于承诺固定收益。

前台表达为：

- 今日任务次数。
- 今日剩余次数。
- 会员解锁更多互动机会。

不要表达为：

- 今日可赚多少钱。
- 会员每天能赚多少钱。
- 开通几天回本。

---

## 8. 后续可扩展小游戏

以下游戏作为 P1/P2 预留，不进入当前 P0 强制开发范围。

### 8.1 猜数字

玩法：

1. 系统在 0–9 中生成一个数字。
2. 用户选择一个数字。
3. 猜中给较高积分，未猜中给基础积分。
4. 可看广告获得再猜一次或积分加倍。

建议积分：

| 结果   | 积分 |
| ------ | ---: |
| 猜中   |  3–5 |
| 未猜中 |    1 |

优点：

- 极快。
- 规则简单。
- 适合做高频任务。

注意：

- 不要让用户用可提现积分下注。
- 不要设计押大押小、倍率下注。

### 8.2 幸运翻牌

玩法：

1. 展示 3–6 张卡牌。
2. 用户任选 1 张。
3. 翻出积分奖励。
4. 可看广告再翻一次或加倍。

建议积分：

| 卡牌类型 | 积分 |
| -------- | ---: |
| 普通卡   |    1 |
| 幸运卡   |  2–3 |
| 稀有卡   |    5 |

优点：

- 视觉反馈强。
- 适合广告加倍。

注意：

- 概率必须后台可配置。
- 前台不要夸大中奖概率。
- 不与现金直接绑定。

### 8.3 每日答题

玩法：

1. 每题 2–4 个选项。
2. 答对得积分。
3. 答错给基础积分或不给积分。
4. 看广告获得提示或复活。

适合题型：

1. 常识题。
2. 成语题。
3. 生活知识题。
4. 影视娱乐题。

优点：

- 比纯随机玩法更自然。
- 适合中老年用户。
- 可以提高停留时长。

### 8.4 连点挑战

玩法：

1. 10 秒内点击按钮。
2. 根据点击次数给积分。
3. 看广告可获得双倍积分或再来一次。

优点：

- 规则秒懂。
- 互动感强。

注意：

- 需要基础防刷，例如过高点击频率判异常。
- 不建议给过高积分。

### 8.5 2048 简版

玩法：

1. 用户玩一局 2048 简版。
2. 达到指定分数给积分。
3. 看广告可复活或加倍奖励。

优点：

- 可玩性更强。
- 适合提高停留。

缺点：

- 一局时间较长。
- 不适合作为当前 P0。

---

## 9. 广告实例与轮换逻辑

### 9.1 背景问题

实战发现：

1. 每个广告需要单独实例配置。
2. 每个广告 ID 对每个用户存在点击或展示数量限制。
3. 单个广告 ID 容易被用户在高频任务中快速消耗。
4. 需要配置多个广告 ID 实例，通过轮换分担每个广告 ID 的点击压力。

因此，小游戏和积分任务必须支持：

> 多广告 ID 实例配置 + 用户维度广告次数记录 + 可用广告自动选择 + 广告完成幂等发奖。

### 9.2 广告类型

MVP 主要使用：

1. 激励视频广告：用于积分加倍、额外奖励、任务领取。

后续可预留：

1. 插屏广告。
2. Banner 广告。
3. 视频信息流广告。

当前 P0 只要求激励视频广告。

### 9.3 广告实例配置

每个广告 ID 作为一个广告实例配置。

示例：

```json
{
  "ad_code": "reward_game_01",
  "ad_unit_id": "xxxxxxxxxx",
  "ad_type": "rewarded_video",
  "scene": "game_bonus",
  "status": "active",
  "priority": 100,
  "weight": 10,
  "daily_user_show_limit": 5,
  "daily_user_complete_limit": 5
}
```

### 9.4 广告轮换策略

推荐 P0 使用：

> 可用广告池 + 权重随机 + 用户次数过滤。

选择逻辑：

1. 根据场景筛选广告实例。
2. 过滤已停用广告。
3. 过滤当前用户今日已达到限制的广告实例。
4. 在剩余广告中按权重随机选择。
5. 如果无可用广告，返回“今日广告机会已用完”或走降级逻辑。

### 9.5 降级逻辑

当没有可用广告时：

1. 不发放广告加倍积分。
2. 展示提示：

```text
今日互动机会暂时已用完，明天再来试试。
```

或：

```text
当前奖励视频暂不可用，可稍后再试。
```

不要让页面卡死。

### 9.6 广告完成后发奖

广告发奖必须满足：

1. 前端只负责展示广告和上报广告完成事件。
2. 后端根据广告事件校验是否可发奖。
3. 同一个 `ad_event_id` 只能发奖一次。
4. 同一个游戏回合的广告加倍只能执行一次。
5. 发奖必须写入积分流水。
6. 发奖失败要有错误提示，但不能重复补发。

---

## 10. 数据结构补充

以下数据结构可作为 `06-data-structure.md` 的小游戏与广告补充。

字段类型可根据现有数据库调整，核心是语义和索引必须保留。

---

## 10.1 广告实例表：`ad_instances`

用途：管理多个广告 ID 实例。

| 字段                       | 类型         | 必填 | 说明                                             |
| -------------------------- | ------------ | ---- | ------------------------------------------------ |
| id                         | bigint       | 是   | 主键                                             |
| ad_code                    | varchar(64)  | 是   | 广告内部编码                                     |
| ad_unit_id                 | varchar(128) | 是   | 微信广告位 ID                                    |
| ad_type                    | varchar(32)  | 是   | rewarded_video/banner/interstitial               |
| scene                      | varchar(64)  | 是   | 使用场景，如 game_bonus/checkin_bonus/media_copy |
| name                       | varchar(128) | 否   | 广告名称                                         |
| status                     | varchar(32)  | 是   | active/inactive/deleted                          |
| priority                   | int          | 是   | 优先级，数字越大越优先                           |
| weight                     | int          | 是   | 权重随机使用                                     |
| daily_user_show_limit      | int          | 否   | 单用户每日展示上限                               |
| daily_user_complete_limit  | int          | 否   | 单用户每日完成上限                               |
| total_daily_show_limit     | int          | 否   | 全局每日展示上限，P1                             |
| total_daily_complete_limit | int          | 否   | 全局每日完成上限，P1                             |
| remark                     | varchar(255) | 否   | 备注                                             |
| created_at                 | datetime     | 是   | 创建时间                                         |
| updated_at                 | datetime     | 是   | 更新时间                                         |

索引：

```text
UNIQUE KEY uk_ad_code (ad_code)
INDEX idx_scene_status (scene, status)
INDEX idx_ad_type_status (ad_type, status)
```

状态枚举：

| 状态     | 说明 |
| -------- | ---- |
| active   | 启用 |
| inactive | 停用 |
| deleted  | 删除 |

---

## 10.2 用户广告记录表：`user_ad_records`

用途：记录用户每天每个广告实例的展示、完成次数。

| 字段             | 类型     | 必填 | 说明         |
| ---------------- | -------- | ---- | ------------ |
| id               | bigint   | 是   | 主键         |
| user_id          | bigint   | 是   | 用户 ID      |
| ad_instance_id   | bigint   | 是   | 广告实例 ID  |
| stat_date        | date     | 是   | 统计日期     |
| show_count       | int      | 是   | 展示次数     |
| complete_count   | int      | 是   | 完成次数     |
| last_show_at     | datetime | 否   | 最近展示时间 |
| last_complete_at | datetime | 否   | 最近完成时间 |
| created_at       | datetime | 是   | 创建时间     |
| updated_at       | datetime | 是   | 更新时间     |

索引：

```text
UNIQUE KEY uk_user_ad_date (user_id, ad_instance_id, stat_date)
INDEX idx_user_date (user_id, stat_date)
INDEX idx_ad_date (ad_instance_id, stat_date)
```

---

## 10.3 广告事件表：`ad_events`

用途：记录每次广告展示、完成和发奖事件，保证幂等。

| 字段             | 类型         | 必填 | 说明                                     |
| ---------------- | ------------ | ---- | ---------------------------------------- |
| id               | bigint       | 是   | 主键                                     |
| ad_event_id      | varchar(128) | 是   | 广告事件唯一 ID                          |
| user_id          | bigint       | 是   | 用户 ID                                  |
| ad_instance_id   | bigint       | 是   | 广告实例 ID                              |
| scene            | varchar(64)  | 是   | 场景                                     |
| related_type     | varchar(64)  | 否   | 关联类型，如 game_round/checkin/media    |
| related_id       | varchar(128) | 否   | 关联业务 ID                              |
| event_status     | varchar(32)  | 是   | created/showed/completed/rewarded/failed |
| reward_points    | int          | 是   | 本次奖励积分                             |
| reward_detail_id | bigint       | 否   | 对应积分流水 ID                          |
| error_message    | varchar(255) | 否   | 错误信息                                 |
| created_at       | datetime     | 是   | 创建时间                                 |
| updated_at       | datetime     | 是   | 更新时间                                 |

索引：

```text
UNIQUE KEY uk_ad_event_id (ad_event_id)
INDEX idx_user_scene (user_id, scene)
INDEX idx_related (related_type, related_id)
INDEX idx_status (event_status)
```

状态枚举：

| 状态      | 说明         |
| --------- | ------------ |
| created   | 已创建       |
| showed    | 已展示       |
| completed | 用户完整观看 |
| rewarded  | 已发放奖励   |
| failed    | 失败         |

---

## 10.4 游戏配置表：`mini_games`

用途：管理小游戏配置。

| 字段            | 类型         | 必填 | 说明                          |
| --------------- | ------------ | ---- | ----------------------------- |
| id              | bigint       | 是   | 主键                          |
| game_code       | varchar(64)  | 是   | 游戏编码，如 rps/guess_number |
| game_name       | varchar(128) | 是   | 游戏名称                      |
| game_type       | varchar(64)  | 是   | rps/guess/flip/quiz/click     |
| status          | varchar(32)  | 是   | active/inactive/deleted       |
| sort_order      | int          | 是   | 排序                          |
| icon            | varchar(255) | 否   | 图标路径                      |
| description     | varchar(255) | 否   | 游戏说明                      |
| base_points_min | int          | 是   | 基础积分最小值                |
| base_points_max | int          | 是   | 基础积分最大值                |
| enable_ad_bonus | boolean      | 是   | 是否支持广告加倍              |
| ad_scene        | varchar(64)  | 否   | 对应广告场景                  |
| created_at      | datetime     | 是   | 创建时间                      |
| updated_at      | datetime     | 是   | 更新时间                      |

索引：

```text
UNIQUE KEY uk_game_code (game_code)
INDEX idx_status_sort (status, sort_order)
```

---

## 10.5 游戏回合表：`mini_game_rounds`

用途：记录用户每一局小游戏。

| 字段            | 类型         | 必填 | 说明                    |
| --------------- | ------------ | ---- | ----------------------- |
| id              | bigint       | 是   | 主键                    |
| round_id        | varchar(128) | 是   | 游戏回合唯一 ID         |
| user_id         | bigint       | 是   | 用户 ID                 |
| game_code       | varchar(64)  | 是   | 游戏编码                |
| stat_date       | date         | 是   | 日期                    |
| user_choice     | varchar(64)  | 否   | 用户选择                |
| system_choice   | varchar(64)  | 否   | 系统结果                |
| result          | varchar(32)  | 是   | win/draw/lose/completed |
| base_points     | int          | 是   | 基础积分                |
| ad_bonus_points | int          | 是   | 广告加成积分            |
| total_points    | int          | 是   | 总积分                  |
| ad_event_id     | varchar(128) | 否   | 广告事件 ID             |
| reward_status   | varchar(32)  | 是   | pending/rewarded/failed |
| created_at      | datetime     | 是   | 创建时间                |
| updated_at      | datetime     | 是   | 更新时间                |

索引：

```text
UNIQUE KEY uk_round_id (round_id)
INDEX idx_user_date (user_id, stat_date)
INDEX idx_user_game_date (user_id, game_code, stat_date)
INDEX idx_reward_status (reward_status)
```

状态枚举：

| 字段          | 值        | 说明               |
| ------------- | --------- | ------------------ |
| result        | win       | 胜利               |
| result        | draw      | 平局               |
| result        | lose      | 失败               |
| result        | completed | 完成，无胜负类游戏 |
| reward_status | pending   | 待发奖             |
| reward_status | rewarded  | 已发奖             |
| reward_status | failed    | 发奖失败           |

---

## 10.6 用户每日任务统计表：`user_daily_task_stats`

用途：统计用户每天任务次数和积分。

| 字段            | 类型        | 必填 | 说明                      |
| --------------- | ----------- | ---- | ------------------------- |
| id              | bigint      | 是   | 主键                      |
| user_id         | bigint      | 是   | 用户 ID                   |
| stat_date       | date        | 是   | 日期                      |
| user_level      | varchar(32) | 是   | normal/month/quarter/year |
| game_task_limit | int         | 是   | 当日任务次数上限          |
| game_task_used  | int         | 是   | 已使用次数                |
| game_points     | int         | 是   | 游戏基础积分              |
| ad_bonus_points | int         | 是   | 广告加成积分              |
| total_points    | int         | 是   | 当日任务总积分            |
| created_at      | datetime    | 是   | 创建时间                  |
| updated_at      | datetime    | 是   | 更新时间                  |

索引：

```text
UNIQUE KEY uk_user_date (user_id, stat_date)
INDEX idx_date (stat_date)
```

---

## 11. 积分流水绑定规则

所有小游戏积分必须进入统一积分流水表，例如 `point_logs` 或现有积分流水表。

### 11.1 积分来源枚举补充

建议补充以下来源：

| source                 | 说明           |
| ---------------------- | -------------- |
| game_base_reward       | 小游戏基础奖励 |
| game_ad_bonus          | 小游戏广告加成 |
| checkin_reward         | 签到奖励       |
| checkin_ad_bonus       | 签到广告加成   |
| invite_register        | 邀请注册奖励   |
| invite_member_rebate   | 邀请会员返利   |
| member_gift            | 开通会员赠送   |
| withdraw_freeze        | 提现冻结       |
| withdraw_success       | 提现成功扣减   |
| withdraw_reject_return | 提现驳回退回   |

### 11.2 小游戏基础积分发放

流程：

1. 用户完成一局游戏。
2. 后端检查今日任务次数是否超限。
3. 后端创建 `mini_game_rounds` 记录。
4. 后端计算基础积分。
5. 后端写入积分流水 `game_base_reward`。
6. 后端更新用户积分账户。
7. 后端更新 `user_daily_task_stats`。
8. 返回本局积分和今日剩余次数。

### 11.3 广告加倍积分发放

流程：

1. 用户完成一局游戏并获得基础积分。
2. 前端请求可用广告实例。
3. 前端展示广告。
4. 用户完整观看广告。
5. 前端上报广告完成事件。
6. 后端校验 `ad_event_id` 是否已处理。
7. 后端校验该游戏回合是否已加倍。
8. 后端写入广告事件。
9. 后端写入积分流水 `game_ad_bonus`。
10. 后端更新游戏回合的 `ad_bonus_points`。
11. 后端更新用户积分账户。
12. 返回加倍积分。

---

## 12. API 补充设计

### 12.1 获取游戏首页数据

```http
GET /api/games/home
```

响应：

```json
{
  "today_points": 12,
  "game_task_used": 2,
  "game_task_limit": 10,
  "is_member": false,
  "member_level": "normal",
  "member_upgrade_text": "开通会员，每日可解锁 100 次互动任务",
  "games": [
    {
      "game_code": "rps",
      "game_name": "石头剪刀布",
      "status": "active",
      "base_points_text": "完成互动得积分",
      "enable_ad_bonus": true
    }
  ]
}
```

### 12.2 完成游戏回合

```http
POST /api/games/round/complete
```

请求：

```json
{
  "round_id": "unique_round_id",
  "game_code": "rps",
  "user_choice": "rock"
}
```

响应：

```json
{
  "success": true,
  "round_id": "unique_round_id",
  "result": "win",
  "system_choice": "scissors",
  "base_points": 2,
  "today_used": 3,
  "today_limit": 10,
  "can_ad_bonus": true
}
```

### 12.3 获取可用广告实例

```http
GET /api/ads/available?scene=game_bonus&related_id=unique_round_id
```

响应：

```json
{
  "available": true,
  "ad_event_id": "ad_evt_xxx",
  "ad_unit_id": "wechat_ad_unit_id",
  "ad_code": "reward_game_01",
  "scene": "game_bonus"
}
```

无可用广告：

```json
{
  "available": false,
  "message": "当前奖励视频暂不可用，可稍后再试。"
}
```

### 12.4 上报广告完成

```http
POST /api/ads/reward/complete
```

请求：

```json
{
  "ad_event_id": "ad_evt_xxx",
  "scene": "game_bonus",
  "related_type": "game_round",
  "related_id": "unique_round_id"
}
```

响应：

```json
{
  "success": true,
  "rewarded": true,
  "points_added": 2,
  "total_round_points": 4
}
```

重复上报：

```json
{
  "success": true,
  "rewarded": false,
  "message": "该奖励已领取"
}
```

---

## 13. 广告选择伪代码

```python
def select_available_ad(user_id, scene, related_id):
    today = current_date()

    ads = query_ad_instances(scene=scene, status="active")
    if not ads:
        return None

    usable_ads = []

    for ad in ads:
        record = get_user_ad_record(user_id, ad.id, today)

        show_count = record.show_count if record else 0
        complete_count = record.complete_count if record else 0

        if ad.daily_user_show_limit is not None and show_count >= ad.daily_user_show_limit:
            continue

        if ad.daily_user_complete_limit is not None and complete_count >= ad.daily_user_complete_limit:
            continue

        usable_ads.append(ad)

    if not usable_ads:
        return None

    selected = weighted_random(usable_ads, weight_field="weight")

    ad_event_id = create_ad_event(
        user_id=user_id,
        ad_instance_id=selected.id,
        scene=scene,
        related_type="game_round",
        related_id=related_id,
        status="created"
    )

    increase_user_ad_show_count(user_id, selected.id, today)

    return {
        "ad_event_id": ad_event_id,
        "ad_unit_id": selected.ad_unit_id,
        "ad_code": selected.ad_code
    }
```

---

## 14. 广告完成发奖伪代码

```python
def complete_reward_ad(user_id, ad_event_id, related_type, related_id):
    event = get_ad_event(ad_event_id)

    if not event:
        raise BusinessError("广告事件不存在")

    if event.user_id != user_id:
        raise BusinessError("广告事件用户不匹配")

    if event.event_status == "rewarded":
        return {
            "success": True,
            "rewarded": False,
            "message": "该奖励已领取"
        }

    if related_type == "game_round":
        round = get_game_round(related_id)

        if not round:
            raise BusinessError("游戏回合不存在")

        if round.user_id != user_id:
            raise BusinessError("游戏回合用户不匹配")

        if round.ad_bonus_points > 0:
            return {
                "success": True,
                "rewarded": False,
                "message": "该游戏奖励已加倍"
            }

        bonus_points = calculate_ad_bonus_points(round)

        point_log = add_points(
            user_id=user_id,
            points=bonus_points,
            source="game_ad_bonus",
            related_type="ad_event",
            related_id=ad_event_id
        )

        update_game_round_ad_bonus(round.id, bonus_points)
        update_ad_event_rewarded(event.id, bonus_points, point_log.id)
        increase_user_ad_complete_count(user_id, event.ad_instance_id, current_date())

        return {
            "success": True,
            "rewarded": True,
            "points_added": bonus_points
        }
```

---

## 15. 配置文件建议

建议新增或合并至现有配置：

```text
config/game.config.json
config/ad.config.json
```

### 15.1 游戏配置：`game.config.json`

```json
{
  "daily_task_limit": {
    "normal": 10,
    "member_month": 100,
    "member_quarter": 150,
    "member_year": 200
  },
  "games": [
    {
      "game_code": "rps",
      "game_name": "石头剪刀布",
      "status": "active",
      "sort_order": 1,
      "base_points": {
        "win": 2,
        "draw": 1,
        "lose": 1
      },
      "enable_ad_bonus": true,
      "ad_bonus_multiplier": 1,
      "ad_scene": "game_bonus"
    },
    {
      "game_code": "guess_number",
      "game_name": "猜数字",
      "status": "reserved",
      "sort_order": 2
    },
    {
      "game_code": "lucky_card",
      "game_name": "幸运翻牌",
      "status": "reserved",
      "sort_order": 3
    }
  ]
}
```

### 15.2 广告配置：`ad.config.json`

```json
{
  "ad_selection_strategy": "weighted_random",
  "scenes": {
    "game_bonus": {
      "enabled": true,
      "fallback_message": "当前奖励视频暂不可用，可稍后再试。"
    },
    "checkin_bonus": {
      "enabled": true,
      "fallback_message": "当前奖励视频暂不可用，可稍后再试。"
    }
  },
  "instances": [
    {
      "ad_code": "reward_game_01",
      "ad_unit_id": "请替换为真实广告ID",
      "ad_type": "rewarded_video",
      "scene": "game_bonus",
      "status": "active",
      "priority": 100,
      "weight": 10,
      "daily_user_show_limit": 5,
      "daily_user_complete_limit": 5
    },
    {
      "ad_code": "reward_game_02",
      "ad_unit_id": "请替换为真实广告ID",
      "ad_type": "rewarded_video",
      "scene": "game_bonus",
      "status": "active",
      "priority": 90,
      "weight": 10,
      "daily_user_show_limit": 5,
      "daily_user_complete_limit": 5
    }
  ]
}
```

---

## 16. Codex 落地指引

Codex 执行时必须遵守：

1. 不要新建独立项目。
2. 在原项目新分支上渐进改造。
3. 先扫描现有游戏页、广告逻辑、积分逻辑。
4. 不要一次性实现所有小游戏。
5. P0 只实现石头剪刀布。
6. 广告轮换必须后端控制。
7. 积分发放必须以后端为准。
8. 不信任前端传入的 `user_id`。
9. 广告完成必须幂等。
10. 游戏回合必须幂等。
11. 积分流水必须完整。
12. 配置项不要硬编码在页面里。

### 16.1 Codex 第一阶段任务

```text
请先扫描当前项目中：
1. 游戏页文件路径。
2. 当前石头剪刀布实现。
3. 当前激励广告接入方式。
4. 当前积分或余额发放逻辑。
5. 当前会员状态判断逻辑。
6. 当前用户登录态。
7. 当前数据库或模型结构。

只输出结构分析，不改代码。
```

### 16.2 Codex 第二阶段任务

```text
请在原项目基础上实现小游戏 P0：
1. 将游戏页改为互动任务中心。
2. 保留石头剪刀布。
3. 完成游戏后发放基础积分。
4. 实现普通用户每日 10 次任务限制。
5. 实现会员任务次数配置：月卡 100，季卡 150，年卡 200。
6. 所有积分写入积分流水。
7. 不要实现其他小游戏，只预留配置。
```

### 16.3 Codex 第三阶段任务

```text
请实现广告轮换逻辑：
1. 新增广告实例配置。
2. 支持多个广告 ID。
3. 根据 scene 获取可用广告。
4. 记录每个用户每天每个广告 ID 的展示和完成次数。
5. 达到限制后自动切换其他广告 ID。
6. 没有可用广告时返回降级提示。
7. 广告完成后幂等发放积分。
```

---

## 17. 验收标准

### 17.1 小游戏验收

1. 游戏页标题和结构体现“互动任务”。
2. 普通用户看到每日 10 次任务限制。
3. 非会员能看到会员更多任务权益。
4. 月卡会员每日任务上限为 100。
5. 季卡会员每日任务上限为 150。
6. 年卡会员每日任务上限为 200。
7. 石头剪刀布可正常完成一局。
8. 游戏结束后基础积分到账。
9. 游戏失败也有基础积分或明确反馈。
10. 今日次数耗尽后不能继续获得基础积分。

### 17.2 广告验收

1. 系统支持多个广告 ID 实例。
2. 每个广告 ID 可配置场景、状态、权重、每日用户上限。
3. 用户达到某个广告 ID 限制后，系统自动切换其他广告 ID。
4. 所有广告 ID 都达到限制时，有明确降级提示。
5. 广告完成后积分加倍到账。
6. 同一个广告完成事件重复上报不会重复发积分。
7. 同一个游戏回合不能重复广告加倍。
8. 广告展示和完成次数有记录。

### 17.3 积分验收

1. 游戏基础积分写入积分流水。
2. 广告加倍积分写入积分流水。
3. 积分账户余额正确更新。
4. 每条流水包含来源、关联业务、积分数量、前后余额。
5. 任务次数统计和积分流水一致。

### 17.4 会员验收

1. 普通用户能看到会员任务权益。
2. 会员任务次数按会员类型生效。
3. 会员权益展示不承诺固定收益。
4. 会员价格使用配置：月卡 19.9，季卡 49.9，年卡 99.9。

---

## 18. 不做清单

本阶段不做：

1. 不做独立游戏小程序。
2. 不做斗地主、麻将、棋牌对战。
3. 不做用户之间积分输赢。
4. 不做现金余额参与游戏。
5. 不做充值积分参与随机输赢。
6. 不做复杂等级成长。
7. 不做排行榜。
8. 不做自动大额提现。
9. 不做所有小游戏一次性开发。
10. 不做收益承诺型文案。

---

## 19. 文案表达规范

推荐表达：

```text
互动任务
玩小游戏领积分
完成互动领取奖励
看视频加倍积分
会员解锁更多任务
今日剩余任务次数
积分可用于兑换权益
```

避免表达：

```text
看广告赚钱
每天赚现金
开会员回本
稳赚不赔
日入 xx 元
提现秒到账
充值赚钱
```

---

---

## 20. 邀请分销正反馈与收益展示设计

### 21.1 设计目标

小游戏与积分任务的核心不只是让用户自己做任务，更重要的是让用户愿意主动推广。

本模块目标：

1. 用户邀请好友后，能清楚看到邀请进度。
2. 好友开通会员后，邀请人能立刻获得强正反馈。
3. 一级、二级返利要让用户感知到“推广是有后续价值的”。
4. 每日结算要用订阅消息或站内提醒刺激用户继续分享。
5. 页面表达以“积分奖励、权益解锁、邀请贡献”为主，不直接使用高风险收益承诺。

优先级判断：

> 邀请分销正反馈优先级高于个人任务积分特效。个人任务特效可以增强体验，但邀请正反馈直接影响裂变和会员成交。

### 21.2 邀请收益反馈优先级

| 优先级 | 能力                           | 说明                                     |
| ------ | ------------------------------ | ---------------------------------------- |
| P0     | 好友开通会员后生成邀请奖励流水 | 必须真实落账，支持一级、二级             |
| P0     | 邀请奖励到账弹窗/站内提醒      | 邀请人再次打开小程序时必须看到           |
| P0     | 邀请页展示累计邀请收益         | 用户能看到推广成果                       |
| P0     | 邀请进度展示                   | 显示邀请人数、高清/4K 解锁进度、会员奖励 |
| P1     | 每日邀请收益结算消息           | 通过订阅消息或站内消息提醒昨日收益       |
| P1     | 收益数字跳动/金币飞入动效      | 增强视觉刺激                             |
| P1     | 邀请冲刺提示                   | “再邀请 2 人，解锁更多权益”              |
| P2     | 邀请排行榜                     | 后续运营活动使用                         |
| P2     | 推广战报海报                   | 生成可分享到朋友圈/群的海报              |

### 21.3 核心展示场景

#### 场景 A：好友开通会员，邀请人在线

触发条件：

1. 用户 A 邀请用户 B。
2. 用户 B 开通月卡/季卡/年卡会员。
3. 后端会员订单支付成功。
4. 系统计算用户 A 的一级邀请积分奖励。
5. 如果用户 A 也存在上级用户 C，则系统计算用户 C 的二级邀请积分奖励。

用户 A 前端展示：

```text
恭喜！你邀请的好友开通会员
本次获得 995 积分
奖励已进入冻结积分，结算后可用

再邀请 2 位好友开通会员，可获得更多积分奖励
```

用户 C 前端展示：

```text
你的团队产生一笔会员奖励
本次获得 99 积分
继续邀请好友，积累更多权益
```

说明：

- 如果当前用户在线，可以用弹窗或顶部浮层实时展示。
- 如果当前用户不在线，下次进入小程序时展示“待查看收益提醒”。
- 返利积分默认先进入冻结积分，避免退款、异常订单、刷单风险。

#### 场景 B：好友开通会员，邀请人不在线

下次进入小程序时，首页或我的页弹出提醒：

```text
你有新的邀请奖励
昨日/刚刚有 1 位好友开通会员
新增奖励：995 积分
去查看
```

点击“去查看”进入邀请页，展示：

```text
邀请收益
累计邀请：3 人
会员好友：2 人
累计邀请奖励：1990 积分
冻结中：995 积分
可用奖励：995 积分
```

#### 场景 C：每日结算提醒

每日定时任务汇总上一日邀请奖励。

站内消息/订阅消息文案示例：

```text
昨日邀请奖励已更新
你邀请的 2 位好友开通会员
一级奖励：1990 积分
二级奖励：99 积分
今日继续邀请，可解锁更多权益
```

如果不能稳定使用订阅消息，至少实现站内消息：

- 首页红点；
- 我的页红点；
- 邀请页顶部消息卡；
- 下次打开弹窗。

### 21.4 邀请页展示结构

邀请页建议分为 5 块：

#### 1. 顶部收益卡

```text
邀请奖励
累计获得：1990 积分
可用奖励：995 积分
冻结中：995 积分
```

按钮：

```text
立即邀请好友
查看奖励明细
```

#### 2. 今日/昨日战报

```text
昨日新增会员好友：2 人
昨日新增奖励：1990 积分
二级贡献：99 积分
```

#### 3. 邀请进度

```text
已邀请 2 / 3 人，解锁高清权益
已邀请 2 / 5 人，解锁 4K 权益
```

#### 4. 会员返利说明

```text
好友开通会员，你可获得积分奖励
好友继续邀请并产生会员权益，你也有机会获得额外积分奖励
```

避免使用：

```text
拉人头赚钱
躺赚收益
无限分销
稳赚返利
```

#### 5. 一键推广

按钮：

```text
复制邀请话术
生成邀请海报
分享到微信群
```

MVP 阶段至少实现“复制邀请话术”。

### 21.5 推荐邀请话术

#### 普通版

```text
我在用悦享互动宝，每天可以做互动任务领积分，还有影视福利和视频工具。
复制我的邀请码，一起解锁更多权益。
邀请码：{{invite_code}}
```

#### 影视版

```text
这里可以查看影视福利，完成互动后可复制资源。
邀请好友还能解锁高清/4K 权益。
我的邀请码：{{invite_code}}
```

#### 积分任务版

```text
每天做互动任务可以领积分，签到、小游戏、邀请都有奖励。
用我的邀请码加入，一起解锁更多任务权益。
邀请码：{{invite_code}}
```

### 21.6 邀请奖励计算规则

默认规则沿用阶段二文档：

| 类型         | 默认规则                    |
| ------------ | --------------------------- |
| 一级会员返利 | 会员支付金额的 50% 等值积分 |
| 二级会员返利 | 会员支付金额的 5% 等值积分  |
| 积分兑换比例 | 100 积分 = 1 元             |
| 月卡         | 19.9 元                     |
| 季卡         | 49.9 元                     |
| 年卡         | 99.9 元                     |
| 邀请返利状态 | 默认进入冻结积分            |
| 冻结期       | 默认 7 天，可配置           |

示例：

用户 B 开通月卡 19.9 元：

- 一级邀请人获得：9.95 元等值积分 = 995 积分。
- 二级邀请人获得：0.995 元等值积分，建议四舍五入为 99 或 100 积分，具体由配置决定。

用户 B 开通年卡 99.9 元：

- 一级邀请人获得：49.95 元等值积分 = 4995 积分。
- 二级邀请人获得：4.995 元等值积分 = 499 或 500 积分。

注意：

1. 前台展示积分，不强调现金金额。
2. 返利进入冻结积分，结算后转为可用积分。
3. 退款、异常订单、违规邀请需要能撤销或冻结奖励。

### 21.7 邀请正反馈动效

| 场景               | 动效                          | 优先级 |
| ------------------ | ----------------------------- | ------ |
| 邀请好友开通会员   | 大额积分弹窗 + 数字增长       | P0/P1  |
| 邀请奖励到账       | 积分飞入顶部积分卡            | P1     |
| 每日结算进入邀请页 | 昨日战报卡片展开              | P1     |
| 达成 3 人邀请      | 高清权益解锁动画              | P1     |
| 达成 5 人邀请      | 4K 权益解锁动画               | P1     |
| 产生二级奖励       | 小气泡提醒“团队奖励 +xx 积分” | P1     |

MVP 可以先不用复杂 Lottie，直接使用：

- 弹窗；
- Toast；
- 数字跳动；
- 红点；
- 简单 CSS 动画。

### 21.8 邀请消息数据结构补充

#### 表：`invite_reward_logs`

用于记录邀请会员返利奖励。

| 字段            | 类型     | 说明                               |
| --------------- | -------- | ---------------------------------- |
| id              | bigint   | 主键                               |
| user_id         | bigint   | 获得奖励的用户 ID                  |
| source_user_id  | bigint   | 触发奖励的好友 ID                  |
| source_order_id | bigint   | 会员订单 ID                        |
| invite_level    | int      | 1=一级，2=二级                     |
| plan_code       | varchar  | month/quarter/year                 |
| paid_amount     | decimal  | 好友支付金额                       |
| rebate_rate     | decimal  | 返利比例                           |
| reward_points   | int      | 奖励积分                           |
| status          | varchar  | pending/frozen/available/cancelled |
| freeze_until    | datetime | 冻结到期时间                       |
| settled_at      | datetime | 转可用时间                         |
| cancel_reason   | varchar  | 取消原因                           |
| created_at      | datetime | 创建时间                           |
| updated_at      | datetime | 更新时间                           |

索引：

```text
idx_invite_reward_user_status(user_id, status)
idx_invite_reward_source_order(source_order_id)
idx_invite_reward_created_at(created_at)
unique_invite_reward_order_level(source_order_id, user_id, invite_level)
```

幂等要求：

- 同一个会员订单对同一个受益人、同一层级只能生成一条奖励。
- 支付回调重复时不能重复发奖励。

#### 表：`invite_daily_reports`

用于生成每日邀请收益战报。

| 字段                | 类型     | 说明                     |
| ------------------- | -------- | ------------------------ |
| id                  | bigint   | 主键                     |
| user_id             | bigint   | 用户 ID                  |
| report_date         | date     | 统计日期                 |
| level1_member_count | int      | 一级会员成交人数         |
| level2_member_count | int      | 二级会员成交人数         |
| level1_points       | int      | 一级奖励积分             |
| level2_points       | int      | 二级奖励积分             |
| total_points        | int      | 总奖励积分               |
| message_status      | varchar  | pending/sent/read/failed |
| sent_at             | datetime | 发送时间                 |
| read_at             | datetime | 阅读时间                 |
| created_at          | datetime | 创建时间                 |
| updated_at          | datetime | 更新时间                 |

索引：

```text
unique_invite_daily_user_date(user_id, report_date)
idx_invite_daily_message_status(message_status)
```

#### 表：`user_notifications`

如项目已有消息表，可复用；没有则建议新增。

| 字段          | 类型     | 说明                                                 |
| ------------- | -------- | ---------------------------------------------------- |
| id            | bigint   | 主键                                                 |
| user_id       | bigint   | 用户 ID                                              |
| type          | varchar  | invite_reward/invite_daily_report/points_task/member |
| title         | varchar  | 标题                                                 |
| content       | text     | 内容                                                 |
| related_id    | bigint   | 关联业务 ID                                          |
| status        | varchar  | unread/read/deleted                                  |
| display_scene | varchar  | home/mine/invite/game                                |
| created_at    | datetime | 创建时间                                             |
| read_at       | datetime | 阅读时间                                             |

### 21.9 API 补充

#### GET `/api/invite/reward-summary`

返回邀请奖励汇总。

```json
{
  "total_invited": 3,
  "member_invited": 2,
  "total_reward_points": 1990,
  "available_reward_points": 995,
  "frozen_reward_points": 995,
  "yesterday": {
    "level1_member_count": 2,
    "level2_member_count": 1,
    "level1_points": 1990,
    "level2_points": 99,
    "total_points": 2089
  },
  "progress": {
    "hd": {"current": 3, "target": 3, "unlocked": true},
    "fourk": {"current": 3, "target": 5, "unlocked": false}
  }
}
```

#### GET `/api/invite/reward-logs`

返回邀请奖励明细。

参数：

```text
page
page_size
status
invite_level
```

#### GET `/api/notifications/unread`

返回未读消息，包括邀请奖励、每日战报等。

#### POST `/api/notifications/read`

标记消息已读。

### 21.10 订阅消息说明

微信订阅消息需要用户授权，不能默认无感推送。

MVP 处理策略：

1. 优先实现站内消息和下次打开弹窗。
2. 在邀请页或收益页引导用户订阅“奖励到账提醒/每日结算提醒”。
3. 用户订阅后，再发送微信订阅消息。
4. 订阅消息失败时，站内消息仍然必须可用。

订阅引导文案：

```text
开启提醒后，好友开通会员和每日积分结算会及时通知你。
```

避免文案：

```text
开启赚钱提醒
每日收益到账
躺赚通知
```

---

## 21. 个人任务收益视觉正反馈设计

### 22.1 设计目标

个人任务收益正反馈用于增强用户继续完成任务的动力，但优先级低于邀请分销正反馈。

目标：

1. 用户完成签到、小游戏、广告加倍后，能立刻看到积分变化。
2. 用户看到今日累计积分，形成进度感。
3. 用户知道会员可以解锁更多任务次数。
4. 用户被自然引导到邀请好友或开通会员。

### 22.2 展示场景

| 场景               | 展示                             | 优先级 |
| ------------------ | -------------------------------- | ------ |
| 签到成功           | `+1 积分，签到成功`              | P0     |
| 游戏完成           | `+2 积分，奖励已入账`            | P0     |
| 广告加倍完成       | `奖励翻倍，额外 +2 积分`         | P0     |
| 今日累计增长       | 顶部“今日已得积分”数字跳动       | P1     |
| 普通用户次数快用完 | 提示“会员可解锁更多互动次数”     | P0     |
| 完成多次任务后     | 提示“邀请好友可获得更多积分奖励” | P1     |

### 22.3 推荐动效

MVP 优先使用轻量方案：

1. Toast 提示积分到账。
2. 顶部积分数字刷新。
3. 简单 `+积分` 上浮动画。
4. 任务完成按钮变成“已领取”。
5. 普通用户次数不足时出现会员权益卡。

P1 可增加：

1. 金币飞入积分卡。
2. 数字滚动增长。
3. 高积分奖励弹窗。
4. 会员加成光效。

不建议：

1. 现金雨。
2. 人民币图案掉落。
3. 强化“赚钱”字眼。
4. 过度阻塞用户操作的长动画。

### 22.4 前端返回字段建议

小游戏任务、签到、广告加倍接口返回中建议包含：

```json
{
  "success": true,
  "points_added": 2,
  "today_points": 18,
  "total_points": 188,
  "remaining_tasks": 8,
  "is_member": false,
  "member_task_limit": 100,
  "feedback": {
    "type": "task_reward",
    "title": "积分到账",
    "message": "+2 积分，奖励已入账",
    "animation": "points_float"
  },
  "next_hint": {
    "type": "invite_or_member",
    "message": "邀请好友或开通会员，可解锁更多积分任务"
  }
}
```

### 22.5 个人任务反馈与邀请转化结合

个人任务完成后，不要只提示积分到账，还要在合适时机引导用户推广。

触发条件建议：

1. 普通用户完成第 3 次任务后，提示邀请好友。
2. 普通用户剩余任务小于等于 2 次时，提示会员权益。
3. 用户今日积分达到一定值时，提示“邀请好友可更快积累积分”。
4. 用户首次提现成功后，提示“邀请好友可获得更多积分权益”。

示例文案：

```text
今日已获得 18 积分
邀请好友加入，可解锁更多积分奖励
```

```text
今日普通任务快用完了
开通会员可解锁更多互动次数
```

---

## 22. 邀请正反馈验收标准

### 23.1 P0 验收

1. 好友开通会员后，一级邀请人生成奖励流水。
2. 好友开通会员后，如存在二级邀请人，二级邀请人生成奖励流水。
3. 同一会员订单不会重复生成邀请奖励。
4. 邀请奖励默认进入冻结积分。
5. 邀请页能展示累计奖励、冻结奖励、可用奖励。
6. 用户再次打开小程序时，能看到未读邀请奖励提醒。
7. 邀请页能展示邀请人数和 3/5 人权益解锁进度。
8. 邀请奖励文案不出现“稳赚、回本、躺赚、拉人头”等表达。

### 23.2 P1 验收

1. 每日定时任务能生成昨日邀请收益战报。
2. 用户能在站内消息中看到昨日一级、二级邀请贡献。
3. 如用户授权订阅消息，可发送每日结算提醒。
4. 邀请奖励到账有数字增长或积分到账动画。
5. 用户接近 3/5 人解锁目标时，有明确提示。

### 23.3 与个人任务反馈的优先级

如果开发资源有限，优先顺序如下：

1. 邀请奖励流水与幂等。
2. 邀请奖励汇总展示。
3. 邀请奖励未读提醒。
4. 每日邀请收益战报。
5. 个人任务积分到账 Toast。
6. 个人任务积分动效。
7. 邀请海报和排行榜。


## 23. 当前结论

小游戏模块是悦享互动宝商业模型的核心之一，但当前阶段必须保持克制。

MVP 只做：

> 石头剪刀布 + 互动任务中心 + 积分发放 + 广告加倍 + 多广告 ID 轮换 + 会员任务次数差异。

其他小游戏只做预留，不影响当前 P0 交付。

本模块跑通后，重点观察：

1. 游戏页点击率。
2. 游戏完成率。
3. 激励广告完成率。
4. 普通用户任务次数消耗率。
5. 会员转化率。
6. 人均广告观看次数。
7. 积分发放成本。
8. 次日留存。

如果数据成立，再进入后续小游戏扩展或独立游戏小程序阶段一。