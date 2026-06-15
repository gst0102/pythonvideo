# 邀请好友页面简化与权益金口径_Codex自测报告

## 1. 本次修改目标

- 邀请页按参考图重做为少文字、强视觉、可直接分享的结构。
- 首屏 banner 使用分享图，并支持点击直接调起微信好友分享。
- 移除无效解释文案和开发口径说明。
- 修正可提现权益金口径，避免把广告/测试现金余额显示成邀请权益金。

## 2. 修改文件列表

- `video-ts/src/pages/netdisk/invite.vue`
- `myproject/services/commission_service.py`

## 3. 核心实现说明

- 邀请页改为：分享 banner、核心数据、邀请方式、奖励规则、最近邀请。
- 删除首屏的分享链接说明、绑定说明、到账长文案、重复叠加解释。
- 生产 `invite-stats` 增加并修正 `equity_*` 字段：只按一级邀请佣金记录统计权益金。
- 前端权益金展示只读取 `equity_balance`，不再 fallback 到用户总现金余额 `balance`。

## 4. 已运行测试

- `npm run type-check`
- `npm run build:mp-weixin`
- `python3 -m py_compile services/commission_service.py`
- 生产 `GET /health`
- 生产容器检查 `equity_balance/equity_total_income/equity_month_income` 字段已存在

## 5. 测试结果

- 小程序类型检查通过。
- 微信小程序构建通过。
- 后端语法检查通过。
- 生产服务重启后健康检查通过。

## 6. 未覆盖测试项

- 未使用登录态实测 `/commission/invite-stats` 当前用户返回值。
- 未在微信开发者工具真机预览最终截图。
- 独立权益金提现页尚未实现。

## 7. 可能影响范围

- 邀请好友页展示。
- 邀请收益统计里的权益金字段。

## 8. 下一步建议

- P0：做独立权益金提现页，接 `/withdrawal/apply`，避免继续跳“我的”或混用积分提现。
- P1：补收益到账订阅消息完整开关。
- P1：正式镜像发布，替代生产容器热修。
