<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import {
  ensureWechatLogin,
  favoriteNetdiskResource,
  getNetdiskFavorites,
  getNetdiskResourceAccess,
  getNetdiskResourceDetail,
  reportNetdiskResource,
  unfavoriteNetdiskResource,
  unlockNetdiskResource,
  type NetdiskResource,
  type NetdiskResourceAccess
} from "@/utils/api";

const selectedId = ref("r1");
const loading = ref(false);
const errorText = ref("");
const resource = ref<NetdiskResource | null>(null);
const access = ref<NetdiskResourceAccess>({
  unlocked: false,
  ledger_id: "",
  points_delta: 0,
  link: "",
  extract_code: "",
  unzip_code: ""
});
const consumablePoints = ref(0);
const favorited = ref(false);
const unlocked = computed(() => access.value.unlocked);

onLoad(async (query) => {
  if (typeof query?.id === "string") {
    selectedId.value = query.id;
  }
  await loadDetail();
});

const loadDetail = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    const detail = await getNetdiskResourceDetail(selectedId.value);
    resource.value = detail.resource;
    await ensureWechatLogin();
    const accessData = await getNetdiskResourceAccess(selectedId.value);
    access.value = accessData.access;
    consumablePoints.value = accessData.account.consumable_points;
    const favorites = await getNetdiskFavorites();
    favorited.value = favorites.favorites.some((item) => item.resource.id === selectedId.value);
  } catch (error: any) {
    errorText.value = error?.message || "资源加载失败";
  } finally {
    loading.value = false;
  }
};

const confirmAccess = async () => {
  if (!resource.value || unlocked.value) return;
  uni.showModal({
    title: "确认获取资源？",
    content: `本资源需要消耗 ${resource.value.cost_points} 积分，当前可用 ${consumablePoints.value} 分。`,
    confirmText: "确认获取",
    success: async (res) => {
      if (!res.confirm) return;
      try {
        await ensureWechatLogin();
        const data = await unlockNetdiskResource(selectedId.value);
        resource.value = data.resource;
        access.value = data.unlock;
        consumablePoints.value = data.account.consumable_points;
        uni.showToast({ title: "解锁成功", icon: "none" });
      } catch (error: any) {
        uni.showToast({ title: error?.message || "解锁失败", icon: "none" });
      }
    }
  });
};

const copyLink = () => {
  if (!access.value.link) return;
  const text = [
    access.value.link,
    access.value.extract_code ? `提取码：${access.value.extract_code}` : "",
    access.value.unzip_code ? `解压码：${access.value.unzip_code}` : ""
  ]
    .filter(Boolean)
    .join("\n");
  uni.setClipboardData({ data: text });
};

const toggleFavorite = async () => {
  if (!resource.value) return;
  try {
    await ensureWechatLogin();
    const data = favorited.value ? await unfavoriteNetdiskResource(resource.value.id) : await favoriteNetdiskResource(resource.value.id);
    resource.value = data.resource;
    favorited.value = data.favorited;
    uni.showToast({ title: favorited.value ? "已收藏" : "已取消收藏", icon: "none" });
  } catch (error: any) {
    uni.showToast({ title: error?.message || "收藏失败", icon: "none" });
  }
};

const reportInvalid = () => {
  if (!resource.value) return;
  uni.showModal({
    title: "确认投诉失效？",
    content: "提交后运营会核验链接状态，确认失效后资源会隐藏处理。",
    confirmText: "提交投诉",
    success: async (res) => {
      if (!res.confirm || !resource.value) return;
      try {
        await ensureWechatLogin();
        await reportNetdiskResource(resource.value, "用户反馈：资源链接失效或内容不符。");
        uni.showToast({ title: "投诉已提交", icon: "none" });
      } catch (error: any) {
        uni.showToast({ title: error?.message || "投诉失败", icon: "none" });
      }
    }
  });
};

