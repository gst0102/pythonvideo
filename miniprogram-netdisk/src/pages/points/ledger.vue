<script setup lang="ts">
import { ref } from "vue";
import { onReachBottom, onShow } from "@dcloudio/uni-app";
import { ensureWechatLogin, getPointsLedger, type PointsLedgerItem, type UserAccount } from "@/utils/api";

const loading = ref(false);
const errorText = ref("");
const hasMore = ref(false);
const page = ref(1);
const items = ref<PointsLedgerItem[]>([]);
const account = ref<UserAccount>({
  total_points: 0,
  withdrawable_points: 0,
  frozen_points: 0,
  consumable_points: 0
});

const typeText = (type: string) => {
  const map: Record<string, string> = {
    signup_seed_points: "新人积分",
    dev_seed: "测试积分",
    resource_unlock: "获取资源",
    resource_creator_share: "资源分成",
    platform_recovery: "平台回收",
    upload_reward_approved_part1: "上传审核奖励",
    upload_reward_valid_7d: "7天有效奖励",
    upload_reward_frozen: "上传待验证",
    upload_reward_release: "上传奖励释放",
    upload_reward_rejected: "上传奖励扣回",
    upload_reward_invalid: "失效扣回",
    repair_reward_frozen: "补链待验证",
    repair_reward_release: "补链奖励",
    repair_reward_rejected: "补链扣回",
    repair_reward_invalid: "补链失效扣回",
    invalid_penalty: "失效处罚",
    credit_adjustment: "信用/贡献调整",
    netdisk_first_resource_invite_reward: "邀请使用奖励",
    withdraw_lock: "提现锁定",
    withdraw_success: "提现成功",
    withdraw_reject_return: "提现退回",
    game_settlement: "游戏结算",
    game_adjustment: "游戏补正"
  };
  return map[type] || type;
};

const sourceText = (source: string) => ({ netdisk: "资源库", netdisk_quality: "质量", signup: "注册", invite: "邀请", game: "游戏", withdraw: "提现", dev: "测试" }[source] || source);
const formatTime = (value: string) => (value ? value.replace("T", " ").slice(0, 16) : "");
const deltaText = (value: number) => (value > 0 ? `+${value}` : String(value));

const loadLedger = async (reset = false) => {
  if (loading.value) return;
  loading.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    const nextPage = reset ? 1 : page.value;
    const data = await getPointsLedger({ page: nextPage, page_size: 20 });
    account.value = data.account;
    items.value = reset ? data.items : [...items.value, ...data.items];
    hasMore.value = data.has_more;
    page.value = data.page + 1;
  } catch (error: any) {
    errorText.value = error?.message || "积分明细加载失败";
  } finally {
    loading.value = false;
  }
};

onShow(() => loadLedger(true));
onReachBottom(() => {
  if (hasMore.value) loadLedger(false);
});
</script>

<template>
  <view class="page">
    <view class="summary card">
      <view>
        <view class="section-title">积分明细</view>
        <view class="muted">收入、消耗、处罚和平台回收记录</view>
      </view>
      <view class="balance">
        <view class="points">{{ account.consumable_points }}</view>
        <view class="muted">可用积分</view>
      </view>
    </view>

    <view v-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadLedger(true)">重试</view>
    </view>

    <view v-else class="section">
      <view v-for="item in items" :key="item.id" class="card ledger-card">
        <view class="row between">
          <view>
            <view class="ledger-title">{{ typeText(item.change_type) }}</view>
            <view class="muted meta">{{ sourceText(item.source) }} · {{ formatTime(item.created_at) }}</view>
          </view>
          <view class="delta" :class="{ income: item.points_delta > 0, outcome: item.points_delta < 0 }">
            {{ deltaText(item.points_delta) }}
          </view>
        </view>
        <view v-if="item.remark" class="remark">{{ item.remark }}</view>
        <view class="muted after">可用余额 {{ item.balance_consumable_after }} 分</view>
      </view>
      <view v-if="!loading && items.length === 0" class="empty">暂无积分明细</view>
      <view v-if="loading" class="load-tip">加载中...</view>
      <view v-else-if="items.length > 0 && !hasMore" class="load-tip">没有更多了</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.balance {
  min-width: 150rpx;
  text-align: right;
}

.ledger-card {
  margin-bottom: 18rpx;
}

.ledger-title {
  font-size: 30rpx;
  font-weight: 800;
}

.delta {
  min-width: 100rpx;
  text-align: right;
  font-size: 34rpx;
  font-weight: 900;
}

.income {
  color: $primary-dark;
}

.outcome {
  color: $danger;
}

.remark {
  margin-top: 14rpx;
  color: $text-main;
  font-size: 26rpx;
  line-height: 1.6;
}

.after {
  margin-top: 12rpx;
  font-size: 24rpx;
}

.empty,
.load-tip {
  margin-top: 120rpx;
  color: $text-muted;
  font-size: 28rpx;
  line-height: 1.8;
  text-align: center;
}

.retry {
  width: 220rpx;
  margin: 28rpx auto 0;
}
</style>
