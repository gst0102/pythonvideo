<script setup lang="ts">
import { computed, ref } from "vue";
import { onShow } from "@dcloudio/uni-app";
import {
  ensureWechatLogin,
  getMyNetdiskRepairs,
  getMyNetdiskUploads,
  getNetdiskFavorites,
  getUserProfile,
  hasLoginToken
} from "@/utils/api";

const loading = ref(false);
const loggingIn = ref(false);
const errorText = ref("");
const nickname = ref("微信用户");
const avatar = ref("");
const consumablePoints = ref(0);
const frozenPoints = ref(0);
const totalPoints = ref(0);
const creditScore = ref(100);
const contributionScore = ref(0);
const creditLevel = ref("normal");
const creditRestoreTip = ref("保持资源有效、及时补链，信用会继续稳定提升。");
const favoriteCount = ref(0);
const uploadCount = ref(0);
const repairCount = ref(0);
const reportCount = ref(0);
const loggedIn = ref(false);

const initial = computed(() => (nickname.value || "资").slice(0, 1));
const todayEarnable = computed(() => Math.max(0, 60 - Math.min(contributionScore.value, 6)));
const creditLabel = computed(() => {
  const map: Record<string, string> = {
    excellent: "优秀",
    good: "良好",
    normal: "正常",
    watch: "待观察"
  };
  return map[creditLevel.value] || "正常";
});

const resetMine = () => {
  nickname.value = "微信用户";
  avatar.value = "";
  consumablePoints.value = 0;
  frozenPoints.value = 0;
  totalPoints.value = 0;
  creditScore.value = 100;
  contributionScore.value = 0;
  creditLevel.value = "normal";
  creditRestoreTip.value = "保持资源有效、及时补链，信用会继续稳定提升。";
  favoriteCount.value = 0;
  uploadCount.value = 0;
  repairCount.value = 0;
  reportCount.value = 0;
};

const loadMine = async () => {
  if (!hasLoginToken()) {
    loggedIn.value = false;
    errorText.value = "";
    resetMine();
    return;
  }
  loading.value = true;
  errorText.value = "";
  try {
    const [profile, favorites, uploads, repairs] = await Promise.all([
      getUserProfile(),
      getNetdiskFavorites(),
      getMyNetdiskUploads(),
      getMyNetdiskRepairs()
    ]);
    loggedIn.value = true;
    nickname.value = profile.nickname || "微信用户";
    avatar.value = profile.avatar || "";
    consumablePoints.value = profile.account?.consumable_points || 0;
    frozenPoints.value = profile.account?.frozen_points || 0;
    totalPoints.value = profile.account?.total_points || consumablePoints.value;
    creditScore.value = profile.credit_score || 100;
    contributionScore.value = profile.contribution_score || 0;
    creditLevel.value = profile.credit_level || "normal";
    creditRestoreTip.value = profile.credit_restore_tip || "上传审核通过、补链成功、资源持续有效满7天，都可以逐步恢复信用。";
    favoriteCount.value = favorites.favorites.length;
    uploadCount.value = uploads.uploads.length;
    repairCount.value = repairs.repairs.filter((item) => item.mode === "repair").length;
    reportCount.value = repairs.repairs.filter((item) => item.mode === "report").length;
  } catch (error: any) {
    errorText.value = error?.message || "我的数据加载失败";
  } finally {
    loading.value = false;
  }
};

const loginAndLoadMine = async () => {
  if (loggingIn.value) return;
  loggingIn.value = true;
  errorText.value = "";
  try {
    await ensureWechatLogin();
    loggedIn.value = true;
    await loadMine();
    if (!errorText.value) {
      uni.showToast({ title: "登录成功", icon: "success" });
    }
  } catch (error: any) {
    loggedIn.value = false;
    errorText.value = error?.message || "登录失败，请稍后重试";
  } finally {
    loggingIn.value = false;
  }
};

const requireLogin = (url: string) => {
  if (!loggedIn.value) {
    uni.showToast({ title: "请先登录", icon: "none" });
    return;
  }
  uni.navigateTo({ url });
};

const openEarn = () => uni.switchTab({ url: "/pages/earn/index" });
const todo = () => uni.showToast({ title: "功能整理中", icon: "none" });

onShow(loadMine);
</script>

