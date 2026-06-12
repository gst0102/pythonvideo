# PC 后台待复核池与质量规则配置_Codex自测报告

## 1. 本次修改目标

- 批量忽略、批量已处理增加二次确认，降低误操作风险。
- 新增独立待复核池页面，只展示 `open/read` 的高风险质量预警。
- 支持质量统计任务失败模拟和恢复测试，验证运营看板顶部提醒。
- 将资源质量自动动作规则放入后台配置：阈值、自动进入待复核池、自动隐藏策略。

## 2. 修改文件列表

- `controllers/admin.py`
- `services/config_service.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/views/dashboard/index.vue`
- `adminVideo/src/views/netdisk/config.vue`
- `adminVideo/src/views/netdisk/quality-alerts.vue`
- `adminVideo/src/views/netdisk/quality-review-pool.vue`
- `adminVideo/src/router/index.ts`
- `adminVideo/src/layout/index.vue`

## 3. 核心实现说明

- 后端质量预警列表支持 `review_pool=true`，并新增 `GET /admin/netdisk/quality-review-pool`。
- 看板待复核数量改为统计预警表中 `open/read` 的真实数量。
- 新增开发环境接口：
  - `POST /admin/netdisk/resource-quality/stats-runtime/dev-simulate-failure`
  - `POST /admin/netdisk/resource-quality/stats-runtime/dev-recover`
- 资源质量规则配置新增：
  - `quality_auto_review_pool`
  - `quality_auto_hide_high_report`
  - `quality_auto_hide_burst`
- 生成质量预警时读取后台配置，默认自动进入待复核池；开启自动隐藏后，会隐藏资源并记录操作日志。
- PC 后台新增待复核池菜单和页面，支持单条/批量处理。

## 4. 已运行测试

- 后端 Python 语法检查。
- PC 后台 `npm run build`。
- 后端接口检查：
  - `GET /admin/netdisk/quality-review-pool`
  - `GET /admin/netdisk/audit-config`
  - `POST /admin/netdisk/resource-quality/stats-runtime/dev-simulate-failure`
  - `POST /admin/netdisk/resource-quality/stats-runtime/dev-recover`
  - `GET /admin/netdisk/ops-dashboard`
- 内置浏览器页面检查：
  - `/quality-review-pool`
  - `/settings`
  - `/quality-alerts`

## 5. 测试结果

- 后端 Python 语法检查通过。
- PC 后台构建通过。
- 待复核池接口返回 200，当前本地演示数据返回 2 条 `read` 状态预警。
- 配置接口已返回新增字段：`quality_auto_review_pool=true`、`quality_auto_hide_high_report=false`、`quality_auto_hide_burst=false`。
- 统计任务模拟失败接口返回 `status=failed`，恢复接口返回 `status=success`，运营看板运行状态恢复为 `success`。
- 浏览器验收通过：
  - 待复核池页面可见标题、批量已处理、批量忽略。
  - 规则配置页面可见自动进入待复核池、高投诉自动隐藏、短时高解锁高投诉自动隐藏。
  - 质量预警页面可见模拟失败、恢复成功、批量已处理、批量忽略。
  - 运营看板在模拟失败后可见“质量统计任务失败”，恢复成功后该提醒消失。

## 6. 未覆盖测试项

- 未做多管理员同时批量处理同一批预警的并发测试。
- 未做生产环境关闭开发模拟接口后的权限回归。
- 未做超大数据量待复核池分页压力测试。

## 7. 可能影响范围

- PC 后台质量预警页、待复核池页、规则配置页、运营看板。
- 后端网盘质量预警生成、统计任务运行状态、资源自动隐藏逻辑。

## 8. 需要 AI 测试官复核的事项

- 自动隐藏策略默认关闭是否符合当前运营节奏。
- 待复核池是否还需要更细的处理状态，例如“人工复核中”。
- 统计任务失败模拟接口是否需要后续加管理员权限控制，而不只依赖开发环境开关。
