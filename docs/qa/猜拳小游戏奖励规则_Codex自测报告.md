# 猜拳小游戏奖励规则_Codex自测报告

## 1. 本次修改目标

将猜拳小游戏调整为后端判定输赢：赢了可领取 4 分，平局不发分，输了扣 2 分。

## 2. 修改文件列表

- `schemas/game.py`
- `controllers/game.py`
- `services/game_task_service.py`
- `scripts/verify_game_ad_flow.py`
- `video-ts/src/components/GameZone.vue`
- `video-ts/src/types/index.d.ts`
- `docs/qa/猜拳小游戏奖励规则_测试清单与验收标准.md`
- `docs/qa/猜拳小游戏奖励规则_Codex自测报告.md`

## 3. 核心实现说明

- `/game/rounds` 支持 `user_choice`，后端随机生成 `system_choice` 并计算 `result`。
- 兼容旧参数 `result`，但奖励规则统一为 win=4、draw/lose=0。
- 小程序猜拳页不再本地决定输赢，只提交用户出拳并展示后端返回的电脑出拳。
- 输局立即写入 `game_penalty=-2`，不触发广告奖励链路。
- 平局不触发广告奖励链路。

## 4. 已运行测试

- `python3 -m py_compile schemas/game.py controllers/game.py services/game_task_service.py scripts/verify_game_ad_flow.py`
- `PATH=".../node/bin:$PATH" ./node_modules/.bin/vue-tsc --noEmit`
- 更新游戏广告验证脚本中的奖励规则断言。

## 5. 未覆盖测试项

- 未连接真实数据库执行 `scripts/verify_game_ad_flow.py --execute`。
- 未在微信开发者工具中手工跑一局猜拳。