const levelText = (level?: string) => ({ normal: "普通", featured: "精选", official: "官方" }[level || ""] || level || "-");
</script>

<template>
  <view class="page">
    <view v-if="loading" class="empty">正在加载资源...</view>
    <view v-else-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadDetail">重试</view>
    </view>

    <template v-else-if="resource">
      <view class="card">
        <view class="resource-title">{{ resource.title }}</view>
        <view class="row tag-line">
          <text class="tag">{{ resource.pan }}</text>
          <text class="tag tag-warning">{{ levelText(resource.level) }}</text>
          <text class="tag">{{ resource.category }}</text>
        </view>
        <view class="price"><text class="points">{{ resource.cost_points }}</text> 积分获取</view>
      </view>

      <view class="card section">
        <view class="section-title">资源简介</view>
        <view class="desc">{{ resource.description }}</view>
      </view>

      <view class="card section">
        <view class="info-line"><text>最近验证</text><text>{{ resource.verified_at }}</text></view>
        <view class="info-line"><text>获取次数</text><text>{{ resource.downloads }}</text></view>
        <view class="info-line"><text>收藏次数</text><text>{{ resource.favorites }}</text></view>
        <view class="info-line"><text>资源状态</text><text>{{ resource.is_active ? "可获取" : "已隐藏" }}</text></view>
      </view>

      <view class="card section secret-box">
        <view class="section-title">{{ unlocked ? "已解锁资源信息" : "解锁后可见" }}</view>
        <template v-if="unlocked">
          <view class="secret-line">链接：{{ access.link }}</view>
          <view class="secret-line">提取码：{{ access.extract_code || "无" }}</view>
          <view class="secret-line">解压码：{{ access.unzip_code || "无" }}</view>
          <view class="btn-secondary btn copy-btn" @click="copyLink">复制链接</view>
        </template>
        <template v-else>
          <view class="masked">完整网盘链接、提取码、解压码将在消耗积分后展示。</view>
        </template>
      </view>

      <view class="bottom-actions">
        <view class="btn" @click="confirmAccess">{{ unlocked ? "已获取" : `获取资源 ${resource.cost_points}分` }}</view>
        <view class="btn-plain" @click="toggleFavorite">{{ favorited ? "已收藏" : "收藏" }}</view>
        <view class="btn-plain danger" @click="reportInvalid">投诉失效</view>
      </view>
    </template>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.tag-line {
  gap: 10rpx;
  margin-top: 18rpx;
  flex-wrap: wrap;
}

.price {
  margin-top: 22rpx;
  font-size: 30rpx;
}

.desc {
  margin-top: 18rpx;
  color: $text-muted;
  font-size: 28rpx;
  line-height: 1.7;
}

.info-line {
  display: flex;
  justify-content: space-between;
  border-bottom: 1rpx solid $border;
  padding: 18rpx 0;
  color: $text-muted;
  font-size: 27rpx;
}

.info-line:last-child {
  border-bottom: 0;
}

.secret-box {
  margin-bottom: 144rpx;
}

.secret-line {
  margin-top: 16rpx;
  color: $text-main;
  font-size: 27rpx;
  line-height: 1.6;
  word-break: break-all;
}

.masked {
  margin-top: 18rpx;
  border: 1rpx dashed $border;
  border-radius: 12rpx;
  background: $tag-bg;
  padding: 24rpx;
  color: $text-muted;
  font-size: 27rpx;
  line-height: 1.6;
}

.copy-btn {
  margin-top: 22rpx;
}

.bottom-actions {
  position: fixed;
  right: 0;
  bottom: 0;
  left: 0;
  display: grid;
  grid-template-columns: 1.8fr 1fr 1fr;
  gap: 14rpx;
  border-top: 1rpx solid $border;
  background: #ffffff;
  padding: 18rpx 28rpx 30rpx;
}

.danger {
  color: $danger;
}

.empty {
  margin-top: 180rpx;
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
