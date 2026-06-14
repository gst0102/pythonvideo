<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { categories, requests } from "@/data/mock";
import {
  ensureWechatLogin,
  favoriteNetdiskResource,
  getNetdiskFavorites,
  getNetdiskResources,
  getUserProfile,
  hasLoginToken,
  type NetdiskResource
} from "@/utils/api";

const resources = ref<NetdiskResource[]>([]);
const loading = ref(false);
const userPoints = ref(0);
const userCredit = ref(100);
const userAvatar = ref("");
const userNickname = ref("微信用户");
const loggedIn = ref(false);
const favoriteIds = ref<string[]>([]);
const userInitial = computed(() => (userNickname.value || "我").slice(0, 1));

const go = (url: string) => {
  uni.navigateTo({ url });
};

const levelText = (level?: string) => ({ normal: "普通", featured: "精选", official: "官方" }[level || ""] || level || "-");
const uploaderInitial = (item: NetdiskResource) => (item.uploader_nickname || "官").slice(0, 1);
const creditText = (score?: number) => `信用${Number(score || 100)}`;

const loadProfile = async () => {
  if (!hasLoginToken()) {
    loggedIn.value = false;
    userPoints.value = 0;
    userCredit.value = 100;
    userAvatar.value = "";
    userNickname.value = "微信用户";
    favoriteIds.value = [];
    return;
  }
  try {
    const profile = await getUserProfile();
    loggedIn.value = true;
    userPoints.value = profile.account?.consumable_points || 0;
    userCredit.value = profile.credit_score || 100;
    userAvatar.value = profile.avatar || "";
    userNickname.value = profile.nickname || "微信用户";
  } catch {
    loggedIn.value = false;
  }
};

const loadFeatured = async () => {
  loading.value = true;
  try {
    const data = await getNetdiskResources({ sort: "latest", page: 1, page_size: 3 });
    resources.value = data.resources || [];
    if (hasLoginToken()) {
      const favorites = await getNetdiskFavorites();
      favoriteIds.value = favorites.favorites.map((item) => item.resource.id);
    }
  } catch {
    resources.value = [];
  } finally {
    loading.value = false;
  }
};

onShow(() => {
  loadProfile();
  loadFeatured();
});

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
</script>

<template>
  <view class="page">
    <view class="topbar row between">
      <view>
        <view class="app-name">互助资源库</view>
        <view class="muted subtitle">网盘资料互助工具</view>
      </view>
      <view class="user-pill" @click="uni.switchTab({ url: '/pages/mine/index' })">
        <image v-if="userAvatar" class="user-avatar" :src="userAvatar" mode="aspectFill" />
        <view v-else class="user-avatar fallback">{{ userInitial }}</view>
        <view>
          <view class="points">{{ loggedIn ? userPoints : "登录" }}</view>
          <view class="pill-sub">{{ loggedIn ? `信用${userCredit}` : "查看积分" }}</view>
        </view>
      </view>
    </view>

    <view class="search section" @click="go('/pages/resources/list')">搜索资源、网盘、资料关键词</view>

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
      <view v-if="loading" class="muted">正在加载...</view>
      <view v-for="item in resources" :key="item.id" class="card resource-card" @click="go(`/pages/resources/detail?id=${item.id}`)">
        <view class="row between">
          <view class="resource-title">{{ item.title }}</view>
          <view class="points">{{ item.cost_points }}分</view>
        </view>
        <view class="row tag-line">
          <text class="tag">{{ item.pan }}</text>
          <text class="tag tag-warning">{{ levelText(item.level) }}</text>
          <text class="tag">{{ item.category }}</text>
          <text class="tag tag-credit">{{ creditText(item.uploader_credit_score) }}</text>
        </view>
        <view class="uploader-row">
          <image v-if="item.uploader_avatar" class="uploader-avatar" :src="item.uploader_avatar" mode="aspectFill" />
          <view v-else class="uploader-avatar fallback">{{ uploaderInitial(item) }}</view>
          <text>{{ item.uploader_nickname || "平台精选" }}</text>
          <text class="muted">上传者</text>
        </view>
        <view class="resource-foot">
          <view class="meta">已验证{{ item.verified_at }} · 获取{{ item.downloads }} · 收藏{{ item.favorites }}</view>
          <view class="favorite-btn" :class="{ active: isFavorited(item.id) }" @click.stop="quickFavorite(item)">
            {{ isFavorited(item.id) ? "已收藏" : "收藏" }}
          </view>
        </view>
      </view>
      <view v-if="!loading && resources.length === 0" class="muted">暂无精选资源</view>
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

.user-pill {
  display: flex;
  align-items: center;
  gap: 12rpx;
  min-width: 172rpx;
  min-height: 72rpx;
  border-radius: 999rpx;
  background: #ffffff;
  padding: 8rpx 16rpx 8rpx 10rpx;
}

.user-avatar,
.uploader-avatar {
  flex: 0 0 auto;
  border-radius: 50%;
  background: $tag-bg;
  color: $primary-dark;
  font-weight: 800;
  text-align: center;
}

.user-avatar {
  width: 52rpx;
  height: 52rpx;
  font-size: 24rpx;
  line-height: 52rpx;
}

.pill-sub {
  margin-top: 2rpx;
  color: $text-muted;
  font-size: 20rpx;
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

.tag-credit {
  background: #eef8f4;
  color: $primary-dark;
}

.uploader-row {
  display: flex;
  align-items: center;
  gap: 10rpx;
  margin-top: 14rpx;
  color: $text-main;
  font-size: 24rpx;
}

.uploader-avatar {
  width: 36rpx;
  height: 36rpx;
  font-size: 19rpx;
  line-height: 36rpx;
}

.resource-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 12rpx;
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
</style>
