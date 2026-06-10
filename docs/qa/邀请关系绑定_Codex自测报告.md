# 邀请关系绑定 Codex 自测报告

## 1. 本次修改目标

进入后端“邀请关系绑定”最小闭环开发：登录时支持读取分享参数 `inviter` / `invite_code`，实现首次绑定、禁止自邀、禁止重复绑定，并通过 `invite_relations` 表保留可追溯绑定记录。

## 2. 修改文件列表

- `controllers/user.py`
- `schemas/user.py`
- `services/user_service.py`
- `models/invite_relation.py`
- `models/__init__.py`
- `migrations/versions/009_invite_relations.py`
- `scripts/verify_login_invite_flow.py`

## 3. 核心实现说明

- 登录接口同时接受 `inviter` 和 `invite_code`，优先使用 `inviter`，兼容旧字段 `invite_code`。
- `UserService.get_or_create_user` 对新用户和已存在但未绑定用户都执行一次邀请绑定尝试。
- 邀请绑定成功时写入 `users.parent_id`、`users.grand_parent_id`，并新增一条 `invite_relations` 追踪记录。
- `invite_relations.invitee_id` 设置唯一约束，保证每个被邀请用户只能有一条绑定记录。
- 服务层显式拦截自邀、空邀请码、无效邀请码、已绑定用户重复绑定。
- 验证脚本增加邀请记录追踪、重复绑定不覆盖、已有未绑定用户后续首次绑定、自邀不建关系等断言。

## 4. 是否涉及高风险模块

涉及。邀请关系绑定属于积分经济系统 P0 基础链路，会影响后续邀请奖励、返利、积分流水和风控判断。

## 5. 已运行测试

- `python -m py_compile services\user_service.py schemas\user.py controllers\user.py models\invite_relation.py scripts\verify_login_invite_flow.py migrations\versions\009_invite_relations.py`
- `python scripts\verify_login_invite_flow.py`

## 6. 测试结果

- Python 语法编译通过。
- 验证脚本 dry run 通过，可确认脚本覆盖计划已更新。

## 7. 未覆盖测试项

- 未执行 `python scripts\verify_login_invite_flow.py --execute`，因为需要目标数据库先应用 Alembic 迁移 `009_invite_relations`。
- 未接入真实微信登录入口的启动参数解析链路。
- 未实现邀请奖励积分发放、奖励幂等、积分流水一致性。
- 未覆盖二级分销、充值返利、提现等后续高风险链路。

## 8. 可能影响范围

- 登录接口请求体新增兼容字段，不影响旧 `invite_code` 入参。
- 登录时已存在但未绑定邀请人的用户，现在可以在后续带分享参数登录时完成首次绑定。
- 绑定成功会更新邀请人统计字段，后续如接积分奖励，需要以 `invite_relations` 作为可追溯依据。

## 9. 需要 AI 测试官复核的事项

- 数据库迁移应用后，执行 `python scripts\verify_login_invite_flow.py --execute` 做真实库回归。
- 复核同一被邀请用户重复登录、重复请求、换邀请人参数时是否仍只有一条绑定记录。
- 复核自邀、无效邀请码、已绑定用户再次携带邀请参数的安全表现。
- 后续接奖励时，必须补充奖励发放幂等、积分流水、余额一致性测试。
