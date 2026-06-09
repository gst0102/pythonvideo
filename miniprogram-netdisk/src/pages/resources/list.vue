<script setup lang="ts">
import { categories, panFilters, resources } from "@/data/mock";

const sorts = ["最新", "热门", "精选", "低积分"];
const goDetail = (id: string) => uni.navigateTo({ url: `/pages/resources/detail?id=${id}` });
</script>

<template>
  <view class="page">
    <view class="search">搜索关键词</view>

    <view class="filter-block section">
      <scroll-view scroll-x>
        <view class="chip-row">
          <view class="chip chip-active">全部分类</view>
          <view v-for="item in categories" :key="item" class="chip">{{ item }}</view>
        </view>
      </scroll-view>
      <scroll-view class="filter-row" scroll-x>
        <view class="chip-row">
          <view v-for="(item, index) in panFilters" :key="item" class="chip" :class="{ 'chip-active': index === 0 }">
            {{ item }}
          </view>
        </view>
      </scroll-view>
      <view class="sorts">
        <view v-for="(item, index) in sorts" :key="item" class="sort" :class="{ active: index === 0 }">{{ item }}</view>
      </view>
    </view>

    <view class="section">
      <view v-for="item in resources" :key="item.id" class="card resource-card" @click="goDetail(item.id)">
        <view class="row between">
          <view class="title-wrap">
            <view class="resource-title">{{ item.title }}</view>
            <view class="row tag-line">
              <text class="tag tag-warning">{{ item.level }}</text>
              <text class="tag">{{ item.pan }}</text>
              <text class="tag">{{ item.category }}</text>
            </view>
          </view>
          <view class="cost">
            <view class="points">{{ item.points }}</view>
            <view class="muted">积分</view>
          </view>
        </view>
        <view class="meta">已验证{{ item.verifiedAt }} · 获取{{ item.downloads }} · 收藏{{ item.favorites }}</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.filter-block {
  display: flex;
  flex-direction: column;
  gap: 16rpx;
}

.filter-row {
  width: 100%;
}

.sorts {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
}

.sort {
  height: 64rpx;
  border-radius: 12rpx;
  background: #ffffff;
  color: $text-muted;
  font-size: 26rpx;
  line-height: 64rpx;
  text-align: center;
}

.sort.active {
  background: $tag-bg;
  color: $primary-dark;
  font-weight: 700;
}

.title-wrap {
  flex: 1;
  min-width: 0;
  padding-right: 18rpx;
}

.tag-line {
  gap: 10rpx;
  margin-top: 16rpx;
  flex-wrap: wrap;
}

.cost {
  width: 96rpx;
  text-align: right;
}
</style>
