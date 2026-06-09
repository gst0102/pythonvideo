<script setup lang="ts">
import { earnTasks, userProfile } from "@/data/mock";
</script>

<template>
  <view class="page">
    <view class="score-card">
      <view class="muted">当前积分</view>
      <view class="score">{{ userProfile.points }}</view>
      <view class="score-copy">签到、小游戏、上传资源和补链都可以增加积分。</view>
    </view>

    <view class="section">
      <view v-for="task in earnTasks" :key="task.title" class="card task-card">
        <view class="row between">
          <view>
            <view class="task-title">{{ task.title }}</view>
            <view class="meta">{{ task.desc }}</view>
          </view>
          <view class="reward">{{ task.reward }}</view>
        </view>
        <view class="btn-secondary btn task-action">{{ task.action }}</view>
      </view>
    </view>
  </view>
</template>

<style lang="scss" scoped>
@import "@/styles/theme.scss";

.score-card {
  border-radius: 18rpx;
  background: $primary-dark;
  padding: 32rpx;
  color: #ffffff;
}

.score-card .muted {
  color: rgba(255, 255, 255, 0.72);
}

.score {
  margin-top: 10rpx;
  font-size: 72rpx;
  font-weight: 900;
}

.score-copy {
  margin-top: 8rpx;
  color: rgba(255, 255, 255, 0.82);
  font-size: 26rpx;
  line-height: 1.55;
}

.task-title {
  font-size: 31rpx;
  font-weight: 700;
}

.reward {
  color: $point;
  font-size: 30rpx;
  font-weight: 800;
}

.task-action {
  margin-top: 20rpx;
}
</style>
