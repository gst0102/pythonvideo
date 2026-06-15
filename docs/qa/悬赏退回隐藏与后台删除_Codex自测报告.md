# 悬赏退回隐藏与后台删除_Codex自测报告

## 1. 本次修改目标

修复用户取消/退回悬赏后，悬赏仍在小程序悬赏页展示的问题；同时在 PC 运营后台增加“悬赏管理”，支持管理员删除悬赏。

## 2. 修改文件列表

- `myproject/services/netdisk_resource_service.py`
- `myproject/controllers/admin.py`
- `video-ts/src/pages/netdisk/requests.vue`
- `adminVideo/src/utils/api.ts`
- `adminVideo/src/router/index.ts`
- `adminVideo/src/layout/index.vue`
- `adminVideo/src/views/netdisk/requests.vue`

## 3. 核心实现说明

- 公开悬赏接口 `GET /netdisk/requests` 后端只返回 `status=open` 且 `bounty_status=frozen` 的进行中悬赏。
- 小程序悬赏页增加前端兜底过滤，全部悬赏和我的求资源都只展示进行中的悬赏。
- 后台新增 `GET /admin/netdisk/requests`，支持按状态、关键词、分页查看悬赏。
- 后台新增 `POST /admin/netdisk/requests/{request_id}/delete`，进行中悬赏会先退回冻结积分，再标记为 `admin_deleted`；已处理悬赏只做软删除状态切换，避免重复退积分。
- PC 后台新增“悬赏管理”菜单和页面，可查看悬赏发布时间、标题、网盘、分类、悬赏积分、投稿数、状态，并执行删除。

## 4. 已运行测试

- `PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile controllers/netdisk.py controllers/admin.py services/netdisk_resource_service.py models/netdisk_request.py schemas/netdisk.py`
- `npm run type-check`，目录：`video-ts`
- `npm run build:mp-weixin`，目录：`video-ts`
- `npm run build`，目录：`adminVideo`
- `python3 scripts/verify_netdisk_request_bounty_flow.py`，未通过环境依赖检查

## 5. 测试结果

- 后端 Python 编译通过。
- 小程序类型检查通过。
- 小程序微信包构建通过。
- PC 后台构建通过。
- 悬赏闭环脚本因本地环境缺少 `httpx` 未运行成功，未进入业务断言。

## 6. 未覆盖测试项

- 未在真实数据库中完整验证“后台删除进行中悬赏 -> 冻结积分退回 -> 重复删除不重复退回”。
- 未在手机真机包里人工确认取消悬赏后页面立即不再显示。
- 未在 PC 生产后台人工确认主管权限删除链路。

## 7. 可能影响范围

- 小程序悬赏页只展示进行中悬赏，已取消、已过期、已采纳的历史悬赏不再显示在该页。
- PC 后台新增悬赏管理入口，需要重新部署后台前端后可见。
- 后端新增后台删除接口，需要后端服务部署后生效。

## 8. 需要 AI 测试官复核的事项

- P0：进行中悬赏后台删除只退回一次积分。
- P0：用户取消悬赏后公开悬赏列表不再展示。
- P0：已采纳悬赏后台删除不回滚已发放悬赏积分。
- P1：PC 后台删除按钮权限和操作日志是否符合运营要求。
