<script setup lang="ts">
import { categories, panFilters, userProfile } from "@/data/mock";

const submit = () => {
  uni.showToast({ title: "已生成 mock 发布单", icon: "none" });
};
</script>

<template>
  <view class="page">
    <view class="card">
      <view class="form-field">
        <view class="label">求资源标题</view>
        <input class="input" placeholder="请输入你想要的资源" />
      </view>
      <view class="form-field">
        <view class="label">资源分类</view>
        <scroll-view scroll-x>
          <view class="chip-row">
            <view v-for="(item, index) in categories" :key="item" class="chip" :class="{ 'chip-active': index === 0 }">
              {{ item }}
            </view>
          </view>
        </scroll-view>
      </view>
      <view class="form-field">
        <view class="label">期望网盘</view>
        <scroll-view scroll-x>
          <view class="chip-row">
            <view v-for="(item, index) in panFilters.slice(1)" :key="item" class="chip" :class="{ 'chip-active': index < 2 }">
              {{ item }}
            </view>
          </view>
        </scroll-view>
      </view>
      <view class="form-field">
        <view class="label">需求说明</view>
        <textarea class="textarea" placeholder="请描述版本、格式、用途等" />
      </view>
      <view class="form-field">
        <view class="label">悬赏积分</view>
        <input class="input" type="number" placeholder="5 - 50" />
      </view>
      <view class="form-field">
        <view class="label">截止时间</view>
        <view class="chip-row">
          <view class="chip chip-active">24小时</view>
          <view class="chip">3天</view>
          <view class="chip">7天</view>
        </view>
      </view>
    </view>

    <view class="card section">
      <view class="row between">
        <text class="muted">当前积分</text>
        <text class="points">{{ userProfile.points }}分</text>
      </view>
      <view class="row between freeze-row">
        <text class="muted">发布后冻结</text>
        <text>20分</text>
      </view>
    </view>

    <view class="btn section" @click="submit">确认发布</view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.freeze-row {
  margin-top: 18rpx;
}
</style>
