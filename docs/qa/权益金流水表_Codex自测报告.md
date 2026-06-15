# 权益金流水表 Codex 自测报告

## 1. 本次修改目标

补齐权益金流水表，所有权益金入账、退款回收、提现冻结、提现成功、提现失败回滚都可追踪，便于后台和用户端解释每一分钱的来源和去向。

## 2. 修改文件列表

- `models/equity_ledger.py`
- `services/equity_ledger_service.py`
- `migrations/versions/030_equity_ledger.py`
- `models/__init__.py`
- `services/payment_service.py`
- `services/withdrawal_service.py`
- `controllers/withdrawal.py`
- `scripts/verify_equity_ledger_flow.py`
- `docs/qa/权益金流水表_测试清单与验收标准.md`

## 3. 核心实现说明

- 新增 `equity_ledger` 表，字段包含：
  - `change_type`
  - `amount_delta`
  - `frozen_delta`
  - `total_income_delta`
  - `total_withdrawn_delta`
  - `balance_after`
  - `frozen_balance_after`
  - `total_income_after`
  - `total_withdrawn_after`
  - `related_type / related_id`
  - `idempotency_key`
  - `remark`
- 新增 `EquityLedgerService.record()`，业务先改用户余额，再写带余额快照的流水。
- 支付成功邀请权益金入账写 `invite_reward` 流水。
- 退款回收权益金写 `refund_revoke` 流水。
- 提现申请冻结写 `withdraw_freeze` 流水。
- 提现成功写 `withdraw_success` 流水。
- 提现失败或超时返还写 `withdraw_failed_return` 流水。
- 新增用户查询接口：`GET /withdrawal/equity-ledger`。

## 4. 已运行测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile myproject/models/equity_ledger.py myproject/services/equity_ledger_service.py myproject/services/payment_service.py myproject/services/withdrawal_service.py myproject/controllers/withdrawal.py myproject/migrations/versions/030_equity_ledger.py myproject/scripts/verify_equity_ledger_flow.py
```

线上容器：

```bash
python -m py_compile models/equity_ledger.py services/equity_ledger_service.py models/__init__.py services/payment_service.py services/withdrawal_service.py controllers/withdrawal.py migrations/versions/030_equity_ledger.py scripts/verify_equity_ledger_flow.py
alembic upgrade head
python scripts/verify_equity_ledger_flow.py --execute
```

## 5. 测试结果

- 线上迁移成功，当前版本：`030_equity_ledger (head)`。
- 线上回滚验证通过：
  - 邀请权益金入账流水生成。
  - 月卡退款权益金回收流水生成。
  - 提现申请冻结流水生成。
  - 提现失败返还流水生成。
  - 提现成功流水生成。
  - 重复退款、重复提现回调不会重复写流水。
  - 每条流水的余额快照与用户余额状态一致。
- 后端已重启，健康检查通过。

## 6. 未覆盖测试项

- 未给 PC 后台新增权益金流水页面，本次先补后端表、写入和用户查询接口。
- 未做历史权益金数据回填；表上线后记录新增链路。
- 未做真实微信转账回调验签链路测试，只验证业务服务层。

## 7. 可能影响范围

- 支付成功回调。
- 退款回调。
- 权益金提现申请。
- 微信商户转账成功/失败回调。
- 邀请页权益金余额解释能力。

## 8. 需要复核的事项

- 如果要解释上线前已产生的权益金，需要单独做历史回填脚本。
- 下一步建议在 PC 后台加“权益金流水”查询页，方便按用户、订单、提现单追踪。
