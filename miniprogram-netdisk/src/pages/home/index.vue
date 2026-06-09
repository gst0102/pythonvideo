<script setup lang="ts">
import { categories, panFilters, requests, resources, userProfile } from "@/data/mock";

const go = (url: string) => {
  uni.navigateTo({ url });
};
</script>

<template>
  <view class="page">
    <view class="topbar row between">
      <view>
        <view class="app-name">互助资源库</view>
        <view class="muted subtitle">网盘资料互助工具</view>
      </view>
      <view class="point-pill" @click="uni.switchTab({ url: '/pages/earn/index' })">
        <text class="points">{{ userProfile.points }}</text>
        <text> 分</text>
      </view>
    </view>

    <view class="search section" @click="go('/pages/resources/list')">搜索资源、网盘、资料关键词</view>

    <scroll-view class="section" scroll-x>
      <view class="chip-row">
        <view v-for="(item, index) in panFilters" :key="item" class="chip" :class="{ 'chip-active': index === 0 }">
          {{ item }}
        </view>
      </view>
    </scroll-view>

    <view class="hero section">
      <view>
        <view class="hero-title">找资料，用积分解锁</view>
        <view class="hero-copy">签到、小游戏、上传和补链都能赚积分。找不到就发布悬赏。</view>
      </view>
      <view class="hero-actions">
        <view class="btn-plain" @click="go('/pages/requests/publish')">发布求资源</view>
        <view class="btn" @click="uni.switchTab({ url: '/pages/earn/index' })">赚积分</view>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <view class="section-title">分类入口</view>
      </view>
      <view class="grid">
        <view v-for="item in categories" :key="item" class="grid-item" @click="go('/pages/resources/list')">
          {{ item }}
        </view>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <view class="section-title">今日精选</view>
        <view class="muted" @click="go('/pages/resources/list')">查看全部</view>
      </view>
      <view v-for="item in resources" :key="item.id" class="card resource-card" @click="go(`/pages/resources/detail?id=${item.id}`)">
        <view class="row between">
          <view class="resource-title">{{ item.title }}</view>
          <view class="points">{{ item.points }}分</view>
        </view>
        <view class="row tag-line">
          <text class="tag">{{ item.pan }}</text>
          <text class="tag tag-warning">{{ item.level }}</text>
          <text class="tag">{{ item.category }}</text>
        </view>
        <view class="meta">已验证{{ item.verifiedAt }} · 获取{{ item.downloads }} · 收藏{{ item.favorites }}</view>
      </view>
    </view>

    <view class="section">
      <view class="section-head">
        <view class="section-title">求资源悬赏</view>
        <view class="muted" @click="uni.switchTab({ url: '/pages/requests/index' })">更多</view>
      </view>
      <view v-for="item in requests.slice(0, 2)" :key="item.id" class="card request-card">
        <view class="row between">
          <view class="request-title">{{ item.title }}</view>
          <view class="points">{{ item.bounty }}分</view>
        </view>
        <view class="meta">期望{{ item.pans }} · {{ item.submissions }}人提交 · {{ item.deadline }}截止</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.topbar {
  padding-top: 8rpx;
}

.app-name {
  font-size: 42rpx;
  font-weight: 800;
}

.subtitle {
  margin-top: 6rpx;
  font-size: 24rpx;
}

.point-pill {
  min-width: 132rpx;
  height: 64rpx;
  border-radius: 999rpx;
  background: #ffffff;
  line-height: 64rpx;
  text-align: center;
  font-size: 26rpx;
}

.hero {
  border-radius: 18rpx;
  background: linear-gradient(135deg, #00a886, #37c6aa);
  color: #ffffff;
  padding: 30rpx;
}

.hero-title {
  font-size: 42rpx;
  font-weight: 800;
}

.hero-copy {
  margin-top: 12rpx;
  color: rgba(255, 255, 255, 0.88);
  font-size: 27rpx;
  line-height: 1.55;
}

.hero-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18rpx;
  margin-top: 28rpx;
}

.hero .btn {
  background: #ffffff;
  color: $primary-dark;
}

.hero .btn-plain {
  border-color: rgba(255, 255, 255, 0.68);
  background: rgba(255, 255, 255, 0.16);
  color: #ffffff;
}

.tag-line {
  gap: 10rpx;
  margin-top: 16rpx;
  flex-wrap: wrap;
}
</style>
