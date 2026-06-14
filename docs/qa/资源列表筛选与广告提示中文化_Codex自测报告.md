# 资源列表筛选与广告提示中文化 Codex 自测报告

## 1. 本次修改目标

- 资源详情页“获取网盘信息”时明确触发可选激励广告提示。
- 资源列表筛选区支持自动换行，按“全部标签”在上、“全部分类”在下展示。
- 首页、资源列表、详情等资源卡展示“上架时间”。
- 常见点击弹窗不直接展示英文错误信息。

## 2. 修改文件列表

- `video-ts/src/api/request.ts`
- `video-ts/src/pages/netdisk/detail.vue`
- `video-ts/src/pages/netdisk/resource-list.vue`
- `video-ts/src/pages/netdisk/index.vue`
- `video-ts/src/pages/netdisk/favorites.vue`
- `video-ts/src/pages/netdisk/points-detail.vue`
- `video-ts/src/pages/netdisk/recharge.vue`
- `video-ts/src/pages/netdisk/repair.vue`
- `video-ts/src/pages/netdisk/request-publish.vue`
- `video-ts/src/pages/netdisk/requests.vue`
- `video-ts/src/pages/netdisk/upload.vue`
- `video-ts/src/components/GameZone.vue`
- `video-ts/src/pages/user-login/login.vue`
- `video-ts/src/pages/mine/mine.vue`
- `video-ts/src/pages/mine/compent/shouyi.vue`
- `video-ts/src/pages/mine/compent/vip.vue`

## 3. 核心实现说明

- 资源详情页解锁按钮改为“获取网盘信息”，点击后先弹出中文选择框：可看广告，也可直接获取。
- 激励广告仍使用 `netdisk_resource` 场景和广告 ID 轮换池；广告失败或用户跳过不阻断资源解锁。
- 资源列表筛选行从横向滚动改为自动换行，分类行放到标签行下面。
- 增加 `toChineseErrorMessage`，把接口或小程序能力返回的英文错误转换为中文提示。

## 4. 已运行测试

- `vue-tsc --noEmit`
- `uni build -p mp-weixin`

## 5. 测试结果

- 类型检查通过。
- 微信小程序构建通过。

## 6. 未覆盖测试项

- 未在真机上验证微信激励广告真实拉起率。
- 未验证生产环境广告曝光、关闭、完成事件统计是否全部入库。

## 7. 可能影响范围

- 资源详情页解锁流程。
- 资源列表筛选区布局。
- 常见页面错误提示文案。

## 8. 需要人工确认的地方

- 微信开发者工具或真机中点击“获取网盘信息”后，弹窗文案和广告触发体验是否符合预期。
- 全部分类在小屏幕下换行后的视觉密度是否可以接受。
