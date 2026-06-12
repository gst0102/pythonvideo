<script setup lang="ts">
import { ref } from "vue";
import { onLoad, onReachBottom } from "@dcloudio/uni-app";
import { categories, panFilters } from "@/data/mock";
import { getNetdiskResources, type NetdiskResource } from "@/utils/api";

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

const goDetail = (id: string) => uni.navigateTo({ url: `/pages/resources/detail?id=${id}` });
const levelText = (level?: string) => ({ normal: "普通", featured: "精选", official: "官方" }[level || ""] || level || "-");

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
            </view>
          </view>
          <view class="cost">
            <view class="points">{{ item.cost_points }}</view>
            <view class="muted">积分</view>
          </view>
        </view>
        <view class="meta">已验证{{ item.verified_at }} · 获取{{ item.downloads }} · 收藏{{ item.favorites }}</view>
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

.cost {
  width: 96rpx;
  text-align: right;
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
