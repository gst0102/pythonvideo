<script setup lang="ts">
import { userProfile } from "@/data/mock";

const menu = [
  { title: "我的消息", url: "/pages/messages/index" },
  { title: "我的上传" },
  { title: "我的获取" },
  { title: "我的求资源" },
  { title: "我的收藏" },
  { title: "积分明细" },
  { title: "规则说明" },
  { title: "联系客服" }
];

const openMenu = (item: { title: string; url?: string }) => {
  if (item.url) {
    uni.navigateTo({ url: item.url });
    return;
  }
  uni.showToast({ title: "功能整理中", icon: "none" });
};
</script>

<template>
  <view class="page">
    <view class="profile">
      <view class="avatar">资</view>
      <view>
        <view class="nickname">{{ userProfile.nickname }}</view>
        <view class="muted">信用分 {{ userProfile.credit }}</view>
      </view>
    </view>

    <view class="stats">
      <view>
        <view class="points stat-number">{{ userProfile.points }}</view>
        <view class="muted">积分</view>
      </view>
      <view>
        <view class="stat-number">{{ userProfile.uploads }}</view>
        <view class="muted">上传</view>
      </view>
      <view>
        <view class="stat-number">{{ userProfile.accesses }}</view>
        <view class="muted">获取</view>
      </view>
      <view>
        <view class="stat-number">{{ userProfile.requests }}</view>
        <view class="muted">求资源</view>
      </view>
    </view>

    <view class="action-row section">
      <view class="btn">充值积分</view>
      <view class="btn btn-secondary">赚积分</view>
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

.avatar {
  width: 104rpx;
  height: 104rpx;
  border-radius: 52rpx;
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
</style>
