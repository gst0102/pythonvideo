# 03-tech-spec.md

## 1. 技术目标

本阶段技术目标：

> 在现有微信小程序基础上，新增统一积分、签到、任务、邀请、会员权益、提现与埋点能力，并尽量复用当前页面与接口。

要求：

1. 不盲目重构现有项目。
2. 能在现有首页、影视、游戏、我的四个 Tab 上渐进改造。
3. 所有核心规则配置化。
4. 积分、广告、提现必须具备幂等处理和明细记录。
5. mock 与真实接入边界明确。

## 2. 运行环境假设

由于当前文档未包含完整代码结构，v0.1 采用以下假设：

1. 前端为微信小程序原生或类原生结构。
2. 后端存在用户、会员、积分、影视资源、视频解析等接口，若不存在则需新增。
3. 数据库可新增表或集合。
4. 已开通微信流量主，激励广告可接入。
5. 会员支付已存在或可接入微信支付。
6. 当前视频下载、影视资源抓取已有基础实现。

Codex 执行前必须先扫描项目结构，并根据真实结构调整文件路径。

## 3. 架构模块

### 3.1 前端模块

1. 首页模块
   - 今日福利卡。
   - 签到入口。
   - 视频下载助手。
   - 热门入口。
   - 下载失败兜底。

2. 影视模块
   - 资源分类。
   - 搜索。
   - 资源列表。
   - 复制资源。
   - 解锁高清/追更。

3. 游戏模块
   - 今日互动任务。
   - 签到任务入口。
   - 小游戏列表。
   - 石头剪刀布游戏。
   - 广告加倍。

4. 我的模块
   - 积分资产。
   - 提现。
   - 会员中心。
   - 邀请好友。
   - 收益记录。
   - 客服。

### 3.2 后端模块

1. 用户模块。
2. 积分账户模块。
3. 积分明细模块。
4. 签到模块。
5. 任务模块。
6. 广告回调模块。
7. 会员模块。
8. 邀请关系模块。
9. 提现模块。
10. 影视权益模块。
11. 视频解析模块。
12. 埋点/统计模块。

## 4. 接口设计 v0.1


### 4.0 微信静默登录

#### POST /api/auth/wechat-login

用途：微信小程序静默登录。

前端流程：

1. 小程序启动或用户执行需要身份的动作前调用 `wx.login()`。
2. 前端将 `code` 和可选 `invite_code` 发送给后端。
3. 前端不得保存或接触 `session_key`。

请求：

```json
{
  "code": "wx.login 返回的临时 code",
  "invite_code": "可选，来自分享路径的邀请码"
}
```

响应：

```json
{
  "token": "系统登录 token",
  "user": {
    "id": 1,
    "nickname": "悦享用户1234",
    "avatar_url": "默认头像 URL",
    "is_member": false,
    "member_level": "none",
    "member_expired_at": null,
    "invite_code": "A1B2C3"
  }
}
```

后端要求：

1. 后端调用微信 `code2Session` 换取 `openid`、`session_key`，如满足条件可获取 `unionid`。
2. 根据 `openid` 查找或创建系统用户。
3. 首次创建用户时同步初始化积分账户、邀请码和新人任务状态。
4. 如请求携带合法 `invite_code`，在用户首次创建或未绑定上级时绑定邀请关系。
5. 用户不能绑定自己，不能重复绑定上级。
6. 后端生成自有登录 token，前端后续请求携带 token。
7. `AppSecret` 和 `session_key` 只能在后端使用，不能返回前端，不能写入前端代码。
8. 支付、积分、广告回调、提现不能依赖前端传入的 user_id，必须以 token 解析出的 user_id 为准。

MVP 阶段不强制获取用户头像、昵称、手机号。用户展示信息使用默认昵称和默认头像。


### 4.1 用户资产

#### GET /api/user/asset

用途：获取用户积分资产。

响应：

```json
{
  "total_points": 75,
  "withdrawable_points": 30,
  "frozen_points": 0,
  "consumed_points": 0,
  "withdrawn_amount": 0.0,
  "exchange_rate": 100,
  "convertible_amount": 0.30,
  "is_member": false,
  "member_expired_at": null
}
```

