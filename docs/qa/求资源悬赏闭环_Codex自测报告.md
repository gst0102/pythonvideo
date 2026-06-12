# 求资源悬赏闭环_Codex自测报告

## 1. 本次修改目标

实现求资源悬赏 MVP 闭环：发布悬赏冻结积分、其他用户投稿、发布者采纳后发放悬赏积分、取消或过期未采纳退回积分。

## 2. 修改文件列表

- `docs/yuexiang-stage2-docs/11-netdisk-request-bounty-loop.md`
- `docs/qa/求资源悬赏闭环_测试清单与验收标准.md`
- `docs/qa/求资源悬赏闭环_Codex自测报告.md`
- `controllers/netdisk.py`
- `services/netdisk_resource_service.py`
- `services/points_account_service.py`
- `models/netdisk_request.py`
- `models/netdisk_upload.py`
- `schemas/netdisk.py`
- `migrations/versions/019_netdisk_request_bounty_loop.py`
- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/requests.vue`
- `video-ts/src/pages/netdisk/request-publish.vue`
- `video-ts/src/pages/netdisk/upload.vue`
- `video-ts/src/pages/netdisk/points-detail.vue`

## 3. 核心实现说明

- 发布求资源时校验可用积分，积分不足或负积分用户不能发布。
- 发布成功后将悬赏积分从可用积分冻结，并写 `request_bounty_freeze` 流水。
- 悬赏投稿绑定 `request_id`，发布者不能给自己的悬赏投稿，同一用户不能重复有效投稿。
- 发布者可查看投稿并采纳；采纳后冻结积分扣出，投稿者可用积分增加，并写 `request_bounty_award` 流水。
- 发布者取消或系统过期未采纳时退回冻结积分，并写 `request_bounty_return` 流水。
- 前端求资源列表增加投稿、查看投稿、采纳、取消退回入口。
- 上传页支持悬赏投稿模式。
- 积分明细增加悬赏相关中文流水展示。

## 4. 已运行测试

```bash
python3 -m py_compile controllers/netdisk.py services/netdisk_resource_service.py services/points_account_service.py models/netdisk_request.py models/netdisk_upload.py schemas/netdisk.py migrations/versions/019_netdisk_request_bounty_loop.py
cd /Users/yiyi/Desktop/Desktop/vedo-project/video-ts
vue-tsc --noEmit
uni build -p mp-weixin
alembic upgrade head
python scripts/verify_netdisk_request_bounty_flow.py
```

## 5. 测试结果

- 后端 Python 编译通过。
- 小程序 TypeScript 检查通过。
- 微信小程序构建通过。
- 已在服务器 Postgres 中创建独立临时测试库，迁移到 Alembic head 成功。
- P0 接口联调脚本通过：发布冻结、积分不足拦截、自己不能投稿、重复投稿拦截、采纳发放、重复采纳不重复发分、取消退回、过期退回。
- 临时测试库和临时代码目录已清理。

## 6. 未覆盖测试项

- 未在本机直接跑数据库迁移：本机没有 Docker/Postgres/psql，改用服务器独立临时测试库验证。
- 未做重复采纳/重复退回并发压测；已做重复请求幂等验证。
- 未做微信开发者工具人工页面验收。
- 干净库迁移时发现历史问题：旧 revision `012_points_ledger_idempotency_unique` 超过 Alembic 默认 32 位版本字段长度。临时测试库通过预建更宽 `alembic_version` 表继续验证，建议后续单独修复迁移链兼容性。

## 7. 可能影响范围

- 求资源列表、发布求资源、上传资源、积分明细。
- 积分账户的可用积分和冻结积分。
- 网盘上传记录新增悬赏投稿状态。

## 8. 需要人工确认

- 悬赏过期时间 MVP 固定为 3 天是否合适。
- 悬赏投稿是否需要先人工审核再允许采纳。
- 采纳后的投稿是否需要自动进入资源库公开列表。
