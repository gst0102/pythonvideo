# PC 后台权益金流水页 Codex 自测报告

## 1. 本次修改目标

给 PC 后台增加“权益金流水”页面，支持按用户、订单、提现单查询权益金入账、退款回收、提现冻结、提现成功、提现失败返还记录，方便处理争议和查账。

## 2. 修改文件列表

- `controllers/admin.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/router/index.ts`
- `adminVideo/src/layout/index.vue`
- `adminVideo/src/views/finance/equity-ledger.vue`

## 3. 核心实现说明

- 新增后台接口 `GET /admin/equity-ledger`。
- 支持筛选：
  - `keyword`：用户昵称 / openid / 邀请码 / 流水 ID / 关联 ID / 备注。
  - `change_type`：入账、退款回收、提现冻结、提现成功、提现失败返还。
  - `related_type`：佣金记录、提现记录。
  - `start_date / end_date`：按流水创建时间筛选。
- 接口返回列表、分页和筛选范围内统计：
  - 入账金额。
  - 扣回/冻结金额。
  - 净变化。
  - 冻结变化。
- PC 后台左侧新增“权益金流水”菜单。
- 页面展示用户、类型、金额变化、冻结变化、累计收益变化、累计提现变化、变更后快照、关联业务 ID、备注和流水 ID。

## 4. 已运行测试

```bash
PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile myproject/controllers/admin.py
npm run build
```

线上：

```bash
python -m py_compile controllers/admin.py
curl http://127.0.0.1:8000/admin/equity-ledger?page=1&page_size=5
```

## 5. 测试结果

- 后端语法检查通过。
- PC 后台构建通过。
- 线上后端已重启，健康检查通过。
- 线上接口返回正常：
  - `code=200`
  - `list=[]`
  - `stats.amount_in=0`
- PC 后台静态文件已更新并 reload Nginx。

## 6. 未覆盖测试项

- 当前线上权益金流水表刚上线，接口返回空列表是正常状态，尚未用真实新订单生成线上流水做页面数据回归。
- 未增加导出 CSV 功能。

## 7. 可能影响范围

- PC 后台导航。
- PC 后台权益金流水查询。
- 后台接口 `/admin/equity-ledger`。

## 8. 需要复核的事项

- 后续产生新权益金入账/提现/退款后，应打开 PC 后台确认流水能按用户和关联 ID 查到。
- 如果查账频率高，下一步可以增加 CSV 导出。
