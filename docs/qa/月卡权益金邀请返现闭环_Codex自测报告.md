## 1. 本次修改目标

实现月卡充值、权益金、邀请返现闭环：

- 充值页支持“充值积分 / 月卡充值”切换。
- 月卡支付成功后一次性发放 300/900 积分，并顺延 30 天免获取网盘广告权益。
- 积分充值和月卡充值都给一级邀请人发放 50% 权益金，并保留等值积分奖励。
- 同一订单重复回调不重复发放；同一好友后续新订单继续产生收益。
- 邀请页首屏突出权益金、提现和收益通知。

## 2. 修改文件列表

- `controllers/vip.py`
- `services/payment_service.py`
- `services/commission_service.py`
- `services/mine_assets_service.py`
- `.env.example`
- `scripts/verify_benefit_card_equity_flow.py`
- `video-ts/src/api/request.ts`
- `video-ts/src/types/index.d.ts`
- `video-ts/src/store/index.ts`
- `video-ts/src/pages/netdisk/recharge.vue`
- `video-ts/src/pages/netdisk/invite.vue`
- `video-ts/src/pages/netdisk/detail.vue`
- `video-ts/src/pages/netdisk/mock.ts`
- `video-ts/src/pages/netdisk/points-detail.vue`

## 3. 核心实现说明

- 后端新增 `/vip/card-packages` 和 `/vip/card-order`，月卡订单使用 `card_month_10`、`card_month_20`。
- 支付成功回调识别月卡订单后激活/顺延 `vip_expire_at`，并用 `benefit_card_points:{order_id}` 幂等发放月卡积分。
- 支付成功回调对积分充值和月卡充值执行邀请返利：一级邀请人获得 50% 权益金，写入 `user.balance` 和 `user.total_income`。
- 权益金幂等锚点是 `order_id + inviter_id + level` 的 `commission_records`，所以重复回调不重复发，同好友新订单会继续发。
- 邀请收益到账会创建站内通知，并在配置 `WX_INVITE_REWARD_TEMPLATE_ID` 后尝试发送微信订阅消息。
- `mine/assets` 返回 `benefit_card.ad_free_netdisk`，小程序资源详情页据此跳过获取网盘前广告，但仍扣资源积分。

## 4. 已运行测试

- `python3 -m py_compile controllers/vip.py services/payment_service.py services/commission_service.py services/mine_assets_service.py scripts/verify_benefit_card_equity_flow.py`
- `npm run type-check`
- `npm run build:mp-weixin`

## 5. 测试结果

- 后端语法检查通过。
- 小程序 TypeScript 类型检查通过。
- 微信小程序本地构建通过，产物在 `video-ts/dist/build/mp-weixin`。

## 6. 未覆盖测试项

- 当前本机没有后端 Python 依赖和 Docker，`scripts/verify_benefit_card_equity_flow.py --execute` 未能实际连数据库执行，报错为缺少 `sqlmodel`。
- 微信订阅消息模板字段未确认，需你申请/配置模板后，用真实模板 ID 验证发送结果。
- 本次未上传微信开发者工具，手机端暂时不会自动看到小程序前端改动。

## 7. 可能影响范围

- 支付成功回调、积分流水、邀请返利、现金提现余额、资源详情广告展示、邀请页收益展示。

## 8. 需要 AI 测试官复核的事项

- P0：重复支付回调是否只发一次月卡积分、权益金、邀请积分。
- P0：同一好友第二次新订单是否继续给邀请人发权益金。
- P0：月卡用户获取网盘是否免广告但仍扣积分。
- P0：权益金余额、提现冻结、商户转账回调是否和现金余额一致。
