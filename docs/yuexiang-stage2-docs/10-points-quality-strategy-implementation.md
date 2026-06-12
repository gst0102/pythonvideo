# 悦享资源库积分质量策略 v0.2 开发文档

## 1. 功能目标

将悦享资源库从“固定积分解锁 + 固定上传奖励”升级为“积分消耗、上传者分成、平台回收、信用/贡献排序”的 MVP 闭环。

本阶段优先落地：

- 新用户注册送 100 可用积分。
- 上传奖励分期：审核通过先发 2 分，资源有效满 7 天再发 3 分。
- 解锁资源后按资源等级做上传者分成和平台回收统计。
- 资源推荐排序引入质量分，鼓励高信用、高贡献上传者资源靠前。
- 确认失效后按上线时长扣分、降信用，并支持负积分处罚。

## 2. 用户流程

### 2.1 新用户

1. 用户首次微信登录。
2. 后端创建用户和积分账户。
3. 发放 `signup_seed_points` 流水，增加 100 可用积分。

### 2.2 上传资源

1. 用户提交资源，不立即发积分。
2. 后台审核通过后生成正式资源，并关联上传者。
3. 系统发放首段奖励 2 分，记录 `upload_reward_approved_part1`。
4. 资源有效满 7 天后，后续定时任务可发放 3 分，记录 `upload_reward_valid_7d`。

### 2.3 解锁资源

1. 用户解锁资源，按资源等级扣可用积分。
2. 首次解锁才增加下载数。
3. 上传者获得分成：普通 1 分、精选 2 分、官方 0 分。
4. 平台回收剩余积分，并用 `platform_recovery` 中性流水记录统计口径。
5. 重复解锁不重复扣分、不重复分成。

### 2.4 投诉与失效

1. 用户投诉后资源 `report_count` 增加，质量分下降。
2. 达到投诉阈值后资源隐藏。
3. 运营确认失效后资源 `invalid_count` 增加并隐藏。
4. 系统根据资源上线时长处罚上传者/补链者：
   - 7 天内：扣 5 分，信用 -3。
   - 7-30 天：扣 5 分，信用 -2。
   - 30 天后：扣 2 分，信用 -1。
5. 积分不足时允许可用积分变成负数，后续限制上传和发布悬赏。

## 3. 数据结构

- `user_quality_profiles`
  - `credit_score`
  - `contribution_score`
  - `short_invalid_count`
  - `upload_restricted_until`
  - `risk_level`

- `netdisk_resources`
  - `uploader_user_id`
  - `invalid_count`
  - `report_count`
  - `quality_score`
  - `valid_days_rewarded`
  - `last_invalid_at`

- `netdisk_uploads`
  - `reward_released_points`
  - `valid_days_rewarded`

## 4. 接口规则

- `GET /netdisk/resources`
  - `sort=hot/recommend/featured` 使用质量分排序。
  - 返回 `quality_score`、`uploader_credit_level`、`valid_days`、`report_count`、`invalid_count`。

- `POST /netdisk/resources/{resource_id}/unlock`
  - 保持原有幂等。
  - 返回 `creator_reward` 和 `platform_recovered_points`。

- `POST /netdisk/uploads`
  - 上传提交不发冻结分。
  - 返回最高奖励和已释放奖励字段。

## 5. 业务规则

- 积分余额不参与资源排序。
- 充值金额不参与资源排序。
- 推荐排序主要看资源质量分，信用/贡献只做适度加权。
- 高风险用户不能上传资源。
- 负积分用户不能上传资源或发布求资源。
- 官方资源没有上传者分成，平台回收全部解锁积分。

## 6. 验收条件草案

- 新用户首次登录后获得 100 可用积分。
- 上传提交后不立即发积分。
- 上传审核通过后发 2 分，并创建正式资源。
- 首次解锁普通资源扣 5 分，上传者得 1 分，平台回收 4 分。
- 首次解锁精选资源扣 10 分，上传者得 2 分，平台回收 8 分。
- 重复解锁不重复扣分、不重复分成。
- 单资源每日上传者分成不超过 10 分。
- 投诉会降低资源质量分。
- 确认失效会隐藏资源、扣分、降信用。
- 积分不足处罚时可用积分允许为负数，负积分用户被限制上传和发布悬赏。
