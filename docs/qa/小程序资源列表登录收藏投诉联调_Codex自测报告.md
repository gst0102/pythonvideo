# 小程序资源列表、登录、收藏投诉联调 Codex 自测报告

## 1. 本次修改目标

- 小程序首页/资源列表使用后端真实资源接口，进入详情时使用数据库资源 ID。
- 小程序登录由本地 `dev-login` 改为正式 `wx.login -> /user/login`。
- 资源详情页接真实收藏/取消收藏接口。
- 资源详情页接真实投诉失效接口。

## 2. 修改文件

- `miniprogram-netdisk/src/utils/api.ts`
- `miniprogram-netdisk/src/pages/home/index.vue`
- `miniprogram-netdisk/src/pages/resources/list.vue`
- `miniprogram-netdisk/src/pages/resources/detail.vue`
- `miniprogram-netdisk/src/pages/messages/index.vue`

## 3. 核心实现说明

- 新增 `ensureWechatLogin`：
  - 无 token 时调用 `uni.login({ provider: "weixin" })`。
  - 使用返回的 `code` 调 `/user/login`。
  - 成功后保存 `token/access_token`。
- 首页“今日精选”调用 `/netdisk/resources`，资源 ID 来自数据库。
- 资源列表页调用 `/netdisk/resources`，支持关键词、分类、网盘、排序、分页加载。
- 详情页收藏按钮调用：
  - `POST /netdisk/resources/{id}/favorite`
  - `DELETE /netdisk/resources/{id}/favorite`
- 详情页投诉失效调用：
  - `POST /netdisk/repairs`
  - `mode=report`

## 4. 已运行测试

- 资源列表接口：
  - `GET /netdisk/resources?page=1&page_size=3&sort=latest`
  - 返回真实数据库资源 ID、等级、消耗积分。
- 收藏接口：
  - 收藏返回 `favorited=true`。
  - 取消收藏返回 `favorited=false`。
- 投诉接口：
  - 投诉成功创建 `mode=report`、`status=pending` 的记录。
- 静态检查：
  - 小程序核心页面已无 `ensureDevLogin`、`/user/dev-login` 残留。

## 5. 未覆盖测试项

- 正式 `wx.login` 必须在微信小程序运行时验证，命令行无法生成真实微信 code。
- 当前本机没有可用 `npm`，小程序目录没有 `node_modules`，未能运行 `npm run build:mp-weixin`。
- 首页仍复用 mock 的分类、求资源、用户积分展示；本轮只替换资源列表/详情主链路。

## 6. 风险

- `/user/login` 依赖后端微信 AppID/Secret 配置；配置错误时正式登录会失败。
- 小程序 API base 仍是本地 `http://127.0.0.1:8000`，上线前要做环境切换。
- 投诉目前使用固定文案，后续可增加用户输入投诉原因。
