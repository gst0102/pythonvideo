# 网盘资源审核等级与用户消息 Codex 自测报告

## 1. 本次修改目标

- 上传审核通过时支持选择资源等级和解锁消耗积分：普通 5、精选 10、官方 20。
- 小程序新增“我的消息”，展示审核结果、确认失效、待追缴通知。
- 待追缴详情支持一键打开原上传/补链审核记录。
- 补充生产迁移检查清单，避免无 `alembic_version` 的历史库直接升级。

## 2. 修改文件

- `schemas/netdisk.py`
- `controllers/netdisk.py`
- `controllers/admin.py`
- `services/netdisk_resource_service.py`
- `miniprogram-netdisk/src/utils/api.ts`
- `miniprogram-netdisk/src/pages/messages/index.vue`
- `miniprogram-netdisk/src/pages/mine/index.vue`
- `miniprogram-netdisk/src/pages.json`
- `docs/qa/生产迁移检查清单_网盘资源审核与通知.md`

## 3. 核心实现说明

- 后端上传审核请求新增 `resource_level`、`cost_points`。
- 后端校验资源等级和积分必须匹配：`normal=5`、`featured=10`、`official=20`。
- 上传审核通过后写入/更新资源表 `level`、`cost_points`、`source_upload_id`。
- 审核通过、拒绝、确认失效、待追缴等动作写入 `netdisk_user_notifications`。
- 小程序新增消息页，读取 `/netdisk/notifications`，并支持点击标记已读。
- PC 待追缴详情可跳转原上传/补链审核记录。

## 4. 已运行测试

- 后端语法检查：
  - `python3 -m py_compile schemas/netdisk.py controllers/netdisk.py controllers/admin.py services/netdisk_resource_service.py`
- PC 后台构建：
  - `vite build`
- Browser 页面检查：
  - 审核中心页面可打开。
  - 上传审核通过弹窗出现“普通 5分 / 精选 10分 / 官方 20分”。
  - 待追缴页面可打开。

## 5. 未覆盖测试项

- 当前 shell 没有 `npm`，小程序目录也没有 `node_modules`，未能运行 `npm run build:mp-weixin`。
- 当前 8000 后端进程未加载最新代码，未完成新版审核接口的实时 curl 验证。
- 本机 `.venv` 是 Windows 风格目录，未能临时启动新版后端验证端口。

## 6. 风险与人工确认

- 小程序消息页依赖用户本地存在 `token` 或 `access_token`，未登录时会显示失败提示。
- 生产库迁移前必须确认 `alembic_version`，不能直接对历史库执行 `upgrade head`。
- 资源等级影响用户解锁扣分，建议上线前人工各审核一条普通/精选/官方资源。