### 4.2 签到

#### GET /api/checkin/status

用途：获取今日签到状态。

响应：

```json
{
  "checked_in_today": false,
  "continuous_days": 0,
  "today_base_points": 1,
  "can_ad_bonus": true
}
```

#### POST /api/checkin

用途：执行每日签到。

请求：

```json
{
  "source": "home"
}
```

响应：

```json
{
  "success": true,
  "points_added": 1,
  "continuous_days": 1,
  "detail_id": "point_detail_id"
}
```

#### POST /api/checkin/ad-bonus

用途：签到后看广告加倍。

请求：

```json
{
  "ad_event_id": "reward_ad_event_id"
}
```

响应：

```json
{
  "success": true,
  "points_added": 2,
  "detail_id": "point_detail_id"
}
```

要求：同一天只能执行一次签到广告加倍。

### 4.3 互动任务

#### GET /api/tasks/today

用途：获取今日任务状态。

响应：

```json
{
  "date": "2026-06-04",
  "today_points": 10,
  "game_tasks_used": 2,
  "game_tasks_limit": 10,
  "is_member": false,
  "tasks": [
    {
      "code": "checkin",
      "name": "每日签到",
      "status": "completed",
      "points": 1
    },
    {
      "code": "rps_game",
      "name": "石头剪刀布",
      "status": "available",
      "points_range": "1-2"
    }
  ]
}
```

#### POST /api/tasks/game/complete

用途：完成小游戏任务后发积分。

请求：

```json
{
  "game_code": "rps",
  "round_id": "unique_round_id",
  "result": "win",
  "ad_event_id": null
}
```

响应：

```json
{
  "success": true,
  "points_added": 2,
  "today_used": 3,
  "today_limit": 10
}
```

要求：round_id 幂等，同一局不能重复发积分。

### 4.4 广告事件

#### POST /api/ad/reward/complete

用途：记录激励广告完成事件。

请求：

```json
{
  "ad_event_id": "unique_ad_event_id",
  "scene": "checkin_bonus",
  "related_id": "checkin_id_or_task_id",
  "provider": "wechat_reward_ad"
}
```

响应：

```json
{
  "success": true,
  "processed": true
}
```

要求：ad_event_id 必须幂等。

### 4.5 会员

#### GET /api/member/status

响应：

```json
{
  "is_member": false,
  "level": "none",
  "expired_at": null,
  "plans": [
    {"code": "month", "name": "月卡", "price": 19.9},
    {"code": "quarter", "name": "季卡", "price": 49.9},
    {"code": "year", "name": "年卡", "price": 99.9}
  ]
}
```

#### POST /api/member/order

用途：创建会员订单。

请求：

```json
{
  "plan_code": "month"
}
```

响应：微信支付参数或 mock 订单。

#### POST /api/member/payment-callback

用途：会员支付成功回调。

要求：

1. 幂等处理。
2. 开通会员。
3. 发放开通赠送积分。
4. 触发邀请返利积分冻结。

### 4.6 邀请

#### GET /api/invite/summary

响应：

```json
{
  "invite_code": "ABC123",
  "invited_count": 2,
  "level1_count": 2,
  "level2_count": 0,
  "points_from_invite": 20,
  "hd_unlock_progress": {"target": 3, "current": 2},
  "fourk_unlock_progress": {"target": 5, "current": 2}
}
```

#### POST /api/invite/bind

请求：

```json
{
  "invite_code": "ABC123"
}
```

要求：

1. 用户不能绑定自己。
2. 用户只能绑定一次上级。
3. 需要记录一级和二级关系。

### 4.7 影视资源

#### GET /api/media/list

参数：category、keyword、page、page_size。

#### POST /api/media/copy

用途：复制资源链接前校验权益。

请求：

```json
{
  "resource_id": "media_id",
  "link_type": "baidu"
}
```

响应：

```json
{
  "allowed": true,
  "need_ad": false,
  "need_points": false,
  "link": "https://..."
}
```

如果需要广告：

```json
{
  "allowed": false,
  "need_ad": true,
  "scene": "media_copy"
}
```

### 4.8 视频解析

