# 前端详情页真实解锁接口 Codex 自测报告

## 1. 本次修改目标

把网盘资源详情页从 mock 解锁改为调用真实后端接口 `/netdisk/resources/{resource_id}/unlock`，成功后展示后端返回的网盘链接、提取码、解压码，并刷新用户积分余额。

## 2. 修改文件列表

- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/pages/netdisk/detail.vue`
- `myproject/docs/qa/前端详情页真实解锁接口_Codex自测报告.md`

## 3. 核心实现说明

- 新增 `NetdiskUnlockResType` 类型。
- 新增 `UnlockNetdiskResourceApi(resourceId)`，使用鉴权请求调用后端解锁接口。
- 详情页未登录时点击解锁会跳转登录页。
- 解锁成功后：
  - 使用后端返回的 `link`、`extract_code`、`unzip_code` 展示网盘信息。
  - 将当前资源加入本地已解锁列表，避免页面内重复点击。
  - 调用 `refreshLocalUserProfile()` 刷新本地用户信息和积分余额。
- 未解锁前仍不展示链接、提取码、解压码。

## 4. 已运行测试

- `video-ts`: `npm run type-check`

## 5. 测试结果

- Vue / TypeScript 类型检查通过。

## 6. 未覆盖测试项

- 未在微信开发者工具中手动点击详情页解锁按钮。
- 未启动前后端服务做真实 HTTP 联调。
- 未验证余额不足时前端 toast 文案是否符合产品预期。
- 未验证重新进入详情页时从后端查询已解锁状态；当前页面刷新后仍依赖 mock 初始状态和本次会话结果。

## 7. 需要 AI 测试官复核的事项

- 未解锁状态下是否完全不泄露网盘链接、提取码、解压码。
- 解锁成功后积分余额是否与 `/user/profile` 返回一致。
- 余额不足、未登录、接口 401/400 等异常分支是否符合小程序体验。
