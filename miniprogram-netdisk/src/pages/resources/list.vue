<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onReachBottom } from "@dcloudio/uni-app";
import { categories, panFilters } from "@/data/mock";
import {
  ensureWechatLogin,
  favoriteNetdiskResource,
  getNetdiskFavorites,
  getNetdiskResources,
  hasLoginToken,
  type NetdiskResource
} from "@/utils/api";

const sorts = [
  { label: "最新", value: "latest" },
  { label: "热门", value: "hot" },
  { label: "精选", value: "featured" },
  { label: "低积分", value: "low_cost" }
];

const resources = ref<NetdiskResource[]>([]);
const loading = ref(false);
const errorText = ref("");
const hasMore = ref(false);
const page = ref(1);
const keyword = ref("");
const activeCategory = ref("全部分类");
const activePan = ref("全部");
const activeSort = ref("latest");
const favoriteIds = ref<string[]>([]);

const goDetail = (id: string) => uni.navigateTo({ url: `/pages/resources/detail?id=${id}` });
const levelText = (level?: string) => ({ normal: "普通", featured: "精选", official: "官方" }[level || ""] || level || "-");
const creditText = (level?: string) => ({ excellent: "优质上传者", good: "高信用", normal: "", watch: "待观察" }[level || ""] || "");
const creditScoreText = (score?: number) => `上传信用${Number(score || 100)}分`;
const uploaderInitial = (item: NetdiskResource) => (item.uploader_nickname || "官").slice(0, 1);
const validText = (days?: number) => {
  const value = Number(days || 0);
  if (value >= 30) return "30天有效";
  if (value >= 7) return "7天有效";
  return "";
};

const loadResources = async (reset = false) => {
  if (loading.value) return;
  loading.value = true;
  errorText.value = "";
  try {
    const nextPage = reset ? 1 : page.value;
    const data = await getNetdiskResources({
      keyword: keyword.value.trim() || undefined,
      category: activeCategory.value === "全部分类" ? undefined : activeCategory.value,
      pan: activePan.value === "全部" ? undefined : activePan.value,
      sort: activeSort.value,
      page: nextPage,
      page_size: 10
    });
    resources.value = reset ? data.resources : [...resources.value, ...data.resources];
    hasMore.value = data.has_more;
    page.value = data.page + 1;
    if (hasLoginToken()) {
      const favorites = await getNetdiskFavorites();
      favoriteIds.value = favorites.favorites.map((item) => item.resource.id);
    }
  } catch (error: any) {
    errorText.value = error?.message || "资源列表加载失败";
  } finally {
    loading.value = false;
  }
};

const chooseCategory = (item: string) => {
  activeCategory.value = item;
  loadResources(true);
};

const choosePan = (item: string) => {
  activePan.value = item;
  loadResources(true);
};

const chooseSort = (item: string) => {
  activeSort.value = item;
  loadResources(true);
};

const search = () => loadResources(true);
const isFavorited = (id: string) => favoriteIds.value.includes(id);

const quickFavorite = async (item: NetdiskResource) => {
  try {
    await ensureWechatLogin();
    const data = await favoriteNetdiskResource(item.id);
    if (!favoriteIds.value.includes(item.id)) favoriteIds.value = [...favoriteIds.value, item.id];
    item.favorites = data.resource.favorites;
    uni.showToast({ title: "已加入我的收藏", icon: "success" });
  } catch (error: any) {
    uni.showToast({ title: error?.message || "收藏失败", icon: "none" });
  }
};

onLoad(() => loadResources(true));
onReachBottom(() => {
  if (hasMore.value) loadResources(false);
});
</script>

