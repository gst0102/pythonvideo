<script setup lang="ts">
import { ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import { ensureWechatLogin, getMyNetdiskRepairs, type RepairListResponse } from "@/utils/api";

const loading = ref(false);
const errorText = ref("");
const reports = ref<RepairListResponse["repairs"]>([]);

const statusText = (status: string) => ({ pending: "待核验", approved: "投诉有效", rejected: "已驳回", invalid_confirmed: "确认失效" }[status] || status);
const formatTime = (value: string) => (value ? value.replace("T", " ").slice(0, 16) : "");

const loadReports = async () => {
  loading.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    const data = await getMyNetdiskRepairs();
    reports.value = data.repairs.filter((item) => item.mode === "report");
  } catch (error: any) {
    errorText.value = error?.message || "投诉记录加载失败";
  } finally {
    loading.value = false;
  }
};

onShow(loadReports);
</script>

<template>
  <view class="page">
    <view class="section-title">我的投诉记录</view>
    <view class="muted subtitle">查看投诉是否已核验、驳回或确认失效。</view>

    <view v-if="loading" class="empty">正在加载...</view>
    <view v-else-if="errorText" class="empty">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loadReports">重试</view>
    </view>

    <view v-else>
      <view v-for="item in reports" :key="item.id" class="card report-card">
        <view class="row between">
          <view class="report-title">{{ item.resource_title }}</view>
          <text class="tag" :class="{ 'tag-warning': item.status === 'pending', 'tag-danger': item.status === 'rejected' }">
            {{ statusText(item.status) }}
          </text>
        </view>
        <view class="meta">提交时间 {{ formatTime(item.created_at) }}</view>
        <view class="reason">{{ item.note }}</view>
        <view class="audit">处理备注：{{ item.audit_note || "等待运营核验" }}</view>
      </view>
      <view v-if="reports.length === 0" class="empty">暂无投诉记录</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.subtitle {
  margin-top: 8rpx;
  font-size: 25rpx;
}

.report-card {
  margin-top: 20rpx;
}

.report-title {
  flex: 1;
  min-width: 0;
  padding-right: 16rpx;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 1.4;
}

.reason,
.audit {
  margin-top: 14rpx;
  color: $text-muted;
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
