# 支付回调邀请权益金与积分回归 Codex 自测报告

## 1. 本次修改目标

完成支付回调里的邀请权益金和积分奖励 P0 回归，重点验证：

- 同一订单重复支付回调，不重复发权益金。
- 同一订单重复支付回调，不重复发邀请积分。
- 同一好友第二个月再次购买月卡或再次充值积分，作为新订单继续给邀请人返权益金和对应积分。
- 数据库层阻止同一订单、同一邀请人、同一层级重复生成佣金记录。

## 2. 修改文件列表

- `models/commission.py`
- `migrations/versions/029_commission_order_inviter_unique.py`
- `scripts/verify_benefit_card_equity_flow.py`
- `services/payment_service.py`（同步线上，确保月卡积分与权益金逻辑生效）

## 3. 核心实现说明

- `commission_records` 增加唯一约束：`user_id + from_user_id + order_id + level`。
- 迁移执行前会检查历史重复数据；如果存在重复佣金组，迁移会中止，不会静默忽略。
- 回归脚本扩展为完整付费邀请回归：
  - 10 元月卡：买家到账 300 积分，邀请人到账 5 元权益金 + 500 冻结邀请积分。
  - 同一月卡订单重复回调：不重复到账。
  - 同一好友续 20 元月卡：邀请人继续到账 10 元权益金 + 1000 冻结邀请积分。
  - 1 元积分充值：邀请人到账 0.5 元权益金 + 50 冻结邀请积分。
  - 同一积分充值订单重复回调：不重复到账。
  - 同一好友第二笔 1 元积分充值：邀请人继续到账 0.5 元权益金 + 50 冻结邀请积分。
  - 固定“首次充值奖励”只发一次，不因后续新订单重复发。

## 4. 已运行测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile myproject/models/commission.py myproject/migrations/versions/029_commission_order_inviter_unique.py myproject/scripts/verify_benefit_card_equity_flow.py
```

线上容器：

```bash
python -m py_compile models/commission.py migrations/versions/029_commission_order_inviter_unique.py scripts/verify_benefit_card_equity_flow.py
alembic upgrade head
python scripts/verify_benefit_card_equity_flow.py --execute
```

## 5. 测试结果

- 线上历史重复佣金预检结果：`duplicate_groups = 0`。
- 数据库唯一约束迁移已执行成功。
- 第一次回归发现线上容器 `payment_service.py` 仍是旧版本，月卡支付后 300/900 积分未到账。
- 同步最新 `payment_service.py` 后，完整回归通过：
  - 月卡积分到账通过。
  - 月卡重复回调幂等通过。
  - 同一好友新月卡订单继续返权益金和积分通过。
  - 积分充值重复回调幂等通过。
  - 同一好友第二笔积分充值继续返权益金和积分通过。
  - 首次充值固定奖励只发一次通过。
- 后端服务已重启，健康检查通过。

## 6. 未覆盖测试项

- 未模拟真实微信支付并发请求压测，只通过数据库唯一约束补强并发写入保护。
- 未真实发送微信订阅消息，只保留现有发送逻辑和失败降级。
- 未覆盖退款后权益金现金余额回滚；退款目前仍需要单独 P0 回归。

## 7. 可能影响范围

- 微信支付成功回调。
- 积分充值订单。
- 月卡订单。
- 邀请权益金。
- 邀请积分奖励。
- 佣金记录查询和邀请页统计。

## 8. 需要复核的事项

- 后续需要把这次线上热更新合并进正式镜像构建流程，避免容器重建后回退旧代码。
- 退款回调对已发权益金现金余额的处理仍建议作为下一条 P0 单独验证。
