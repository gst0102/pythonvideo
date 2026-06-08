# 06-data-structure.md

# 悦享互动宝 MVP v0.1 数据结构设计

## 1. 文档说明

本文档用于指导 Codex 或开发人员落地悦享互动宝 MVP v0.1 的数据结构、状态枚举、索引设计、积分流水、提现流水、广告幂等、会员订单和邀请关系。

本阶段目标不是搭建完整财务系统或大型运营后台，而是建立一套可上线、可审计、可扩展、可风控的最小数据模型。

## 2. 设计原则

### 2.1 前台统一积分，后台分账

前台统一使用“积分”作为用户理解的主概念。

后台必须区分不同积分状态，避免账务混乱：

- 总积分：用户历史获得积分总和的展示口径。
- 可提现积分：允许申请提现的积分。
- 冻结积分：邀请返利、异常任务、待审核奖励等暂不可提现积分。
- 消耗积分：已用于兑换权益、抵扣广告、参与互动的积分。
- 已提现积分：已提现成功对应的积分。

### 2.2 所有积分变化必须有流水

任何积分增加、扣减、冻结、解冻、提现、退回，都必须写入积分流水表。

不能只更新用户账户余额。

### 2.3 广告、游戏、订单、提现必须幂等

以下业务必须有唯一幂等键：

- 激励广告完成事件。
- 游戏任务完成事件。
- 签到广告翻倍事件。
- 会员支付订单回调。
- 邀请返利发放。
- 提现申请。

### 2.4 配置化优先

以下规则不得散落写死在页面代码里：

- 积分兑换比例。
- 签到积分。
- 游戏积分。
- 会员每日任务次数。
- 邀请奖励。
- 会员返利比例。
- 提现门槛。
- 提现手续费。
- 冻结期。

### 2.5 MVP 不做复杂后台，但数据要为后台预留

MVP 阶段可以只做接口与数据表，不做完整运营后台。

但提现审核、用户冻结、积分调整、会员订单、广告事件等必须预留字段，方便后续补后台。

---

# 3. 数据库假设

本文档以关系型数据库模型描述，推荐 MySQL / PostgreSQL。

如果当前项目使用 MongoDB、云开发数据库或其他 NoSQL，可按同样字段语义转换为集合结构。

通用字段约定：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | bigint / varchar | 主键，推荐雪花 ID、UUID 或数据库自增 ID |
| created_at | datetime | 创建时间 |
| updated_at | datetime | 更新时间 |
| deleted_at | datetime nullable | 软删除时间，可选 |

金额建议：

- 金额字段用 `decimal(10,2)` 或整数分表示。
- 积分字段用整数 `int` 或 `bigint`。
- 不建议用 float 存储金额。

---

# 4. 核心状态枚举

## 4.1 用户状态 user_status

| 枚举值 | 说明 |
|---|---|
| active | 正常 |
| disabled | 禁用 |
| frozen | 冻结，不能提现和领取高价值奖励 |
| deleted | 注销或软删除 |


## 4.1.1 登录来源 auth_source

| 枚举值 | 说明 |
|---|---|
| wechat_silent | 微信小程序静默登录 |
| wechat_profile | 用户主动完善微信头像昵称 |
| admin_import | 后台导入或修复 |

## 4.2 会员等级 member_level

| 枚举值 | 说明 |
|---|---|
| none | 非会员 |
| month | 月卡会员 |
| quarter | 季卡会员 |
| year | 年卡会员 |

## 4.3 积分流水类型 points_type

| 枚举值 | 说明 |
|---|---|
| earn | 获得积分 |
| consume | 消耗积分 |
| freeze | 冻结积分 |
| unfreeze | 解冻积分 |
| withdraw_lock | 提现锁定积分 |
| withdraw_success | 提现成功扣除积分 |
| withdraw_reject_return | 提现驳回退回积分 |
| adjust_add | 后台补发积分 |
| adjust_sub | 后台扣减积分 |

## 4.4 积分来源 points_source

| 枚举值 | 说明 |
|---|---|
| checkin | 每日签到 |
| checkin_ad_bonus | 签到广告加倍 |
| game_task | 小游戏任务 |
| game_ad_bonus | 游戏广告加倍 |
| invite_register | 邀请注册奖励 |
| invite_member_rebate | 好友开会员返利 |
| member_gift | 开通会员赠送 |
| media_copy_reward | 影视互动奖励 |
| video_download_reward | 视频下载互动奖励 |
| withdraw | 提现相关 |
| admin_adjust | 后台调整 |
| system | 系统处理 |

## 4.5 积分可用状态 points_availability

| 枚举值 | 说明 |
|---|---|
| withdrawable | 可提现 |
| frozen | 冻结中 |
| consumable_only | 仅可消耗，不可提现 |

## 4.6 广告事件状态 ad_event_status

| 枚举值 | 说明 |
|---|---|
| init | 已创建，未完成 |
| completed | 已完成观看 |
| rewarded | 已发奖励 |
| failed | 失败 |
| ignored_duplicate | 重复事件已忽略 |

## 4.7 广告场景 ad_scene

| 枚举值 | 说明 |
|---|---|
| checkin_bonus | 签到翻倍 |
| game_reward | 游戏奖励 |
| game_bonus | 游戏奖励加倍 |
| media_copy | 影视复制资源 |
| video_download | 视频下载 |
| task_reward | 普通任务奖励 |

## 4.8 游戏回合状态 game_round_status

| 枚举值 | 说明 |
|---|---|
| started | 已开始 |
| completed | 已完成 |
| rewarded | 已发积分 |
| invalid | 无效回合 |

## 4.9 会员订单状态 member_order_status

| 枚举值 | 说明 |
|---|---|
| pending | 待支付 |
| paid | 已支付 |
| activated | 已开通会员权益 |
| closed | 已关闭 |
| refunded | 已退款 |
| failed | 支付失败 |

## 4.10 提现状态 withdraw_status

| 枚举值 | 说明 |
|---|---|
| pending | 待审核 |
| approved | 审核通过，待打款 |
| paid | 已打款 |
| rejected | 已驳回 |
| canceled | 用户取消 |
| failed | 打款失败 |

## 4.11 邀请关系状态 invite_status

| 枚举值 | 说明 |
|---|---|
| active | 有效 |
| invalid | 无效 |
| blocked | 被风控拦截 |

## 4.12 返利状态 rebate_status

| 枚举值 | 说明 |
|---|---|
| pending | 待处理 |
| frozen | 已冻结入账 |
| available | 已解冻可用 |
| canceled | 已取消 |

---

# 5. 表结构总览

## 5.1 MVP 必须表