<template>
  <view class="page">
    <view class="search-box">
      <input v-model="keyword" class="search-input" placeholder="搜索关键词" confirm-type="search" @confirm="search" />
      <view class="search-btn" @click="search">搜索</view>
    </view>

    <view class="filter-block section">
      <scroll-view scroll-x>
        <view class="chip-row">
          <view class="chip" :class="{ 'chip-active': activeCategory === '全部分类' }" @click="chooseCategory('全部分类')">全部分类</view>
          <view
            v-for="item in categories"
            :key="item"
            class="chip"
            :class="{ 'chip-active': activeCategory === item }"
            @click="chooseCategory(item)"
          >
            {{ item }}
          </view>
        </view>
      </scroll-view>
      <scroll-view class="filter-row" scroll-x>
        <view class="chip-row">
          <view
            v-for="item in panFilters"
            :key="item"
            class="chip"
            :class="{ 'chip-active': activePan === item }"
            @click="choosePan(item)"
          >
            {{ item }}
          </view>
        </view>
      </scroll-view>
      <view class="sorts">
        <view
          v-for="item in sorts"
          :key="item.value"
          class="sort"
          :class="{ active: activeSort === item.value }"
          @click="chooseSort(item.value)"
        >
          {{ item.label }}
        </view>
      </view>
    </view>

    <view v-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadResources(true)">重试</view>
    </view>

    <view v-else class="section">
      <view v-for="item in resources" :key="item.id" class="card resource-card" @click="goDetail(item.id)">
        <view class="row between">
          <view class="title-wrap">
            <view class="resource-title">{{ item.title }}</view>
            <view class="row tag-line">
              <text class="tag tag-warning">{{ levelText(item.level) }}</text>
              <text class="tag">{{ item.pan }}</text>
              <text class="tag">{{ item.category }}</text>
              <text class="tag tag-credit">{{ creditScoreText(item.uploader_credit_score) }}</text>
              <text v-if="creditText(item.uploader_credit_level)" class="tag">{{ creditText(item.uploader_credit_level) }}</text>
              <text v-if="validText(item.valid_days)" class="tag">{{ validText(item.valid_days) }}</text>
            </view>
            <view class="uploader-row">
              <image v-if="item.uploader_avatar" class="uploader-avatar" :src="item.uploader_avatar" mode="aspectFill" />
              <view v-else class="uploader-avatar fallback">{{ uploaderInitial(item) }}</view>
              <text>{{ item.uploader_nickname || "平台精选" }}</text>
            </view>
          </view>
          <view class="cost">
            <view class="points">{{ item.cost_points }}</view>
            <view class="muted">积分</view>
          </view>
        </view>
        <view class="resource-foot">
          <view class="meta">已验证{{ item.verified_at }} · 获取{{ item.downloads }} · 收藏{{ item.favorites }} · 质量{{ item.quality_score || 0 }}</view>
          <view class="favorite-btn" :class="{ active: isFavorited(item.id) }" @click.stop="quickFavorite(item)">
            {{ isFavorited(item.id) ? "已收藏" : "收藏" }}
          </view>
        </view>
      </view>
      <view v-if="!loading && resources.length === 0" class="empty">暂无符合条件的资源</view>
      <view v-if="loading" class="load-tip">加载中...</view>
      <view v-else-if="resources.length > 0 && !hasMore" class="load-tip">没有更多了</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.search-box {
  display: grid;
  grid-template-columns: 1fr 128rpx;
  gap: 14rpx;
}

.search-input {
  height: 82rpx;
  border: 1rpx solid $border;
  border-radius: 16rpx;
  background: #ffffff;
  padding: 0 22rpx;
  font-size: 28rpx;
}

.search-btn {
  height: 82rpx;
  border-radius: 16rpx;
  background: $primary;
  color: #ffffff;
  font-size: 28rpx;
  font-weight: 700;
  line-height: 82rpx;
  text-align: center;
}

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

.tag-credit {
  background: #eef8f4;
  color: $primary-dark;
}

.uploader-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 14rpx;
  color: $text-muted;
  font-size: 24rpx;
}

.uploader-avatar {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  background: $tag-bg;
  color: $primary-dark;
  font-size: 19rpx;
  font-weight: 800;
  line-height: 36rpx;
  text-align: center;
}

.cost {
  width: 96rpx;
  text-align: right;
}

.resource-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 14rpx;
}

.resource-foot .meta {
  flex: 1;
  min-width: 0;
}

.favorite-btn {
  flex: 0 0 auto;
  min-width: 112rpx;
  height: 52rpx;
  border: 1rpx solid $border;
  border-radius: 12rpx;
  background: #ffffff;
  color: $primary-dark;
  font-size: 24rpx;
  font-weight: 700;
  line-height: 52rpx;
  text-align: center;
}

.favorite-btn.active {
  background: $tag-bg;
}

.empty,
.load-tip {
  padding: 42rpx 0;
  color: $text-muted;
  font-size: 27rpx;
  text-align: center;
}

.retry {
  width: 220rpx;
  margin: 28rpx auto 0;
}
</style>
