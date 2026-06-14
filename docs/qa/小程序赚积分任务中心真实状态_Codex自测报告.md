# 小程序赚积分任务中心真实状态_Codex自测报告

日期：2026-06-15

## 1. 本次修改目标

将小程序“赚积分任务中心”的关键任务状态接入真实后端接口，避免前端本地任务状态与真实积分流水不一致。

## 2. 修改文件列表

- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/earn.vue`
- `video-ts/src/pages/netdisk/index.vue`

## 3. 核心实现说明

- 新增 `TaskOverviewApi()`，调用后端 `/tasks/overview`。
- 新增 `TaskOverviewResType` 类型，承接后端签到、小游戏、账户余额状态。
- “每日签到”任务改为以后端 `checkin.checked_in` 判断是否已完成。
- “小游戏赚积分”任务改为以后端 `game_task.today_used / today_limit / today_remaining` 判断是否可继续。
- 上传、补链、邀请类任务改为用 `/mine/assets` 的真实统计做进度提示，不再读取本地 `netdisk_earn_task_status`。
- 删除任务中心本地点按钮后写“任务已完成”的逻辑。
- 修复首页求资源投稿数字段名：`submission_count` 改为后端真实字段 `submissions_count`。

## 4. 已运行测试

- `pnpm run type-check`
- `pnpm run build:mp-weixin`
- 关键静态扫描：确认任务中心不再写入 `netdisk_earn_task_status`，不再出现“任务已完成”本地假完成提示。

## 5. 测试结果

- 类型检查通过。
- 微信小程序构建通过。
- 构建产物 `dist` 已清理，未纳入提交范围。

## 6. 未覆盖测试项

- 本机无法运行后端专项脚本：本机系统 Python 为 3.9，项目要求 3.10+；仓库 `.venv` 是 Windows 结构；Codex 内置 Python 缺少 `sqlalchemy`。
- 未在生产数据库直接运行后端验证脚本，避免测试脚本写入生产数据。

## 7. 可能影响范围

- 小程序“赚积分任务中心”页面。
- 小程序首页热门求资源投稿人数展示。
- 签到和小游戏入口按钮状态展示。

## 8. 需要人工确认的地方

- 在小程序体验版登录真实账号后确认：
  1. 未签到时显示“可领取”，点击进入签到页。
  2. 签到后返回任务中心显示“已完成”。
  3. 小游戏次数用完后显示“今日已满”。
  4. 上传、补链、邀请任务按钮仍然能进入对应页面，但不会前端假完成。

## 9. 2026-06-15 补充修复

- 修复赚积分页面小游戏任务卡片被长文案挤压变形的问题。
- 小游戏页面去掉“预估积分”文案，统一展示“积分”。
- 小游戏文案调整为“赢 +4、平 0、输 -2，完整看广告后积分到账”。
- 积分明细中的 `game_estimated` 展示文案由“小游戏预估积分”改为“小游戏积分”。
- 签到任务文案改为真实规则：普通用户每日签到 +1 分，会员每日签到 +2 分。
- 后端补齐 `stage2_points_config` 默认值，保证代码默认结算规则和前端文案一致：
  - `game_rps_win_points = 4`
  - `game_rps_lose_points = -2`
  - `checkin_base_points_normal = 1`
  - `checkin_base_points_member = 2`

## 10. 线上配置确认

- 当前线上 `stage2_points_config` 中签到配置为：普通用户 1 分、会员 2 分，所以体验版显示 +1 属于当前后端配置结果。
- 当前线上 `stage2_task_config` 中普通用户小游戏每日上限为 10 次，所以页面显示 9/10 是配置结果，不是前端写死。
- 如果产品上希望普通用户每天只玩 3 次或 5 次，需要更新线上 `stage2_task_config.daily_game_task_limit_normal`。

## 11. PC 后台配置入口

- PC 后台“规则配置”页新增：
  - “签到与小游戏积分”：可配置普通签到分、会员签到分、签到广告奖励、猜拳赢局积分、猜拳输局扣分、广告倍数。
  - “每日任务次数”：可配置普通用户、月会员、季会员、年会员每日小游戏次数。
- 保存接口：
  - `stage2_points_config` 通过 `/admin/configs` 保存。
  - `stage2_task_config` 通过 `/admin/configs` 保存。
- 已运行：
  - PC 后台 `npm run build`
  - 小程序 `pnpm run type-check`
  - 小程序 `pnpm run build:mp-weixin`
  - 后端 `python3 -m py_compile services/config_service.py`
