# PC 后台确认失效待追缴闭环_Codex自测报告

## 1. 本次修改目标

- 待复核池中选择“确认失效”后，不直接扣用户积分。
- 系统应隐藏资源，并为可归因的已通过补链记录生成待追缴记录。
- 重复确认失效不能重复生成待追缴。
- PC 后台应能从确认失效结果引导管理员进入风控/待追缴处理。

## 2. 修改文件列表

- `services/netdisk_resource_service.py`
- `controllers/admin.py`
- `adminVideo/src/views/netdisk/quality-review-pool.vue`
- `adminVideo/src/views/netdisk/risk.vue`
- `adminVideo/src/views/netdisk/logs.vue`
- `adminVideo/src/views/netdisk/resource-quality-detail.vue`
- `docs/qa/PC后台确认失效待追缴闭环_Codex自测报告.md`

## 3. 核心实现说明

- 新增资源级确认失效服务：`NetdiskResourceService.confirm_resource_invalid`。
- 待复核池“确认失效”会：
  - 隐藏资源。
  - 查找该资源下已通过的补链记录。
  - 将相关补链记录标记为 `invalid_confirmed`。
  - 按 `reward_points * invalid_penalty_multiplier` 生成待追缴记录。
  - 使用幂等键避免重复生成待追缴。
- 前端确认失效后，如果生成待追缴记录，会提示管理员跳转到“风控/待追缴”。
- 风控页补充中文原因展示：`resource_invalid_pending_penalty` 显示为“资源失效待处罚”。

## 4. 已运行测试

- 后端 Python 语法检查。
- PC 后台 `npm run build`。
- 后端接口验证：
  - 待复核池确认失效返回 200。
  - 首次确认失效生成 1 条待追缴记录。
  - 重复确认失效不重复生成待追缴记录。
  - 风控/待追缴接口可查询到 `resource_invalid_pending_penalty`。
- 内置浏览器验证：
  - 风控/待追缴页面可见“资源失效待处罚”。
  - 页面可见“追缴扣除”和“人工关闭”处理入口。

## 5. 测试结果

- 后端语法检查通过。
- 前端构建通过。
- 待追缴生成与幂等验证通过。
- PC 风控页展示通过。

## 6. 未覆盖测试项

- 上传记录目前尚未与资源表建立直接关联，本轮只对已通过补链记录做资源级归因追缴。
- 未做真实管理员确认扣除后的完整财务审计复核。
- 未做多条补链同时归因时的大批量性能测试。

## 7. 可能影响范围

- 待复核池确认失效。
- 风控/待追缴列表。
- 资源质量详情最近日志。
- 积分处罚流程入口。

## 8. 需要 AI 测试官复核的事项

- 资源级确认失效是否只追缴补链者，还是后续需要建立上传记录与资源表关联后追缴上传者。
- 待追缴金额是否保持当前 `奖励分 * 处罚倍数`。
- 管理员从确认失效跳转待追缴的交互是否足够清晰。
