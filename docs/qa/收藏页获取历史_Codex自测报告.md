# 收藏页获取历史 Codex 自测报告

## 1. 本次修改目标

- 在底部 TabBar 的“收藏”页内，新增与“我的收藏”平行的“获取历史”胶囊入口。
- 用户可以查看自己获取过的网盘资源。
- 用户可以删除自己的获取历史展示记录。
- 删除获取历史不得删除积分流水，不得影响已解锁状态。

## 2. 修改文件列表

- `models/netdisk_unlock_hidden.py`
- `migrations/versions/028_netdisk_unlock_hidden.py`
- `models/__init__.py`
- `schemas/netdisk.py`
- `services/netdisk_resource_service.py`
- `controllers/netdisk.py`
- `src/api/request.ts`
- `src/types/index.d.ts`
- `src/pages/netdisk/favorites.vue`

## 3. 核心实现说明

- 获取历史来源于 `points_ledger` 中 `change_type = resource_unlock` 的真实解锁流水。
- 新增 `netdisk_unlock_hidden` 表，用于记录用户主动隐藏的获取历史。
- 删除获取历史只是写隐藏记录，不删除账务流水，不影响资源详情页继续查看已获取链接。
- 后端新增接口：
  - `GET /netdisk/unlocks/mine`
  - `DELETE /netdisk/unlocks/{ledger_id}`
- 小程序收藏页新增“我的收藏 / 获取历史”胶囊切换，两个列表共用资源卡片样式。

## 4. 已运行测试

- `python3 -m py_compile models/netdisk_unlock_hidden.py migrations/versions/028_netdisk_unlock_hidden.py controllers/netdisk.py services/netdisk_resource_service.py schemas/netdisk.py`
- `npm run build:mp-weixin`

## 5. 测试结果

- 后端语法检查通过。
- 小程序微信构建通过。
- 删除历史逻辑未触碰积分流水，仅隐藏用户侧历史展示。

## 6. 未覆盖测试项

- 尚未执行数据库迁移后的真实接口联调。
- 尚未在体验版真机验证“获取历史列表”和“删除历史”。

## 7. 风险

- 需要部署后端代码并执行 `028_netdisk_unlock_hidden` 迁移后，前端新功能才能正常调用接口。
- 如果历史资源已下架，列表会自动跳过无法映射到资源表的流水。

## 8. 下一步建议

- 部署后端并执行迁移。
- 用已有解锁用户打开收藏页，切换“获取历史”，删除一条历史后确认积分明细仍保留该解锁流水。