<template>
  <view class="page">
    <view class="account-card">
      <view class="account-left">
        <view class="muted">我的资源账户</view>
        <view class="profile-row">
          <image v-if="avatar" class="avatar-img" :src="avatar" mode="aspectFill" />
          <view v-else class="avatar">{{ initial }}</view>
          <view>
            <view class="nickname">{{ nickname }}</view>
            <view v-if="loggedIn" class="credit-pill">信用 {{ creditScore }} · {{ creditLabel }}</view>
            <view v-else class="muted">登录后查看积分与信用</view>
          </view>
        </view>
      </view>
      <view class="points-box" @click="requireLogin('/pages/points/ledger')">
        <view class="points-total">{{ totalPoints }}</view>
        <view class="points-label">总积分</view>
        <view class="muted small">可用{{ consumablePoints }} · 待验证{{ frozenPoints }}</view>
      </view>
    </view>

    <view v-if="loggedIn" class="credit-strip">
      <view>
        <text class="credit-strip-label">信用分</text>
        <text class="credit-strip-score">{{ creditScore }}</text>
        <text class="credit-strip-level">{{ creditLabel }}</text>
      </view>
      <view class="muted">贡献值 {{ contributionScore }}</view>
    </view>

    <view v-if="!loggedIn" class="login-card section">
      <view>
        <view class="login-title">登录悦享资源库</view>
        <view class="muted login-desc">登录后可解锁资源、赚积分、管理上传收藏。</view>
      </view>
      <view class="btn login-btn" :class="{ disabled: loggingIn }" @click="loginAndLoadMine">
        {{ loggingIn ? "登录中..." : "微信一键登录" }}
      </view>
    </view>

    <view v-if="errorText" class="error-box">
      <view>{{ errorText }}</view>
      <view class="btn retry" @click="loggedIn ? loadMine() : loginAndLoadMine()">{{ loggedIn ? "重试" : "重新登录" }}</view>
    </view>

    <view class="quick-row">
      <view class="quick-item" @click="openEarn">
        <view class="quick-number">{{ todayEarnable }}分</view>
        <view class="muted">今日可赚</view>
      </view>
      <view class="quick-item" @click="openEarn">赚积分任务</view>
      <view class="quick-item" @click="todo">邀请奖励</view>
      <view class="quick-item" @click="todo">充值积分</view>
    </view>

    <view v-if="loggedIn" class="credit-card section">
      <view class="credit-main">
        <view>
          <view class="section-title compact-title">信用分</view>
          <view class="muted">影响资源排序和上传权益，不可消费</view>
        </view>
        <view class="credit-score">
          <text>{{ creditScore }}</text>
          <text>{{ creditLabel }}</text>
        </view>
      </view>
      <view class="credit-tip">{{ creditRestoreTip }}</view>
      <view class="muted credit-foot">贡献值 {{ contributionScore }}。上传通过、补链成功、资源持续有效满7天可提升；短期失效、恶意投诉会降低。</view>
    </view>

    <view class="stats-grid section">
      <view class="stat-card" @click="requireLogin('/pages/favorites/index')">
        <view class="stat-number">{{ favoriteCount }}</view>
        <view class="muted">收藏资源</view>
      </view>
      <view class="stat-card" @click="requireLogin('/pages/uploads/mine')">
        <view class="stat-number">{{ uploadCount }}</view>
        <view class="muted">上传记录</view>
      </view>
      <view class="stat-card" @click="requireLogin('/pages/reports/mine')">
        <view class="stat-number">{{ repairCount + reportCount }}</view>
        <view class="muted">补链/投诉</view>
      </view>
    </view>

    <view class="section-head">
      <view class="section-title">资源管理</view>
      <view class="help" @click="todo">?</view>
    </view>
    <view class="action-grid">
      <view class="action-btn" @click="requireLogin('/pages/favorites/index')">我的收藏</view>
      <view class="action-btn" @click="requireLogin('/pages/uploads/mine')">我的上传</view>
      <view class="action-btn" @click="requireLogin('/pages/reports/mine')">补链/投诉</view>
    </view>

    <view class="section-head">
      <view class="section-title">积分与邀请</view>
      <view class="help" @click="todo">?</view>
    </view>
    <view class="action-grid two">
      <view class="action-btn" @click="openEarn">赚积分任务</view>
      <view class="action-btn" @click="requireLogin('/pages/points/ledger')">积分明细</view>
      <view class="action-btn muted-btn" @click="todo">邀请奖励记录</view>
      <view class="action-btn muted-btn" @click="todo">充值记录</view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.account-card {
  display: grid;
  grid-template-columns: 1fr 200rpx;
  gap: 20rpx;
  border: 1rpx solid $border;
  border-radius: 18rpx;
  background: #ffffff;
  padding: 28rpx;
}

.credit-strip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16rpx;
  margin-top: 14rpx;
  border: 1rpx solid $border;
  border-radius: 14rpx;
  background: rgba(255, 255, 255, 0.82);
  padding: 16rpx 20rpx;
  font-size: 24rpx;
}

