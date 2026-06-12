<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ensureDevLogin, getNetdiskNotifications, markNetdiskNotificationRead, type NetdiskNotification } from "@/utils/api";

const loading = ref(false);
const errorText = ref("");
const unreadCount = ref(0);
const notifications = ref<NetdiskNotification[]>([]);

const hasData = computed(() => notifications.value.length > 0);

const loadMessages = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    await ensureDevLogin();
    const data = await getNetdiskNotifications();
    notifications.value = data.notifications || [];
    unreadCount.value = data.unread_count || 0;
  } catch (error: any) {
    errorText.value = error?.message || "消息加载失败";
  } finally {
    loading.value = false;
  }
};

const readMessage = async (item: NetdiskNotification) => {
  if (item.status === "read") return;
  try {
    await markNetdiskNotificationRead(item.id);
    item.status = "read";
    unreadCount.value = Math.max(0, unreadCount.value - 1);
  } catch {
    uni.showToast({ title: "标记已读失败", icon: "none" });
  }
};

const formatType = (type: string) => {
  const map: Record<string, string> = {
    netdisk_upload_approved: "上传通过",
    netdisk_upload_rejected: "上传驳回",
    netdisk_upload_invalid: "确认失效",
    netdisk_repair_approved: "补链通过",
    netdisk_repair_rejected: "补链驳回",
    netdisk_repair_invalid: "补链失效",
    netdisk_report_approved: "投诉通过",
    netdisk_report_rejected: "投诉驳回",
    netdisk_report_confirmed: "投诉有效",
    netdisk_risk_pending: "待追缴"
  };
  return map[type] || "系统通知";
};

const formatTime = (value: string) => {
  if (!value) return "";
  return value.replace("T", " ").slice(0, 16);
};

onShow(loadMessages);
</script>

<template>
  <view class="page">
    <view class="summary card">
      <view>
        <view class="section-title">我的消息</view>
        <view class="muted">审核结果、确认失效和待追缴提醒</view>
      </view>
      <view class="unread">
        <text class="points">{{ unreadCount }}</text>
        <text> 未读</text>
      </view>
    </view>

    <view v-if="loading" class="empty">正在加载消息...</view>
    <view v-else-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="muted tip">请先登录，或确认后端服务已启动。</view>
      <view class="btn retry" @click="loadMessages">重试</view>
    </view>
    <view v-else-if="!hasData" class="empty">暂无消息</view>

    <view v-else class="section">
      <view
        v-for="item in notifications"
        :key="item.id"
        class="card message-card"
        :class="{ unread-card: item.status === 'unread' }"
        @click="readMessage(item)"
      >
        <view class="row between">
          <text class="tag" :class="{ 'tag-warning': item.status === 'unread' }">{{ formatType(item.notice_type) }}</text>
          <text class="muted time">{{ formatTime(item.created_at) }}</text>
        </view>
        <view class="message-title">{{ item.title }}</view>
        <view class="message-content">{{ item.content }}</view>
        <view class="muted related">{{ item.related_type }} · {{ item.related_id }}</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.unread {
  min-width: 116rpx;
  text-align: right;
}

.empty {
  margin-top: 160rpx;
  color: $text-muted;
  font-size: 28rpx;
  line-height: 1.8;
  text-align: center;
}

.tip {
  margin-top: 8rpx;
  font-size: 24rpx;
}

.retry {
  width: 220rpx;
  margin: 28rpx auto 0;
}

.message-card {
  margin-bottom: 18rpx;
}

.unread-card {
  border-color: $primary;
}

.time {
  font-size: 23rpx;
}

.message-title {
  margin-top: 18rpx;
  font-size: 31rpx;
  font-weight: 800;
}

.message-content {
  margin-top: 12rpx;
  color: $text-muted;
  font-size: 27rpx;
  line-height: 1.65;
}

.related {
  margin-top: 14rpx;
  font-size: 23rpx;
}
</style>