| 表名 | 用途 | MVP 必须 |
|---|---|---|
| users | 用户基础信息 | 是 |
| user_accounts | 用户积分账户 | 是 |
| points_ledger | 积分流水 | 是 |
| checkin_records | 签到记录 | 是 |
| ad_events | 激励广告事件与幂等 | 是 |
| game_rounds | 小游戏回合记录 | 是 |
| daily_task_stats | 每日任务统计 | 是 |
| member_plans | 会员套餐配置 | 是 |
| member_orders | 会员订单 | 是 |
| user_memberships | 用户会员状态 | 是 |
| invite_relations | 邀请关系 | 是 |
| invite_rebates | 邀请返利 | 是 |
| withdraw_orders | 提现申请 | 是 |
| withdraw_logs | 提现流水/状态日志 | 是 |
| app_configs | 业务配置 | 是 |
| event_logs | 行为埋点 | 是 |

## 5.2 P1/P2 可选表

| 表名 | 用途 | 优先级 |
|---|---|---|
| media_unlocks | 影视权益解锁记录 | P1 |
| video_parse_logs | 视频解析日志 | P1 |
| admin_audit_logs | 后台操作审计 | P1 |
| risk_flags | 风控标记 | P2 |
| user_devices | 设备信息 | P2 |
| resource_usage_logs | 资源/权益使用日志 | P2 |

---

# 6. 用户与账户表

## 6.1 users 用户表

用途：存储微信小程序用户基础信息。

