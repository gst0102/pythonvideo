# 求资源悬赏闭环 MVP 开发文档

## 功能目标

把“求资源”从展示需求升级为可流通积分闭环：发布者发布悬赏时冻结可用积分，其他用户按悬赏投稿，发布者采纳后悬赏积分发给投稿者；未采纳、取消或过期时冻结积分退回发布者。

## 用户流程

1. 发布者进入求资源页，发布需求并设置 5-50 分悬赏。
2. 后端校验发布者可用积分和信用风险，通过后冻结悬赏积分。
3. 其他用户从悬赏卡片进入投稿页，提交资源链接。
4. 发布者在“我的求资源”中查看投稿。
5. 发布者采纳其中一条投稿后，悬赏状态改为已采纳，冻结积分转为投稿者可用积分。
6. 未采纳需求支持取消或过期退回积分。

## 接口设计

- `GET /netdisk/requests`
  - 返回悬赏列表，增加 `accepted_upload_id`、`bounty_status`、`can_submit`。
- `GET /netdisk/requests/mine`
  - 返回我发布的悬赏，增加投稿摘要。
- `POST /netdisk/requests`
  - 创建悬赏并冻结积分。
- `GET /netdisk/requests/{id}/submissions`
  - 发布者查看该悬赏投稿列表；投稿者可看到自己的投稿。
- `POST /netdisk/requests/{id}/submissions`
  - 对悬赏投稿，复用上传字段。
- `POST /netdisk/requests/{id}/submissions/{upload_id}/accept`
  - 发布者采纳投稿，转移悬赏积分。
- `POST /netdisk/requests/{id}/cancel`
  - 发布者取消未采纳悬赏，退回冻结积分。
- `POST /netdisk/requests/expire`
  - 后端任务或人工触发，过期未采纳悬赏退回积分。

## 数据结构

`netdisk_requests` 增加：

- `accepted_upload_id`
- `bounty_status`: `frozen / paid / returned`
- `expires_at`
- `accepted_at`
- `closed_at`

`netdisk_uploads` 增加：

- `request_id`
- `accepted_at`

积分流水新增类型：

- `request_bounty_freeze`
- `request_bounty_award`
- `request_bounty_return`

## 业务规则

- 悬赏积分范围 5-50 分。
- 发布时从 `consumable_points` 冻结到 `frozen_points`。
- 可用积分不足不能发布。
- 负积分或高风险用户不能发布悬赏。
- 同一用户不能给自己的悬赏投稿。
- 同一悬赏同一用户只能保留一次有效投稿。
- 同一悬赏只能采纳一次。
- 采纳后发布者冻结积分减少，投稿者可用积分增加。
- 取消/过期只允许未采纳悬赏退回。
- 所有冻结、发放、退回都必须写积分流水并使用幂等 key。

## 前端范围

- 求资源列表展示悬赏状态、投稿人数、是否已采纳。
- 发布页文案改为“发布后冻结悬赏积分”。
- 悬赏卡片“提交资源”进入带 `request_id` 的投稿页。
- 我的求资源卡片展示投稿列表入口、采纳按钮、取消按钮。
- 我的上传展示“悬赏投稿/已被采纳/未采纳”状态。

## 风险点

- 重复点击采纳导致重复发积分。
- 取消和采纳并发导致既退回又发放。
- 投稿者可给自己悬赏投稿。
- 前端展示的悬赏状态和积分流水不一致。
- 过期退回重复执行导致重复退分。

## MVP 不做

- 自动检测资源是否真实可用。
- 复杂仲裁和申诉。
- 多人分摊悬赏。
- 悬赏置顶/加急付费。
