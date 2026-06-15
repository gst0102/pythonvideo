# 邀请页权益金提现_Codex自测报告

## 1. 本次修改目标

邀请好友页补齐“50%权益金 + 50%积分”规则展示，并接入权益金提现入口。

## 2. 修改文件列表

- `video-ts/src/pages/netdisk/invite.vue`
- `myproject/services/config_service.py`

## 3. 核心实现说明

- 邀请页首屏权益金卡片展示“好友每次付费，你拿50%权益金”。
- 奖励规则新增“好友付费 50%权益金”和“额外积分 50%积分”。
- 邀请页新增“提现”入口，调用现有 `/withdrawal/apply` 商户转账提现接口。
- 提现金额默认取 `inviteStats.equity_balance`，提交前二次确认，文案为“预计24小时内到账”。
- 线上提现配置已更新为最低 `0.1` 元，避免权益金小额余额不能提现。

## 4. 已运行测试

- `npm run type-check`，目录：`video-ts`
- `npm run build:mp-weixin`，目录：`video-ts`
- `GET https://api.lifelove.top/withdrawal/config`

## 5. 测试结果

- 小程序类型检查通过。
- 小程序微信构建通过。
- 线上提现配置返回 `min_amount=0.1`，文案为“提现申请提交后，预计24小时内到账。”

## 6. 未覆盖测试项

- 未用真实登录用户点击提现发起商户转账。
- 未验证微信提现回调成功后 `user.total_withdrawn / balance / frozen_balance` 最终一致。

## 7. 需要人工确认

- 小程序需重新上传后，手机端才能看到邀请页新规则和提现入口。
- 微信商户转账到账通知由微信支付/商户转账链路处理，不依赖前端手填模板号。
