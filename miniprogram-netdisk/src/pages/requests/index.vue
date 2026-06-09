<script setup lang="ts">
import { panFilters, requests } from "@/data/mock";

const publish = () => uni.navigateTo({ url: "/pages/requests/publish" });
</script>

<template>
  <view class="page">
    <view class="row between">
      <view class="section-title">求资源悬赏</view>
      <view class="btn-small" @click="publish">发布</view>
    </view>

    <view class="search section">搜索求资源需求</view>

    <scroll-view class="section" scroll-x>
      <view class="chip-row">
        <view v-for="(item, index) in panFilters" :key="item" class="chip" :class="{ 'chip-active': index === 0 }">
          {{ item }}
        </view>
      </view>
    </scroll-view>

    <view class="section">
      <view v-for="item in requests" :key="item.id" class="card request-card">
        <view class="row between">
          <view class="request-title">{{ item.title }}</view>
          <view class="points">{{ item.bounty }}分</view>
        </view>
        <view class="meta">分类{{ item.category }} · 期望{{ item.pans }}</view>
        <view class="desc">{{ item.description }}</view>
        <view class="row between footer-line">
          <view class="muted">{{ item.submissions }}人提交 · {{ item.deadline }}截止</view>
          <view class="btn-plain submit-btn">提交资源</view>
        </view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.btn-small {
  min-width: 108rpx;
  height: 60rpx;
  border-radius: 999rpx;
  background: $primary;
  color: #ffffff;
  font-size: 26rpx;
  line-height: 60rpx;
  text-align: center;
}

.desc {
  margin-top: 16rpx;
  color: $text-muted;
  font-size: 27rpx;
  line-height: 1.6;
}

.footer-line {
  margin-top: 20rpx;
}

.submit-btn {
  width: 150rpx;
  height: 64rpx;
  line-height: 64rpx;
  color: $primary-dark;
}
</style>
