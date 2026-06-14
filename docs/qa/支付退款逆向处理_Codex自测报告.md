# 支付退款逆向处理_Codex自测报告

## 1. 本次修改目标

- 给支付退款补齐后端账务逆向能力。
- 退款后撤回积分包到账、会员赠送积分、邀请会员返利、积分包首充邀请奖励。
- 保证退款重复处理、退款后支付成功回调重放都不会重新发奖励。

## 2. 修改文件列表

- `services/payment_service.py`
- `services/points_account_service.py`
- `scripts/verify_payment_refund_flow.py`

## 3. 核心实现说明

- 新增 `PaymentService.handle_payment_refund()`：
  - 积分包订单：撤回 `points_recharge`，并撤回由该订单触发的 `invite_first_recharge`。
  - 会员订单：撤回 `vip_gift`，撤回一级/二级邀请返利，佣金记录标记为 `cancelled`，会员时长按订单时长扣回。
  - 已退款订单重复处理直接返回成功，不重复生成流水。
  - 已退款订单收到迟到的支付成功回调时直接忽略，不重新发奖励。
- 新增 `PointsAccountService.clawback_points()`：
  - 用于退款逆向扣回 `withdrawable`、`frozen`、`consumable` 三类积分。
  - 使用独立幂等键，重复退款不会重复扣分。
- 新增 `verify_payment_refund_flow.py`：
  - 覆盖会员退款、积分包退款、返利已结算/未结算两种邀请奖励撤回、重复退款、迟到支付成功回调。

## 4. 已运行测试

- `python3 -m py_compile services/payment_service.py services/points_account_service.py scripts/verify_payment_refund_flow.py`
- `git diff --check`

## 5. 测试结果

- 本地语法检查通过。
- 本地差异检查通过。

## 6. 未覆盖测试项

- 本机没有可用后端依赖环境和 Docker，`verify_payment_refund_flow.py --execute` 需要部署后在服务器容器内执行。
- 本轮只实现退款逆向服务层能力，尚未接入真实微信/苹果退款回调入口。
- 后台人工退款按钮尚未接入该方法。

## 7. 可能影响范围

- 支付成功回调：已退款订单的迟到成功回调会被忽略。
- 积分账户：退款逆向可能使用户可用/可提现/冻结积分变为负数，用于表达用户已消费后仍需追缴的状态。
- 邀请返利：退款后佣金记录会标记为 `cancelled`。

## 8. 需要 AI 测试官复核的事项

- 服务器容器内专项验证是否通过。
- 真实退款回调接入前，是否需要先在 PC 后台增加人工“标记退款并撤回奖励”按钮。
