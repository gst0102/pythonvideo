<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ensureWechatLogin, getNetdiskFavorites, unfavoriteNetdiskResource, type FavoriteListResponse } from "@/utils/api";

type FavoriteItem = FavoriteListResponse["favorites"][number];

const loading = ref(false);
const errorText = ref("");
const keyword = ref("");
const favorites = ref<FavoriteItem[]>([]);

const filteredFavorites = computed(() => {
  const word = keyword.value.trim();
  const list = [...favorites.value].sort((a, b) => (b.favorite_at || "").localeCompare(a.favorite_at || ""));
  if (!word) return list;
  return list.filter((item) => item.resource.title.includes(word) || item.resource.category.includes(word) || item.resource.pan.includes(word));
});

const levelText = (level?: string) => ({ normal: "普通", featured: "精选", official: "官方" }[level || ""] || level || "-");
const formatTime = (value: string) => (value ? value.replace("T", " ").slice(0, 16) : "");
const goDetail = (id: string) => uni.navigateTo({ url: `/pages/resources/detail?id=${id}` });

const loadFavorites = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    const data = await getNetdiskFavorites();
    favorites.value = data.favorites || [];
  } catch (error: any) {
    errorText.value = error?.message || "收藏列表加载失败";
  } finally {
    loading.value = false;
  }
};

const removeFavorite = async (item: FavoriteItem) => {
  try {
    await unfavoriteNetdiskResource(item.resource.id);
    favorites.value = favorites.value.filter((favorite) => favorite.resource.id !== item.resource.id);
    uni.showToast({ title: "已取消收藏", icon: "success" });
  } catch (error: any) {
    uni.showToast({ title: error?.message || "取消收藏失败", icon: "none" });
  }
};

onShow(loadFavorites);
</script>

<template>
  <view class="page">
    <view class="section-title">我的收藏</view>
    <view class="muted subtitle">按收藏时间展示，可搜索并取消收藏。</view>

    <view class="search-box section">
      <input v-model="keyword" class="search-input" placeholder="搜索收藏资源" confirm-type="search" />
    </view>

    <view v-if="loading" class="empty">正在加载...</view>
    <view v-else-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadFavorites">重试</view>
    </view>

    <view v-else>
      <view v-for="item in filteredFavorites" :key="item.resource.id" class="card favorite-card">
        <view class="row between" @click="goDetail(item.resource.id)">
          <view class="title-wrap">
            <view class="resource-title">{{ item.resource.title }}</view>
            <view class="row tag-line">
              <text class="tag tag-warning">{{ levelText(item.resource.level) }}</text>
              <text class="tag">{{ item.resource.pan }}</text>
              <text class="tag">{{ item.resource.category }}</text>
            </view>
          </view>
          <view class="cost">
            <view class="points">{{ item.resource.cost_points }}</view>
            <view class="muted">积分</view>
          </view>
        </view>
        <view class="meta">收藏于 {{ formatTime(item.favorite_at) }} · 获取{{ item.resource.downloads }} · 收藏{{ item.resource.favorites }}</view>
        <view class="btn-plain unfavorite" @click="removeFavorite(item)">取消收藏</view>
      </view>
      <view v-if="filteredFavorites.length === 0" class="empty">{{ keyword ? "没有匹配的收藏" : "暂无收藏资源" }}</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.subtitle {
  margin-top: 8rpx;
  font-size: 25rpx;
}

.search-input {
  box-sizing: border-box;
  width: 100%;
  height: 82rpx;
  border: 1rpx solid $border;
  border-radius: 16rpx;
  background: #ffffff;
  padding: 0 22rpx;
  font-size: 28rpx;
}

.favorite-card {
  margin-top: 20rpx;
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

.unfavorite {
  margin-top: 18rpx;
}

.empty {
  margin-top: 160rpx;
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
