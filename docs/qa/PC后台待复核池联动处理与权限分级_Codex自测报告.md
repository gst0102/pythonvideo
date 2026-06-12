# PC 后台待复核池联动处理与权限分级_Codex自测报告

## 1. 本次修改目标

- 待复核池处理预警时可直接选择恢复上架、确认失效、继续隐藏。
- 新增预警详情抽屉，运营不用跳页即可查看投诉记录、解锁记录、最近处理日志。
- 自动隐藏灰度规则调整为：高投诉资源可自动隐藏，短时高解锁高投诉只进入待复核池。
- 管理员权限分级：普通运营可标记已读；忽略、确认失效、恢复上架、复核结果处理等高风险动作需要主管权限。

## 2. 修改文件列表

- `controllers/admin.py`
- `schemas/netdisk.py`
- `services/config_service.py`
- `adminVideo/src/store/index.ts`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/layout/index.vue`
- `adminVideo/src/views/netdisk/quality-review-pool.vue`
- `adminVideo/src/views/netdisk/quality-alerts.vue`
- `adminVideo/src/views/netdisk/resource-quality-detail.vue`
- `adminVideo/src/views/netdisk/review.vue`
- `adminVideo/src/views/netdisk/config.vue`

## 3. 核心实现说明

- 后端新增 `POST /admin/netdisk/resource-quality/alerts-action/{alert_id}/resolve`，支持复核结果动作：
  - `restore`
  - `confirm_invalid`
  - `keep_hidden`
- 后端通过 `X-Admin-Role` 校验主管权限，普通运营不能执行忽略、确认失效、恢复上架、复核结果处理。
- 前端登录 `admin` 后保存 `supervisor` 角色，所有后台请求自动携带角色头。
- 待复核池详情改为抽屉展示，含投诉记录、最近解锁、最近处理日志。
- 自动隐藏默认灰度规则：`quality_auto_hide_high_report=true`，`quality_auto_hide_burst=false`。

## 4. 已运行测试

- 后端 Python 语法检查。
- PC 后台 `npm run build`。
- 后端接口验证：
  - 普通运营调用忽略预警返回 403。
  - 普通运营调用复核结果处理返回 403。
  - 主管调用复核结果处理返回 200。
  - 主管联动处理后可重新打开预警，待复核池状态正常。
  - 配置接口返回高投诉自动隐藏开启、爆发类自动隐藏关闭、自动进入待复核池开启。
- 内置浏览器验证：
  - 待复核池页面可见权限提示、批量处理按钮。
  - 点击详情可打开抽屉。
  - 抽屉内可见恢复上架、确认失效、继续隐藏、投诉记录、最近解锁、最近处理日志。

## 5. 测试结果

- 后端语法检查通过。
- 前端构建通过。
- 权限拦截符合预期。
- 预警详情抽屉展示符合预期。
- 复核结果联动接口可用。

## 6. 未覆盖测试项

- 未接真实管理员账号体系，当前角色仍是 PC 后台本地 MVP 权限。
- 未做多管理员并发处理同一条预警的锁定机制。
- 确认失效当前只处理资源隐藏和日志，不在此入口直接触发积分处罚。

## 7. 可能影响范围

- PC 后台待复核池、质量预警、资源质量详情、审核中心、规则配置。
- 后端资源质量预警处理接口、资源恢复和确认失效权限。

## 8. 需要 AI 测试官复核的事项

- “主管权限”在正式管理员体系接入后是否需要改成真实 RBAC。
- 待复核池确认失效是否应该进一步联动积分处罚流程。
- 高投诉自动隐藏开启后，是否需要更明显的看板提示和恢复上架二次确认。
