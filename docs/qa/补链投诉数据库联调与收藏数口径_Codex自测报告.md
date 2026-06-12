# 补链投诉数据库联调与收藏数口径 Codex 自测报告

## 修改目标

完成补链/投诉真实数据库联调，并让资源收藏数在收藏/取消收藏时保持后端实时口径。

## 修改文件

- `models/netdisk_repair.py`
- `migrations/versions/011_netdisk_repairs.py`
- `models/__init__.py`
- `schemas/netdisk.py`
- `controllers/netdisk.py`
- `services/netdisk_resource_service.py`
- `services/mine_assets_service.py`
- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/repair.vue`
- `video-ts/src/pages/netdisk/favorites.vue`

## 实现内容

- 新增 `netdisk_repairs` 表，保存补链和投诉提交。
- 新增接口：
  - `GET /netdisk/repairs`
  - `GET /netdisk/repairs/mine`
  - `POST /netdisk/repairs`
- `/mine/assets` 的 `repair_count` 改为统计真实补链/投诉记录。
- 收藏成功时资源表 `favorites + 1`。
- 取消收藏时资源表 `favorites - 1`，最低为 0。
- 小程序补链页提交改为真实接口，登录后展示我的数据库记录。
- 补链/投诉提交后清理我的页统计缓存。
- 收藏页删除收藏后清理我的页统计和资源列表缓存。
- 上传资源、补链提交成功后不再把赚积分任务本地标记为 completed。
- “完成求资源”任务默认改为待完成，点击仅进入求资源列表，不再本地直接标完成。

## 已执行测试

- `python -m py_compile controllers/netdisk.py schemas/netdisk.py services/netdisk_resource_service.py services/mine_assets_service.py models/netdisk_repair.py models/__init__.py migrations/versions/011_netdisk_repairs.py`
- `npm run type-check`
- `npm run build:mp-weixin:local`
- `POST /user/dev-login`
- `POST /netdisk/repairs`
- `GET /netdisk/repairs/mine`
- `GET /netdisk/repairs`
- `GET /mine/assets`
- `POST /netdisk/resources/r1/favorite`
- `DELETE /netdisk/resources/r1/favorite`
- `GET /netdisk/resources/r1`
- 发布求资源、上传资源、提交补链前后查询 `GET /points/ledger?source=netdisk`

## 测试结果

- 后端语法检查通过。
- 前端类型检查通过。
- 微信小程序本地构建通过。
- 补链提交成功，返回 pending 记录。
- 我的补链记录能查到当前用户提交。
- 全部补链/投诉列表能查到提交记录。
- 我的页 `repair_count` 随提交增长。
- 收藏后资源收藏数从 33 到 34。
- 取消收藏后资源收藏数从 34 回到 33。
- 发布求资源、上传资源、提交补链后，netdisk 积分流水仍为 0。
- 前端本地任务状态不再因上传/补链提交直接完成。

## 未覆盖测试项

- 未在微信开发者工具内人工点击补链/投诉完整流程。
- 未做后台审核通过后发放补链奖励的积分流水。
- 未做补链/投诉后台管理页面。
- 未实现取消/删除求资源、上传、补链接口；当前不存在通过取消/删除触发积分的后端路径。

## 风险

- 补链奖励目前只是待审核记录里的 `reward_points`，不会自动发积分。
- 全部补链/投诉列表当前返回最近 100 条，后续数据量变大需要分页。
- 生产环境需要执行 `011_netdisk_repairs` 迁移。
- 后续如果新增取消/删除/审核通过接口，必须以审核通过记录 ID 作为幂等键发放积分，取消或删除不得发积分。
