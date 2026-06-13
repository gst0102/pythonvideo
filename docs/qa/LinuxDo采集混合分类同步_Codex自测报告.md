# LinuxDo采集混合分类同步_Codex自测报告

## 1. 本次修改目标

落地 LinuxDo 网盘资源采集、规则库优先分类、DeepSeek 兜底、影视跨来源去重、影视积分定价和小程序上架时间展示。

## 2. 修改文件列表

- `docs/yuexiang-stage2-docs/12-linuxdo-hybrid-classification-sync.md`
- `docs/qa/LinuxDo采集混合分类同步_测试清单与验收标准.md`
- `main.py`
- `models/netdisk_resource.py`
- `models/netdisk_collected_resource.py`
- `models/__init__.py`
- `schemas/netdisk.py`
- `services/resource_classification_service.py`
- `services/linuxdo_resource_service.py`
- `services/sync_service.py`
- `services/netdisk_resource_service.py`
- `migrations/versions/021_netdisk_resource_source_tags.py`
- `migrations/versions/022_netdisk_collected_resources.py`
- `scripts/linuxdo_netdisk_sync.py`
- `scripts/deepseek_resource_classifier.py`
- `scripts/verify_linuxdo_hybrid_classification.py`
- `scripts/verify_kdocs_netdisk_sync.py`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/index.vue`
- `video-ts/src/pages/netdisk/resource-list.vue`
- `video-ts/src/pages/netdisk/favorites.vue`
- `video-ts/src/pages/netdisk/detail.vue`
- `video-ts/src/pages/netdisk/repair.vue`
- `video-ts/src/pages/netdisk/mock.ts`

## 3. 核心实现说明

- 后端资源增加 `tags/source_type/source_ref/normalized_title`，接口返回 `created_at/published_at/tags/source_type/source_ref`。
- KDocs 影视同步改为按“完结/全集/合集”等完整关键词定价 20 分；更新中或普通影视定价 5 分。
- LinuxDo 每日同步接入 FastAPI 生命周期，默认每日 04:10 执行。
- LinuxDo 入库前按链接、规范化影视标题、网盘类型做去重；同链接跳过，同片名同网盘跳过，同片名新增网盘自动补充。
- 低置信或异常资源进入 `netdisk_collected_resources` 待审核池。
- DeepSeek 只在规则低置信时调用，未配置或失败时回退规则结果。
- 小程序首页、资源列表、收藏、详情展示“上架时间”。

## 4. 已运行测试

- `python3 -m py_compile ...`
- `/tmp/codex-netdisk-verify-venv/bin/python scripts/verify_linuxdo_hybrid_classification.py`
- `/tmp/codex-netdisk-verify-venv/bin/python scripts/verify_kdocs_netdisk_sync.py`
- `PATH="/Users/yiyi/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" ./node_modules/.bin/vue-tsc --noEmit`

## 5. 测试结果

- Python 语法检查通过。
- LinuxDo P0 验证通过：同链接跳过、同片名新增网盘补充、完结 20 分、更新中 5 分、重复运行不重复创建。
- KDocs 迅雷解析和影视定价回归通过。
- 小程序 TypeScript 类型检查通过。

## 6. 未覆盖测试项

- 未真实登录 LinuxDo 抓取线上帖子。
- 未连接真实 PostgreSQL 执行 Alembic 迁移。
- DeepSeek 真实 API 未调用，只覆盖了未配置时的回退路径。

## 7. 可能影响范围

- 网盘资源列表、详情、收藏、补链资源选择。
- KDocs 影视资源同步定价。
- LinuxDo 每日同步任务和待审核池。

## 8. 需要 AI 测试官复核的事项

- 生产数据库迁移后字段默认值是否符合预期。
- LinuxDo 登录态文件缺失时是否按预期跳过同步并记录错误。
- 真实 LinuxDo 数据中标题规范化是否需要继续补关键词。
