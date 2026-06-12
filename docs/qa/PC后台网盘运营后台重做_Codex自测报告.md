# PC后台网盘运营后台重做_Codex自测报告

## 1. 本次修改目标

- 将 PC 后台重做为悦享资源库运营后台。
- 新增运营看板，展示今日用户增长、积分发放、积分消耗、积分池和待处理事项。
- 保留网盘运营核心工作流：审核、资源库、风控待追缴、规则配置。
- 删除旧 PC 页面入口和旧视频平台功能页面。

## 2. 修改文件列表

后端：

- `controllers/admin.py`

PC 后台：

- `src/utils/api.ts`
- `src/store/index.ts`
- `src/router/index.ts`
- `src/layout/index.vue`
- `src/views/login/index.vue`
- `src/views/dashboard/index.vue`
- `src/views/netdisk/review.vue`
- `src/views/netdisk/resources.vue`
- `src/views/netdisk/risk.vue`
- `src/views/netdisk/config.vue`
- `src/components.d.ts`
- 删除旧页面：视频下载、影视资源、旧用户管理、财务、客服、旧配置、上传测试。

## 3. 核心实现说明

- 新增 `GET /admin/netdisk/ops-dashboard`，后端统一聚合运营看板指标。
- 积分增长按当天 `points_ledger.points_delta > 0` 统计。
- 积分消耗按当天 `points_ledger.points_delta < 0` 的绝对值统计。
- 增长/消耗人数按当天去重用户数统计。
- PC 后台菜单收敛为：运营看板、审核中心、资源库、风控/待追缴、规则配置。
- 审核中心拆分上传审核、补链审核、投诉核验。
- 资源库独立支持搜索、可见/隐藏筛选、恢复上架。
- 规则配置独立支持上传奖励、补链奖励、投诉阈值、处罚倍数配置。

## 4. 已运行测试

| 测试命令 / 方式 | 结果 |
|---|---|
| `/private/tmp/vedo-backend-venv/bin/python -m py_compile controllers/admin.py` | 通过 |
| `curl http://127.0.0.1:8000/admin/netdisk/ops-dashboard` | 通过，返回 200 |
| `curl -X POST http://127.0.0.1:8000/admin/netdisk/dev-seed` | 通过，返回 200 |
| `PATH="$HOME/.local/bin:$PATH" npm run build` | 通过 |
| 浏览器打开 `/dashboard` | 通过，展示运营看板指标 |
| 浏览器打开 `/review`、`/resources`、`/risks`、`/settings` | 通过，无 400/500 裸错误 |

## 5. 未覆盖测试项

- 未逐个点击新版审核中心所有按钮做完整 UI 操作回归。
- 未做 7 日趋势、积分来源分布、资源转化漏斗。
- 未新增后台真实管理员权限系统。

## 6. 可能影响范围

- `adminVideo` PC 后台旧功能入口被移除。
- 小程序端不受影响。
- 后端新增只读看板接口，不改变现有小程序业务接口。

## 7. 需要人工确认

- 看板指标顺序和命名是否符合你的运营习惯。
- 旧 PC 页面删除后是否还有某个后台功能需要用新版方式补回来。
