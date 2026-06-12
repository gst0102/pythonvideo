# 网盘资源真实列表详情接口 Codex 自测报告

生成日期：2026-06-12

## 1. 本次修改目标

接入网盘资源真实列表/详情接口，逐步替换前端首页和详情页中的资源 mock 数据；公开列表/详情接口不得返回网盘链接、提取码、解压码。

## 2. 修改文件列表

- `myproject/controllers/netdisk.py`
- `myproject/schemas/netdisk.py`
- `myproject/services/netdisk_resource_service.py`
- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/index.vue`
- `video-ts/src/pages/netdisk/detail.vue`

## 3. 核心实现说明

- 后端新增 `GET /netdisk/resources`，返回资源安全摘要列表。
- 后端新增 `GET /netdisk/resources/{resource_id}`，返回单个资源安全详情。
- 公开资源 payload 仅包含标题、分类、网盘、等级、积分、验证时间、获取数、收藏数和说明。
- 网盘链接、提取码、解压码仍只通过已鉴权的 access/unlock 结果展示。
- 前端资源首页优先读取真实资源列表，失败时降级使用本地 mock。
- 前端资源详情优先读取真实资源详情，未解锁状态不展示访问凭据。

## 4. 已运行测试

- `myproject`: `PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile controllers/netdisk.py schemas/netdisk.py services/netdisk_resource_service.py`
- `video-ts`: 使用本地 `vue-tsc --noEmit` 入口执行类型检查

## 5. 测试结果

- 后端语法检查通过。
- 前端 TypeScript / Vue 类型检查通过。
- 代码路径确认公开列表/详情接口不使用 access/unlock payload，不返回 `link`、`extract_code`、`unzip_code`。

## 6. 未覆盖测试项

- 当前 Codex 环境仍无法解析 `registry.npmjs.org`，未能重新联网安装依赖。
- 本地 Python 运行级依赖缺少 `sqlmodel/httpx`，未启动 FastAPI 服务做真实 HTTP 联调。
- 本机未找到微信开发者工具 CLI，未能自动预览小程序主流程。
- 未做真实登录态下的端到端解锁点击验证。

## 7. 需要 AI 测试官复核的事项

- 首页资源列表切换到真实接口后，卡片仍不得泄露网盘链接、提取码、解压码。
- 详情页未解锁状态必须只展示说明和解锁按钮。
- 已解锁用户刷新详情页后，应通过 access 接口展示完整链接和提取信息。
- 真实后端服务启动后需补充接口级 P0 验证：未解锁详情响应不含敏感字段、重复解锁不重复扣积分。
