# 小程序我的页、投诉记录与正式登录 Codex 自测报告

## 1. 本次修改目标

- 使用微信正式登录链路：`wx.login -> /user/login`。
- “我的”页读取真实数据：可用积分、冻结积分、收藏数、上传数、补链数、投诉数。
- 资源详情投诉失效时允许用户填写投诉原因。
- 新增“我的投诉记录”，展示投诉状态和运营处理备注。

## 2. 修改文件

- `miniprogram-netdisk/src/utils/api.ts`
- `miniprogram-netdisk/src/pages/mine/index.vue`
- `miniprogram-netdisk/src/pages/resources/detail.vue`
- `miniprogram-netdisk/src/pages/reports/mine.vue`
- `miniprogram-netdisk/src/pages/messages/index.vue`
- `miniprogram-netdisk/src/pages.json`

## 3. 核心实现说明

- `ensureWechatLogin` 无 token 时调用 `uni.login({ provider: "weixin" })`，拿 code 后请求 `/user/login`。
- “我的”页并行请求：
  - `/user/profile`
  - `/netdisk/favorites`
  - `/netdisk/uploads/mine`
  - `/netdisk/repairs/mine`
- 资源详情投诉失效改为底部输入面板，用户必须填写原因后才能提交。
- 我的投诉记录页复用 `/netdisk/repairs/mine`，只展示 `mode=report` 的记录。

## 4. 已运行测试

- `/user/login` 配置探测：
  - 使用假 code 请求，微信返回 `invalid code`。
  - 说明后端已能请求微信 `jscode2session`，不是缺少 AppID/Secret。
- 我的页接口验证：
  - profile 返回用户积分。
  - favorites 返回收藏数。
  - uploads/mine 返回上传记录。
  - repairs/mine 可区分补链与投诉记录。
- 投诉记录接口验证：
  - 提交投诉后，`repairs/mine` 返回 `mode=report`、`status=pending` 记录。
- 后端语法检查：
  - `python3 -m py_compile controllers/user.py controllers/netdisk.py services/user_service.py services/netdisk_resource_service.py`
- 微信开发者工具：
  - 已尝试 CLI 启动服务端口。
  - CLI 提示服务端口未完全可用，已通过 `open` 打开微信开发者工具项目目录。

## 5. 未覆盖测试项

- 正式 `wx.login` 需要在微信开发者工具模拟器中获取真实 code，命令行无法伪造。
- 当前 Mac shell 没有 npm，小程序目录没有 `node_modules`，未能运行小程序构建。
- 投诉记录目前只展示列表，不支持点击进入投诉详情。

## 6. 风险

- 如果微信开发者工具项目 AppID 与后端 `.env` 的 AppID 不一致，`/user/login` 会失败。
- API base 仍是本地 `http://127.0.0.1:8000`，上线前要切环境配置。
- “我的上传 / 我的收藏 / 积分明细”入口仍是占位，后续需要补独立页面。
