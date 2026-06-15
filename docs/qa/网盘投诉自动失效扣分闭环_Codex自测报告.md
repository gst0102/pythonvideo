# 网盘投诉自动失效扣分闭环_Codex自测报告

## 1. 本次修改目标

把“链接失效投诉”从人工监管改成系统规则闭环：

- 同名同盘不同链接允许存在，不强行清理。
- 资源被 2 个不同用户投诉失效后，系统自动确认失效。
- 自动下架资源，并复用现有失效处罚逻辑扣上传者积分。
- 防止同一用户重复投诉刷阈值。
- 防止重复确认失效导致重复扣分。

## 2. 修改文件列表

- `services/netdisk_resource_service.py`
- `scripts/verify_netdisk_auto_report_invalid_flow.py`
- `docs/qa/网盘投诉自动失效扣分闭环_Codex自测报告.md`

## 3. 核心实现说明

- 用户提交 `mode=report` 投诉时，先检查同一用户是否已经对同一资源提交过有效投诉。
- 投诉计数按 `不同用户数` 统计，不按投诉条数统计。
- 默认自动确认失效阈值：`report_confirm_invalid_threshold = 2`。
- 达到阈值后调用现有 `confirm_resource_invalid`：
  - `resource.is_active = false`
  - `invalid_count + 1`
  - 上传者/补链者按既有规则扣分
  - 生成风险记录
  - 生成用户通知
- 自动确认后，相关投诉单批量标记为 `invalid_confirmed`。

## 4. 已运行测试

- 语法检查：`python3 -m py_compile services/netdisk_resource_service.py scripts/verify_netdisk_auto_report_invalid_flow.py`
- 线上容器验证：`python3 /app/scripts/verify_netdisk_auto_report_invalid_flow.py --execute`
- 今日精选回归：`python3 /app/scripts/verify_featured_today_selection.py`
- 每日积分口径回归：`python3 /app/scripts/verify_daily_earn_summary.py --execute`

## 5. 测试结果

全部通过。

验证覆盖：

- 第 1 个用户投诉后，资源仍保持活跃。
- 同一用户重复投诉被拦截。
- 第 2 个不同用户投诉后，资源自动下架。
- 上传者产生 `invalid_penalty` 扣分流水。
- 生成 `netdisk_risk_records` 风险记录。
- 重复确认失效不会重复扣分。
- 今日精选接口未被破坏。
- 每日积分口径未被破坏。

## 6. 未覆盖测试项

- 小程序前端投诉按钮真机流程未复测，当前小程序包上传仍受微信开发者工具服务端口限制。
- 真实用户投诉后的通知展示需要真机确认。

## 7. 可能影响范围

- 用户投诉资源失效会更快触发自动下架。
- 上传者如果发布失效资源，会被系统自动扣分。
- 同名同盘不同链接不会被自动清理，靠用户投诉和补链机制循环净化。

## 8. 需要人工确认

- 是否要把阈值长期固定为 2，还是后续在后台配置页暴露成可调整项。
- 是否要给投诉成功用户额外奖励积分，目前本次未新增奖励。
