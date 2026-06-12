# 小程序资源详情真实接口联调 Codex 自测报告

## 1. 本次修改目标

- 重启后端 8000，让服务加载最新代码并连接本地 PostgreSQL。
- 验证 PC 后台上传审核三档资源等级：普通 5、精选 10、官方 20。
- 小程序补本地开发登录态，让“我的消息”能读取后端通知。
- 小程序资源详情页接真实数据库接口：详情、未解锁隐藏链接、解锁后展示链接/提取码/解压码。

## 2. 修改文件

- `miniprogram-netdisk/src/utils/api.ts`
- `miniprogram-netdisk/src/pages/messages/index.vue`
- `miniprogram-netdisk/src/pages/resources/detail.vue`

## 3. 核心实现说明

- 新增本地开发登录辅助：无 token 时调用 `/user/dev-login` 并保存 token。
- 消息页加载前自动确保登录态，再请求 `/netdisk/notifications`。
- 资源详情页不再读取 mock，改为：
  - `/netdisk/resources/{id}` 获取资源等级、消耗积分和基础信息。
  - `/netdisk/resources/{id}/access` 获取当前用户是否已解锁。
  - `/netdisk/resources/{id}/unlock` 解锁后展示真实链接、提取码、解压码。
- 解锁前页面不展示链接、提取码、解压码。

## 4. 已运行测试

- 后端重启：
  - 使用 `DATABASE_URL=postgresql+asyncpg://postgres:099899@127.0.0.1:5432/agent`
  - 后端 8000 启动成功，PostgreSQL 连接成功。
- 后端语法检查：
  - `python3 -m py_compile controllers/netdisk.py controllers/admin.py services/netdisk_resource_service.py schemas/netdisk.py`
- 三档审核接口验证：
  - 普通：`level=normal`，`cost_points=5`
  - 精选：`level=featured`，`cost_points=10`
  - 官方：`level=official`，`cost_points=20`
- 消息接口验证：
  - dev 用户提交上传后，后台审核通过。
  - `/netdisk/notifications` 返回 `netdisk_upload_approved` 未读通知。
- 资源详情/解锁接口验证：
  - `/netdisk/resources/{id}` 返回资源等级和消耗积分。
  - `/access` 未解锁时 `link/extract_code` 为空。
  - `/unlock` 后返回真实网盘链接、提取码，并扣除对应积分。

## 5. 未覆盖测试项

- 当前 Mac shell 没有 `npm`，小程序目录没有 `node_modules`，未能运行 `npm run build:mp-weixin`。
- 未在微信开发者工具里做真机/模拟器视觉验收。
- 当前登录态是本地开发 dev-login；正式微信登录仍需后续接 `wx.login`。

## 6. 风险

- 小程序 API base 暂时写死 `http://127.0.0.1:8000`，后续需要按环境切换。
- 如果用户积分不足，解锁接口会失败；前端目前以 toast 展示后端错误。
- 首页和列表页仍有部分 mock 数据入口，后续需要继续替换为真实资源列表。
