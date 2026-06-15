# 每日获取积分口径_Codex自测报告

## 1. 本次修改目标

修复“每日获取积分 0/60”分子口径：取消求资源后退回的悬赏本金不应算作今日获取积分。

## 2. 修改文件列表

- `services/points_summary_service.py`
- `scripts/verify_daily_earn_summary.py`
- `../AGENTS.md`
- `../docs/codex-error-memory.md`

## 3. 核心实现说明

- 保留每日获取积分的动态汇总逻辑。
- 新增退回类 `change_type` 排除规则。
- `request_bounty_return`、提现驳回退回、退款回滚等“本金/回滚”流水不计入今日获取。
- 真正奖励类流水仍可计入，例如签到、游戏正向奖励。

## 4. 已运行测试

- 线上容器执行：`python3 /app/scripts/verify_daily_earn_summary.py --execute`
- 线上容器执行：`python3 /app/scripts/verify_featured_today_selection.py`
- 线上真实用户服务层复查：`PointsSummaryService.build_summary`
- 线上真实 HTTP 接口复查：`GET /mine/assets`

## 5. 测试结果

- 每日获取口径验证通过：签到/游戏计入，求资源悬赏退回不计入。
- 今日精选回归通过。
- 真实用户 `mine/assets` 返回：
  - `today_earned_points = 10`
  - `today_earn_cap = 60`
  - `today_can_earn = 50`

## 6. 未覆盖测试项

- 小程序端页面截图未复测，因为前端包上传状态不由后端部署自动完成。
- 其他历史退回类流水只按当前已知 `change_type` 覆盖，后续新增退回类型需要同步加入排除清单。

## 7. 可能影响范围

- 影响首页、赚积分页、我的页中每日获取积分进度展示。
- 不影响积分余额，不修改任何历史流水，不影响用户实际可用积分。

## 8. 需要 AI 测试官复核的事项

- 复核“每日获取积分”是否只应该统计签到、游戏、广告、邀请、上传/修复奖励等真实收益。
- 复核是否还存在其他“退回本金”类 `change_type` 需要排除。
