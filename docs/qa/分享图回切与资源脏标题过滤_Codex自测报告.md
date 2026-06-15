# 分享图回切与资源脏标题过滤_Codex自测报告

## 1. 本次修改目标

- 邀请页 banner 和微信分享图统一使用用户新提供的 `share-invite.png`。
- 过滤接口上传/采集导致的半截资源标题，避免直接出现在首页和资源列表。

## 2. 修改文件列表

- `video-ts/src/pages/netdisk/invite.vue`
- `video-ts/src/pages/netdisk/index.vue`
- `video-ts/src/pages/netdisk/resource-list.vue`
- `video-ts/src/pages/netdisk/detail.vue`
- `myproject/services/netdisk_resource_service.py`
- `docs/codex-error-memory.md`

## 3. 核心实现说明

- 邀请页展示图和分享图都指向 `/static/share-invite.png`。
- 删除此前生成的 `share-invite.jpg`，避免误引用。
- 后端公开资源列表返回前过滤明显半截标题。
- 今日精选去重前过滤明显半截标题。
- 用户上传、求资源、采集候选人工发布时拦截不完整标题。
- 前端首页、资源列表、详情页增加兜底过滤。

## 4. 已运行测试

- `python3 -m py_compile services/netdisk_resource_service.py`
- `npm run type-check`
- `npm run build:mp-weixin`
- 生产 `GET /health`
- 生产 `GET /netdisk/resources/featured-today?limit=8`
- 生产 `GET /netdisk/resources?page=1&page_size=8&sort=latest`

## 5. 测试结果

- 后端语法检查通过。
- 小程序类型检查通过。
- 微信小程序构建通过。
- 生产健康检查通过。
- 线上今日精选和资源列表前 8 条未再返回 `.HD4K更 20`、`.HD4K更 19` 这类半截标题。

## 6. 未覆盖测试项

- 未使用真实登录态调用上传接口提交半截标题做端到端拒绝验证。
- 生产修复是容器热修，仍需后续正式镜像发布固化。

## 7. 可能影响范围

- 首页今日精选。
- 资源列表默认展示。
- 用户上传和求资源标题校验。
- 后台采集候选发布。
