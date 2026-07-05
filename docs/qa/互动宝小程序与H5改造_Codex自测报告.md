# 互动宝小程序与 H5 改造_Codex自测报告

## 1. 本次修改目标

将小程序前台改造为“互动宝助手”，新增需求审核后进广场规则，新增独立 H5 轻量详情页，并提供后台审核与配置能力。

## 2. 修改文件列表

- 后端：`controllers/netdisk.py`、`controllers/admin.py`、`schemas/netdisk.py`、`services/config_service.py`、`services/netdisk_resource_service.py`
- 小程序：`src/pages.json`、`src/components/NetdiskTabBar.vue`、`src/pages/netdisk/*`、`src/api/request.ts`、`src/types/index.d.ts`
- 后台：`src/utils/api.ts`、`src/views/netdisk/requests.vue`、`src/views/netdisk/config.vue`
- H5：`h5-interactbao/`

## 3. 核心实现说明

- 小程序主 tab 改为推荐/需求/任务/收藏/我的，首页和详情页去除主路径高风险表达。
- 资料详情页改为摘要展示和复制独立 H5 链接，不再在小程序内展示完整访问字段。
- 资料需求默认 10 积分，默认 `pending_review`，后台通过后进入广场，拒绝/删除/取消/过期退回冻结积分。
- 后台需求管理新增待审核、通过、拒绝；配置页新增 H5 域名、安全分类、审核模式和默认悬赏配置。
- H5 新增 `/r/:resourceId`、`/q/:requestId`、`/login/wechat/callback`，授权未配置时降级只读。

## 4. 已运行测试

- `python3 -m compileall controllers services schemas models`
- `npm run type-check`（video-ts）
- `npm run build`（adminVideo）
- `npm install && npm run build`（h5-interactbao）

## 5. 测试结果

以上命令均通过。

## 6. 未覆盖测试项

- 未连接真实生产数据库验证积分流水。
- 未部署后端和 H5 到线上域名。
- 未通过微信开发者工具上传小程序包。
- 未完成公众号网页授权真实 unionid 绑定。

## 7. 可能影响范围

- 需求悬赏状态流转、需求广场展示、后台需求审核。
- 小程序首页、详情、任务、收藏、我的、需求页面文案和入口。
- 后台前台展示配置和 H5 域名配置。

## 8. 需要 AI 测试官复核的事项

- P0 积分冻结、退回、采纳发放幂等。
- 小程序主路径是否仍有敏感表达。
- H5 独立访问和小程序复制链接是否符合“不内嵌”要求。
- 上线前部署、迁移、上传、真机新包确认。
