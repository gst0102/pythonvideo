# 资源获取激励广告_Codex自测报告

## 1. 本次修改目标

在资源详情页点击“积分解锁”时触发一次可关闭的激励广告，并保证广告不阻断获取网盘信息。

## 2. 修改文件列表

- `video-ts/src/utils/rewarded-ad.ts`
- `video-ts/src/pages/netdisk/detail.vue`
- `docs/qa/资源获取激励广告_测试清单与验收标准.md`
- `docs/qa/资源获取激励广告_Codex自测报告.md`

## 3. 核心实现说明

- 新增广告场景 `netdisk_resource`。
- 资源详情页每次解锁前调用 `createRewardedAdController('netdisk_resource')` 创建独立广告实例。
- `netdisk_resource` 使用 5 个激励广告 ID 随机池：`adunit-0eae76b6a64cabbb`、`adunit-5983ee0404c414fc`、`adunit-c08be6f761c3b0a7`、`adunit-a921c4e0383a451f`、`adunit-7c61b0922792ddc9`。
- 广告完整观看、关闭、不可用或报错后，都会继续执行原资源解锁流程。

## 4. 已运行测试

- `PATH=".../node/bin:$PATH" ./node_modules/.bin/vue-tsc --noEmit`

## 5. 未覆盖测试项

- 未在微信开发者工具里验证真实激励广告弹出。
- 未做服务端资源广告轮换策略，当前资源广告池由小程序端随机选择。
