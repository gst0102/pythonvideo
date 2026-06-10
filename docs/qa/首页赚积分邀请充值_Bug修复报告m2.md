# 首页赚积分邀请充值_Bug修复报告m2

生成日期：2026-06-11
执行角色：开发 Codex
依据文档：`docs/qa/当前项目_验收报告m2.md`

## 1. 修复目标

本轮只处理 m2 验收报告中明确指出的静态原型问题：

- 修复 BUG-M2-001：`earn.vue` 中“高收益任务”存在高风险收益文案。
- 优化邀请页原型：不再以邀请码为核心展示，改为“分享链接自动携带邀请人；首次绑定后其他邀请链接失效”。

本轮不修改后端、支付、积分流水、邀请奖励、二级分销、提现、广告统计等真实业务逻辑。

## 2. 修改文件

`video-ts`：

- `src/pages/netdisk/earn.vue`
- `src/pages/netdisk/invite.vue`
- `src/pages/netdisk/index.vue`
- `src/pages/netdisk/mock.ts`

`myproject`：

- `docs/qa/首页赚积分邀请充值_Bug修复报告m2.md`

## 3. 核心实现说明

### 3.1 修复高风险文案

- 将 `赚积分` 页的 `高收益任务` 改为 `重点任务`。
- 将说明 `增长和资源供给` 改为 `资源供给与协作`。
- 将邀请相关的 `最高+35分` 调整为 `最多+35分`。
- 将首页邀请提示同步为 `邀请好友最多+35分`。

### 3.2 邀请分享链路 mock

- 新增 `myInviteCode = 'YX2026'` 作为当前用户 mock 分享标识。
- 新增 `inviteBindingStorageKey = 'netdisk_bound_inviter'`，用于模拟“首次绑定邀请人”。
- 邀请页展示 mock 分享链接：

```text
/pages/netdisk/invite?inviter=YX2026
```

- 邀请页加载时读取 `query.inviter`：
  - 没有 inviter：展示“分享链接自动携带邀请人”的说明。
  - 首次带 inviter 进入：写入本地 mock storage，展示已绑定。
  - 已绑定后再次带不同 inviter 进入：展示“该邀请链接已失效”，不覆盖原绑定。
- `onShareAppMessage` 返回带 inviter 的分享路径。

### 3.3 保持静态原型边界

- 不发放真实积分。
- 不绑定真实邀请关系。
- 不触发真实支付。
- 不创建真实邀请奖励流水。

## 4. 已运行测试

在 `video-ts` 执行：

```bash
npm run type-check
```

结果：通过。

执行文案扫描：

```bash
rg -n "高收益|稳赚|暴利|返佣|二级分销|提现到账|真实到账|真实收益|高收益承诺|无条件|邀请码|最高" src\pages\netdisk\index.vue src\pages\netdisk\earn.vue src\pages\netdisk\invite.vue src\pages\netdisk\recharge.vue src\pages\netdisk\mock.ts
```

结果：无命中。

## 5. 回归验证结果

| 验证项 | 结果 | 说明 |
|---|---|---|
| `高收益任务` 文案移除 | 通过 | 已改为 `重点任务` |
| 邀请入口不使用“最高”表述 | 通过 | 已改为 `最多+35分` |
| 邀请页不突出邀请码 | 通过 | 改为分享链接携带邀请人 |
| 首次邀请绑定 mock | 通过 | 首次带 inviter 进入会写本地 storage |
| 二次不同邀请失效 | 通过 | 已绑定后不同 inviter 显示失效，不覆盖 |
| 不真实发放积分 | 通过 | 仅保存本地 mock 绑定状态 |
| 不接真实支付/后端 | 通过 | 未修改相关逻辑 |

## 6. 未覆盖测试项

- 未在微信开发者工具中验证真实分享卡片路径。
- 未在真机验证从分享链接进入后的 query 参数。
- 未验证真实登录绑定、邀请关系唯一约束、禁止自邀、支付后邀请奖励幂等。

## 7. 需要 AI 测试官复核的事项

- 复核 BUG-M2-001 是否关闭。
- 复核邀请页“分享链接携带邀请人”表达是否满足产品预期。
- 复核已绑定后其他邀请失效的 mock 展示是否清晰。
- 后续进入真实后端阶段时，必须按 P0 补登录、邀请绑定、防自邀、防重复绑定、邀请奖励和支付回调幂等测试。
