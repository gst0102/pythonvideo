<script setup lang="ts">
import { categories, panFilters } from "@/data/mock";

const submit = () => {
  uni.showToast({ title: "已提交 mock 审核", icon: "none" });
};
</script>

<template>
  <view class="page">
    <view class="card">
      <view class="form-field">
        <view class="label">资源标题</view>
        <input class="input" placeholder="请输入资源标题" />
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
        <view class="label">网盘类型</view>
        <scroll-view scroll-x>
          <view class="chip-row">
            <view v-for="(item, index) in panFilters.slice(1)" :key="item" class="chip" :class="{ 'chip-active': index === 0 }">
              {{ item }}
            </view>
          </view>
        </scroll-view>
      </view>
      <view class="form-field">
        <view class="label">资源简介</view>
        <textarea class="textarea" placeholder="请说明内容、目录、适用人群" />
      </view>
      <view class="two-col">
        <view class="form-field">
          <view class="label">文件数量</view>
          <input class="input" placeholder="约 30 个" />
        </view>
        <view class="form-field">
          <view class="label">文件大小</view>
          <input class="input" placeholder="约 2GB" />
        </view>
      </view>
      <view class="form-field">
        <view class="label">网盘链接</view>
        <input class="input" placeholder="请输入链接" />
      </view>
      <view class="two-col">
        <view class="form-field">
          <view class="label">提取码</view>
          <input class="input" placeholder="选填" />
        </view>
        <view class="form-field">
          <view class="label">解压码</view>
          <input class="input" placeholder="选填" />
        </view>
      </view>
    </view>

    <view class="notice section">
      新用户每日最多上传 3 条。审核通过后获得 5 积分，违规内容会被下架并影响信用分。
    </view>

    <view class="btn section" @click="submit">提交审核</view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.two-col {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16rpx;
}

.notice {
  border-radius: 14rpx;
  background: $accent-bg;
  padding: 20rpx;
  color: #8b610f;
  font-size: 25rpx;
  line-height: 1.6;
}
</style>
