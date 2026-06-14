<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ensureWechatLogin, getMyNetdiskUploads, type UploadListResponse } from "@/utils/api";

const loading = ref(false);
const errorText = ref("");
const uploads = ref<UploadListResponse["uploads"]>([]);

const statusText = (status: string) =>
  ({ pending: "待审核", approved: "已通过", rejected: "已驳回", invalid_confirmed: "确认失效" }[status] || status);

const statusClass = (status: string) => ({
  "tag-warning": status === "pending",
  "tag-danger": status === "rejected" || status === "invalid_confirmed"
});

const formatTime = (value: string) => (value ? value.replace("T", " ").slice(0, 16) : "");

const loadUploads = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    const data = await getMyNetdiskUploads();
    uploads.value = data.uploads || [];
  } catch (error: any) {
    errorText.value = error?.message || "上传记录加载失败";
  } finally {
    loading.value = false;
  }
};

onShow(loadUploads);
</script>

<template>
  <view class="page">
    <view class="section-title">我的上传</view>
    <view class="muted subtitle">查看资源审核状态、冻结奖励和运营备注。</view>

    <view v-if="loading" class="empty">正在加载...</view>
    <view v-else-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadUploads">重试</view>
    </view>

    <view v-else>
      <view v-for="item in uploads" :key="item.id" class="card upload-card">
        <view class="row between">
          <view class="upload-title">{{ item.title }}</view>
          <text class="tag" :class="statusClass(item.status)">{{ statusText(item.status) }}</text>
        </view>
        <view class="meta">{{ item.pan }} · {{ item.category }} · {{ formatTime(item.created_at) }}</view>
        <view class="reward">
          <text class="points">+{{ item.reward_released_points || 0 }}</text>
          <text class="muted"> 已到账 / 最高 {{ item.reward_points || 0 }} 分</text>
        </view>
        <view class="stage muted">7天有效奖励：{{ item.valid_days_rewarded >= 7 ? "已发放" : "待资源持续有效" }}</view>
        <view class="audit">审核备注：{{ item.audit_note || "等待运营处理" }}</view>
      </view>
      <view v-if="uploads.length === 0" class="empty">暂无上传记录</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.subtitle {
  margin-top: 8rpx;
  font-size: 25rpx;
}

.upload-card {
  margin-top: 20rpx;
}

.upload-title {
  flex: 1;
  min-width: 0;
  padding-right: 16rpx;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.4;
}

.reward,
.stage,
.audit {
  margin-top: 14rpx;
  font-size: 26rpx;
  line-height: 1.6;
}

.audit {
  color: $primary-dark;
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