#### POST /api/video/parse

请求：

```json
{
  "input_text": "视频分享链接或带链接文案"
}
```

响应：

```json
{
  "success": true,
  "platform": "douyin",
  "download_url": "https://...",
  "need_ad": true,
  "fallback_message": null
}
```

失败响应：

```json
{
  "success": false,
  "error_code": "PARSE_FAILED",
  "message": "当前链接解析失败，可换链接重试。",
  "fallback_actions": ["retry", "feedback", "go_tasks", "go_media"]
}
```

### 4.9 提现

#### GET /api/withdraw/summary

响应：

```json
{
  "withdrawable_points": 300,
  "withdrawable_amount": 3.0,
  "min_withdraw_amount": 1.0,
  "fee_rate": 0.1,
  "is_member": false
}
```

#### POST /api/withdraw/apply

请求：

```json
{
  "amount": 1.0
}
```

响应：

```json
{
  "success": true,
  "withdraw_id": "withdraw_id",
  "status": "pending"
}
```

### 4.10 埋点

#### POST /api/events/track

请求：

```json
{
  "event_name": "checkin_success",
  "scene": "home",
  "extra": {}
}
```

## 5. 配置项

建议新增配置表或配置文件。

```json
{
  "points_exchange_rate": 100,
  "checkin_base_points_normal": 1,
  "checkin_base_points_member": 2,
  "checkin_ad_bonus_min": 1,
  "checkin_ad_bonus_max": 3,
  "game_task_limit_normal": 10,
  "game_task_limit_member_month": 100,
  "game_task_limit_member_quarter": 150,
  "game_task_limit_member_year": 200,
  "game_base_points_min": 1,
  "game_base_points_max": 2,
  "invite_register_points": 10,
  "invite_hd_unlock_count": 3,
  "invite_4k_unlock_count": 5,
  "member_level1_rebate_rate": 0.5,
  "member_level2_rebate_rate": 0.05,
  "invite_rebate_freeze_days": 7,
  "withdraw_min_first": 1,
  "withdraw_min_normal": 5,
  "withdraw_min_member": 1,
  "withdraw_fee_rate_normal": 0.1,
  "withdraw_fee_rate_member": 0.05
}
```

## 6. Mock 与真实接入边界

### 6.1 可以 mock

1. 会员支付：可以先 mock 支付成功，保留回调接口。
2. 提现打款：MVP 只做提现申请和人工审核状态，不自动打款。
3. 邀请海报：可以先用复制邀请码替代。
4. 新游戏：除石头剪刀布外可先用占位卡片。
5. 影视权益：如现有资源接口复杂，可先完成按钮文案和权限校验 mock。
6. 后台统计：可先用日志表记录，后续再做可视化后台。

### 6.2 必须真实接入或复用现有能力

1. 用户身份识别。
2. 积分账户和积分明细。
3. 签到防重复。
4. 广告完成回调幂等。
5. 游戏任务完成记录。
6. 会员状态判断。
7. 邀请关系绑定。
8. 提现申请记录。
9. 现有视频解析流程。
10. 现有影视资源列表。

### 6.3 不要在 v0.1 做的真实接入

1. 自动提现打款。
2. 完整财务后台。
3. 风控模型自动化。
4. 独立游戏小程序互通。
5. 多游戏复杂结算。

## 7. 幂等与账务要求

1. 每次积分变动必须产生积分明细。
2. 广告回调必须使用唯一 ad_event_id 防重复。
3. 游戏每局必须使用唯一 round_id 防重复。
4. 会员支付回调必须使用订单号防重复。
5. 邀请返利必须绑定会员订单，不能重复发放。
6. 提现申请后对应可提现积分必须冻结或扣减。
7. 提现驳回必须退回积分。
8. 所有积分变动需要记录 reason、source、related_id。

## 8. 安全与风控基础

1. 同一用户同一天签到一次。
2. 同一设备/用户广告完成频率可限制。
3. 邀请关系不能自邀请。
4. 提现需要人工审核。
5. 可配置每日提现上限。
6. 可配置每日可提现积分上限。
7. 异常用户可冻结积分。
8. 不在前台承诺固定收益。