.credit-strip-label {
  color: $text-muted;
}

.credit-strip-score {
  margin-left: 12rpx;
  color: $primary-dark;
  font-size: 30rpx;
  font-weight: 800;
}

.credit-strip-level {
  margin-left: 10rpx;
  color: $text-main;
  font-weight: 700;
}

.profile-row {
  display: flex;
  align-items: center;
  gap: 18rpx;
  margin-top: 18rpx;
}

.avatar,
.avatar-img {
  width: 88rpx;
  height: 88rpx;
  border-radius: 44rpx;
}

.avatar {
  background: $tag-bg;
  color: $primary-dark;
  font-size: 38rpx;
  font-weight: 800;
  line-height: 88rpx;
  text-align: center;
}

.nickname {
  color: $text-main;
  font-size: 36rpx;
  font-weight: 900;
}

.credit-pill {
  display: inline-block;
  margin-top: 10rpx;
  border-radius: 999rpx;
  background: #eef8f4;
  padding: 5rpx 14rpx;
  color: $primary-dark;
  font-size: 22rpx;
  font-weight: 700;
}

.points-box {
  border-radius: 18rpx;
  background: #fff7e8;
  padding: 22rpx 10rpx;
  text-align: center;
}

.points-total {
  color: #f5a623;
  font-size: 42rpx;
  font-weight: 900;
}

.points-label {
  margin-top: 8rpx;
  color: #9a6b13;
  font-size: 24rpx;
  font-weight: 800;
}

.small {
  margin-top: 6rpx;
  font-size: 21rpx;
}

.login-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18rpx;
  border-radius: 18rpx;
  background: #ffffff;
  padding: 24rpx;
}

.login-title {
  font-size: 30rpx;
  font-weight: 800;
}

.login-desc {
  margin-top: 8rpx;
  font-size: 24rpx;
}

.login-btn {
  width: 210rpx;
}

.disabled {
  opacity: 0.65;
}

.quick-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12rpx;
  margin-top: 18rpx;
}

.quick-item {
  min-height: 78rpx;
  border-radius: 14rpx;
  background: #ffffff;
  color: $primary-dark;
  font-size: 25rpx;
  font-weight: 800;
  line-height: 78rpx;
  text-align: center;
}

.quick-number {
  margin-top: 10rpx;
  color: #f5a623;
  font-size: 27rpx;
  line-height: 32rpx;
}

.quick-number + .muted {
  font-size: 22rpx;
  line-height: 30rpx;
}

.credit-card {
  border-radius: 16rpx;
  background: #ffffff;
  padding: 22rpx;
}

.credit-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16rpx;
}

.compact-title {
  margin-bottom: 6rpx;
  font-size: 29rpx;
}

.credit-score {
  min-width: 112rpx;
  text-align: right;
}

.credit-score text:first-child {
  display: block;
  color: $primary-dark;
  font-size: 34rpx;
  font-weight: 900;
}

.credit-score text:last-child {
  display: block;
  margin-top: 4rpx;
  color: $text-muted;
  font-size: 22rpx;
}

.credit-tip {
  margin-top: 16rpx;
  color: $text-main;
  font-size: 25rpx;
  line-height: 1.6;
}

.credit-foot {
  margin-top: 10rpx;
  font-size: 22rpx;
  line-height: 1.5;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14rpx;
}

.stat-card {
  border: 1rpx solid $border;
  border-radius: 16rpx;
  background: #ffffff;
  padding: 24rpx 10rpx;
  text-align: center;
}

.stat-number {
  margin-bottom: 8rpx;
  color: $text-main;
  font-size: 34rpx;
  font-weight: 900;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 24rpx;
}

.help {
  width: 48rpx;
  height: 48rpx;
  color: $primary;
  font-size: 30rpx;
  font-weight: 800;
  line-height: 48rpx;
  text-align: center;
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12rpx;
  margin-top: 14rpx;
}

.action-grid.two {
  grid-template-columns: repeat(2, 1fr);
}

.action-btn {
  min-height: 78rpx;
  border-radius: 14rpx;
  background: #ffffff;
  color: $text-main;
  font-size: 27rpx;
  font-weight: 800;
  line-height: 78rpx;
  text-align: center;
}

.muted-btn {
  color: $text-muted;
}

.error-box {
  margin-top: 18rpx;
  border-radius: 16rpx;
  background: #fff4e2;
  padding: 20rpx;
  color: #8b610f;
  font-size: 26rpx;
  line-height: 1.6;
  text-align: center;
}

.retry {
  width: 220rpx;
  margin: 18rpx auto 0;
}
</style>
