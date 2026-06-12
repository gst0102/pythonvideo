<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import {
  ensureWechatLogin,
  getMyNetdiskRepairs,
  getMyNetdiskUploads,
  getNetdiskFavorites,
  getUserProfile
} from "@/utils/api";

const loading = ref(false);
const errorText = ref("");
const nickname = ref("微信用户");
const avatar = ref("");
const consumablePoints = ref(0);
const frozenPoints = ref(0);
const favoriteCount = ref(0);
const uploadCount = ref(0);
const repairCount = ref(0);
const reportCount = ref(0);

const initial = computed(() => (nickname.value || "资").slice(0, 1));

const menu = [
  { title: "我的消息", url: "/pages/messages/index" },
  { title: "我的投诉记录", url: "/pages/reports/mine" },
  { title: "我的上传" },
  { title: "我的收藏" },
  { title: "积分明细" },
  { title: "规则说明" },
  { title: "联系客服" }
];

const loadMine = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    const [profile, favorites, uploads, repairs] = await Promise.all([
      getUserProfile(),
      getNetdiskFavorites(),
      getMyNetdiskUploads(),
      getMyNetdiskRepairs()
    ]);
    nickname.value = profile.nickname || "微信用户";
    avatar.value = profile.avatar || "";
    consumablePoints.value = profile.account?.consumable_points || 0;
    frozenPoints.value = profile.account?.frozen_points || 0;
    favoriteCount.value = favorites.favorites.length;
    uploadCount.value = uploads.uploads.length;
    repairCount.value = repairs.repairs.filter((item) => item.mode === "repair").length;
    reportCount.value = repairs.repairs.filter((item) => item.mode === "report").length;
  } catch (error: any) {
    errorText.value = error?.message || "我的数据加载失败";
  } finally {
    loading.value = false;
  }
};

const openMenu = (item: { title: string; url?: string }) => {
  if (item.url) {
    uni.navigateTo({ url: item.url });
    return;
  }
  uni.showToast({ title: "功能整理中", icon: "none" });
};

onShow(loadMine);
</script>

<template>
  <view class="page">
    <view class="profile">
      <image v-if="avatar" class="avatar-img" :src="avatar" mode="aspectFill" />
      <view v-else class="avatar">{{ initial }}</view>
      <view>
        <view class="nickname">{{ nickname }}</view>
        <view class="muted">可用 {{ consumablePoints }} 分 · 冻结 {{ frozenPoints }} 分</view>
      </view>
    </view>

    <view v-if="errorText" class="error-box">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadMine">重试</view>
    </view>

    <view class="stats">
      <view>
        <view class="points stat-number">{{ consumablePoints }}</view>
        <view class="muted">可用积分</view>
      </view>
      <view>
        <view class="stat-number">{{ frozenPoints }}</view>
        <view class="muted">冻结积分</view>
      </view>
      <view>
        <view class="stat-number">{{ favoriteCount }}</view>
        <view class="muted">收藏</view>
      </view>
      <view>
        <view class="stat-number">{{ uploadCount }}</view>
        <view class="muted">上传</view>
      </view>
    </view>

    <view class="stats compact">
      <view>
        <view class="stat-number">{{ repairCount }}</view>
        <view class="muted">补链</view>
      </view>
      <view>
        <view class="stat-number">{{ reportCount }}</view>
        <view class="muted">投诉</view>
      </view>
      <view>
        <view class="stat-number">{{ loading ? "..." : repairCount + reportCount }}</view>
        <view class="muted">补链/投诉</view>
      </view>
    </view>

    <view class="action-row section">
      <view class="btn">充值积分</view>
      <view class="btn btn-secondary" @click="uni.switchTab({ url: '/pages/earn/index' })">赚积分</view>
    </view>

    <view class="card section menu">
      <view v-for="item in menu" :key="item.title" class="menu-item" @click="openMenu(item)">
        <text>{{ item.title }}</text>
        <text class="muted">›</text>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.profile {
  display: flex;
  align-items: center;
  gap: 20rpx;
  border-radius: 18rpx;
  background: #ffffff;
  padding: 28rpx;
}

.avatar,
.avatar-img {
  width: 104rpx;
  height: 104rpx;
  border-radius: 52rpx;
}

.avatar {
  background: $tag-bg;
  color: $primary-dark;
  font-size: 42rpx;
  font-weight: 800;
  line-height: 104rpx;
  text-align: center;
}

.nickname {
  margin-bottom: 10rpx;
  font-size: 34rpx;
  font-weight: 800;
}

.stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin-top: 20rpx;
  border-radius: 18rpx;
  background: #ffffff;
  padding: 24rpx 12rpx;
  text-align: center;
}

.stats.compact {
  grid-template-columns: repeat(3, 1fr);
}

.stat-number {
  margin-bottom: 8rpx;
  font-size: 34rpx;
  font-weight: 800;
}

.action-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.menu {
  padding: 4rpx 24rpx;
}

.menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1rpx solid $border;
  padding: 28rpx 0;
  font-size: 29rpx;
}

.menu-item:last-child {
  border-bottom: 0;
}

.error-box {
  margin-top: 20rpx;
  border-radius: 16rpx;
  background: #fff4e2;
  padding: 20rpx;
  color: #8b610f;
  font-size: 26rpx;
  line-height: 1.6;
  text-align: center;
}

.retry {
  width: 220rpx;
  margin: 18rpx auto 0;
}
</style>
