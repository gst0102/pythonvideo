# 退款回调月卡权益金邀请奖励回滚 Codex 自测报告

## 1. 本次修改目标

修复并验证退款回调对月卡积分、邀请权益金、邀请积分奖励的回滚，避免退款后奖励仍留在买家或邀请人账户里。

## 2. 修改文件列表

- `services/payment_service.py`
- `scripts/verify_payment_refund_flow.py`

## 3. 核心实现说明

- 积分充值退款现在会同时回滚：
  - 买家充值积分。
  - 邀请人的首次充值固定奖励。
  - 邀请人的每笔订单邀请积分返利。
  - 邀请人的 50% 权益金现金余额和累计收益。
- 月卡退款现在会同时回滚：
  - 买家月卡一次性到账积分。
  - 买家月卡有效期。
  - 邀请人的每笔订单邀请积分返利。
  - 邀请人的 50% 权益金现金余额和累计收益。
- 权益金回收会生成站内通知 `invite_equity_refund`，方便以后用户端或后台展示原因。
- 重复退款回调保持幂等：订单已 `refunded` 时直接返回，不重复扣钱扣积分。
- 退款后的迟到支付成功回调会被忽略，不会重新发奖励。

## 4. 已运行测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile myproject/services/payment_service.py myproject/scripts/verify_payment_refund_flow.py
```

线上容器：

```bash
python -m py_compile services/payment_service.py scripts/verify_payment_refund_flow.py
python scripts/verify_payment_refund_flow.py --execute
```

## 5. 测试结果

线上容器回滚验证通过：

- 老 VIP 退款：会员赠送积分、一级/二级邀请积分均回滚。
- 月卡退款：月卡积分、邀请积分、权益金余额、累计收益均回滚。
- 积分充值退款：充值积分、首次充值固定奖励、邀请积分、权益金余额、累计收益均回滚。
- 重复退款回调不会重复扣钱扣积分。
- 退款后迟到的支付成功回调不会重新发奖励。
- 后端服务已重启，健康检查通过。

## 6. 未覆盖测试项

- 未真实触发微信退款回调签名验签链路，只验证业务服务层回滚逻辑。
- 未覆盖“权益金已提现后退款”的真实资金追回策略；当前逻辑会从 `balance/total_income` 扣回，必要时可能形成负余额，用后续收益抵扣。

## 7. 可能影响范围

- 微信支付退款回调。
- 积分充值订单退款。
- 月卡订单退款。
- 邀请权益金和邀请积分统计。
- 邀请页权益金余额展示。

## 8. 需要复核的事项

- 如果后续要支持“已提现后退款”的更精细财务策略，建议新增权益金流水表，明确展示回收、抵扣、负余额原因。
- 当前线上是热更新，后续仍需合入正式镜像构建，避免容器重建回退。
