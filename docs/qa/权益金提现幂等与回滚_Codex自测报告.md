# 权益金提现幂等与回滚 Codex 自测报告

## 1. 本次修改目标

修复权益金/现金提现的 P0 风险：用户已有一笔提现处理中时，重复提交不同金额不应自动失败旧单、解冻旧金额并创建新单。提现链路必须保持用户余额、冻结金额、提现单、微信转账回调一致。

## 2. 修改文件列表

- `services/withdrawal_service.py`
- `scripts/verify_equity_withdrawal_flow.py`
- `../video-ts/src/api/request.ts`

## 3. 核心实现说明

- `apply_withdrawal` 增加处理中提现拦截：同一用户只要存在 `processing` 提现单，直接返回 `existing withdrawal is processing`。
- 移除旧的“同金额重试 / 不同金额自动失败旧单并替换新单”行为，避免旧微信转账仍在处理时被本地状态提前改坏。
- 保留提交微信转账失败时的本地余额回滚逻辑。
- 新增权益金提现验证脚本，覆盖冻结、重复申请拦截、失败回滚、成功到账、重复回调幂等。
- 小程序错误文案增加提现处理中提示：`已有提现处理中，请等待到账后再提交`。

## 4. 已运行测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile myproject/services/withdrawal_service.py myproject/scripts/verify_equity_withdrawal_flow.py
```

```bash
docker exec video-service-app python /app/scripts/verify_equity_withdrawal_flow.py --execute
```

```bash
npm run type-check
npm run build:mp-weixin
```

## 5. 测试结果

- 本地语法检查通过。
- 线上容器回滚验证通过：
  - 申请提现后 `balance` 扣减、`frozen_balance` 增加。
  - 已有处理中提现时，第二次申请被拦截，不新增提现单，不改变余额。
  - 转账失败回调后，冻结金额返还到账户余额。
  - 转账成功回调后，冻结金额清零，累计提现增加。
  - 重复失败 / 成功回调不会重复改余额。
- 小程序类型检查通过，微信小程序构建通过。

## 6. 未覆盖测试项

- 未真实触发微信商户转账 API，只模拟了提交成功后的本地状态机。
- 未覆盖微信平台真实回调签名验签链路。
- 未覆盖后台人工审核提现入口。

## 7. 可能影响范围

- 小程序邀请页权益金提现。
- 老的现金余额提现。
- 后台提现处理中记录。

## 8. 需要复核的事项

- 前端应把 `existing withdrawal is processing` 显示成中文：“已有提现处理中，请等待到账后再提交”。
- 如果业务未来允许用户取消处理中提现，应单独做“取消申请”流程，不能再用新申请覆盖旧申请。