```sql
CREATE TABLE users (
  id BIGINT PRIMARY KEY,
  openid VARCHAR(128) NOT NULL,
  unionid VARCHAR(128) NULL,
  nickname VARCHAR(64) NOT NULL DEFAULT '',
  avatar_url VARCHAR(512) NULL,
  default_nickname VARCHAR(64) NOT NULL DEFAULT '',
  default_avatar_url VARCHAR(512) NULL,
  invite_code VARCHAR(32) NOT NULL,
  invited_by_user_id BIGINT NULL,
  member_level VARCHAR(32) NOT NULL DEFAULT 'none',
  member_expired_at DATETIME NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  auth_source VARCHAR(32) NOT NULL DEFAULT 'wechat_silent',
  last_login_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  deleted_at DATETIME NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| id | 用户 ID |
| openid | 微信小程序 openid |
| unionid | 微信 unionid，可为空 |
| nickname | 用户昵称 |
| avatar_url | 头像 |
| phone | 手机号，可为空 |
| invite_code | 用户自己的邀请码 |
| status | 用户状态 |
| first_source | 首次来源，如 group、media、video、invite |
| first_scene | 微信小程序 scene 参数或自定义来源 |
| last_login_at | 最近登录时间 |

索引：

```sql
CREATE UNIQUE INDEX uk_users_openid ON users(openid);
CREATE UNIQUE INDEX uk_users_invite_code ON users(invite_code);
CREATE INDEX idx_users_unionid ON users(unionid);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_users_invited_by_user_id ON users(invited_by_user_id);
```

约束：

1. `openid` 必须唯一。
2. `invite_code` 必须唯一。
3. 用户被冻结时，不允许提现。

登录与用户创建规则：

1. MVP 阶段使用微信小程序静默登录，基于 `openid` 唯一识别用户。
2. 首次登录时自动创建 `users`、`user_accounts`、邀请码和新人任务状态。
3. 未授权头像昵称时，`nickname` 可以为空或使用 `default_nickname` 展示，例如“悦享用户1234”。
4. `AppSecret`、`session_key` 不得存储在前端，不得返回给前端。
5. 用户通过邀请链接进入时，登录接口携带 `invite_code`，后端校验后写入 `invited_by_user_id` 并创建邀请关系。
6. 用户不能绑定自己，不能重复绑定上级。
7. 所有业务接口使用 token 解析出的 `user_id`，不能信任前端传入的 `user_id`。


---


## 6.1.1 auth_tokens 登录态表

用途：存储系统自有登录 token，前端后续请求携带 token。

```sql
CREATE TABLE auth_tokens (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  token_hash VARCHAR(128) NOT NULL,
  expired_at DATETIME NOT NULL,
  revoked_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE UNIQUE INDEX uk_auth_tokens_token_hash ON auth_tokens(token_hash);
CREATE INDEX idx_auth_tokens_user_id ON auth_tokens(user_id);
CREATE INDEX idx_auth_tokens_expired_at ON auth_tokens(expired_at);
```

规则：

1. 前端只保存系统 token，不保存 `session_key`。
2. 后端可只存 token hash，不存明文 token。
3. token 过期后前端重新调用 `wx.login()`。
4. 用户被冻结后，可撤销未过期 token。

## 6.2 user_accounts 用户积分账户表

用途：存储用户积分账户汇总数据。

```sql
CREATE TABLE user_accounts (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  total_points BIGINT NOT NULL DEFAULT 0,
  withdrawable_points BIGINT NOT NULL DEFAULT 0,
  frozen_points BIGINT NOT NULL DEFAULT 0,
  consumable_points BIGINT NOT NULL DEFAULT 0,
  consumed_points BIGINT NOT NULL DEFAULT 0,
  withdrawn_points BIGINT NOT NULL DEFAULT 0,
  locked_withdraw_points BIGINT NOT NULL DEFAULT 0,
  version BIGINT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| total_points | 历史累计获得积分口径，可用于展示 |
| withdrawable_points | 可提现积分 |
| frozen_points | 冻结积分 |
| consumable_points | 仅可消耗积分，不可提现 |
| consumed_points | 已消耗积分 |
| withdrawn_points | 已提现成功积分 |
| locked_withdraw_points | 提现申请中锁定积分 |
| version | 乐观锁版本号 |

索引：

```sql
CREATE UNIQUE INDEX uk_user_accounts_user_id ON user_accounts(user_id);
```

账务要求：

1. 每次修改账户，都必须写入 `points_ledger`。
2. 扣减积分时必须使用事务。
3. 建议使用 `version` 乐观锁防止并发扣减。
4. 可提现积分不能小于 0。
5. 冻结积分不能小于 0。

账户余额校验建议：

```text
withdrawable_points >= 0
frozen_points >= 0
consumable_points >= 0
locked_withdraw_points >= 0
```

---

# 7. 积分流水表

## 7.1 points_ledger 积分流水表

用途：记录所有积分变化，是积分系统的核心审计表。

```sql
CREATE TABLE points_ledger (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  account_id BIGINT NOT NULL,
  change_type VARCHAR(32) NOT NULL,
  source VARCHAR(64) NOT NULL,
  availability VARCHAR(32) NOT NULL,
  points_delta BIGINT NOT NULL,
  balance_withdrawable_after BIGINT NOT NULL,
  balance_frozen_after BIGINT NOT NULL,
  balance_consumable_after BIGINT NOT NULL,
  related_type VARCHAR(64) NULL,
  related_id VARCHAR(128) NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  remark VARCHAR(512) NULL,
  created_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| user_id | 用户 ID |
| account_id | 用户积分账户 ID |
| change_type | 积分变化类型，如 earn、consume、freeze、unfreeze |
| source | 积分来源，如 checkin、game_task、invite_member_rebate |
| availability | 积分可用类型：withdrawable、frozen、consumable_only |
| points_delta | 积分变化，可正可负 |
| balance_withdrawable_after | 变动后可提现积分 |
| balance_frozen_after | 变动后冻结积分 |
| balance_consumable_after | 变动后可消耗积分 |
| related_type | 关联业务类型，如 ad_event、game_round、withdraw_order |
| related_id | 关联业务 ID |
| idempotency_key | 幂等键 |
| remark | 备注 |

索引：

```sql
CREATE INDEX idx_points_ledger_user_created ON points_ledger(user_id, created_at);
CREATE INDEX idx_points_ledger_source ON points_ledger(source);
CREATE INDEX idx_points_ledger_related ON points_ledger(related_type, related_id);
CREATE UNIQUE INDEX uk_points_ledger_idempotency ON points_ledger(idempotency_key);
```

积分流水规则：

1. 同一个 `idempotency_key` 只能产生一条流水。
2. `points_delta > 0` 表示增加。
3. `points_delta < 0` 表示扣减。
4. 提现申请时，建议先从 `withdrawable_points` 扣到 `locked_withdraw_points`，并写 `withdraw_lock` 流水。
5. 提现成功时，扣除 `locked_withdraw_points`，写 `withdraw_success` 流水。
6. 提现驳回时，从 `locked_withdraw_points` 退回 `withdrawable_points`，写 `withdraw_reject_return` 流水。

幂等键建议格式：

| 场景 | idempotency_key 示例 |
|---|---|
| 签到 | `checkin:{user_id}:{date}` |
| 签到广告翻倍 | `checkin_ad_bonus:{user_id}:{date}:{ad_event_id}` |
| 游戏奖励 | `game_task:{user_id}:{round_id}` |
| 广告奖励 | `ad_reward:{user_id}:{ad_event_id}` |
| 邀请注册 | `invite_register:{inviter_id}:{invitee_id}` |
| 会员返利 | `invite_member_rebate:{order_id}:{beneficiary_user_id}:{level}` |
| 会员赠送积分 | `member_gift:{order_id}` |
| 提现锁定 | `withdraw_lock:{withdraw_order_id}` |
| 提现成功 | `withdraw_success:{withdraw_order_id}` |
| 提现驳回退回 | `withdraw_reject:{withdraw_order_id}` |

---

# 8. 签到表

## 8.1 checkin_records 签到记录表

用途：记录用户每日签到和广告翻倍状态。

```sql
CREATE TABLE checkin_records (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  checkin_date DATE NOT NULL,
  base_points BIGINT NOT NULL DEFAULT 0,
  bonus_points BIGINT NOT NULL DEFAULT 0,
  total_points BIGINT NOT NULL DEFAULT 0,
  continuous_days INT NOT NULL DEFAULT 1,
  is_member_at_checkin BOOLEAN NOT NULL DEFAULT FALSE,
  ad_bonus_used BOOLEAN NOT NULL DEFAULT FALSE,
  ad_event_id VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE UNIQUE INDEX uk_checkin_user_date ON checkin_records(user_id, checkin_date);
CREATE INDEX idx_checkin_user_created ON checkin_records(user_id, created_at);
```

规则：

1. 同一用户同一天只能签到一次。
2. 签到成功后写入积分流水。
3. 广告翻倍只能对当天签到执行一次。
4. 广告翻倍必须关联 `ad_event_id`。
5. `continuous_days` 由后端计算，不由前端传入。

---

# 9. 广告幂等表

## 9.1 ad_events 激励广告事件表

用途：记录所有激励广告展示、完成、发奖状态，防止重复发积分。

```sql
CREATE TABLE ad_events (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  ad_event_id VARCHAR(128) NOT NULL,
  provider VARCHAR(64) NOT NULL DEFAULT 'wechat_reward_ad',
  scene VARCHAR(64) NOT NULL,
  related_type VARCHAR(64) NULL,
  related_id VARCHAR(128) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'init',
  reward_points BIGINT NOT NULL DEFAULT 0,
  reward_ledger_id BIGINT NULL,
  client_trace_id VARCHAR(128) NULL,
  ip VARCHAR(64) NULL,
  device_id VARCHAR(128) NULL,
  completed_at DATETIME NULL,
  rewarded_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| ad_event_id | 广告事件唯一 ID，必须由前端或后端生成并传入 |
| provider | 广告提供方，默认微信激励广告 |
| scene | 广告场景 |
| related_type | 关联业务类型，如 checkin、game_round、media_copy |
| related_id | 关联业务 ID |
| status | 广告事件状态 |
| reward_points | 本次广告发放积分 |
| reward_ledger_id | 对应积分流水 ID |
| client_trace_id | 前端追踪 ID，可选 |
| device_id | 设备 ID，可选 |

索引：

```sql
CREATE UNIQUE INDEX uk_ad_events_event_id ON ad_events(ad_event_id);
CREATE INDEX idx_ad_events_user_scene_created ON ad_events(user_id, scene, created_at);
CREATE INDEX idx_ad_events_related ON ad_events(related_type, related_id);
CREATE INDEX idx_ad_events_status ON ad_events(status);
```

广告幂等规则：

1. `ad_event_id` 全局唯一。
2. 同一广告事件不能重复发积分。
3. 如果收到重复回调，返回已处理结果，不再发奖。
4. 广告完成后，先更新 `ad_events.status = completed`。
5. 发放积分成功后，再更新 `status = rewarded` 并记录 `reward_ledger_id`。
6. 广告发奖和积分流水必须在同一事务内完成。

推荐处理流程：

```text
1. 接收广告完成请求。
2. 查询 ad_event_id 是否存在。
3. 如果不存在，创建 completed 记录。
4. 如果已 rewarded，直接返回 processed=true。
5. 根据 scene 校验是否允许发奖。
6. 计算 reward_points。
7. 写入积分流水。
8. 更新账户。
9. 更新 ad_events.rewarded。
```

---

# 10. 游戏任务表

## 10.1 game_rounds 小游戏回合表

用途：记录用户每局小游戏结果和发奖状态。

```sql
CREATE TABLE game_rounds (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  round_id VARCHAR(128) NOT NULL,
  game_code VARCHAR(64) NOT NULL,
  result VARCHAR(32) NOT NULL,
  base_points BIGINT NOT NULL DEFAULT 0,
  bonus_points BIGINT NOT NULL DEFAULT 0,
  total_points BIGINT NOT NULL DEFAULT 0,
  ad_event_id VARCHAR(128) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'completed',
  ledger_id BIGINT NULL,
  played_date DATE NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| round_id | 前端或后端生成的单局唯一 ID |
| game_code | 游戏编码，如 rps、guess_number |
| result | win、lose、draw、completed |
| base_points | 基础积分 |
| bonus_points | 广告加倍或会员加成积分 |
| total_points | 本局总积分 |
| ad_event_id | 如本局关联广告，记录广告事件 ID |
| status | 回合状态 |
| played_date | 游戏日期，用于统计每日次数 |

索引：

```sql
CREATE UNIQUE INDEX uk_game_rounds_round_id ON game_rounds(round_id);
CREATE INDEX idx_game_rounds_user_date ON game_rounds(user_id, played_date);
CREATE INDEX idx_game_rounds_user_game_created ON game_rounds(user_id, game_code, created_at);
```

规则：

1. `round_id` 必须唯一，防止重复提交同一局。
2. 每完成一局并满足发奖条件，写入积分流水。
3. 每日任务次数以 `daily_task_stats` 为准，`game_rounds` 可辅助校验。
4. 不建议由前端决定最终积分，前端只传游戏结果，后端按配置计算积分。

---

## 10.2 daily_task_stats 每日任务统计表

用途：记录用户每日任务次数、积分汇总，提升查询效率。

```sql
CREATE TABLE daily_task_stats (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  stat_date DATE NOT NULL,
  checkin_done BOOLEAN NOT NULL DEFAULT FALSE,
  game_tasks_used INT NOT NULL DEFAULT 0,
  game_tasks_limit INT NOT NULL DEFAULT 0,
  ad_bonus_used INT NOT NULL DEFAULT 0,
  ad_bonus_limit INT NOT NULL DEFAULT 0,
  today_points BIGINT NOT NULL DEFAULT 0,
  is_member_snapshot BOOLEAN NOT NULL DEFAULT FALSE,
  member_level_snapshot VARCHAR(32) NOT NULL DEFAULT 'none',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE UNIQUE INDEX uk_daily_task_user_date ON daily_task_stats(user_id, stat_date);
CREATE INDEX idx_daily_task_date ON daily_task_stats(stat_date);
```

规则：

1. 每天每个用户一条记录。
2. `game_tasks_limit` 按用户当天会员状态计算。
3. 用户当天升级会员后，可以选择立即刷新当天 limit，具体由业务配置决定。
4. 所有任务积分增加时同步更新 `today_points`。

---

# 11. 会员表

## 11.1 member_plans 会员套餐表

用途：存储会员套餐配置。

```sql
CREATE TABLE member_plans (
  id BIGINT PRIMARY KEY,
  plan_code VARCHAR(32) NOT NULL,
  name VARCHAR(64) NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  original_price DECIMAL(10,2) NULL,
  duration_days INT NOT NULL,
  gift_points BIGINT NOT NULL DEFAULT 0,
  daily_game_task_limit INT NOT NULL DEFAULT 0,
  level VARCHAR(32) NOT NULL,
  tag VARCHAR(64) NULL,
  is_recommended BOOLEAN NOT NULL DEFAULT FALSE,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  sort_order INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

推荐初始数据：

| plan_code | name | price | original_price | duration_days | gift_points | daily_game_task_limit | level | tag |
|---|---|---:|---:|---:|---:|---:|---|---|
| month | 月卡 | 19.90 | 29.90 | 31 | 199 | 100 | month | 轻度体验 |
| quarter | 季卡 | 49.90 | 59.90 | 93 | 599 | 150 | quarter | 推荐 |
| year | 年卡 | 99.90 | 239.90 | 365 | 1299 | 200 | year | 限时福利 |

索引：

```sql
CREATE UNIQUE INDEX uk_member_plans_code ON member_plans(plan_code);
CREATE INDEX idx_member_plans_status_sort ON member_plans(status, sort_order);
```

---

## 11.2 member_orders 会员订单表

用途：记录会员购买订单和支付状态。

```sql
CREATE TABLE member_orders (
  id BIGINT PRIMARY KEY,
  order_no VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  plan_code VARCHAR(32) NOT NULL,
  plan_name VARCHAR(64) NOT NULL,
  member_level VARCHAR(32) NOT NULL,
  price DECIMAL(10,2) NOT NULL,
  pay_amount DECIMAL(10,2) NOT NULL,
  pay_channel VARCHAR(32) NOT NULL DEFAULT 'wechat_pay',
  transaction_id VARCHAR(128) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  gift_points BIGINT NOT NULL DEFAULT 0,
  gift_ledger_id BIGINT NULL,
  paid_at DATETIME NULL,
  activated_at DATETIME NULL,
  expired_at DATETIME NULL,
  invite_rebate_processed BOOLEAN NOT NULL DEFAULT FALSE,
  idempotency_key VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| order_no | 内部订单号 |
| transaction_id | 微信支付交易号 |
| plan_code | 套餐编码 |
| member_level | 会员等级 |
| pay_amount | 实付金额 |
| status | 订单状态 |
| gift_points | 开通会员赠送积分 |
| gift_ledger_id | 赠送积分流水 ID |
| invite_rebate_processed | 是否已处理邀请返利 |
| idempotency_key | 支付回调幂等键 |

索引：

```sql
CREATE UNIQUE INDEX uk_member_orders_order_no ON member_orders(order_no);
CREATE UNIQUE INDEX uk_member_orders_idempotency ON member_orders(idempotency_key);
CREATE INDEX idx_member_orders_user_created ON member_orders(user_id, created_at);
CREATE INDEX idx_member_orders_status ON member_orders(status);
CREATE INDEX idx_member_orders_transaction ON member_orders(transaction_id);
```

会员订单处理规则：

1. 创建订单时状态为 `pending`。
2. 微信支付成功后更新为 `paid`。
3. 开通会员成功后更新为 `activated`。
4. 支付回调必须按 `order_no` 或 `transaction_id` 幂等。
5. 会员赠积分必须写入 `points_ledger`。
6. 邀请返利只允许处理一次，以 `invite_rebate_processed` 标记。

---

## 11.3 user_memberships 用户会员状态表

用途：存储用户当前会员状态。

```sql
CREATE TABLE user_memberships (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  member_level VARCHAR(32) NOT NULL DEFAULT 'none',
  active_order_id BIGINT NULL,
  started_at DATETIME NULL,
  expired_at DATETIME NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'inactive',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

会员状态枚举：

| status | 说明 |
|---|---|
| inactive | 非会员或已过期 |
| active | 生效中 |
| expired | 已过期 |
| canceled | 已取消 |

索引：

```sql
CREATE UNIQUE INDEX uk_user_memberships_user_id ON user_memberships(user_id);
CREATE INDEX idx_user_memberships_expired ON user_memberships(expired_at);
CREATE INDEX idx_user_memberships_status ON user_memberships(status);
```

会员续费规则：

1. 如果用户当前非会员，从支付成功时间开始计算。
2. 如果用户当前会员未过期，从当前 `expired_at` 追加时长。
3. 高等级会员覆盖低等级会员的权益展示，具体策略可配置。
4. 会员过期后，状态应由定时任务或登录时检查更新。

---

# 12. 邀请关系与返利表

## 12.1 invite_relations 邀请关系表

用途：记录用户之间的一级/二级邀请关系。

```sql
CREATE TABLE invite_relations (
  id BIGINT PRIMARY KEY,
  inviter_user_id BIGINT NOT NULL,
  invitee_user_id BIGINT NOT NULL,
  parent_inviter_user_id BIGINT NULL,
  invite_code VARCHAR(32) NOT NULL,
  level INT NOT NULL DEFAULT 1,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  source_scene VARCHAR(128) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| inviter_user_id | 直接邀请人 |
| invitee_user_id | 被邀请人 |
| parent_inviter_user_id | 邀请人的上级，用于二级关系 |
| invite_code | 绑定的邀请码 |
| level | 关系层级，直接关系为 1 |
| source_scene | 来源场景 |

索引：

```sql
CREATE UNIQUE INDEX uk_invite_invitee ON invite_relations(invitee_user_id);
CREATE INDEX idx_invite_inviter ON invite_relations(inviter_user_id);
CREATE INDEX idx_invite_parent ON invite_relations(parent_inviter_user_id);
CREATE INDEX idx_invite_code ON invite_relations(invite_code);
```

邀请绑定规则：

1. 用户不能邀请自己。
2. 用户只能绑定一次上级。
3. 已绑定上级后不可更换，除非后台人工处理。
4. 如果上级被冻结，后续返利可暂停。
5. 二级关系只记录到第二层，不扩展更多层级。

---

## 12.2 invite_rebates 邀请返利表

用途：记录好友开通会员后给邀请人的积分返利。

```sql
CREATE TABLE invite_rebates (
  id BIGINT PRIMARY KEY,
  order_id BIGINT NOT NULL,
  order_no VARCHAR(64) NOT NULL,
  payer_user_id BIGINT NOT NULL,
  beneficiary_user_id BIGINT NOT NULL,
  rebate_level INT NOT NULL,
  rebate_rate DECIMAL(5,4) NOT NULL,
  order_pay_amount DECIMAL(10,2) NOT NULL,
  rebate_points BIGINT NOT NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  freeze_until DATETIME NULL,
  frozen_ledger_id BIGINT NULL,
  available_ledger_id BIGINT NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| order_id | 会员订单 ID |
| payer_user_id | 付款用户 |
| beneficiary_user_id | 获得返利的用户 |
| rebate_level | 1 表示一级，2 表示二级 |
| rebate_rate | 返利比例 |
| order_pay_amount | 订单实付金额 |
| rebate_points | 返利积分 |
| status | 返利状态 |
| freeze_until | 冻结到期时间 |
| frozen_ledger_id | 冻结积分流水 |
| available_ledger_id | 解冻积分流水 |

索引：

```sql
CREATE UNIQUE INDEX uk_invite_rebates_idempotency ON invite_rebates(idempotency_key);
CREATE INDEX idx_invite_rebates_beneficiary ON invite_rebates(beneficiary_user_id, created_at);
CREATE INDEX idx_invite_rebates_order ON invite_rebates(order_id);
CREATE INDEX idx_invite_rebates_status_freeze ON invite_rebates(status, freeze_until);
```

返利规则：

1. 一级返利默认 50% 等值积分。
2. 二级返利默认 5% 等值积分。
3. 返利进入冻结积分。
4. 默认冻结 7 天。
5. 冻结期结束后，由定时任务解冻为可提现积分或可用积分。
6. 如果会员订单退款，返利应取消或扣回。

返利积分计算示例：

```text
积分兑换比例：100 积分 = 1 元
订单金额：19.9 元
一级返利：19.9 * 50% * 100 = 995 积分
二级返利：19.9 * 5% * 100 = 99.5，向下取整 99 积分
```

建议取整规则：

```text
rebate_points = floor(order_pay_amount * rebate_rate * exchange_rate)
```

---

# 13. 提现表

## 13.1 withdraw_orders 提现申请表

用途：记录用户提现申请。

```sql
CREATE TABLE withdraw_orders (
  id BIGINT PRIMARY KEY,
  withdraw_no VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  points_amount BIGINT NOT NULL,
  cash_amount DECIMAL(10,2) NOT NULL,
  fee_amount DECIMAL(10,2) NOT NULL DEFAULT 0,
  actual_amount DECIMAL(10,2) NOT NULL,
  exchange_rate INT NOT NULL DEFAULT 100,
  status VARCHAR(32) NOT NULL DEFAULT 'pending',
  is_first_withdraw BOOLEAN NOT NULL DEFAULT FALSE,
  is_member_snapshot BOOLEAN NOT NULL DEFAULT FALSE,
  member_level_snapshot VARCHAR(32) NOT NULL DEFAULT 'none',
  apply_ip VARCHAR(64) NULL,
  apply_device_id VARCHAR(128) NULL,
  review_by VARCHAR(64) NULL,
  review_remark VARCHAR(512) NULL,
  reviewed_at DATETIME NULL,
  paid_at DATETIME NULL,
  failed_reason VARCHAR(512) NULL,
  idempotency_key VARCHAR(128) NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

字段说明：

| 字段 | 说明 |
|---|---|
| withdraw_no | 提现单号 |
| points_amount | 提现消耗积分 |
| cash_amount | 积分兑换金额 |
| fee_amount | 手续费金额 |
| actual_amount | 实际到账金额 |
| exchange_rate | 兑换比例快照 |
| status | 提现状态 |
| is_first_withdraw | 是否首提 |
| is_member_snapshot | 申请时是否会员 |
| member_level_snapshot | 申请时会员等级 |
| review_by | 审核人 |
| review_remark | 审核备注 |
| idempotency_key | 提现申请幂等键 |

索引：

```sql
CREATE UNIQUE INDEX uk_withdraw_orders_no ON withdraw_orders(withdraw_no);
CREATE UNIQUE INDEX uk_withdraw_orders_idempotency ON withdraw_orders(idempotency_key);
CREATE INDEX idx_withdraw_orders_user_created ON withdraw_orders(user_id, created_at);
CREATE INDEX idx_withdraw_orders_status ON withdraw_orders(status);
CREATE INDEX idx_withdraw_orders_created ON withdraw_orders(created_at);
```

提现规则：

1. 新人首提门槛默认 1 元。
2. 普通用户后续提现门槛默认 5 元。
3. 会员提现门槛默认 1 元。
4. 提现申请后，积分先进入锁定状态。
5. 审核通过后，状态改为 `approved`。
6. 打款成功后，状态改为 `paid`，对应积分最终扣除。
7. 审核驳回后，状态改为 `rejected`，锁定积分退回可提现积分。

手续费计算：

```text
cash_amount = points_amount / exchange_rate
fee_amount = cash_amount * fee_rate
actual_amount = cash_amount - fee_amount
```

---

## 13.2 withdraw_logs 提现流水/状态日志表

用途：记录提现状态变化和审核操作。

```sql
CREATE TABLE withdraw_logs (
  id BIGINT PRIMARY KEY,
  withdraw_order_id BIGINT NOT NULL,
  withdraw_no VARCHAR(64) NOT NULL,
  user_id BIGINT NOT NULL,
  from_status VARCHAR(32) NULL,
  to_status VARCHAR(32) NOT NULL,
  operator_type VARCHAR(32) NOT NULL DEFAULT 'system',
  operator_id VARCHAR(64) NULL,
  remark VARCHAR(512) NULL,
  created_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE INDEX idx_withdraw_logs_order ON withdraw_logs(withdraw_order_id);
CREATE INDEX idx_withdraw_logs_user_created ON withdraw_logs(user_id, created_at);
```

日志规则：

1. 创建提现申请时写一条 `pending` 日志。
2. 审核通过、驳回、打款成功、打款失败均写日志。
3. 日志不可删除。

---

# 14. 影视与视频相关表

## 14.1 media_unlocks 影视权益解锁记录表（P1）

用途：记录用户通过邀请、会员、积分等方式解锁高清/4K 权益。

```sql
CREATE TABLE media_unlocks (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NOT NULL,
  unlock_type VARCHAR(32) NOT NULL,
  resource_id VARCHAR(128) NULL,
  category VARCHAR(64) NULL,
  source VARCHAR(64) NOT NULL,
  points_cost BIGINT NOT NULL DEFAULT 0,
  related_id VARCHAR(128) NULL,
  expired_at DATETIME NULL,
  created_at DATETIME NOT NULL
);
```

unlock_type 枚举：

| 值 | 说明 |
|---|---|
| hd | 高清权益 |
| fourk | 4K 权益 |
| copy_without_ad | 免广告复制 |
| follow_reminder | 追更提醒 |

索引：

```sql
CREATE INDEX idx_media_unlocks_user_type ON media_unlocks(user_id, unlock_type);
CREATE INDEX idx_media_unlocks_resource ON media_unlocks(resource_id);
```

---

## 14.2 video_parse_logs 视频解析日志表（P1）

用途：记录视频解析成功/失败，便于分析平台稳定性。

```sql
CREATE TABLE video_parse_logs (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NULL,
  input_hash VARCHAR(128) NOT NULL,
  platform VARCHAR(64) NULL,
  success BOOLEAN NOT NULL DEFAULT FALSE,
  error_code VARCHAR(64) NULL,
  error_message VARCHAR(512) NULL,
  need_ad BOOLEAN NOT NULL DEFAULT TRUE,
  is_member_snapshot BOOLEAN NOT NULL DEFAULT FALSE,
  duration_ms INT NULL,
  created_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE INDEX idx_video_parse_user_created ON video_parse_logs(user_id, created_at);
CREATE INDEX idx_video_parse_platform_success ON video_parse_logs(platform, success);
CREATE INDEX idx_video_parse_created ON video_parse_logs(created_at);
```

注意：

1. 不建议存储完整用户原始链接，建议存 hash 或脱敏内容。
2. 失败原因用于优化解析稳定性。

---

# 15. 配置表

## 15.1 app_configs 业务配置表

用途：存储积分、任务、会员、邀请、提现等业务配置。

```sql
CREATE TABLE app_configs (
  id BIGINT PRIMARY KEY,
  config_key VARCHAR(128) NOT NULL,
  config_value TEXT NOT NULL,
  description VARCHAR(512) NULL,
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE UNIQUE INDEX uk_app_configs_key ON app_configs(config_key);
CREATE INDEX idx_app_configs_status ON app_configs(status);
```

建议配置项：

| config_key | 内容 |
|---|---|
| points_config | 积分兑换、签到积分、广告加倍配置 |
| task_config | 每日任务次数配置 |
| member_config | 会员套餐与权益配置 |
| invite_config | 邀请奖励、返利、冻结期配置 |
| withdraw_config | 提现门槛、手续费、审核配置 |
| media_rights_config | 影视复制、高清/4K 权益配置 |
| video_config | 视频下载广告、会员免广告次数配置 |

示例：

```json
{
  "exchange_rate": 100,
  "checkin_base_points_normal": 1,
  "checkin_base_points_member": 2,
  "game_task_limit_normal": 10,
  "game_task_limit_member_month": 100,
  "withdraw_min_first": 1,
  "withdraw_min_normal": 5,
  "withdraw_min_member": 1
}
```

---

# 16. 埋点与日志表

## 16.1 event_logs 行为埋点表

用途：记录用户行为，支撑 MVP 数据验证。

```sql
CREATE TABLE event_logs (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NULL,
  event_name VARCHAR(128) NOT NULL,
  scene VARCHAR(128) NULL,
  page VARCHAR(128) NULL,
  source VARCHAR(128) NULL,
  extra_json TEXT NULL,
  device_id VARCHAR(128) NULL,
  ip VARCHAR(64) NULL,
  created_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE INDEX idx_event_logs_event_created ON event_logs(event_name, created_at);
CREATE INDEX idx_event_logs_user_created ON event_logs(user_id, created_at);
CREATE INDEX idx_event_logs_scene_created ON event_logs(scene, created_at);
```

核心事件：

| event_name | 说明 |
|---|---|
| app_open | 打开小程序 |
| tab_click | 点击 Tab |
| home_checkin_click | 首页签到点击 |
| checkin_success | 签到成功 |
| checkin_ad_bonus_success | 签到广告翻倍成功 |
| game_page_view | 游戏页访问 |
| game_start | 游戏开始 |
| game_complete | 游戏完成 |
| game_reward_success | 游戏积分到账 |
| ad_show | 广告展示 |
| ad_complete | 广告完成 |
| ad_failed | 广告失败 |
| media_page_view | 影视页访问 |
| media_copy_click | 资源复制点击 |
| media_copy_success | 资源复制成功 |
| video_parse_submit | 提交视频解析 |
| video_parse_success | 视频解析成功 |
| video_parse_failed | 视频解析失败 |
| member_page_view | 会员页访问 |
| member_order_create | 创建会员订单 |
| member_pay_success | 会员支付成功 |
| invite_page_view | 邀请页访问 |
| invite_share_click | 邀请分享点击 |
| invite_bind_success | 邀请绑定成功 |
| withdraw_apply_click | 提现申请点击 |
| withdraw_apply_success | 提现申请成功 |

---

# 17. 管理与风控表

## 17.1 admin_audit_logs 后台操作审计表（P1）

用途：记录后台审核提现、调整积分、冻结用户等操作。

```sql
CREATE TABLE admin_audit_logs (
  id BIGINT PRIMARY KEY,
  operator_id VARCHAR(64) NOT NULL,
  operator_name VARCHAR(128) NULL,
  action VARCHAR(128) NOT NULL,
  target_type VARCHAR(64) NOT NULL,
  target_id VARCHAR(128) NOT NULL,
  before_json TEXT NULL,
  after_json TEXT NULL,
  remark VARCHAR(512) NULL,
  created_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE INDEX idx_admin_audit_operator ON admin_audit_logs(operator_id, created_at);
CREATE INDEX idx_admin_audit_target ON admin_audit_logs(target_type, target_id);
```

---

## 17.2 risk_flags 风控标记表（P2）

用途：记录异常用户、异常设备、异常广告行为。

```sql
CREATE TABLE risk_flags (
  id BIGINT PRIMARY KEY,
  user_id BIGINT NULL,
  device_id VARCHAR(128) NULL,
  flag_type VARCHAR(64) NOT NULL,
  severity VARCHAR(32) NOT NULL DEFAULT 'medium',
  status VARCHAR(32) NOT NULL DEFAULT 'active',
  reason VARCHAR(512) NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
```

索引：

```sql
CREATE INDEX idx_risk_flags_user ON risk_flags(user_id, status);
CREATE INDEX idx_risk_flags_device ON risk_flags(device_id, status);
CREATE INDEX idx_risk_flags_type ON risk_flags(flag_type, status);
```

---

# 18. 关键业务流程数据写入

## 18.1 签到流程

```text
1. 用户点击签到。
2. 后端检查 users.status 是否正常。
3. 查询 checkin_records 是否已有当天记录。
4. 如果已有，返回已签到。
5. 读取积分配置。
6. 判断用户是否会员。
7. 创建 checkin_records。
8. 更新 user_accounts.withdrawable_points 或 consumable_points。
9. 写 points_ledger，idempotency_key = checkin:{user_id}:{date}。
10. 更新 daily_task_stats.checkin_done = true。
11. 返回签到成功。
```

## 18.2 签到广告翻倍流程

```text
1. 前端完成激励广告。
2. 提交 ad_event_id 和签到记录。
3. 后端检查 ad_events 是否已 rewarded。
4. 检查当天签到记录存在且 ad_bonus_used = false。
5. 创建或更新 ad_events。
6. 计算 bonus_points。
7. 更新 checkin_records.bonus_points。
8. 更新 user_accounts。
9. 写 points_ledger。
10. 更新 ad_events.status = rewarded。
```

## 18.3 游戏发积分流程

```text
1. 用户完成一局游戏。
2. 前端提交 round_id、game_code、result。
3. 后端检查 round_id 是否已存在。
4. 查询 daily_task_stats，判断是否超过每日任务次数。
5. 按配置计算 base_points。
6. 创建 game_rounds。
7. 更新 user_accounts。
8. 写 points_ledger，idempotency_key = game_task:{user_id}:{round_id}。
9. 更新 daily_task_stats.game_tasks_used 和 today_points。
10. 返回积分到账。
```

## 18.4 会员购买流程

```text
1. 用户选择会员套餐。
2. 创建 member_orders，状态 pending。
3. 发起微信支付。
4. 收到支付成功回调。
5. 按 order_no 或 transaction_id 幂等检查。
6. 更新订单状态 paid。
7. 更新或创建 user_memberships。
8. 发放会员赠送积分，写 points_ledger。
9. 处理邀请返利，写 invite_rebates 和冻结积分流水。
10. 更新订单状态 activated。
```

## 18.5 邀请绑定流程

```text
1. 新用户携带 invite_code 进入。
2. 登录后调用 invite/bind。
3. 根据 invite_code 找到邀请人。
4. 检查不能邀请自己。
5. 检查 invitee_user_id 是否已有绑定关系。
6. 查询邀请人的上级，确定二级关系。
7. 创建 invite_relations。
8. 发放邀请注册积分，可写 points_ledger。
9. 返回绑定成功。
```

## 18.6 会员返利流程

```text
1. 会员订单 activated。
2. 查询 payer_user_id 的邀请关系。
3. 如果有一级邀请人，计算一级返利积分。
4. 如果有二级邀请人，计算二级返利积分。
5. 分别创建 invite_rebates。
6. 返利积分进入 frozen_points。
7. 写 points_ledger，change_type = freeze。
8. 设置 freeze_until。
9. 标记 member_orders.invite_rebate_processed = true。
```

## 18.7 邀请返利解冻流程

```text
1. 定时任务扫描 invite_rebates.status = frozen 且 freeze_until <= 当前时间。
2. 检查关联订单未退款、用户未被冻结。
3. 从 frozen_points 扣减。
4. 增加 withdrawable_points 或 consumable_points，按配置决定。
5. 写 points_ledger，change_type = unfreeze。
6. 更新 invite_rebates.status = available。
```

## 18.8 提现申请流程

```text
1. 用户提交提现金额。
2. 后端读取提现配置和用户会员状态。
3. 判断是否满足首提/普通/会员提现门槛。
4. 计算 points_amount、cash_amount、fee_amount、actual_amount。
5. 检查 withdrawable_points 是否足够。
6. 创建 withdraw_orders，状态 pending。
7. 从 withdrawable_points 扣到 locked_withdraw_points。
8. 写 points_ledger，change_type = withdraw_lock。
9. 写 withdraw_logs。
10. 返回申请成功。
```

## 18.9 提现驳回流程

```text
1. 管理员审核驳回。
2. 更新 withdraw_orders.status = rejected。
3. 从 locked_withdraw_points 退回 withdrawable_points。
4. 写 points_ledger，change_type = withdraw_reject_return。
5. 写 withdraw_logs。
```

## 18.10 提现成功流程

```text
1. 管理员审核并完成打款。
2. 更新 withdraw_orders.status = paid。
3. 从 locked_withdraw_points 扣除。
4. 增加 withdrawn_points。
5. 写 points_ledger，change_type = withdraw_success。
6. 写 withdraw_logs。
```

---

# 19. 索引总表

## 19.1 唯一索引

| 表 | 唯一索引 | 目的 |
|---|---|---|
| users | openid | 防止重复用户 |
| users | invite_code | 邀请码唯一 |
| user_accounts | user_id | 每用户一个账户 |
| points_ledger | idempotency_key | 积分流水幂等 |
| checkin_records | user_id + checkin_date | 防重复签到 |
| ad_events | ad_event_id | 广告幂等 |
| game_rounds | round_id | 游戏回合幂等 |
| daily_task_stats | user_id + stat_date | 每日任务唯一 |
| member_plans | plan_code | 套餐唯一 |
| member_orders | order_no | 订单唯一 |
| member_orders | idempotency_key | 订单回调幂等 |
| user_memberships | user_id | 每用户一个会员状态 |
| invite_relations | invitee_user_id | 每用户只绑定一个上级 |
| invite_rebates | idempotency_key | 返利幂等 |
| withdraw_orders | withdraw_no | 提现单唯一 |
| withdraw_orders | idempotency_key | 提现申请幂等 |
| app_configs | config_key | 配置唯一 |

## 19.2 查询索引

| 表 | 索引 | 场景 |
|---|---|---|
| points_ledger | user_id + created_at | 我的收益明细 |
| ad_events | user_id + scene + created_at | 广告完成统计 |
| game_rounds | user_id + played_date | 每日游戏次数 |
| member_orders | user_id + created_at | 用户订单列表 |
| invite_relations | inviter_user_id | 我的邀请人数 |
| invite_rebates | beneficiary_user_id + created_at | 我的返利记录 |
| withdraw_orders | user_id + created_at | 我的提现记录 |
| event_logs | event_name + created_at | 数据分析 |

---

# 20. Mock 与真实边界

## 20.1 MVP 必须真实落库

以下数据必须真实落库，不能只 mock：

1. 用户信息。
2. 用户积分账户。
3. 积分流水。
4. 签到记录。
5. 广告事件幂等记录。
6. 游戏回合记录。
7. 每日任务统计。
8. 会员订单。
9. 用户会员状态。
10. 邀请关系。
11. 邀请返利。
12. 提现申请。
13. 提现日志。

## 20.2 可先 mock 的部分

1. 微信支付真实回调：可先用 mock 支付成功接口，但必须走 `member_orders` 和 `user_memberships` 数据流程。
2. 自动打款：可先人工打款，只记录提现状态。
3. 邀请海报：可先复制邀请码。
4. 影视权益校验：可先用简单配置判断。
5. 风控：可先只做状态字段和基础限制。
6. 后台统计：可先写 `event_logs`，不做可视化页面。

## 20.3 不允许 mock 的关键点

1. 积分余额不能前端写死。
2. 积分发放不能没有流水。
3. 广告奖励不能没有幂等。
4. 提现不能只改状态不锁定积分。
5. 会员订单不能不记录订单号。
6. 邀请返利不能重复发放。

---

# 21. Codex 执行建议

请 Codex 按以下顺序落地：

1. 先扫描当前项目使用的数据库类型和 ORM。
2. 如果已有用户、积分、会员、提现等表，优先兼容旧表，不要重复造表。
3. 如果旧表字段不足，新增字段或新增流水表。
4. 优先实现 `user_accounts` 和 `points_ledger`。
5. 再实现 `checkin_records`、`ad_events`、`game_rounds`、`daily_task_stats`。
6. 再实现 `member_orders`、`user_memberships`、`invite_relations`、`invite_rebates`。
7. 最后实现 `withdraw_orders`、`withdraw_logs`、`event_logs`。
8. 所有涉及积分变动的接口必须开启事务。
9. 所有幂等键必须加唯一索引。
10. 所有金额和积分计算必须放在后端。
11. 前端只能展示后端返回的数据，不能自行计算最终奖励。

---

# 22. 验收标准

## 22.1 积分系统验收

1. 用户签到后积分增加。
2. 游戏完成后积分增加。
3. 会员赠送积分能到账。
4. 邀请返利能进入冻结积分。
5. 提现申请能锁定积分。
6. 提现驳回能退回积分。
7. 每次积分变化都能在积分明细查到。
8. 重复请求不会重复发积分。

## 22.2 广告幂等验收

1. 同一个 `ad_event_id` 重复提交，只发一次奖励。
2. 广告事件能记录 scene。
3. 广告奖励能关联积分流水。
4. 广告失败不会发积分。

## 22.3 会员订单验收

1. 创建订单后状态为 pending。
2. 支付成功后会员状态生效。
3. 会员权益过期时间正确。
4. 会员赠送积分只发一次。
5. 邀请返利只处理一次。

## 22.4 邀请关系验收

1. 用户不能邀请自己。
2. 用户只能绑定一个上级。
3. 一级邀请关系正确。
4. 二级邀请关系正确。
5. 邀请人数能正确统计。
6. 返利进入冻结积分。

## 22.5 提现验收

1. 不满足提现门槛不能提交。
2. 可提现积分不足不能提交。
3. 提现申请后积分被锁定。
4. 提现通过后锁定积分被扣除。
5. 提现驳回后积分退回。
6. 提现状态变更有日志。

## 22.6 数据分析验收

1. 打开小程序有 app_open 事件。
2. 签到成功有 checkin_success 事件。
3. 游戏完成有 game_complete 事件。
4. 广告完成有 ad_complete 事件。
5. 会员页访问有 member_page_view 事件。
6. 提现申请有 withdraw_apply_success 事件。

---

# 23. 待确认问题

以下问题不阻塞 v0.1 建模，但上线前建议确认：

1. 当前项目实际数据库类型是什么。
2. 当前是否已有积分/余额表。
3. 当前是否已有会员订单表。
4. 当前微信支付是否已接入。
5. 当前提现是人工打款还是企业付款到零钱。
6. 积分兑换比例是否最终确定为 `100 积分 = 1 元`。
7. 会员价格是否采用 `19.9 / 49.9 / 99.9`。
8. 邀请返利是否仍采用一级 50%、二级 5%。
9. 邀请返利是可提现积分还是仅可消耗积分。
10. 签到积分和游戏积分是否都允许提现。
11. 会员赠送积分是否允许提现，还是仅可消耗。
12. 普通用户和会员的每日游戏任务次数是否最终为 10 / 100 / 150 / 200。
13. 提现手续费是否正式启用。
14. 提现审核周期如何展示。
15. 异常用户冻结规则是否需要在 v0.1 上线。

---

# 24. v0.1 推荐默认配置

```json
{
  "points": {
    "exchange_rate": 100,
    "display_unit": "积分"
  },
  "checkin": {
    "normal_points": 1,
    "member_points": 2,
    "ad_bonus_min": 1,
    "ad_bonus_max": 3,
    "continuous_3_days_bonus": 3,
    "continuous_7_days_bonus": 10
  },
  "game_task": {
    "normal_daily_limit": 10,
    "month_member_daily_limit": 100,
    "quarter_member_daily_limit": 150,
    "year_member_daily_limit": 200,
    "base_points_min": 1,
    "base_points_max": 2,
    "ad_multiplier": 2
  },
  "member": {
    "plans": [
      {
        "code": "month",
        "name": "月卡",
        "price": 19.9,
        "original_price": 29.9,
        "duration_days": 31,
        "gift_points": 199,
        "daily_game_task_limit": 100
      },
      {
        "code": "quarter",
        "name": "季卡",
        "price": 49.9,
        "original_price": 59.9,
        "duration_days": 93,
        "gift_points": 599,
        "daily_game_task_limit": 150
      },
      {
        "code": "year",
        "name": "年卡",
        "price": 99.9,
        "original_price": 239.9,
        "duration_days": 365,
        "gift_points": 1299,
        "daily_game_task_limit": 200
      }
    ]
  },
  "invite": {
    "register_points": 10,
    "hd_unlock_count": 3,
    "fourk_unlock_count": 5,
    "level1_member_rebate_rate": 0.5,
    "level2_member_rebate_rate": 0.05,
    "rebate_freeze_days": 7
  },
  "withdraw": {
    "first_min_amount": 1,
    "normal_min_amount": 5,
    "member_min_amount": 1,
    "normal_fee_rate": 0.1,
    "member_fee_rate": 0.05,
    "manual_review": true,
    "daily_limit_amount": 100,
    "show_daily_limit_to_user": false
  }
}
```
