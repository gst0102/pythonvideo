# 邀请启动参数登录闭环 Codex 自测报告

## 1. 本次修改目标

把小程序分享链接中的 `inviter` 从启动参数贯通到后端 `/user/login`，让后端邀请关系绑定最小闭环可以接收到真实前端传参。

## 2. 修改文件列表

- `video-ts/src/App.vue`
- `video-ts/src/pages/netdisk/invite.vue`
- `video-ts/src/pages/user-login/login.vue`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/utils/invite.ts`

## 3. 核心实现说明

- 新增 `src/utils/invite.ts`，集中处理邀请参数解析、标准化、本地缓存和登录后清理。
- `App.vue` 在 `onLaunch` / `onShow` 中读取小程序启动参数，支持 `inviter`、`invite_code` 和 `scene`。
- 未登录用户首次进入分享链接时，把邀请人写入 `pending_inviter`，并兼容旧 key `inviteCode`。
- 已登录用户打开别人分享链接时不写入待绑定邀请人，避免退出后误绑定。
- 邀请页 `onLoad` 也写入同一套 pending inviter，保证直接进入邀请页时可在登录时提交。
- 登录页调用 `/user/login` 时同时传 `inviter` 和兼容字段 `invite_code`，登录成功后清理待绑定邀请缓存。

## 4. 是否涉及高风险模块

涉及。该链路会影响邀请关系绑定、后续邀请奖励、积分流水和返利幂等。

## 5. 已运行测试

- `video-ts`: `npm run type-check`
- `myproject`: `python -m py_compile scripts\verify_login_invite_flow.py`
- `myproject`: 尝试执行 `.venv\Scripts\python.exe -m alembic upgrade head`

## 6. 测试结果

- 前端 TypeScript / Vue 类型检查通过。
- 后端验证脚本语法检查通过。
- Alembic CLI 在全局 Python 中不可用；使用项目 `.venv` 后可启动 Alembic。
- 使用 `PYTHONUTF8=1` 解决了 Windows 读取 `alembic.ini` 的编码问题。
- 迁移执行被本地 PostgreSQL 连接中断阻塞：`asyncpg.exceptions.ConnectionDoesNotExistError: connection was closed in the middle of operation`。

## 7. 未覆盖测试项

- 未完成真实数据库迁移后的 `python scripts\verify_login_invite_flow.py --execute`。
- 未在微信开发者工具中手动验证分享进入、登录、后端绑定全链路。
- 未验证真实微信 `scene` 二维码参数进入场景。
- 未接入邀请奖励积分发放、奖励流水和奖励幂等。

## 8. 可能影响范围

- 小程序全局启动参数捕获。
- 登录请求体新增 `inviter` 字段，同时保留旧 `invite_code` 字段。
- 邀请页 mock 绑定状态与真实登录 pending inviter 存储共存。

## 9. 需要 AI 测试官复核的事项

- 在可连接数据库环境中应用迁移 `009_invite_relations`。
- 执行 `python scripts\verify_login_invite_flow.py --execute`。
- 使用微信开发者工具模拟 `/pages/netdisk/invite?inviter=xxx` 冷启动和热启动进入。
- 验证第一次邀请生效、第二个邀请人参数不覆盖、自邀不绑定、登录成功后本地 pending inviter 被清理。
