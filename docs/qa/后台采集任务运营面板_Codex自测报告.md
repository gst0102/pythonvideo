# 后台采集任务运营面板 Codex 自测报告

## 1. 本次修改目标

- 在后台待处理中心展示 KDocs / LinuxDo 采集规则和状态。
- 支持运营手动触发“最新一批”采集。
- 手动触发不开放历史回补，避免误操作造成服务器压力。

## 2. 修改文件列表

- `controllers/admin.py`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/views/netdisk/ops-center.vue`

## 3. 核心实现说明

- 新增 `GET /admin/netdisk/crawlers/status`：
  - 返回 4 个采集任务：KDocs 影视剧、KDocs 电影、KDocs 4K、LinuxDo。
  - 返回频率、采集范围、开关状态、已入库数量、待审核数量、浏览器守护配置。
- 新增 `POST /admin/netdisk/crawlers/{crawler_key}/run`：
  - 支持 `kdocs_anime`、`kdocs_movie`、`kdocs_4k`、`linuxdo`。
  - 需要主管权限。
  - 只触发最新批次，不触发 LinuxDo 历史回补。
- PC 后台待处理中心新增“资源采集任务”面板：
  - 展示采集规则。
  - 展示浏览器并发和自动清理状态。
  - 支持点击“同步最新”。

## 4. 已运行测试

- 后端静态检查：
  - `python3 -m py_compile controllers/admin.py core/kdocs_service.py services/sync_service.py services/linuxdo_resource_service.py scripts/linuxdo_netdisk_sync.py`
- PC 后台类型检查：
  - `vue-tsc --noEmit`
- PC 后台生产构建：
  - `vite build`

## 5. 测试结果

- 后端静态检查通过。
- PC 后台类型检查通过。
- PC 后台生产构建通过。
- Vite 仍有既有大包体积提示，不影响本次功能。

## 6. 未覆盖测试项

- 未在真实后端依赖完整环境下调用采集接口。
- 未真实触发 KDocs / LinuxDo 外部采集。
- 未测试主管权限以外角色的真实后台拦截效果。

## 7. 可能影响范围

- 后台待处理中心首屏新增采集任务面板。
- 主管角色可以手动触发最新批次采集。
- 采集失败时后台展示中文错误提示。

## 8. 需要人工确认的地方

- 是否允许普通运营也手动触发采集；当前默认需要主管权限。
- LinuxDo 历史回补仍建议只通过服务器命令低峰期执行，不建议放到后台按钮。
