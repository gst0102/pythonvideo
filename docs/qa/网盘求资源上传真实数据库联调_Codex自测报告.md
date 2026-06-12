# 网盘求资源与上传真实数据库联调_Codex自测报告

## 1. 本次修改目标

将网盘 MVP 中的求资源与上传资源从本地 mock 状态推进到真实数据库记录闭环：

- 发布求资源写入数据库。
- 求资源列表读取数据库。
- 我的求资源读取当前登录用户数据库记录。
- 上传资源提交写入数据库。
- 我的上传读取当前登录用户数据库记录和审核状态。

本轮不接入积分冻结、审核通过发放积分、后台审核流，避免扩大积分流水风险。

## 2. 修改文件列表

后端：

- `controllers/netdisk.py`
- `models/__init__.py`
- `models/netdisk_request.py`
- `models/netdisk_upload.py`
- `schemas/netdisk.py`
- `services/netdisk_resource_service.py`

前端：

- `video-ts/src/api/request.ts`
- `video-ts/src/pages/netdisk/request-publish.vue`
- `video-ts/src/pages/netdisk/requests.vue`
- `video-ts/src/pages/netdisk/upload.vue`
- `video-ts/src/types/index.d.ts`

## 3. 核心实现说明

- 新增 `netdisk_requests` 表，用于保存求资源标题、期望网盘、分类、悬赏积分、说明、状态、提交数和创建时间。
- 新增 `netdisk_uploads` 表，用于保存用户上传资源的标题、分类、网盘类型、链接、提取码、解压码、说明、审核状态、奖励积分占位和审核备注。
- 新增接口：
  - `GET /netdisk/requests`
  - `GET /netdisk/requests/mine`
  - `POST /netdisk/requests`
  - `GET /netdisk/uploads/mine`
  - `POST /netdisk/uploads`
- 前端发布求资源和上传资源均要求登录；未登录跳转登录页。
- 前端接口失败时保留本地 mock 兜底，避免开发预览白屏。

## 4. 已运行测试

- `PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile controllers/netdisk.py schemas/netdisk.py services/netdisk_resource_service.py models/netdisk_request.py models/netdisk_upload.py models/__init__.py`
- `npm run type-check`
- `npm run build:mp-weixin:local`
- 本地 `8001` 接口联调：
  - `POST /user/dev-login`
  - `POST /netdisk/requests`
  - `GET /netdisk/requests`
  - `GET /netdisk/requests/mine`
  - `POST /netdisk/uploads`
  - `GET /netdisk/uploads/mine`

## 5. 测试结果

- 后端语法检查通过。
- 前端类型检查通过。
- 小程序本地构建通过。
- 发布求资源成功，列表和我的求资源可读取到记录。
- 上传资源成功，我的上传可读取到 `pending` 审核记录。

## 6. 未覆盖测试项

- 未接真实后台审核操作。
- 未接审核通过后的积分奖励流水。
- 未接求资源悬赏积分冻结和采纳后转移。
- 未做微信开发者工具人工完整点击验收。

## 7. 可能影响范围

- 网盘求资源页、发布求资源页、上传资源页。
- 后端 `/netdisk` 路由。
- 本地数据库会新增 `netdisk_requests` 和 `netdisk_uploads` 表。

## 8. 需要 AI 测试官复核的事项

- 未登录发布求资源、上传资源是否正确跳登录。
- 求资源列表是否不展示网盘私密链接。
- 上传记录是否只在“我的上传”中展示。
- 后续接积分冻结和审核奖励时，需要按 P0 处理积分流水一致性和重复提交幂等。
