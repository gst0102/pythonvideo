# 网盘资源真实数据库联调 Codex 自测报告

生成日期：2026-06-12

## 1. 本次修改目标

建立本地 PostgreSQL 真实数据库联调能力，并验证网盘资源解锁最小闭环：测试登录、用户账户初始化、未解锁 access 防泄露、首次解锁扣积分、重复解锁幂等、数据库账户与流水一致。

## 2. 修改文件列表

- `controllers/user.py`
- `schemas/user.py`
- `.env.example`
- `docs/qa/网盘资源真实数据库联调_Codex自测报告.md`

## 3. 核心实现说明

- 新增 `POST /user/dev-login` 本地开发测试登录接口。
- 该接口默认关闭，只有设置 `ENABLE_DEV_LOGIN=true` 时可用。
- dev-login 会基于指定 openid 创建或读取用户，初始化 `user_accounts`，并按幂等键写入一笔可消费积分种子流水。
- 本地 PostgreSQL `agent` 数据库已初始化项目模型表。
- 后端已用真实 PostgreSQL 连接重启，端口为 `8001`。

## 4. 已运行测试

- Python 语法检查：
  - `PYTHONPYCACHEPREFIX=/private/tmp/vedo-pycache python3 -m py_compile controllers/user.py schemas/user.py main.py`
- PostgreSQL 连接检查：
  - `pg_isready -h 127.0.0.1 -p 5432 -U postgres`
  - `select version();`
- 数据库初始化：
  - `models.base.init_db()`
- 后端接口联调：
  - `POST /user/dev-login`
  - `GET /user/profile`
  - `GET /netdisk/resources/r1/access`
  - `POST /netdisk/resources/r1/unlock`
  - 重复 `POST /netdisk/resources/r1/unlock`
  - 再次 `GET /netdisk/resources/r1/access`
- 数据库对账：
  - 查询 `users + user_accounts`
  - 查询 `points_ledger`

## 5. 测试结果

- 本地 PostgreSQL 16 启动成功，`agent` 数据库可连接。
- dev-login 创建测试用户成功，并写入 100 可消费积分。
- 未解锁 access 返回 `unlocked=false`，且 `link`、`extract_code`、`unzip_code` 均为空。
- 首次 unlock 返回完整链接、提取码、解压码，账户 `consumable_points` 从 100 变为 90。
- 重复 unlock 返回相同 ledger_id，提示 `resource already unlocked`，账户积分仍为 90。
- 数据库 `points_ledger` 只有两条相关流水：
  - `dev_seed +100`
  - `netdisk resource_unlock -10`

## 6. 未覆盖测试项

- 未在微信开发者工具中写入 dev-login token 做前端点击解锁验证。
- 未启动 Redis，本轮 Redis 仅作为可忽略的本地连接失败提示。
- 未跑 Alembic 迁移链；本地空库采用 SQLModel `init_db()` 初始化模型表。
- 未测试积分不足分支。

## 7. 需要 AI 测试官复核的事项

- dev-login 仅允许本地联调使用，生产必须保持 `ENABLE_DEV_LOGIN=false`。
- 真实解锁前端点击流程需要继续在微信开发者工具中验证。
- 需要补积分不足测试账号，确认不会生成解锁流水。
