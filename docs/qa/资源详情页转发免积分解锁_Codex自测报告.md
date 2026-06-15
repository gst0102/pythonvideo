# 资源详情页转发免积分解锁_Codex自测报告

## 1. 本次修改目标

在资源详情页新增“转发好友免积分”能力：发起人完成转发后免积分解锁；好友通过带签名 token 的分享链接进入后，也可免积分、免广告领取同一资源网盘信息。

## 2. 修改文件列表

- `controllers/netdisk.py`
- `schemas/netdisk.py`
- `services/netdisk_resource_service.py`
- `scripts/verify_netdisk_unlock_flow.py`
- `video-ts/src/api/request.ts`
- `video-ts/src/pages/netdisk/detail.vue`
- `video-ts/src/types/index.d.ts`

## 3. 核心实现说明

- 后端新增 `share-token`、`share-unlock`、`share-claim` 三个接口。
- 分享 token 使用后端 HMAC 签名，默认 30 天有效，防止随意拼参数解锁任意资源。
- 分享解锁使用 `resource_share_unlock` 0 分流水，不扣积分、不增加消耗积分。
- 普通扣积分解锁前会先检查是否已经通过普通或分享方式解锁，避免误扣。
- 获取历史兼容普通解锁和分享解锁。
- 小程序新增“转发好友免积分”按钮，与“获取网盘信息”同一行。
- 好友打开分享链接后，登录即可自动领取免积分解锁。

## 4. 已运行测试

- `python3 -m py_compile controllers/netdisk.py schemas/netdisk.py services/netdisk_resource_service.py scripts/verify_netdisk_unlock_flow.py`
- `npm run type-check`
- `npm run build:mp-weixin`
- 生产容器：`python /app/scripts/verify_netdisk_unlock_flow.py --execute`
- 生产公网：`https://api.lifelove.top/health`
- 生产公网 OpenAPI：确认 `share-token`、`share-unlock`、`share-claim` 三个接口存在

## 5. 测试结果

- 后端语法编译通过。
- 小程序类型检查通过。
- 小程序微信包构建通过。
- 后端生产容器已重启，健康检查通过。
- 生产容器数据库回滚验证通过：扣积分解锁、幂等、首次资源邀请奖励、分享免积分解锁、余额不足拦截。

## 6. 未覆盖测试项

- 本机未执行 `scripts/verify_netdisk_unlock_flow.py --execute`：当前 macOS 本机 Python 环境缺少 `sqlalchemy`，项目 `.venv` 是 Windows 结构，`uv` 命令也不可用；已在生产容器内执行通过。
- 微信开发者工具未由 Codex 上传，因此手机端当前还看不到新按钮；需要用户手动上传小程序包。
- 未做真机分享成功回调验证。

## 7. 可能影响范围

- 资源详情页解锁流程。
- 获取历史列表。
- 积分流水中 `resource_unlock` 查询口径。
- 微信分享链接参数。

## 8. 需要 AI 测试官复核的事项

- 分享成功回调是否在微信开发者工具和真机均触发。
- 分享 token 被篡改时后端是否稳定拒绝。
- 0 分解锁流水是否满足后台统计口径。
- 多好友通过同一分享链接领取时，业务上是否允许全部免积分获取。
