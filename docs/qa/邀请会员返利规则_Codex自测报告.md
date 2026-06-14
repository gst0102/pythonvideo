# 邀请会员返利规则_Codex自测报告

## 1. 本次修改目标

- 明确邀请奖励规则：会员开通走一级 50% / 二级 5% 返积分；积分包首充才发固定 20 分。
- 小程序邀请页首屏突出 50% 返利，避免用户看不到核心力度。
- 防止同一笔会员订单同时触发会员返利和固定首充 20 分。

## 2. 修改文件列表

- `services/payment_service.py`
- `scripts/verify_invite_rebate_flow.py`
- `video-ts/src/pages/netdisk/invite.vue`
- `video-ts/src/pages/netdisk/earn.vue`
- `video-ts/src/pages/netdisk/mock.ts`
- `video-ts/src/pages/netdisk/points-detail.vue`

## 3. 核心实现说明

- 后端把 `invite_first_recharge` 固定 20 分限制在 `points_*` 积分包订单分支内。
- VIP/会员订单继续发放 VIP 权益、会员赠送积分、一级 50% / 二级 5% 邀请返利，不再额外叠加固定 20 分。
- 邀请返利验证脚本新增真实 `invite_relations` 关系，覆盖会员订单不发固定 20、积分包首充发固定 20。
- 小程序邀请页新增“一级好友 50% / 二级团队 5%”首屏卡片，规则说明明确“不重复叠加”。
- 赚积分页邀请入口从“最多 35 分”改为“会员返 50%”。
- 积分明细补充邀请返利冻结、解冻、积分包首充的中文说明。

## 4. 已运行测试

- 后端语法检查：`python3 -m py_compile services/payment_service.py scripts/verify_invite_rebate_flow.py`
- 后端差异检查：`git diff --check`
- 小程序类型检查：`pnpm run type-check`
- 小程序微信构建：`pnpm run build:mp-weixin`
- 小程序差异检查：`git diff --check`

## 5. 测试结果

- 后端语法检查通过。
- 小程序类型检查通过。
- 小程序微信构建通过，当前 `dist/build/mp-weixin` 约 708K。
- 本机后端数据库专项未执行：本机缺少可用 Python 依赖环境，项目 `.venv` 为 Windows 虚拟环境，且本机没有 Docker。

## 6. 未覆盖测试项

- 服务器容器内还需要执行：`python scripts/verify_invite_rebate_flow.py --execute`
- 部署后需要用真实支付链路复测会员订单：邀请人只得到 50%/5%返利，不额外得到固定 20 分。
- 部署后需要用积分包首充复测：邀请人得到固定 20 分。

## 7. 可能影响范围

- 支付成功回调后的邀请奖励发放。
- 小程序邀请页、赚积分页、积分明细页展示文案。

## 8. 需要 AI 测试官复核的事项

- 会员返利、固定首充奖励是否按业务预期互斥。
- 后台统计、用户积分明细、用户余额是否一致。
- 小程序邀请页面 50%/5% 说明是否足够明显且不过度承诺现金收益。
